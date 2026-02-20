"""Tests for src/esptool_wrapper.py."""

import subprocess
from unittest.mock import patch

import pytest

from src.exceptions import ToolExecutionError
from src.esptool_wrapper import _parse_chip_from_esptool, run_python, run_with_fallbacks


class TestParseChipFromEsptool:
    def test_detecting_pattern(self):
        output = "Connecting...\nDetecting chip type... ESP32-S3\nChip is ESP32-S3"
        assert _parse_chip_from_esptool(output) == "esp32s3"

    def test_chip_is_pattern(self):
        output = "Chip is ESP32-C3 (revision v0.4)"
        assert _parse_chip_from_esptool(output) == "esp32c3"

    def test_plain_esp32(self):
        output = "Detecting chip type... ESP32"
        assert _parse_chip_from_esptool(output) == "esp32"

    def test_no_match(self):
        assert _parse_chip_from_esptool("No chip info here") == ""

    def test_empty(self):
        assert _parse_chip_from_esptool("") == ""


class TestRunPython:
    @patch("src.esptool_wrapper.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python", "-c", "pass"], returncode=0, stdout="ok\n", stderr=""
        )
        result = run_python(["-c", "pass"])
        assert result.returncode == 0

    @patch("src.esptool_wrapper.subprocess.run")
    def test_failure_raises(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python", "-c", "fail"], returncode=1, stdout="", stderr="error"
        )
        with pytest.raises(ToolExecutionError):
            run_python(["-c", "fail"])

    @patch("src.esptool_wrapper.subprocess.run")
    def test_no_check(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python", "-c", "fail"], returncode=1, stdout="", stderr=""
        )
        result = run_python(["-c", "fail"], check=False)
        assert result.returncode == 1

    @patch("src.esptool_wrapper.subprocess.run")
    def test_logger_called(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["python", "-c", "pass"], returncode=0, stdout="output\n", stderr=""
        )
        logs = []
        run_python(["-c", "pass"], logger=logs.append)
        assert any("output" in l for l in logs)


class TestRunWithFallbacks:
    @patch("src.esptool_wrapper.subprocess.run")
    def test_first_succeeds(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        result = run_with_fallbacks([["-c", "pass"], ["-c", "alt"]])
        assert result.returncode == 0
        assert mock_run.call_count == 1

    @patch("src.esptool_wrapper.subprocess.run")
    def test_first_fails_second_succeeds(self, mock_run):
        fail = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
        mock_run.side_effect = [fail, ok]
        result = run_with_fallbacks([["-c", "bad"], ["-c", "good"]])
        assert result.returncode == 0
        assert mock_run.call_count == 2

    @patch("src.esptool_wrapper.subprocess.run")
    def test_all_fail(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="err"
        )
        with pytest.raises(ToolExecutionError):
            run_with_fallbacks([["-c", "bad1"], ["-c", "bad2"]])

    def test_no_variants(self):
        with pytest.raises(RuntimeError, match="No command variant"):
            run_with_fallbacks([])
