"""Tests for src/nvs.py."""

import pytest

from src.nvs import (
    NvsRow,
    compare_nvs_keys,
    read_nvs_csv,
    rows_to_ns_keys,
    validate_nvs_rows,
    write_nvs_csv,
)


class TestReadWriteRoundtrip:
    def test_roundtrip(self, tmp_path):
        rows = [
            NvsRow(namespace="storage", key="wifi_ssid", type="data", encoding="string", value="MyNet"),
            NvsRow(namespace="storage", key="wifi_pass", type="data", encoding="string", value="secret"),
            NvsRow(namespace="config", key="baud", type="data", encoding="u32", value="115200"),
        ]
        csv_path = str(tmp_path / "test.csv")
        write_nvs_csv(csv_path, rows)
        result = read_nvs_csv(csv_path)
        assert len(result) == 3
        assert {r["namespace"] for r in result} == {"storage", "config"}
        keys = {r["key"] for r in result}
        assert keys == {"wifi_ssid", "wifi_pass", "baud"}

    def test_namespace_resolution(self, nvs_csv):
        rows = read_nvs_csv(nvs_csv)
        assert all(r["namespace"] == "storage" for r in rows)
        assert len(rows) == 2


class TestCompareNvsKeys:
    def test_missing_in_csv(self):
        h_data = {"storage": {"wifi_ssid", "wifi_pass", "extra_key"}}
        c_data = {"storage": {"wifi_ssid", "wifi_pass"}}
        issues = compare_nvs_keys(h_data, c_data, "CSV")
        assert len(issues) == 1
        assert "extra_key" in issues[0]
        assert "NOT in CSV" in issues[0]

    def test_extra_in_csv(self):
        h_data = {"storage": {"wifi_ssid"}}
        c_data = {"storage": {"wifi_ssid", "bonus"}}
        issues = compare_nvs_keys(h_data, c_data, "CSV")
        assert len(issues) == 1
        assert "bonus" in issues[0]
        assert "NOT in .h" in issues[0]

    def test_namespace_mismatch(self):
        h_data = {"storage": {"key1"}}
        c_data = {"other": {"key2"}}
        issues = compare_nvs_keys(h_data, c_data, "CSV")
        assert len(issues) == 2  # one for each missing namespace

    def test_no_issues(self):
        data = {"storage": {"k1", "k2"}}
        assert compare_nvs_keys(data, data, "CSV") == []


class TestRowsToNsKeys:
    def test_basic(self):
        rows = [
            NvsRow(namespace="a", key="k1", type="data", encoding="string", value=""),
            NvsRow(namespace="a", key="k2", type="data", encoding="string", value=""),
            NvsRow(namespace="b", key="k3", type="data", encoding="string", value=""),
        ]
        result = rows_to_ns_keys(rows)
        assert result == {"a": {"k1", "k2"}, "b": {"k3"}}


class TestValidateNvsRows:
    def test_valid_pin(self):
        rows = [NvsRow(namespace="s", key="led_pin", type="data", encoding="u8", value="13")]
        assert validate_nvs_rows(rows) == []

    def test_invalid_pin(self):
        rows = [NvsRow(namespace="s", key="led_pin", type="data", encoding="u8", value="99")]
        issues = validate_nvs_rows(rows)
        assert len(issues) == 1
        assert "led_pin" in issues[0]

    def test_valid_ip(self):
        rows = [NvsRow(namespace="s", key="ip", type="data", encoding="string", value="10.0.0.1")]
        assert validate_nvs_rows(rows) == []

    def test_invalid_ip(self):
        rows = [NvsRow(namespace="s", key="ip", type="data", encoding="string", value="bad")]
        issues = validate_nvs_rows(rows)
        assert len(issues) == 1

    def test_with_header(self, nvs_header):
        rows = [
            NvsRow(namespace="storage", key="wifi_ssid", type="data", encoding="string", value="net"),
            NvsRow(namespace="storage", key="wifi_pass", type="data", encoding="string", value="pass"),
        ]
        assert validate_nvs_rows(rows, header_path=nvs_header) == []

    def test_clean_rows(self):
        rows = [NvsRow(namespace="s", key="name", type="data", encoding="string", value="hello")]
        assert validate_nvs_rows(rows) == []
