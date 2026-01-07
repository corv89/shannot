"""
Self-test for verifying sandbox installation and execution.

Provides end-to-end verification that the sandbox runtime works correctly
by executing a minimal test script.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass

# Minimal script that exercises basic sandbox functionality
# Uses pure Python (no subprocess calls) to verify execution works
SELF_TEST_SCRIPT = """\
import sys
print('sandbox ok:', sys.version_info[:2])
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

    try:
        # Run with --code flag (no temp files needed)
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-m", "shannot", "run", "--nocolor", "--code", SELF_TEST_SCRIPT],
            capture_output=True,
            timeout=30,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if result.returncode == 0:
            # Extract first line of script output (skip summary messages)
            stdout = result.stdout.decode().strip()
            lines = [ln for ln in stdout.split("\n") if ln.strip() and not ln.startswith("***")]
            output = lines[0] if lines else ""

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

            # Run with --code flag (no temp files needed)
            # Shell-escape the script for remote execution
            import shlex

            from .config import get_remote_deploy_dir

            deploy_dir = get_remote_deploy_dir()
            escaped_script = shlex.quote(SELF_TEST_SCRIPT)
            # Point to deployed runtime (pypy3-c and lib-python are in deploy_dir)
            cmd = (
                f"{deploy_dir}/shannot run --nocolor "
                f"--lib-path={deploy_dir} "
                f"--pypy-sandbox={deploy_dir}/pypy3-c "
                f"--code={escaped_script}"
            )
            start = time.perf_counter()
            result = ssh.run(cmd, timeout=30)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if result.returncode == 0:
                # Extract first line of script output (skip summary messages)
                stdout = result.stdout.decode().strip()
                lines = [ln for ln in stdout.split("\n") if ln.strip() and not ln.startswith("***")]
                output = lines[0] if lines else ""

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
