"""Shared fixtures for tests."""

import pytest

SAMPLE_PARTITION_CSV = """\
# Name,   Type, SubType, Offset,   Size,   Flags
nvs,       data, nvs,     0x9000,   0x5000,
otadata,   data, ota,     0xe000,   0x2000,
app0,      app,  ota_0,   0x10000,  0x1E0000,
spiffs,    data, spiffs,  0x1F0000, 0x10000,
"""

SAMPLE_NVS_CSV = """\
key,type,encoding,value
storage,namespace,,
wifi_ssid,data,string,MyNetwork
wifi_pass,data,string,secret123
"""

SAMPLE_NVS_HEADER = """\
#pragma once
namespace storage {
    constexpr const char* kNamespace = "storage";
    constexpr const char* wifi_ssid = "wifi_ssid";
    constexpr const char* wifi_pass = "wifi_pass";
}
"""


@pytest.fixture
def partition_csv(tmp_path):
    """Write sample partition CSV to tmp_path and return its path."""
    p = tmp_path / "partitions.csv"
    p.write_text(SAMPLE_PARTITION_CSV)
    return str(p)


@pytest.fixture
def nvs_csv(tmp_path):
    """Write sample NVS CSV to tmp_path and return its path."""
    p = tmp_path / "nvs_keys.csv"
    p.write_text(SAMPLE_NVS_CSV)
    return str(p)


@pytest.fixture
def nvs_header(tmp_path):
    """Write sample NVS header to tmp_path and return its path."""
    p = tmp_path / "nvs_keys.h"
    p.write_text(SAMPLE_NVS_HEADER)
    return str(p)
