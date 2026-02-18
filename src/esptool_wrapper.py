"""Subprocess runners, serial port detection, and chip auto-detection."""

import re
import subprocess
import sys
from typing import Callable

from .validators import sanitize_chip


def detect_serial_ports() -> list[str]:
    """Return sorted list of available serial port device names."""
    try:
        from serial.tools import list_ports

        return sorted(p.device for p in list_ports.comports() if p.device)
    except Exception:
        return []


def _parse_chip_from_esptool(output: str) -> str:
    """Extract chip family from esptool stdout/stderr."""
    patterns = [
        r"Detecting chip type\.\.\.\s*(ESP32[\w\-]*)",
        r"Chip is\s+(ESP32[\w\-]*)",
    ]
    for pat in patterns:
        m = re.search(pat, output, flags=re.IGNORECASE)
        if m:
            return sanitize_chip(m.group(1))
    return ""


def detect_chip_family(port: str, timeout: int = 12) -> str:
    """Run ``esptool chip_id`` and parse the chip family.

    Returns the chip string (e.g. ``"esp32s3"``) or ``""`` on failure.
    """
    try:
        cmd = [sys.executable, "-m", "esptool", "--port", port, "chip_id"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
        output = "\n".join([result.stdout or "", result.stderr or ""])
        return _parse_chip_from_esptool(output)
    except Exception:
        return ""


def run_python(
    args: list[str],
    check: bool = True,
    logger: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess:
    """Run a Python subprocess, optionally logging stdout/stderr."""
    cmd = [sys.executable] + args
    if logger:
        logger(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if logger:
        if result.stdout:
            logger(result.stdout.rstrip())
        if result.stderr:
            logger(result.stderr.rstrip())
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result


def run_with_fallbacks(
    variants: list[list[str]],
    logger: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess:
    """Try multiple command variants, return first success."""
    last = None
    for args in variants:
        try:
            return run_python(args, check=True, logger=logger)
        except subprocess.CalledProcessError as exc:
            last = exc
    raise last if last else RuntimeError("No command variant provided")
