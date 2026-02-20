"""LittleFS operations: staging, image building, and flashing."""

import gzip
import os
import shutil
import subprocess
import tempfile
from typing import Callable

from .esptool_wrapper import read_flash_region, run_python
from .exceptions import ToolExecutionError


def human_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    unit = 0
    while value >= 1024.0 and unit < len(units) - 1:
        value /= 1024.0
        unit += 1
    if unit == 0:
        return f"{int(value)} {units[unit]}"
    return f"{value:.2f} {units[unit]}"


def _resolve_target_dir(staging_dir: str, subdir: str) -> str:
    """Resolve a user-provided LittleFS subdir under staging root."""
    cleaned = (subdir or "").strip().replace("\\", "/").strip("/")
    if not cleaned:
        return staging_dir
    parts = [p for p in cleaned.split("/") if p and p not in (".", "..")]
    target = os.path.join(staging_dir, *parts)
    os.makedirs(target, exist_ok=True)
    return target


def stage_copy_files(
    source_dir: str,
    staging_dir: str,
    target_subdir: str = "",
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> int:
    """Copy files to *staging_dir*. Returns the file count."""
    if not os.path.isdir(source_dir):
        if logger:
            logger("[WARN] Source folder not found. Building image without copy-mode files.")
        if progress_cb:
            progress_cb(30, "No copy-mode files to stage")
        return 0

    target_staging = _resolve_target_dir(staging_dir, target_subdir)
    files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
    total = len(files)
    total_bytes = 0
    if logger:
        logger("========== COPY MODE ==========")
        logger(f"[COPY] target=/{target_subdir.strip('/').replace('\\', '/')}" if target_subdir.strip() else "[COPY] target=/")
    for idx, f in enumerate(files):
        src = os.path.join(source_dir, f)
        shutil.copy2(src, target_staging)
        size = os.path.getsize(src)
        total_bytes += size
        if logger:
            logger(f"[COPY] {idx + 1:>2}/{total:<2}  {f}  [{human_bytes(size)}]")
        if progress_cb and total:
            progress_cb(10 + (idx / total) * 20, f"Staging copy file {idx + 1}/{total}")
    if logger:
        logger(f"[COPY] Summary: {total} file(s), total={human_bytes(total_bytes)}")
    return total


def stage_gzip_files(
    source_dir: str,
    staging_dir: str,
    target_subdir: str = "",
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> int:
    """Gzip all source files into staging. Returns the file count."""
    gzip_staging = _resolve_target_dir(staging_dir, target_subdir)

    if not os.path.isdir(source_dir):
        if logger:
            logger("[WARN] Source folder not found. Building image without gzip-mode files.")
        if progress_cb:
            progress_cb(70, "No gzip-mode files to stage")
        return 0

    files = sorted(
        f
        for f in os.listdir(source_dir)
        if os.path.isfile(os.path.join(source_dir, f))
    )
    total = len(files)
    total_raw = 0
    total_gz = 0
    if logger:
        logger("========== GZIP MODE ==========")
        logger(f"[GZIP] target=/{target_subdir.strip('/').replace('\\', '/')}" if target_subdir.strip() else "[GZIP] target=/")
    for idx, f in enumerate(files):
        src = os.path.join(source_dir, f)
        dst = os.path.join(gzip_staging, f + ".gz")
        if os.path.exists(dst) and logger:
            logger(f"[WARN] Overwriting existing staged file: {os.path.basename(dst)}")
        with open(src, "rb") as fin, gzip.open(dst, "wb") as fout:
            shutil.copyfileobj(fin, fout)
        raw_size = os.path.getsize(src)
        gz_size = os.path.getsize(dst)
        total_raw += raw_size
        total_gz += gz_size
        if logger:
            if raw_size > 0:
                ratio = (1.0 - (gz_size / raw_size)) * 100.0
                logger(
                    f"[GZIP] {idx + 1:>2}/{total:<2}  {f}.gz  "
                    f"[{human_bytes(raw_size)} -> {human_bytes(gz_size)}, {ratio:.1f}% saved]"
                )
            else:
                logger(f"[GZIP] {idx + 1:>2}/{total:<2}  {f}.gz  [0 B -> {human_bytes(gz_size)}]")
        if progress_cb and total:
            progress_cb(50 + (idx / total) * 20, f"Staging gzip file {idx + 1}/{total}")
    if logger:
        if total_raw > 0:
            saved = (1.0 - (total_gz / total_raw)) * 100.0
            logger(
                f"[GZIP] Summary: {total} file(s), "
                f"{human_bytes(total_raw)} -> {human_bytes(total_gz)} ({saved:.1f}% saved)"
            )
        else:
            logger(f"[GZIP] Summary: {total} file(s), 0 B -> {human_bytes(total_gz)}")
    return total


def build_image(
    mklittlefs_path: str,
    staging_dir: str,
    output_path: str,
    partition_size: int,
    block_size: int = 4096,
    page_size: int = 256,
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> None:
    """Run ``mklittlefs`` to build the LittleFS binary image."""
    cmd = [
        mklittlefs_path,
        "-c", staging_dir,
        "-b", str(block_size),
        "-p", str(page_size),
        "-s", str(partition_size),
        output_path,
    ]
    if logger:
        logger(f">>> {' '.join(cmd)}")
    if progress_cb:
        progress_cb(75, "Building LittleFS image...")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if logger:
        if result.stdout:
            logger(result.stdout.rstrip())
        if result.stderr:
            logger(result.stderr.rstrip())
    if result.returncode != 0:
        raise ToolExecutionError("mklittlefs", result.returncode, stderr=result.stderr or "")
    if progress_cb:
        progress_cb(85, "LittleFS image built")


def flash_littlefs(
    chip: str,
    port: str,
    mklittlefs_path: str,
    offset: int,
    partition_size: int,
    erase_first: bool = False,
    block_size: int = 4096,
    page_size: int = 256,
    baud: str = "921600",
    entries: list[dict[str, str]] | None = None,
    verify: bool = False,
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> None:
    """Full LittleFS pipeline: stage, build, flash.

    Creates a temporary staging directory and image file. Both are cleaned up
    on exit.
    """
    if logger:
        logger(f">>> LittleFS partition offset={hex(offset)}, size={hex(partition_size)}")
    if progress_cb:
        progress_cb(5, "Partition info loaded")

    with tempfile.TemporaryDirectory(prefix="littlefs_") as tmpdir:
        staging = os.path.join(tmpdir, "staging")
        os.makedirs(staging)
        image_path = os.path.join(tmpdir, "littlefs.bin")

        normalized_entries: list[dict[str, str]] = []
        if entries:
            for item in entries:
                source_dir = (item.get("source_dir") or "").strip()
                if not source_dir:
                    continue
                mode = (item.get("mode") or "raw").strip().lower()
                if mode not in {"raw", "gzip"}:
                    mode = "raw"
                normalized_entries.append(
                    {
                        "source_dir": source_dir,
                        "target_dir": (item.get("target_dir") or "").strip(),
                        "mode": mode,
                    }
                )
        copy_count = 0
        gzip_count = 0
        for item in normalized_entries:
            source_dir = item["source_dir"]
            target_dir = item["target_dir"]
            if item["mode"] == "gzip":
                gzip_count += stage_gzip_files(
                    source_dir,
                    staging,
                    target_subdir=target_dir,
                    logger=logger,
                    progress_cb=progress_cb,
                )
            else:
                copy_count += stage_copy_files(
                    source_dir,
                    staging,
                    target_subdir=target_dir,
                    logger=logger,
                    progress_cb=progress_cb,
                )
        if logger:
            logger("========== STAGING SUMMARY ==========")
            logger(
                f"[STAGING] copy={copy_count} file(s), gzip={gzip_count} file(s), rows={len(normalized_entries)}"
            )
        build_image(mklittlefs_path, staging, image_path, partition_size, block_size=block_size, page_size=page_size, logger=logger, progress_cb=progress_cb)

        if erase_first:
            if logger:
                logger(">>> Erasing FS partition...")
            if progress_cb:
                progress_cb(90, "Erasing FS partition")
            run_python(
                ["-m", "esptool", "--chip", chip, "--port", port, "--baud", baud,
                 "erase-region", hex(offset), hex(partition_size)],
                logger=logger,
            )

        if logger:
            logger(">>> Flashing LittleFS...")
        if progress_cb:
            progress_cb(95, "Flashing LittleFS to device")
        run_python(
            ["-m", "esptool", "--chip", chip, "--port", port, "--baud", baud,
             "write-flash", hex(offset), image_path],
            logger=logger,
        )

        if verify:
            import hashlib
            if progress_cb:
                progress_cb(97, "Verifying flash...")
            if logger:
                logger(">>> Verifying flash contents...")
            verify_path = os.path.join(tmpdir, "verify.bin")
            read_flash_region(chip, port, baud, offset, partition_size, verify_path, logger=logger)
            with open(image_path, "rb") as f:
                expected = hashlib.sha256(f.read()).hexdigest()
            with open(verify_path, "rb") as f:
                actual = hashlib.sha256(f.read()[:partition_size]).hexdigest()
            if expected != actual:
                raise ToolExecutionError(
                    "verify", 1,
                    remediation="Flash verification failed. The data on device does not match the image. Try flashing again.",
                )
            if logger:
                logger(f"[VERIFY] SHA-256 match: {expected[:16]}...")

        if progress_cb:
            progress_cb(100, "Flash complete!")
