"""Tests for src/validators.py."""

from src.validators import (
    sanitize_chip,
    validate_baud_rate,
    validate_boolean,
    validate_ipv4,
    validate_pin_number,
    validate_port,
    validate_positive_int,
)


class TestSanitizeChip:
    def test_lowercase_and_strip_hyphens(self):
        assert sanitize_chip("ESP32-S3") == "esp32s3"

    def test_strip_spaces(self):
        assert sanitize_chip(" esp32 ") == "esp32"

    def test_already_clean(self):
        assert sanitize_chip("esp32c3") == "esp32c3"


class TestValidateIPv4:
    def test_valid(self):
        assert validate_ipv4("192.168.1.1") == (True, "")

    def test_valid_zeros(self):
        assert validate_ipv4("0.0.0.0") == (True, "")

    def test_valid_max(self):
        assert validate_ipv4("255.255.255.255") == (True, "")

    def test_invalid_format(self):
        ok, msg = validate_ipv4("abc.def.ghi.jkl")
        assert not ok
        assert "format" in msg.lower()

    def test_octet_overflow(self):
        ok, msg = validate_ipv4("256.1.1.1")
        assert not ok
        assert "octet" in msg.lower()

    def test_too_few_octets(self):
        ok, _ = validate_ipv4("192.168.1")
        assert not ok


class TestValidateBaudRate:
    def test_standard_rate(self):
        assert validate_baud_rate("115200") == (True, "")

    def test_high_rate(self):
        assert validate_baud_rate("921600") == (True, "")

    def test_nonstandard(self):
        ok, msg = validate_baud_rate("12345")
        assert not ok
        assert "Non-standard" in msg

    def test_not_a_number(self):
        ok, msg = validate_baud_rate("fast")
        assert not ok
        assert "number" in msg.lower()


class TestValidatePinNumber:
    def test_zero(self):
        assert validate_pin_number("0") == (True, "")

    def test_max(self):
        assert validate_pin_number("48") == (True, "")

    def test_too_high(self):
        ok, _ = validate_pin_number("49")
        assert not ok

    def test_negative(self):
        ok, _ = validate_pin_number("-1")
        assert not ok

    def test_not_a_number(self):
        ok, msg = validate_pin_number("abc")
        assert not ok
        assert "number" in msg.lower()


class TestValidatePositiveInt:
    def test_one(self):
        assert validate_positive_int("1") == (True, "")

    def test_zero_fails(self):
        ok, _ = validate_positive_int("0")
        assert not ok

    def test_negative_fails(self):
        ok, _ = validate_positive_int("-1")
        assert not ok

    def test_not_a_number(self):
        ok, msg = validate_positive_int("abc")
        assert not ok
        assert "number" in msg.lower()


class TestValidateBoolean:
    def test_zero(self):
        assert validate_boolean("0") == (True, "")

    def test_one(self):
        assert validate_boolean("1") == (True, "")

    def test_two_fails(self):
        ok, _ = validate_boolean("2")
        assert not ok

    def test_true_string_fails(self):
        ok, _ = validate_boolean("true")
        assert not ok


class TestValidatePort:
    def test_min(self):
        assert validate_port("1") == (True, "")

    def test_max(self):
        assert validate_port("65535") == (True, "")

    def test_zero_fails(self):
        ok, _ = validate_port("0")
        assert not ok

    def test_over_max_fails(self):
        ok, _ = validate_port("65536")
        assert not ok

    def test_not_a_number(self):
        ok, msg = validate_port("http")
        assert not ok
        assert "number" in msg.lower()
