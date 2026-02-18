"""Validation functions for ESP32 configuration values."""

import re

VALID_CHIPS = (
    "esp32", "esp32s2", "esp32s3", "esp32c2", "esp32c3",
    "esp32c6", "esp32h2", "esp32p4", "esp8266",
)


def sanitize_chip(value: str) -> str:
    """Normalise a chip string: lowercase, strip hyphens/spaces."""
    return value.lower().replace("-", "").replace(" ", "").strip()


def validate_ipv4(value: str) -> tuple[bool, str]:
    """Validate IPv4 address format."""
    pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    match = re.match(pattern, value)
    if not match:
        return False, "Invalid IPv4 format (expected: x.x.x.x)"
    octets = [int(g) for g in match.groups()]
    if any(o > 255 for o in octets):
        return False, "IPv4 octets must be 0-255"
    return True, ""


def validate_baud_rate(value: str) -> tuple[bool, str]:
    """Validate baud rate is a standard rate."""
    standard_rates = {
        50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800,
        9600, 19200, 38400, 57600, 115200, 230400, 460800, 500000, 576000,
        921600, 1000000, 2000000,
    }
    try:
        rate = int(value)
        if rate in standard_rates:
            return True, ""
        return False, f"Non-standard baud rate. Use one of: {', '.join(str(r) for r in sorted(standard_rates))}"
    except ValueError:
        return False, "Baud rate must be a number"


def validate_pin_number(value: str) -> tuple[bool, str]:
    """Validate ESP32 pin number (0-48)."""
    try:
        pin = int(value)
        if 0 <= pin <= 48:
            return True, ""
        return False, "Pin number must be 0-48"
    except ValueError:
        return False, "Pin number must be a number"


def validate_positive_int(value: str) -> tuple[bool, str]:
    """Validate positive integer."""
    try:
        val = int(value)
        if val > 0:
            return True, ""
        return False, "Value must be a positive integer"
    except ValueError:
        return False, "Value must be a number"


def validate_boolean(value: str) -> tuple[bool, str]:
    """Validate boolean (0 or 1)."""
    if value in ("0", "1"):
        return True, ""
    return False, "Boolean value must be 0 or 1"


def validate_port(value: str) -> tuple[bool, str]:
    """Validate port number (1-65535)."""
    try:
        port = int(value)
        if 1 <= port <= 65535:
            return True, ""
        return False, "Port must be 1-65535"
    except ValueError:
        return False, "Port must be a number"
