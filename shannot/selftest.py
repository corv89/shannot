"""
Self-test for verifying sandbox installation and execution.

Provides end-to-end verification that the sandbox runtime works correctly
by executing a minimal test script.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

# Minimal script that exercises basic sandbox functionality
# Uses platform.node() which is a simple syscall (gethostname)
SELF_TEST_SCRIPT = """\
import platform
print("hello from", platform.node())
"""


@dataclass
class SelfTestResult:
    """Result of a self-test execution."""

    success: bool
    elapsed_ms: float
    output: str = ""
    error: str | None = None


def run_local_self_test() -> SelfTestResult:
    """
    Run minimal script through local sandbox to verify installation.

    Returns:
        SelfTestResult with success status, timing, and output/error.
    """
    from .runtime import find_pypy_sandbox, get_runtime_path

    # Check prerequisites
    runtime_path = get_runtime_path()
    if not runtime_path:
        return SelfTestResult(
            success=False,
            elapsed_ms=0,
            error="Runtime not installed",
        )

    sandbox_binary = find_pypy_sandbox()
    if not sandbox_binary:
        return SelfTestResult(
            success=False,
            elapsed_ms=0,
            error="Sandbox binary not found",
        )

    # Create temporary script file
    fd, script_path = tempfile.mkstemp(suffix=".py", prefix="shannot_selftest_")
    try:
        os.write(fd, SELF_TEST_SCRIPT.encode())
        os.close(fd)

        # Run through shannot (exercises full path)
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-m", "shannot", "run", "--nocolor", script_path],
            capture_output=True,
            timeout=30,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            # Extract output (last non-empty line from stdout)
            stdout = result.stdout.decode().strip()
            # Filter out any setup messages, get the actual script output
            lines = [line for line in stdout.split("\n") if line.strip()]
            output = lines[-1] if lines else ""

            return SelfTestResult(
                success=True,
                elapsed_ms=elapsed_ms,
                output=output,
            )
        else:
            stderr = result.stderr.decode().strip()
            return SelfTestResult(
                success=False,
                elapsed_ms=elapsed_ms,
                error=stderr or f"Exit code {result.returncode}",
            )

    except subprocess.TimeoutExpired:
        return SelfTestResult(
            success=False,
            elapsed_ms=30000,
            error="Timeout (30s)",
        )
    except Exception as e:
        return SelfTestResult(
            success=False,
            elapsed_ms=0,
            error=str(e),
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def run_remote_self_test(
    user: str,
    host: str,
    port: int,
    *,
    deploy_if_missing: bool = True,
) -> SelfTestResult:
    """
    Run minimal script through remote sandbox to verify deployment.

    Args:
        user: SSH username
        host: SSH host
        port: SSH port
        deploy_if_missing: If True, deploy shannot if not present

    Returns:
        SelfTestResult with success status, timing, and output/error.
    """
    from .deploy import ensure_deployed
    from .ssh import SSHConfig, SSHConnection

    config = SSHConfig(target=f"{user}@{host}", port=port, connect_timeout=10)

    try:
        with SSHConnection(config) as ssh:
            if not ssh.connect():
                return SelfTestResult(
                    success=False,
                    elapsed_ms=0,
                    error="SSH connection failed",
                )

            # Check/deploy shannot on remote
            if deploy_if_missing:
                try:
                    ensure_deployed(ssh)
                except Exception as e:
                    return SelfTestResult(
                        success=False,
                        elapsed_ms=0,
                        error=f"Deployment failed: {e}",
                    )

            # Create temp script on remote
            script_content = SELF_TEST_SCRIPT.encode()
            remote_script = "/tmp/shannot_selftest.py"

            # Write script to remote
            write_result = ssh.run(f"cat > {remote_script}", input_data=script_content)
            if write_result.returncode != 0:
                return SelfTestResult(
                    success=False,
                    elapsed_ms=0,
                    error="Failed to write test script",
                )

            # Run through shannot on remote
            start = time.perf_counter()
            result = ssh.run(f"shannot run --nocolor {remote_script}", timeout=30)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Cleanup
            ssh.run(f"rm -f {remote_script}")

            if result.returncode == 0:
                stdout = result.stdout.decode().strip()
                lines = [line for line in stdout.split("\n") if line.strip()]
                output = lines[-1] if lines else ""

                return SelfTestResult(
                    success=True,
                    elapsed_ms=elapsed_ms,
                    output=output,
                )
            else:
                stderr = result.stderr.decode().strip()
                return SelfTestResult(
                    success=False,
                    elapsed_ms=elapsed_ms,
                    error=stderr or f"Exit code {result.returncode}",
                )

    except Exception as e:
        return SelfTestResult(
            success=False,
            elapsed_ms=0,
            error=str(e),
        )
