"""Mixin for subprocess execution with tiered security."""

import subprocess as real_subprocess
import sys

from .virtualizedproc import signature
from .queue import write_pending


class MixSubprocess:
    """
    Mixin to handle system() calls from the sandbox.

    Security tiers (checked in order):
        1. subprocess_always_deny: set - never execute
        2. subprocess_approved: set - session-approved commands
        3. subprocess_auto_approve: set - execute immediately (from profile)
        4. Everything else: queue for review

    Profile-based configuration:
        - .shannot/profile.json (project-local, takes precedence)
        - ~/.config/shannot/profile.json (global fallback)
        - DEFAULT_PROFILE if no file exists

    Modes:
        subprocess_dry_run: bool - log all, execute none
    """

    # Command sets (populated by load_profile() and load_session_commands())
    subprocess_auto_approve = set()  # Execute immediately (from profile)
    subprocess_always_deny = set()  # Never execute (from profile)

    # Behavior
    subprocess_dry_run = False  # Log but don't execute

    # State
    subprocess_pending = []  # Commands awaiting approval
    subprocess_approved = set()  # Commands approved this session

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

    @signature("system(p)i")
    def s_system(self, p_command):
        cmd = self.sandio.read_charp(p_command, 4096).decode("utf-8")

        # Dry-run mode: log everything, execute nothing
        if self.subprocess_dry_run:
            self.subprocess_pending.append(cmd)
            if self.subprocess_auto_persist:
                self.save_pending()
            sys.stderr.write(f"[DRY-RUN] {cmd}\n")
            return 0

        permission = self._check_permission(cmd)

        if permission == "deny":
            sys.stderr.write(f"[DENIED] {cmd}\n")
            return 127  # Command not found

        elif permission == "queue":
            self.subprocess_pending.append(cmd)
            if self.subprocess_auto_persist:
                self.save_pending()
            sys.stderr.write(f"[QUEUED] {cmd}\n")
            # Return fake success - script continues, but command didn't run
            return 0

        elif permission == "allow":
            sys.stderr.write(f"[EXEC] {cmd}\n")
            result = real_subprocess.run(cmd, shell=True)
            return result.returncode

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
        from .config import load_profile

        profile = load_profile()
        self.subprocess_auto_approve.update(profile.get("auto_approve", []))
        self.subprocess_always_deny.update(profile.get("always_deny", []))

    def save_pending(self):
        """Write pending commands to queue file."""
        write_pending(self.subprocess_pending)

    def finalize_session(self):
        """
        Create a Session from queued commands after script completes.

        Call this at the end of a dry-run execution to bundle all
        queued commands into a reviewable session.

        Returns the created Session, or None if no commands were queued.
        """
        if not self.subprocess_pending:
            return None

        from .session import create_session

        session = create_session(
            script_path=self.subprocess_script_path or "<unknown>",
            commands=list(self.subprocess_pending),
            script_content=self.subprocess_script_content,
            name=self.subprocess_script_name,
            analysis=self.subprocess_analysis or "",
            sandbox_args=self.subprocess_sandbox_args,
        )

        self.subprocess_pending.clear()
        return session

    def load_session_commands(self, session):
        """
        Load a session's commands as pre-approved.

        Use this when re-executing an approved session.
        """
        for cmd in session.commands:
            self.subprocess_approved.add(cmd)
