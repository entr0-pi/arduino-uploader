"""ESP32 partition table CSV parsing."""

import csv
from typing import Callable


def parse_partition_table(
    csv_file: str,
    logger: Callable[[str], None] | None = None,
) -> list[dict]:
    """Parse an ESP32 partition CSV.

    Returns list of ``{name, type, subtype, offset, size}`` dicts.
    """
    out: list[dict] = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(row for row in f if not row.lstrip().startswith("#"))
        for row in reader:
            if len(row) < 5:
                continue
            try:
                out.append(
                    {
                        "name": row[0].strip(),
                        "type": row[1].strip().lower(),
                        "subtype": row[2].strip().lower(),
                        "offset": int(row[3].strip(), 0),
                        "size": int(row[4].strip(), 0),
                    }
                )
            except Exception as exc:
                if logger:
                    logger(f"[WARN] Skipping malformed partition row: {row} ({exc})")
    return out


def get_partition(
    csv_file: str,
    subtype: str,
    logger: Callable[[str], None] | None = None,
) -> dict:
    """Find a partition entry by *subtype*.

    Raises ``ValueError`` if the CSV is missing or the subtype is not found.
    """
    import os

    if not os.path.isfile(csv_file):
        raise ValueError("Select a valid partition CSV first.")
    for entry in parse_partition_table(csv_file, logger=logger):
        if entry["subtype"] == subtype:
            return entry
    raise ValueError(f"Partition subtype '{subtype}' not found in CSV.")
