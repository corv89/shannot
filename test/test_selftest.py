"""Tests for self-test functionality."""

import subprocess
from unittest.mock import MagicMock, patch

from shannot.selftest import (
    SELF_TEST_SCRIPT,
    SelfTestResult,
    run_local_self_test,
)


class TestSelfTestResult:
    """Tests for SelfTestResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = SelfTestResult(
            success=True,
            elapsed_ms=15.5,
            output="sandbox host: sandbox",
        )
        assert result.success is True
        assert result.elapsed_ms == 15.5
        assert result.output == "sandbox host: sandbox"
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = SelfTestResult(
            success=False,
            elapsed_ms=0,
            error="Runtime not installed",
        )
        assert result.success is False
        assert result.elapsed_ms == 0
        assert result.error == "Runtime not installed"


class TestSelfTestScript:
    """Tests for the self-test script."""

    def test_script_content(self):
        """Test that the script is valid Python."""
        # Should parse without error
        compile(SELF_TEST_SCRIPT, "<selftest>", "exec")

    def test_script_uses_sys_version(self):
        """Test that the script uses sys.version_info (pure Python, no subprocess)."""
        assert "sys.version_info" in SELF_TEST_SCRIPT
        assert "sandbox ok" in SELF_TEST_SCRIPT
        assert "print" in SELF_TEST_SCRIPT


class TestRunLocalSelfTest:
    """Tests for run_local_self_test()."""

    def test_missing_runtime(self):
        """Test failure when runtime is not installed."""
        with patch("shannot.runtime.get_runtime_path", return_value=None):
            result = run_local_self_test()

        assert result.success is False
        assert result.error == "Runtime not installed"
        assert result.elapsed_ms == 0

    def test_missing_sandbox_binary(self):
        """Test failure when sandbox binary is not found."""
        with (
            patch("shannot.runtime.get_runtime_path", return_value="/some/path"),
            patch("shannot.runtime.find_pypy_sandbox", return_value=None),
        ):
            result = run_local_self_test()

        assert result.success is False
        assert result.error == "Sandbox binary not found"
        assert result.elapsed_ms == 0

    def test_subprocess_success(self):
        """Test successful subprocess execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"sandbox ok: (3, 6)\n"
        mock_result.stderr = b""

        with (
            patch("shannot.runtime.get_runtime_path", return_value="/some/path"),
            patch("shannot.runtime.find_pypy_sandbox", return_value="/path/to/pypy-sandbox"),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = run_local_self_test()

        assert result.success is True
        assert result.output == "sandbox ok: (3, 6)"
        assert result.error is None
        assert result.elapsed_ms > 0

        # Verify --code flag is used (no temp files)
        call_args = mock_run.call_args
        assert "--code" in call_args[0][0]
        assert SELF_TEST_SCRIPT in call_args[0][0]

    def test_subprocess_failure(self):
        """Test failed subprocess execution."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"Some error occurred\n"

        with (
            patch("shannot.runtime.get_runtime_path", return_value="/some/path"),
            patch("shannot.runtime.find_pypy_sandbox", return_value="/path/to/pypy-sandbox"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = run_local_self_test()

        assert result.success is False
        assert "Some error occurred" in str(result.error)

    def test_subprocess_timeout(self):
        """Test subprocess timeout handling."""
        with (
            patch("shannot.runtime.get_runtime_path", return_value="/some/path"),
            patch("shannot.runtime.find_pypy_sandbox", return_value="/path/to/pypy-sandbox"),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=30)),
        ):
            result = run_local_self_test()

        assert result.success is False
        assert "Timeout" in str(result.error)
        assert result.elapsed_ms == 30000

    def test_output_parsing_multiline(self):
        """Test that we extract the first line, skipping summary messages."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        # Script output comes first, summary message comes after
        mock_result.stdout = b"sandbox ok: (3, 6)\n\n*** No commands or writes were queued. ***\n"
        mock_result.stderr = b""

        with (
            patch("shannot.runtime.get_runtime_path", return_value="/some/path"),
            patch("shannot.runtime.find_pypy_sandbox", return_value="/path/to/pypy-sandbox"),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = run_local_self_test()

        assert result.success is True
        # Should get the script output, not the summary message
        assert result.output == "sandbox ok: (3, 6)"
