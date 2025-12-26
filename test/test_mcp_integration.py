"""MCP protocol compliance tests using mcp-probe."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
class TestMCPProtocolCompliance:
    """Integration tests using mcp-probe external tool."""

    @pytest.fixture(autouse=True)
    def check_mcp_probe(self):
        """Skip all tests if mcp-probe not installed."""
        if not shutil.which("mcp-probe"):
            pytest.skip("mcp-probe not installed")

    @pytest.fixture
    def shannot_mcp_path(self) -> Path:
        """Get path to shannot-mcp executable."""
        venv_bin = Path(sys.executable).parent
        shannot_mcp = venv_bin / "shannot-mcp"
        if shannot_mcp.exists():
            return shannot_mcp
        # Try PATH
        which = shutil.which("shannot-mcp")
        if which:
            return Path(which)
        pytest.skip("shannot-mcp not found")
        raise AssertionError("unreachable")  # pytest.skip raises

    def test_mcp_probe_test_suite(self, shannot_mcp_path: Path):
        """Run mcp-probe test suite against shannot-mcp."""
        result = subprocess.run(
            [
                "mcp-probe",
                "test",
                "--stdio",
                str(shannot_mcp_path),
                "--fail-fast",
                "--timeout",
                "60",
            ],
            capture_output=True,
            timeout=90,
        )

        stdout = result.stdout.decode()
        if result.returncode != 0:
            pytest.fail(f"mcp-probe test suite failed:\n{stdout}")

    def test_mcp_protocol_validation(self, shannot_mcp_path: Path):
        """Validate MCP protocol compliance."""
        result = subprocess.run(
            [
                "mcp-probe",
                "validate",
                "--stdio",
                str(shannot_mcp_path),
                "--severity",
                "error",
            ],
            capture_output=True,
            timeout=60,
        )

        stdout = result.stdout.decode()
        if result.returncode != 0:
            pytest.fail(f"Protocol validation failed:\n{stdout}")
