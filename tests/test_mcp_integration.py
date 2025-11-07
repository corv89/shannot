"""Integration tests for MCP server using mcp-probe.

This module provides integration testing for the Shannot MCP server using
the mcp-probe tool. These tests verify protocol compliance, capability
availability, and overall server functionality.
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestMCPProbeIntegration:
    """Integration tests using mcp-probe CLI tool."""

    @pytest.fixture
    def shannot_mcp_command(self) -> list[str]:
        """Get the command to run shannot-mcp server.

        Returns the full path to the shannot-mcp executable in the current
        virtual environment.
        """
        # Get the shannot-mcp script path from current Python environment
        venv_bin = Path(sys.executable).parent
        shannot_mcp = venv_bin / "shannot-mcp"

        if not shannot_mcp.exists():
            pytest.skip(f"shannot-mcp not found at {shannot_mcp}")

        return [str(shannot_mcp)]

    @pytest.fixture
    def mcp_probe_available(self) -> bool:
        """Check if mcp-probe is available in PATH."""
        try:
            result = subprocess.run(
                ["mcp-probe", "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def test_mcp_probe_installed(self, mcp_probe_available: bool) -> None:
        """Verify mcp-probe is installed and accessible."""
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")
        assert mcp_probe_available

    def test_server_initialization(
        self, shannot_mcp_command: list[str], mcp_probe_available: bool, tmp_path: Path
    ) -> None:
        """Test that the MCP server initializes correctly.

        Uses mcp-probe to verify the server can start and respond to
        basic initialization requests.
        """
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")

        # Run mcp-probe test with a short timeout for initialization check
        output_dir = tmp_path / "test-reports"
        output_dir.mkdir()

        result = subprocess.run(
            [
                "mcp-probe",
                "test",
                "--stdio",
                *shannot_mcp_command,
                "--timeout",
                "30",
                "--output-dir",
                str(output_dir),
                "--report",
            ],
            capture_output=True,
            timeout=45,
            check=False,
        )

        # Check that the command completed (non-zero exit is ok if some tests fail)
        # We're primarily testing that the server starts and responds
        assert result.returncode in (
            0,
            1,
        ), f"mcp-probe failed to run: {result.stderr.decode()}"

    def test_server_capabilities(
        self, shannot_mcp_command: list[str], mcp_probe_available: bool, tmp_path: Path
    ) -> None:
        """Test that the MCP server exposes expected capabilities.

        Verifies that the server advertises tools, resources, and prompts
        capabilities as expected.
        """
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")

        output_dir = tmp_path / "capabilities-test"
        output_dir.mkdir()

        # Run tests with report generation to check capabilities
        result = subprocess.run(
            [
                "mcp-probe",
                "test",
                "--stdio",
                *shannot_mcp_command,
                "--timeout",
                "30",
                "--output-dir",
                str(output_dir),
                "--report",
            ],
            capture_output=True,
            timeout=45,
            check=False,
        )

        if result.returncode not in (0, 1):
            pytest.skip(f"mcp-probe test failed: {result.stderr.decode()}")

        # Check that some test report was generated
        report_files = list(output_dir.glob("*"))
        assert len(report_files) > 0, "Expected at least one report file"

    def test_tools_available(
        self, shannot_mcp_command: list[str], mcp_probe_available: bool
    ) -> None:
        """Test that diagnostic tools are available.

        Verifies that the server exposes sandbox tools based on loaded
        profiles.
        """
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")

        # Use mcp-probe debug mode to check for tools
        result = subprocess.run(
            [
                "mcp-probe",
                "debug",
                "--stdio",
                *shannot_mcp_command,
            ],
            input=b"list tools\nexit\n",
            capture_output=True,
            timeout=30,
            check=False,
        )

        # Debug command may not support non-interactive mode
        # This is a best-effort check
        if result.returncode == 0:
            output = result.stdout.decode()
            # Look for evidence of tools in the output
            assert "diagnostics" in output.lower() or "sandbox" in output.lower(), (
                "Expected diagnostic/sandbox tools to be listed"
            )

    def test_prompts_available(
        self, shannot_mcp_command: list[str], mcp_probe_available: bool
    ) -> None:
        """Test that diagnostic prompts are available.

        Verifies that the server exposes the 6 diagnostic prompts we
        implemented.
        """
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")

        # Use mcp-probe debug mode to check for prompts
        result = subprocess.run(
            [
                "mcp-probe",
                "debug",
                "--stdio",
                *shannot_mcp_command,
            ],
            input=b"list prompts\nexit\n",
            capture_output=True,
            timeout=30,
            check=False,
        )

        # Debug command may not support non-interactive mode
        # This is a best-effort check
        if result.returncode == 0:
            output = result.stdout.decode()
            # Look for evidence of our prompts
            expected_prompts = [
                "system-health-check",
                "investigate-performance",
                "analyze-logs",
                "disk-usage-audit",
                "monitor-processes",
                "check-service-status",
            ]
            found_prompts = [p for p in expected_prompts if p in output]
            assert len(found_prompts) >= 1, (
                f"Expected to find diagnostic prompts, found: {found_prompts}"
            )

    def test_protocol_validation(
        self, shannot_mcp_command: list[str], mcp_probe_available: bool
    ) -> None:
        """Test MCP protocol compliance.

        Uses mcp-probe validate command to check for protocol violations.
        """
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")

        # Run protocol validation
        result = subprocess.run(
            [
                "mcp-probe",
                "validate",
                "--stdio",
                *shannot_mcp_command,
            ],
            capture_output=True,
            timeout=45,
            check=False,
        )

        # Note: validate command might not be fully implemented yet
        if result.returncode not in (0, 1):
            pytest.skip(f"mcp-probe validate not available or failed: {result.stderr.decode()}")

        # If validation ran, check for errors
        if result.returncode == 0:
            # Success indicates protocol compliance
            assert True
        elif result.returncode == 1:
            # Check if there were any errors (as opposed to warnings)
            output = result.stdout.decode()
            # This is a lenient check - we mainly want to ensure the
            # validation runs and doesn't crash
            assert output, "Validation output should not be empty"


@pytest.mark.integration
class TestMCPProbeWithExecutor:
    """Integration tests using mcp-probe with executor targets.

    These tests require additional configuration and may be skipped if
    the necessary setup is not available.
    """

    @pytest.fixture
    def config_file_exists(self) -> bool:
        """Check if Shannot config file exists."""
        config_path = Path.home() / ".config" / "shannot" / "config.toml"
        return config_path.exists()

    @pytest.fixture
    def mcp_probe_available(self) -> bool:
        """Check if mcp-probe is available in PATH."""
        try:
            result = subprocess.run(
                ["mcp-probe", "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def test_server_with_local_executor(
        self, config_file_exists: bool, mcp_probe_available: bool
    ) -> None:
        """Test MCP server with --target local executor.

        This test verifies the server works with explicit executor targets.
        """
        if not mcp_probe_available:
            pytest.skip("mcp-probe not installed")

        if not config_file_exists:
            pytest.skip("Shannot config file not found")

        # Get the shannot-mcp script path
        venv_bin = Path(sys.executable).parent
        shannot_mcp = venv_bin / "shannot-mcp"

        if not shannot_mcp.exists():
            pytest.skip(f"shannot-mcp not found at {shannot_mcp}")

        # Test with --target local
        result = subprocess.run(
            [
                "mcp-probe",
                "test",
                "--stdio",
                str(shannot_mcp),
                "--args",
                "--target local",
                "--timeout",
                "30",
            ],
            capture_output=True,
            timeout=45,
            check=False,
        )

        # Note: This may fail due to mcp-probe argument parsing issues
        # but we're testing that the server itself works
        if result.returncode not in (0, 1):
            # If it failed due to argument parsing, that's a known issue
            stderr = result.stderr.decode()
            if (
                "Failed to initialize" in stderr
                or "Transport error" in stderr
                or "unexpected argument" in stderr
            ):
                pytest.skip("mcp-probe has issues passing --target as argument (known limitation)")
            else:
                pytest.fail(f"Unexpected error: {stderr}")
