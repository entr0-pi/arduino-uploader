"""NVS operations: CSV I/O, header parsing, validation, binary generation, flashing."""

import csv
import os
import re
import tempfile
from pathlib import Path
from typing import Callable, TypedDict

from .esptool_wrapper import read_flash_region, run_python, run_with_fallbacks
from .exceptions import ToolExecutionError
from .validators import (
    validate_baud_rate,
    validate_boolean,
    validate_ipv4,
    validate_pin_number,
    validate_port,
    validate_positive_int,
)


class NvsRow(TypedDict):
    namespace: str
    key: str
    type: str
    encoding: str
    value: str


# ---------------------------------------------------------------------------
# NVS CSV I/O
# ---------------------------------------------------------------------------

def read_nvs_csv(csv_path: str) -> list[NvsRow]:
    """Read an NVS CSV file. Returns list of row dicts with namespace resolved."""
    rows: list[NvsRow] = []
    current_ns = "storage"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0] == "key" or row[0].startswith("#"):
                continue
            key = row[0].strip()
            typ = row[1].strip() if len(row) > 1 else "data"
            enc = row[2].strip() if len(row) > 2 else "string"
            val = row[3].strip() if len(row) > 3 else ""
            if typ == "namespace":
                current_ns = key
                continue
            rows.append(NvsRow(namespace=current_ns, key=key, type=typ, encoding=enc, value=val))
    return rows


def write_nvs_csv(csv_path: str, rows: list[NvsRow]) -> None:
    """Write NVS rows to CSV, grouped by namespace."""
    by_ns: dict[str, list[NvsRow]] = {}
    for r in rows:
        by_ns.setdefault(r["namespace"], []).append(r)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "type", "encoding", "value"])
        for ns in sorted(by_ns.keys()):
            w.writerow([ns, "namespace", "", ""])
            for r in by_ns[ns]:
                w.writerow([r["key"], r["type"], r["encoding"], r["value"]])


# ---------------------------------------------------------------------------
# nvs_keys.h header parsing (embedded from check_nvs_keys.py)
# ---------------------------------------------------------------------------

def parse_nvs_header(header_path: str) -> dict[str, set[str]]:
    """Parse ``nvs_keys.h`` and return ``{nvs_namespace: {key, ...}}``."""
    text = Path(header_path).read_text(encoding="utf-8")

    result: dict[str, set[str]] = {}
    nvs_ns_stack: list[str | None] = []
    current_nvs_ns: str | None = None

    for line in text.splitlines():
        stripped = line.strip()

        # Track C++ namespace openings: "namespace foo {"
        ns_match = re.match(r"namespace\s+(\w+)\s*\{", stripped)
        if ns_match:
            nvs_ns_stack.append(current_nvs_ns)
            continue

        # Track closing braces
        if stripped.startswith("}"):
            if nvs_ns_stack:
                current_nvs_ns = nvs_ns_stack.pop()
            continue

        # kNamespace = "xxx" -> sets the NVS namespace for this scope
        ns_val = re.match(
            r'constexpr\s+const\s+char\*\s+kNamespace\s*=\s*"([^"]+)"', stripped
        )
        if ns_val:
            current_nvs_ns = ns_val.group(1)
            result.setdefault(current_nvs_ns, set())
            continue

        # kSomething = "xxx" -> a key under current NVS namespace
        key_val = re.match(
            r'constexpr\s+const\s+char\*\s+\w+\s*=\s*"([^"]+)"', stripped
        )
        if key_val and current_nvs_ns is not None:
            result[current_nvs_ns].add(key_val.group(1))

    return result


def compare_nvs_keys(
    h_data: dict[str, set[str]],
    csv_data: dict[str, set[str]],
    csv_label: str,
) -> list[str]:
    """Compare header vs CSV data and return a list of issue strings."""
    issues: list[str] = []

    all_ns = sorted(set(h_data.keys()) | set(csv_data.keys()))
    for ns in all_ns:
        h_keys = h_data.get(ns, set())
        c_keys = csv_data.get(ns, set())

        if ns not in h_data:
            issues.append(f"  namespace '{ns}': in {csv_label} but NOT in .h")
            continue
        if ns not in csv_data:
            issues.append(f"  namespace '{ns}': in .h but NOT in {csv_label}")
            continue

        for k in sorted(h_keys - c_keys):
            issues.append(f"  [{ns}] key '{k}': in .h but NOT in {csv_label}")
        for k in sorted(c_keys - h_keys):
            issues.append(f"  [{ns}] key '{k}': in {csv_label} but NOT in .h")

    return issues


# ---------------------------------------------------------------------------
# NVS validation
# ---------------------------------------------------------------------------

def rows_to_ns_keys(rows: list[NvsRow]) -> dict[str, set[str]]:
    """Build ``{namespace: {key, ...}}`` from NVS rows."""
    result: dict[str, set[str]] = {}
    for row in rows:
        result.setdefault(row["namespace"], set()).add(row["key"])
    return result


