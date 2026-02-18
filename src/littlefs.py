"""LittleFS operations: staging, image building, and flashing."""

import gzip
import os
import shutil
import subprocess
import tempfile
from typing import Callable

from .esptool_wrapper import run_python


def _human_bytes(size: int) -> str:
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


def stage_data_files(
    data_dir: str,
    staging_dir: str,
    target_subdir: str = "",
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> int:
    """Copy data files to *staging_dir*. Returns the file count."""
    if not os.path.isdir(data_dir):
        if logger:
            logger("[WARN] data/ folder not found. Building image without data files.")
        if progress_cb:
            progress_cb(30, "No data files to stage")
        return 0

    data_staging = _resolve_target_dir(staging_dir, target_subdir)
    files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    total = len(files)
    total_bytes = 0
    if logger:
        logger("========== RAW DATA ==========")
        logger(f"[RAW DATA] target=/{target_subdir.strip('/').replace('\\', '/')}" if target_subdir.strip() else "[RAW DATA] target=/")
    for idx, f in enumerate(files):
        src = os.path.join(data_dir, f)
        shutil.copy2(src, data_staging)
        size = os.path.getsize(src)
        total_bytes += size
        if logger:
            logger(f"[RAW DATA] {idx + 1:>2}/{total:<2}  {f}  [{_human_bytes(size)}]")
        if progress_cb and total:
            progress_cb(10 + (idx / total) * 20, f"Staging data file {idx + 1}/{total}")
    if logger:
        logger(f"[RAW DATA] Summary: {total} file(s), total={_human_bytes(total_bytes)}")
    return total


def stage_web_files(
    web_dir: str,
    staging_dir: str,
    target_subdir: str = "",
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> int:
    """Gzip all web files into ``<staging_dir>/`` root. Returns the file count."""
    web_staging = _resolve_target_dir(staging_dir, target_subdir)

    if not os.path.isdir(web_dir):
        if logger:
            logger("[WARN] web/ folder not found. Building image without web files.")
        if progress_cb:
            progress_cb(70, "No web files to stage")
        return 0

    files = sorted(
        f
        for f in os.listdir(web_dir)
        if os.path.isfile(os.path.join(web_dir, f))
    )
    total = len(files)
    total_raw = 0
    total_gz = 0
    if logger:
        logger("========== GZIP DATA ==========")
        logger(f"[GZIP DATA] target=/{target_subdir.strip('/').replace('\\', '/')}" if target_subdir.strip() else "[GZIP DATA] target=/")
    for idx, f in enumerate(files):
        src = os.path.join(web_dir, f)
        dst = os.path.join(web_staging, f + ".gz")
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
                    f"[GZIP DATA] {idx + 1:>2}/{total:<2}  {f}.gz  "
                    f"[{_human_bytes(raw_size)} -> {_human_bytes(gz_size)}, {ratio:.1f}% saved]"
                )
            else:
                logger(f"[GZIP DATA] {idx + 1:>2}/{total:<2}  {f}.gz  [0 B -> {_human_bytes(gz_size)}]")
        if progress_cb and total:
            progress_cb(50 + (idx / total) * 20, f"Staging web file {idx + 1}/{total}")
    if logger:
        if total_raw > 0:
            saved = (1.0 - (total_gz / total_raw)) * 100.0
            logger(
                f"[GZIP DATA] Summary: {total} file(s), "
                f"{_human_bytes(total_raw)} -> {_human_bytes(total_gz)} ({saved:.1f}% saved)"
            )
        else:
            logger(f"[GZIP DATA] Summary: {total} file(s), 0 B -> {_human_bytes(total_gz)}")
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
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    if progress_cb:
        progress_cb(85, "LittleFS image built")


def flash_littlefs(
    chip: str,
    port: str,
    mklittlefs_path: str,
    data_dir: str,
    web_dir: str,
    offset: int,
    partition_size: int,
    erase_first: bool = False,
    block_size: int = 4096,
    page_size: int = 256,
    baud: str = "921600",
    raw_target_dir: str = "",
    gzip_target_dir: str = "",
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

    image_path = tempfile.mktemp(suffix=".bin", prefix="littlefs_")
    staging = tempfile.mkdtemp(prefix="littlefs_staging_")
    try:
        data_count = stage_data_files(
            data_dir,
            staging,
            target_subdir=raw_target_dir,
            logger=logger,
            progress_cb=progress_cb,
        )
        web_count = stage_web_files(
            web_dir,
            staging,
            target_subdir=gzip_target_dir,
            logger=logger,
            progress_cb=progress_cb,
        )
        if logger:
            logger("========== STAGING SUMMARY ==========")
            logger(f"[STAGING] data={data_count} file(s), web(gz)={web_count} file(s)")
        build_image(mklittlefs_path, staging, image_path, partition_size, block_size=block_size, page_size=page_size, logger=logger, progress_cb=progress_cb)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    try:
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

        if progress_cb:
            progress_cb(100, "Flash complete!")
    finally:
        if os.path.isfile(image_path):
            os.remove(image_path)
