"""Mixin for subprocess execution with tiered security."""

from __future__ import annotations

import subprocess as real_subprocess
import sys
from typing import TYPE_CHECKING

from .queue import write_pending
from .virtualizedproc import signature

if TYPE_CHECKING:
    from ._protocols import HasSandio
    from .ssh import SSHConnection


class MixSubprocess:
    """
    Mixin to handle system() calls from the sandbox.

    Security tiers (checked in order):
        1. subprocess_always_deny: set - never execute
        2. subprocess_approved: set - session-approved commands
        3. subprocess_auto_approve: set - execute immediately (from profile)
        4. Everything else: queue for review

    Profile-based configuration:
        - .shannot/config.toml (project-local, takes precedence)
        - ~/.config/shannot/config.toml (global fallback)
        - Built-in defaults if no config file exists

    Modes:
        subprocess_dry_run: bool - log all, execute none
    """

    # Command sets (populated by load_profile() and load_session_commands())
    subprocess_auto_approve = set()  # Execute immediately (from profile)
    subprocess_always_deny = set()  # Never execute (from profile)

    # Behavior
    subprocess_dry_run = False  # Log but don't execute

    # Remote execution (set by MixRemote or CLI)
    remote_target: str | None = None  # SSH target (user@host), None = local

    # State
    subprocess_pending = []  # Commands awaiting approval
    subprocess_approved = set()  # Commands approved this session
    file_writes_pending = []  # File writes awaiting approval
    file_deletions_pending = []  # File/dir deletions awaiting approval

    # Execution tracking (populated during execution, NOT dry-run)
    # Note: Use _get_executed_commands() to access - ensures instance-level list
    _executed_commands: list[dict] | None = None

    # Persistence
    subprocess_auto_persist = True  # Auto-save pending when queuing

    # Session context (set by interact.py before run)
    subprocess_script_name = None  # str | None
    subprocess_script_path = None  # str | None
    subprocess_script_content = None  # str | None
    subprocess_analysis = None  # str | None
    subprocess_sandbox_args = {}  # dict - Structured args for re-execution

    def _parse_command(self, cmd):
        """Extract base command from shell string."""
        # Handle pipes, redirects, etc.
        parts = cmd.split()
        if not parts:
            return "", []

        # Skip env vars like FOO=bar cmd
        base = parts[0]
        for p in parts:
            if "=" not in p:
                base = p
                break

        # Strip path
        base = base.split("/")[-1]
        return base, parts

    def _check_permission(self, cmd):
        """
        Check permission for a command.

        Returns: 'allow', 'deny', or 'queue'

        Permission flow:
            1. always_deny -> deny
            2. session approved -> allow
            3. auto_approve -> allow
            4. everything else -> queue
        """
        base, parts = self._parse_command(cmd)

        # 1. Check always_deny first (never run these)
        if base in self.subprocess_always_deny or cmd in self.subprocess_always_deny:
            return "deny"

        # 2. Check if previously approved this session
        if cmd in self.subprocess_approved:
            return "allow"

        # 3. Check auto_approve (profile-trusted commands)
        if base in self.subprocess_auto_approve or cmd in self.subprocess_auto_approve:
            return "allow"

        # 4. Everything else queues for review
        return "queue"

    def _get_ssh_connection(self) -> SSHConnection | None:
        """Get SSH connection from MixRemote if available."""
        return getattr(self, "_ssh_connection", None)

    def _get_executed_commands(self) -> list[dict]:
        """Get executed commands list, creating instance-level list if needed."""
        if self._executed_commands is None:
            self._executed_commands = []
        return self._executed_commands

    def get_execution_results(self) -> list[dict]:
        """Get list of executed commands with their exit codes."""
        return self._get_executed_commands()

    def _execute_command(self, cmd: str) -> int:
        """
        Execute command locally or remotely.

        If remote_target is set, executes via SSH. Otherwise executes locally.

        Args:
            cmd: Shell command to execute

        Returns:
            Command exit code
        """
        if self.remote_target:
            # Try to use existing SSH connection from MixRemote
            ssh = self._get_ssh_connection()
            if ssh:
                result = ssh.run(cmd)
                return result.returncode

            # Fallback: one-shot SSH connection
            result = real_subprocess.run(
                ["ssh", self.remote_target, cmd],
                shell=False,
            )
            return result.returncode

        # Local execution
        result = real_subprocess.run(cmd, shell=True)
        return result.returncode

    @signature("system(p)i")
    def s_system(self: HasSandio, p_command):
        cmd = self.sandio.read_charp(p_command, 4096).decode("utf-8")
        base, _ = self._parse_command(cmd)  # type: ignore[attr-defined]

        # Dry-run mode: log everything, execute nothing
        if self.subprocess_dry_run:  # type: ignore[attr-defined]
            self.subprocess_pending.append(cmd)  # type: ignore[attr-defined]
            if self.subprocess_auto_persist:  # type: ignore[attr-defined]
                self.save_pending()  # type: ignore[attr-defined]
            sys.stderr.write(f"[DRY-RUN] {cmd}\n")

            # Audit log queued command in dry-run mode
            from .audit import log_command_decision

            log_command_decision(
                session_id=None,  # Session not yet created
                command=cmd,
                decision="queue",
                reason="dry_run",
                base_command=base,
                target=self.remote_target,  # type: ignore[attr-defined]
            )
            return 0

        permission = self._check_permission(cmd)  # type: ignore[attr-defined]

        if permission == "deny":
            sys.stderr.write(f"[DENIED] {cmd}\n")
            # Audit log denied command
            from .audit import log_command_decision

            log_command_decision(
                session_id=None,
                command=cmd,
                decision="deny",
                reason="always_deny",
                base_command=base,
                target=self.remote_target,  # type: ignore[attr-defined]
            )
            return 127  # Command not found

        elif permission == "queue":
            self.subprocess_pending.append(cmd)  # type: ignore[attr-defined]
            if self.subprocess_auto_persist:  # type: ignore[attr-defined]
                self.save_pending()  # type: ignore[attr-defined]
            sys.stderr.write(f"[QUEUED] {cmd}\n")
            # Audit log queued command
            from .audit import log_command_decision

            log_command_decision(
                session_id=None,
                command=cmd,
                decision="queue",
                reason="not_in_auto_approve",
                base_command=base,
                target=self.remote_target,  # type: ignore[attr-defined]
            )
            # Return fake success - script continues, but command didn't run
            return 0

        elif permission == "allow":
            target_info = f" @ {self.remote_target}" if self.remote_target else ""  # type: ignore[attr-defined]
            sys.stderr.write(f"[EXEC{target_info}] {cmd}\n")
            # Determine reason for allow
            if cmd in self.subprocess_approved:  # type: ignore[attr-defined]
                reason = "session_approved"
            else:
                reason = "auto_approve"
            # Audit log allowed command
            from .audit import log_command_decision

            log_command_decision(
                session_id=None,
                command=cmd,
                decision="allow",
                reason=reason,
                base_command=base,
                target=self.remote_target,  # type: ignore[attr-defined]
            )
            exit_code = self._execute_command(cmd)  # type: ignore[attr-defined]

            # Track execution result
            self._get_executed_commands().append(  # type: ignore[attr-defined]
                {
                    "cmd": cmd,
                    "exit_code": exit_code,
                }
            )

            return exit_code

        return 127

    def approve_command(self, cmd):
        """Approve a specific command for this session."""
        self.subprocess_approved.add(cmd)
        if cmd in self.subprocess_pending:
            self.subprocess_pending.remove(cmd)

    def approve_all_pending(self):
        """Approve all pending commands."""
        for cmd in self.subprocess_pending:
            self.subprocess_approved.add(cmd)
        self.subprocess_pending.clear()

    def get_pending(self):
        """Return list of commands awaiting approval."""
        return list(self.subprocess_pending)

    def load_profile(self):
        """Load security profile into class attributes."""
        from .config import load_config

        profile = load_config().profile
        self.subprocess_auto_approve.update(profile.auto_approve)
        self.subprocess_always_deny.update(profile.always_deny)

    def save_pending(self):
        """Write pending commands to queue file."""
        write_pending(self.subprocess_pending)

    def finalize_session(self):
        """
        Create a Session from queued commands, writes, and deletions.

        Call this at the end of a dry-run execution to bundle all
        queued operations into a reviewable session.

        Returns the created Session, or None if nothing was queued.
        """
        if (
            not self.subprocess_pending
            and not self.file_writes_pending
            and not self.file_deletions_pending
        ):
            return None

        from .session import create_session

        # Convert PendingWrite objects to dicts for serialization
        pending_write_dicts = []
        for write in self.file_writes_pending:
            if hasattr(write, "to_dict"):
                pending_write_dicts.append(write.to_dict())
            elif isinstance(write, dict):
                pending_write_dicts.append(write)

        # Convert PendingDeletion objects to dicts for serialization
        pending_deletion_dicts = []
        for deletion in self.file_deletions_pending:
            if hasattr(deletion, "to_dict"):
                pending_deletion_dicts.append(deletion.to_dict())
            elif isinstance(deletion, dict):
                pending_deletion_dicts.append(deletion)

        session = create_session(
            script_path=self.subprocess_script_path or "<unknown>",
            commands=list(self.subprocess_pending),
            script_content=self.subprocess_script_content,
            name=self.subprocess_script_name,
            analysis=self.subprocess_analysis or "",
            sandbox_args=self.subprocess_sandbox_args,
            pending_writes=pending_write_dicts,
            pending_deletions=pending_deletion_dicts,
        )

        self.subprocess_pending.clear()
        self.file_writes_pending.clear()
        self.file_deletions_pending.clear()
        return session

    def load_session_commands(self, session):
        """
        Load a session's commands as pre-approved.

        Use this when re-executing an approved session.
        """
        for cmd in session.commands:
            self.subprocess_approved.add(cmd)
