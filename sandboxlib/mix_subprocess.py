"""Mixin for subprocess execution with tiered security."""

import subprocess as real_subprocess
import sys

from .virtualizedproc import signature


class MixSubprocess:
    """
    Mixin to handle system() calls from the sandbox.

    Security tiers:
        subprocess_allowlist: set - execute immediately
        subprocess_requires_approval: set - queue for human approval
        subprocess_denylist: set - always deny

    Modes:
        subprocess_default_deny: bool - deny unknown commands (default True)
        subprocess_dry_run: bool - log all, execute none
    """

    # Command sets
    subprocess_allowlist = set()  # Always allowed
    subprocess_requires_approval = set()  # Need human approval
    subprocess_denylist = set()  # Always denied

    # Behavior
    subprocess_default_deny = True  # Deny commands not in any list
    subprocess_dry_run = False  # Log but don't execute

    # State
    subprocess_pending = []  # Commands awaiting approval
    subprocess_approved = set()  # Commands approved this session

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
        Returns: 'allow', 'deny', or 'queue'
        """
        base, parts = self._parse_command(cmd)

        # Check denylist first
        if base in self.subprocess_denylist or cmd in self.subprocess_denylist:
            return "deny"

        # Check if previously approved this session
        if cmd in self.subprocess_approved:
            return "allow"

        # Check allowlist
        if base in self.subprocess_allowlist or cmd in self.subprocess_allowlist:
            return "allow"

        # Check if requires approval
        if (
            base in self.subprocess_requires_approval
            or cmd in self.subprocess_requires_approval
        ):
            return "queue"

        # Default behavior for unknown commands
        if self.subprocess_default_deny:
            return "deny"
        else:
            return "queue"

    @signature("system(p)i")
    def s_system(self, p_command):
        cmd = self.sandio.read_charp(p_command, 4096).decode("utf-8")

        # Dry-run mode: log everything, execute nothing
        if self.subprocess_dry_run:
            self.subprocess_pending.append(cmd)
            sys.stderr.write(f"[DRY-RUN] {cmd}\n")
            return 0

        permission = self._check_permission(cmd)

        if permission == "deny":
            sys.stderr.write(f"[DENIED] {cmd}\n")
            return 127  # Command not found

        elif permission == "queue":
            self.subprocess_pending.append(cmd)
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
