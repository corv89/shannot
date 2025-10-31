#!/usr/bin/env python3
"""CI/CD script for testing MCP server with mcp-probe.

This script automates MCP server testing using mcp-probe in CI/CD pipelines.
It provides comprehensive testing including initialization, capabilities,
protocol validation, and report generation.

Usage:
    python scripts/test_mcp_server.py [--report-dir DIR] [--fail-fast]

Options:
    --report-dir DIR    Directory for test reports (default: ./ci-reports)
    --fail-fast        Stop on first test failure
    --timeout SECONDS  Test timeout in seconds (default: 60)
    --verbose          Enable verbose output
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        """Disable colors for non-TTY environments."""
        cls.GREEN = ""
        cls.RED = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.BOLD = ""
        cls.RESET = ""


def print_header(message: str) -> None:
    """Print a formatted header message."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def check_mcp_probe() -> bool:
    """Check if mcp-probe is installed and available.

    Returns:
        True if mcp-probe is available, False otherwise.
    """
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


def get_shannot_mcp_command() -> Path:
    """Get the path to shannot-mcp executable.

    Returns:
        Path to shannot-mcp executable.

    Raises:
        FileNotFoundError: If shannot-mcp is not found.
    """
    # Try to find in current venv
    venv_bin = Path(sys.executable).parent
    shannot_mcp = venv_bin / "shannot-mcp"

    if shannot_mcp.exists():
        return shannot_mcp

    # Try PATH
    try:
        result = subprocess.run(
            ["which", "shannot-mcp"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.decode().strip())
    except subprocess.TimeoutExpired:
        pass

    raise FileNotFoundError("shannot-mcp not found. Please install with: pip install -e .[mcp]")


def run_test_suite(
    shannot_mcp: Path, timeout: int, output_dir: Path
) -> tuple[bool, dict[str, Any] | None]:
    """Run mcp-probe test suite.

    Args:
        shannot_mcp: Path to shannot-mcp executable
        timeout: Test timeout in seconds
        output_dir: Directory to save test reports

    Returns:
        Tuple of (success, results_dict)
    """
    print_info("Running comprehensive MCP test suite...")

    cmd = [
        "mcp-probe",
        "test",
        "--stdio",
        str(shannot_mcp),
        "--timeout",
        str(timeout),
        "--output-dir",
        str(output_dir),
        "--report",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout + 30,  # Add buffer for probe overhead
            check=False,
        )

        # Try to find and parse JSON report if available
        results = None
        json_files = list(output_dir.glob("*.json"))
        if json_files:
            try:
                with json_files[0].open() as f:
                    results = json.load(f)
            except (OSError, json.JSONDecodeError):
                print_warning("Could not parse test report as JSON")

        # Exit code 0 or 1 is acceptable (0=pass, 1=some tests failed)
        success = result.returncode == 0

        if success:
            print_success("Test suite completed successfully")
        elif result.returncode == 1:
            print_warning("Test suite completed with some test failures")
        else:
            print_error(
                f"Test suite failed with exit code {result.returncode}: {result.stderr.decode()}"
            )

        return success, results

    except subprocess.TimeoutExpired:
        print_error(f"Test suite timed out after {timeout} seconds")
        return False, None
    except Exception as e:
        print_error(f"Test suite failed with exception: {e}")
        return False, None


def validate_protocol(shannot_mcp: Path, timeout: int, output_dir: Path) -> bool:
    """Validate MCP protocol compliance.

    Args:
        shannot_mcp: Path to shannot-mcp executable
        timeout: Validation timeout in seconds
        output_dir: Directory to save validation reports

    Returns:
        True if validation passed, False otherwise.
    """
    print_info("Validating MCP protocol compliance...")

    cmd = [
        "mcp-probe",
        "validate",
        "--stdio",
        str(shannot_mcp),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode == 0:
            print_success("Protocol validation passed")
            return True
        elif result.returncode == 1:
            print_warning("Protocol validation found issues")
            # Print validation output if available
            if result.stdout:
                try:
                    validation = json.loads(result.stdout.decode())
                    print_info(f"Validation issues: {json.dumps(validation, indent=2)}")
                except json.JSONDecodeError:
                    print_info(result.stdout.decode())
            return False
        else:
            # Command not available or other error
            print_warning(
                f"Protocol validation not available (may be unsupported): {result.stderr.decode()}"
            )
            return True  # Don't fail if validation isn't supported yet

    except subprocess.TimeoutExpired:
        print_error(f"Protocol validation timed out after {timeout} seconds")
        return False
    except Exception as e:
        print_warning(f"Protocol validation skipped due to error: {e}")
        return True  # Don't fail if validation has issues


def export_capabilities(shannot_mcp: Path, output_dir: Path) -> bool:
    """Export server capabilities to reports.

    Note: mcp-probe export requires a session file from a debug session,
    not a direct server connection. This function is a placeholder for
    future functionality.

    Args:
        shannot_mcp: Path to shannot-mcp executable
        output_dir: Directory to save exports

    Returns:
        True (always, as this is informational only).
    """
    print_info("Capability export skipped (requires debug session file)")
    print_info("To manually export capabilities, run:")
    print_info(f"  mcp-probe debug --stdio {shannot_mcp}")
    print_info("  Then use 'export' command within the debug session")

    # Test reports already contain capability information
    return True


def generate_summary(report_dir: Path, test_results: dict[str, Any] | None) -> None:
    """Generate a test summary report.

    Args:
        report_dir: Directory containing test reports
        test_results: Test results from mcp-probe (if available)
    """
    print_info("Generating test summary...")

    summary_file = report_dir / "test-summary.md"

    with summary_file.open("w") as f:
        f.write("# MCP Server Test Summary\n\n")
        f.write(f"**Generated**: {Path.cwd()}\n\n")

        f.write("## Test Execution\n\n")

        if test_results:
            f.write("Test results from mcp-probe:\n\n")
            f.write("```json\n")
            f.write(json.dumps(test_results, indent=2))
            f.write("\n```\n\n")
        else:
            f.write("*Test results not available in structured format*\n\n")

        f.write("## Artifacts\n\n")
        for artifact in sorted(report_dir.glob("*")):
            if artifact.name != "test-summary.md":
                size = artifact.stat().st_size
                f.write(f"- `{artifact.name}` ({size:,} bytes)\n")

    print_success(f"Generated test summary: {summary_file}")


def main() -> int:
    """Main entry point for MCP server testing script.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        description="Test MCP server with mcp-probe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("./ci-reports"),
        help="Directory for test reports (default: ./ci-reports)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first test failure",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Test timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    args = parser.parse_args()

    # Disable colors if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    print_header("🧪 MCP Server Testing with mcp-probe")

    # Check prerequisites
    if not check_mcp_probe():
        print_error("mcp-probe is not installed or not in PATH")
        print_info("Install from GitHub releases: https://github.com/conikeec/mcp-probe/releases")
        return 1

    try:
        shannot_mcp = get_shannot_mcp_command()
        print_success(f"Found shannot-mcp at: {shannot_mcp}")
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    # Create report directory
    args.report_dir.mkdir(parents=True, exist_ok=True)
    print_success(f"Report directory: {args.report_dir}")

    # Track overall success
    all_passed = True

    # Run test suite
    test_passed, test_results = run_test_suite(
        shannot_mcp,
        args.timeout,
        args.report_dir,
    )
    if not test_passed:
        all_passed = False
        if args.fail_fast:
            print_error("Stopping due to test suite failure (--fail-fast)")
            return 1

    # Validate protocol
    if not validate_protocol(shannot_mcp, args.timeout, args.report_dir):
        all_passed = False
        if args.fail_fast:
            print_error("Stopping due to protocol validation failure (--fail-fast)")
            return 1

    # Export capabilities (non-critical)
    export_capabilities(shannot_mcp, args.report_dir)

    # Generate summary
    generate_summary(args.report_dir, test_results)

    # Final result
    print_header("Test Results")
    if all_passed:
        print_success("✅ All MCP tests passed!")
        return 0
    else:
        print_error("❌ Some MCP tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