def validate_nvs_rows(
    rows: list[NvsRow],
    header_path: str | None = None,
) -> list[str]:
    """Full NVS validation: consistency with header + value checks.

    Returns a list of human-readable issue strings (empty == valid).
    """
    issues: list[str] = []
    ns_keys = rows_to_ns_keys(rows)

    # Header consistency check (optional)
    if header_path and os.path.isfile(header_path):
        h_data = parse_nvs_header(header_path)
        issues.extend(compare_nvs_keys(h_data, ns_keys, "NVS editor"))

    # Value validation
    for row in rows:
        key = row["key"]
        value = row["value"]

        if key.endswith("_pin"):
            valid, msg = validate_pin_number(value)
            if not valid:
                issues.append(f"Key '{key}': {msg}")

        if key == "baud":
            valid, msg = validate_baud_rate(value)
            if not valid:
                issues.append(f"Key 'baud': {msg}")

        if key in ("ip", "gw", "subnet", "dns"):
            valid, msg = validate_ipv4(value)
            if not valid:
                issues.append(f"Key '{key}': {msg}")

        if key == "port":
            valid, msg = validate_port(value)
            if not valid:
                issues.append(f"Key '{key}': {msg}")

        if key in ("enabled", "dhcp", "accesspoint"):
            valid, msg = validate_boolean(value)
            if not valid:
                issues.append(f"Key '{key}': {msg}")

        if any(s in key for s in ("_timeout", "_delay", "_ms", "_tries", "_size", "_attempts", "_abandoned", "_valid")):
            valid, msg = validate_positive_int(value)
            if not valid:
                issues.append(f"Key '{key}': {msg}")

    return issues


# ---------------------------------------------------------------------------
# Device operations
# ---------------------------------------------------------------------------

def generate_nvs_binary(
    nvs_gen_py: str,
    csv_path: str,
    bin_path: str,
    partition_size: int,
    logger: Callable[[str], None] | None = None,
) -> None:
    """Generate NVS binary via ``nvs_partition_gen.py``."""
    run_with_fallbacks(
        [
            [nvs_gen_py, "generate", csv_path, bin_path, str(partition_size)],
            [nvs_gen_py, "generate", "--input", csv_path, "--output", bin_path, "--size", str(partition_size)],
        ],
        logger=logger,
    )


def flash_nvs(
    chip: str,
    port: str,
    nvs_gen_py: str,
    rows: list[NvsRow],
    offset: int,
    partition_size: int,
    erase_first: bool = False,
    baud: str = "921600",
    verify: bool = False,
    logger: Callable[[str], None] | None = None,
    progress_cb: Callable[[float, str], None] | None = None,
) -> None:
    """Write NVS rows to device: generate CSV, build binary, flash."""
    if not rows:
        raise ValueError("NVS table is empty.")

    if progress_cb:
        progress_cb(10, "Preparing NVS CSV...")

    with tempfile.TemporaryDirectory(prefix="nvs_write_") as tmp:
        csv_path = os.path.join(tmp, "nvs.csv")
        bin_path = os.path.join(tmp, "nvs.bin")
        write_nvs_csv(csv_path, rows)

        if progress_cb:
            progress_cb(30, "Generating NVS binary...")
        generate_nvs_binary(nvs_gen_py, csv_path, bin_path, partition_size, logger=logger)

        if erase_first:
            if progress_cb:
                progress_cb(60, "Erasing NVS partition...")
            run_python(
                ["-m", "esptool", "--chip", chip, "--port", port, "--baud", baud,
                 "erase-region", hex(offset), hex(partition_size)],
                logger=logger,
            )

        if progress_cb:
            progress_cb(80, "Flashing NVS to device...")
        run_python(
            ["-m", "esptool", "--chip", chip, "--port", port, "--baud", baud,
             "write-flash", hex(offset), bin_path],
            logger=logger,
        )

        if verify:
            import hashlib
            if progress_cb:
                progress_cb(92, "Verifying NVS flash...")
            if logger:
                logger(">>> Verifying NVS flash contents...")
            verify_path = os.path.join(tmp, "verify.bin")
            read_flash_region(chip, port, baud, offset, partition_size, verify_path, logger=logger)
            with open(bin_path, "rb") as f:
                expected = hashlib.sha256(f.read()).hexdigest()
            with open(verify_path, "rb") as f:
                actual = hashlib.sha256(f.read()[:partition_size]).hexdigest()
            if expected != actual:
                raise ToolExecutionError(
                    "verify", 1,
                    remediation="NVS verification failed. The data on device does not match the binary. Try writing again.",
                )
            if logger:
                logger(f"[VERIFY] SHA-256 match: {expected[:16]}...")

    if progress_cb:
        progress_cb(100, "NVS write complete!")
