"""
DEPRECATED: Command-level queue persistence.

This module is deprecated. Use session.py for new code.

The session module provides script-level session management which
groups commands from a single script execution into reviewable sessions.
"""
from __future__ import annotations

import warnings

warnings.warn(
    "sandboxlib.queue is deprecated, use sandboxlib.session instead",
    DeprecationWarning,
    stacklevel=2,
)

import json
from pathlib import Path

DEFAULT_QUEUE = Path("/tmp/shannot-pending.json")
DEFAULT_SESSION_APPROVALS = Path("/tmp/shannot-approved.json")
DEFAULT_PERSISTENT_ALLOWLIST = Path.home() / ".config/shannot/approved.json"


def read_pending(path: Path = DEFAULT_QUEUE) -> list[str]:
    if path.exists():
        return json.loads(path.read_text())
    return []


def write_pending(commands: list[str], path: Path = DEFAULT_QUEUE):
    path.write_text(json.dumps(commands, indent=2))


def read_approvals(path: Path = DEFAULT_SESSION_APPROVALS) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def write_approvals(commands: list[str], path: Path = DEFAULT_SESSION_APPROVALS):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(commands), indent=2))


def append_persistent(commands: list[str], path: Path = DEFAULT_PERSISTENT_ALLOWLIST):
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        existing = set(json.loads(path.read_text()))
    merged = sorted(existing | set(commands))
    path.write_text(json.dumps(merged, indent=2))


def read_persistent(path: Path = DEFAULT_PERSISTENT_ALLOWLIST) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def clear_session(queue: Path = DEFAULT_QUEUE, approvals: Path = DEFAULT_SESSION_APPROVALS):
    for f in (queue, approvals):
        if f.exists():
            f.unlink()
