"""Remote execution protocol for shannot."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from .config import get_remote_deploy_dir, get_version, resolve_target
from .deploy import ensure_deployed
from .session import Session, create_session
from .ssh import SSHConfig, SSHConnection

if TYPE_CHECKING:
    pass


class RemoteExecutionError(Exception):
    """Remote execution failed."""

    pass


def run_remote_fast_path(
    ssh: SSHConnection,
    script_content: str,
) -> dict[str, str | int]:
    """
    Execute script on remote immediately without session workflow.

    Used by MCP fast path when all operations are pre-approved.
    Does not create a session - executes script directly in PyPy sandbox.

    Args:
        ssh: Connected SSH session
        script_content: Python script to execute

    Returns:
        Dictionary with 'exit_code', 'stdout', 'stderr' keys
    """
    deploy_dir = get_remote_deploy_dir()
    work_id = uuid.uuid4().hex[:8]
    workdir = f"/tmp/shannot-fast-{work_id}"

    try:
        # Create workdir
        result = ssh.run(f"mkdir -p {workdir}")
        if result.returncode != 0:
            raise RemoteExecutionError(f"Failed to create workdir: {result.stderr.decode()}")

        # Upload script
        remote_script = f"{workdir}/script.py"
        ssh.write_file(remote_script, script_content.encode("utf-8"))

        # Execute directly without --dry-run (operations execute immediately)
        # --json-output captures structured results
        cmd = (
            f"{deploy_dir}/shannot run --json-output "
            f"--tmp={workdir} "
            f"--lib-path={deploy_dir} "
            f"--pypy-sandbox={deploy_dir}/pypy3-c "
            f"{remote_script}"
        )

        result = ssh.run(cmd, timeout=300)

        # Parse JSON response if available
        stdout_str = result.stdout.decode("utf-8", errors="replace")
        stderr_str = result.stderr.decode("utf-8", errors="replace")

        try:
            response = json.loads(stdout_str)
            return {
                "exit_code": response.get("exit_code", result.returncode),
                "stdout": response.get("stdout", ""),
                "stderr": response.get("stderr", stderr_str),
            }
        except json.JSONDecodeError:
            # Fallback: use raw output
            return {
                "exit_code": result.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
            }

    finally:
        # Clean up workdir
        ssh.run(f"rm -rf {workdir}")


def _create_remote_workdir(ssh: SSHConnection) -> str:
    """Create temporary work directory on remote."""
    work_id = uuid.uuid4().hex[:8]
    workdir = f"/tmp/shannot-work-{work_id}"
    result = ssh.run(f"mkdir -p {workdir}")
    if result.returncode != 0:
        raise RemoteExecutionError(f"Failed to create workdir: {result.stderr.decode()}")
    return workdir


def _cleanup_remote_workdir(ssh: SSHConnection, workdir: str) -> None:
    """Remove remote work directory."""
    ssh.run(f"rm -rf {workdir}")


def _upload_script(ssh: SSHConnection, workdir: str, script_content: str) -> str:
    """Upload script to remote and return remote path."""
    remote_path = f"{workdir}/script.py"
    ssh.write_file(remote_path, script_content.encode("utf-8"))
    return remote_path


def run_remote_dry_run(
    target: str,
    script_path: str,
    script_content: str | None = None,
    name: str | None = None,
    analysis: str = "",
) -> Session | None:
    """
    Run script on remote in dry-run mode.

    Deploys shannot if needed, uploads script, runs in sandbox,
    and returns session with queued commands/writes.

    Args:
        target: SSH target (remote name, user@host, or user@host:port)
        script_path: Original script path (for naming)
        script_content: Script content to run (reads from script_path if not provided)
        name: Human-readable session name
        analysis: Description of script purpose

    Returns:
        Session object with remote session data, or None if no commands queued
    """
    if script_content is None:
        with open(script_path) as f:
            script_content = f.read()

    # Resolve target to (user, host, port)
    user, host, port = resolve_target(target)
    resolved_target = f"{user}@{host}"
    ssh_config = SSHConfig(target=resolved_target, port=port)

    with SSHConnection(ssh_config) as ssh:
        # Audit log remote connection
        from .audit import log_remote_connection, log_remote_deployment

        log_remote_connection(
            session_id=None,
            action="connected",
            target=resolved_target,
            port=port,
        )

        # Ensure shannot is deployed
        if not ensure_deployed(ssh):
            log_remote_deployment(
                session_id=None,
                action="failed",
                target=resolved_target,
                error="Failed to deploy shannot",
            )
            raise RemoteExecutionError("Failed to deploy shannot to remote")

        deploy_dir = get_remote_deploy_dir()

        log_remote_deployment(
            session_id=None,
            action="deployed",
            target=resolved_target,
            deploy_dir=deploy_dir,
        )
        workdir = _create_remote_workdir(ssh)

        try:
            # Upload script
            remote_script = _upload_script(ssh, workdir, script_content)

            # Run script (dry-run is default) with JSON output
            cmd = (
                f"{deploy_dir}/shannot run --json-output "
                f"--tmp={workdir} "
                f"--lib-path={deploy_dir} "
                f"--pypy-sandbox={deploy_dir}/pypy3-c "
                f"{remote_script}"
            )

            result = ssh.run(cmd, timeout=300)

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise RemoteExecutionError(f"Remote dry-run failed: {stderr}")

            # Parse JSON response
            stdout = result.stdout.decode("utf-8")
            try:
                response = json.loads(stdout)
            except json.JSONDecodeError as e:
                raise RemoteExecutionError(f"Invalid JSON response: {e}\n{stdout}") from e

            # Check version compatibility
            remote_version = response.get("version", "unknown")
            local_version = get_version()
            if remote_version != local_version:
                sys.stderr.write(
                    f"[WARN] Version mismatch: local={local_version}, remote={remote_version}\n"
                )

            # Extract session data
            session_data = response.get("session")
            if session_data is None:
                # No commands/writes queued - clean up workdir
                _cleanup_remote_workdir(ssh, workdir)
                return None

            # Create local session with remote metadata
            session = create_session(
                script_path=script_path,
                commands=session_data.get("commands", []),
                script_content=script_content,
                name=name or Path(script_path).stem,
                analysis=analysis,
                sandbox_args={
                    "target": target,
                    "remote_workdir": workdir,
                },
                pending_writes=session_data.get("pending_writes", []),
            )

            # Mark session as remote
            session.target = target
            session.remote_session_id = session_data.get("id")
            session.save()

            return session

        except (OSError, RemoteExecutionError):
            # Clean up workdir on error (but not on success - needed for execution)
            _cleanup_remote_workdir(ssh, workdir)
            raise


def execute_remote_session(session: Session) -> int:
    """
    Execute an approved session on the remote target.

    Args:
        session: Approved session with remote metadata

    Returns:
        Exit code from remote execution
    """
    target = session.target
    remote_session_id = session.remote_session_id
    remote_workdir = session.sandbox_args.get("remote_workdir")

    if not target:
        raise RemoteExecutionError("Session missing target")

    # Resolve target to (user, host, port)
    user, host, port = resolve_target(target)
    resolved_target = f"{user}@{host}"
    ssh_config = SSHConfig(target=resolved_target, port=port)

    with SSHConnection(ssh_config) as ssh:
        # Audit log remote connection
        from .audit import log_remote_connection

        log_remote_connection(
            session_id=session.id,
            action="connected",
            target=resolved_target,
            port=port,
        )

        deploy_dir = get_remote_deploy_dir()

        # Check if remote session still exists
        if remote_session_id:
            result = ssh.run(f"test -d ~/.local/share/shannot/sessions/{remote_session_id}")
            if result.returncode != 0:
                # Remote session was cleaned up - use recovery path
                msg = f"[WARN] Remote session {remote_session_id} not found, re-executing\n"
                sys.stderr.write(msg)
                return run_remote_with_approvals(session, ssh)

        # Execute on remote
        cmd = f"{deploy_dir}/shannot run --session={remote_session_id} --json-output"

        result = ssh.run(cmd, timeout=600)

        # Parse response
        try:
            response = json.loads(result.stdout.decode("utf-8"))
        except json.JSONDecodeError:
            # Fallback: use raw output
            session.stdout = result.stdout.decode("utf-8", errors="replace")
            session.stderr = result.stderr.decode("utf-8", errors="replace")
            session.exit_code = result.returncode
            session.status = "executed" if result.returncode == 0 else "failed"

            # Commit pending writes to remote filesystem
            if session.pending_writes:
                session.completed_writes = session.commit_writes_remote(ssh)

            session.save()
            return result.returncode

        # Update session with results
        session.stdout = response.get("stdout", "")
        session.stderr = response.get("stderr", "")
        session.exit_code = response.get("exit_code", result.returncode)
        session.status = "executed" if session.exit_code == 0 else "failed"

        # Commit pending writes to remote filesystem
        if session.pending_writes:
            session.completed_writes = session.commit_writes_remote(ssh)

        session.save()

        # Clean up remote workdir
        if remote_workdir:
            _cleanup_remote_workdir(ssh, remote_workdir)

        return session.exit_code or 0


def run_remote_with_approvals(session: Session, ssh: SSHConnection) -> int:
    """
    Re-run script on remote with pre-approved commands.

    Used when remote session was cleaned up but local still has approval.
    Uploads script and runs with --approved-commands flag.

    Args:
        session: Local session with approved commands
        ssh: Connected SSH session

    Returns:
        Exit code from execution
    """
    deploy_dir = get_remote_deploy_dir()

    # Create new workdir
    workdir = _create_remote_workdir(ssh)

    try:
        # Upload script from local session
        script_content = session.load_script()
        if not script_content:
            raise RemoteExecutionError("Session script content not found")

        remote_script = _upload_script(ssh, workdir, script_content)

        # JSON-encode approved commands
        approved_commands_json = json.dumps(session.commands)

        # Run with pre-approved commands (not dry-run)
        cmd = (
            f"{deploy_dir}/shannot run "
            f"--tmp={workdir} "
            f"--lib-path={deploy_dir} "
            f"--pypy-sandbox={deploy_dir}/pypy3-c "
            f"--approved-commands={json.dumps(approved_commands_json)} "
            f"{remote_script}"
        )

        result = ssh.run(cmd, timeout=600)

        # Update session with results
        session.stdout = result.stdout.decode("utf-8", errors="replace")
        session.stderr = result.stderr.decode("utf-8", errors="replace")
        session.exit_code = result.returncode
        session.status = "executed" if result.returncode == 0 else "failed"

        # Commit pending writes to remote filesystem
        if session.pending_writes:
            session.completed_writes = session.commit_writes_remote(ssh)

        session.save()

        return result.returncode

    finally:
        # Clean up workdir
        _cleanup_remote_workdir(ssh, workdir)
