"""Tests for src/partitions.py."""

import pytest

from src.exceptions import PartitionLookupError
from src.partitions import get_partition, parse_partition_table


class TestParsePartitionTable:
    def test_parse_valid_csv(self, partition_csv):
        entries = parse_partition_table(partition_csv)
        assert len(entries) == 4
        spiffs = [e for e in entries if e["subtype"] == "spiffs"]
        assert len(spiffs) == 1
        assert spiffs[0]["offset"] == 0x1F0000
        assert spiffs[0]["size"] == 0x10000

    def test_skips_comments(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text("# comment line\nnvs, data, nvs, 0x9000, 0x5000\n")
        entries = parse_partition_table(str(p))
        assert len(entries) == 1
        assert entries[0]["name"] == "nvs"

    def test_skips_short_rows(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text("too,few,cols\nnvs, data, nvs, 0x9000, 0x5000\n")
        entries = parse_partition_table(str(p))
        assert len(entries) == 1

    def test_malformed_offset_skipped(self, tmp_path):
        p = tmp_path / "test.csv"
        p.write_text("bad, data, nvs, not_a_number, 0x5000\n")
        log_messages = []
        entries = parse_partition_table(str(p), logger=log_messages.append)
        assert entries == []
        assert any("malformed" in m.lower() for m in log_messages)


class TestGetPartition:
    def test_found(self, partition_csv):
        entry = get_partition(partition_csv, "spiffs")
        assert entry["name"] == "spiffs"
        assert entry["offset"] == 0x1F0000

    def test_not_found(self, partition_csv):
        with pytest.raises(PartitionLookupError, match="not found"):
            get_partition(partition_csv, "nonexistent")

    def test_not_found_has_remediation(self, partition_csv):
        with pytest.raises(PartitionLookupError) as exc_info:
            get_partition(partition_csv, "nonexistent")
        assert exc_info.value.remediation

    def test_missing_file(self):
        with pytest.raises(PartitionLookupError, match="valid partition CSV"):
            get_partition("/nonexistent/file.csv", "spiffs")
