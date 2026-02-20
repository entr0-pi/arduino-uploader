"""Structured exceptions with user-facing remediation hints."""


class UploaderError(Exception):
    """Base exception with optional remediation guidance."""

    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class ToolExecutionError(UploaderError):
    """A subprocess tool (esptool, mklittlefs, nvs_partition_gen) failed."""

    def __init__(self, tool: str, returncode: int, stderr: str = "", remediation: str = ""):
        first_line = next((l for l in stderr.splitlines() if l.strip()), "") if stderr else ""
        msg = f"{tool} failed (exit code {returncode})"
        if first_line:
            msg += f": {first_line}"
        super().__init__(msg, remediation or f"Check the Terminal Output tab for full {tool} logs.")
        self.tool = tool
        self.returncode = returncode


class PartitionLookupError(UploaderError):
    """Partition CSV missing or subtype not found."""
    pass


class ValidationError(UploaderError):
    """Config or NVS data validation failure."""
    pass
