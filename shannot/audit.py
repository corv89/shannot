"""Audit logging for shannot operations.

Append-only JSONL logging of security-relevant events including:
- Session lifecycle (created, loaded, status changes)
- Command permission decisions (allow, deny, queue)
- File write queueing and execution
- Approval/rejection decisions
- Session execution events
- Remote execution events

Configuration via [audit] section in config.toml.
Logs written to ~/.local/share/shannot/audit/*.jsonl.

Events include sequence numbers for tamper detection - gaps indicate deleted entries.
File locking prevents interleaved writes from concurrent processes.
"""

from __future__ import annotations

import fcntl
import getpass
import json
import os
import socket
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .session import Session

from .config import AuditConfig, load_audit_config

# Constants
AUDIT_LOG_DIR = load_audit_config().effective_log_dir

EventType = Literal[
    "session_created",
    "session_loaded",
    "session_status_changed",
    "session_expired",
    "command_decision",
    "file_write_queued",
    "file_write_executed",
    "file_deletion_queued",
    "file_deletion_executed",
    "approval_decision",
    "execution_started",
    "execution_completed",
    "command_executed",
    "remote_connection",
    "remote_deployment",
]


@dataclass
class AuditEvent:
    """Single audit log entry."""

    seq: int
    timestamp: str
    event_type: str
    session_id: str | None
    host: str
    target: str | None
    user: str
    pid: int
    payload: dict[str, Any]

    def to_json(self) -> str:
        """Serialize to compact JSON line (no trailing newline)."""
        return json.dumps(asdict(self), separators=(",", ":"))


class AuditLogger:
    """Append-only JSONL audit logger with rotation and file locking."""

    _instance: AuditLogger | None = None

    def __init__(self, config: AuditConfig | None = None):
        self.config = config or load_audit_config()
        self._hostname = socket.gethostname()
        self._user = getpass.getuser()
        self._pid = os.getpid()

    @classmethod
    def get_instance(cls, config: AuditConfig | None = None) -> AuditLogger:
        """Get or create singleton logger instance."""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def _get_log_path(self, session_id: str | None = None) -> Path:
        """Determine log file path based on rotation strategy."""
        log_dir = self.config.effective_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        if self.config.rotation == "daily":
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            return log_dir / f"audit-{date_str}.jsonl"
        elif self.config.rotation == "session" and session_id:
            return log_dir / f"audit-{session_id}.jsonl"
        else:  # "none"
            return log_dir / "audit.jsonl"

    def _get_next_seq(self, path: Path) -> int:
        """Get next sequence number by reading last line of file."""
        if not path.exists():
            return 1

        try:
            # Read last line efficiently
            with open(path, "rb") as f:
                # Seek to end
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return 1

                # Read last chunk to find last line
                chunk_size = min(4096, size)
                f.seek(-chunk_size, 2)
                chunk = f.read()

                # Find last complete line
                lines = chunk.split(b"\n")
                for line in reversed(lines):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            return data.get("seq", 0) + 1
                        except json.JSONDecodeError:
                            continue
            return 1
        except OSError:
            return 1

    def _cleanup_old_logs(self) -> None:
        """Remove old log files beyond max_files limit."""
        if self.config.max_files <= 0:
            return

        log_dir = self.config.effective_log_dir
        if not log_dir.exists():
            return

        log_files = sorted(log_dir.glob("audit-*.jsonl"), reverse=True)
        for old_file in log_files[self.config.max_files :]:
            try:
                old_file.unlink()
            except OSError:
                pass  # Best effort cleanup

    def log(
        self,
        event_type: EventType,
        session_id: str | None,
        payload: dict[str, Any],
        target: str | None = None,
    ) -> None:
        """Write an audit event to the log with file locking."""
        if not self.config.enabled:
            return

        if not self.config.is_event_enabled(event_type):
            return

        try:
            path = self._get_log_path(session_id)
            path.parent.mkdir(parents=True, exist_ok=True)

            # Use file locking for concurrent write safety
            with open(path, "a", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    # Get sequence number while holding lock
                    seq = self._get_next_seq(path)

                    event = AuditEvent(
                        seq=seq,
                        timestamp=datetime.now(UTC).isoformat(),
                        event_type=event_type,
                        session_id=session_id,
                        host=self._hostname,
                        target=target,
                        user=self._user,
                        pid=self._pid,
                        payload=payload,
                    )

                    f.write(event.to_json() + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            self._cleanup_old_logs()
        except OSError:
            pass  # Silent failure - audit should never break main flow
        except Exception:
            pass  # Catch-all: never break main execution


def get_logger() -> AuditLogger:
    """Get singleton audit logger."""
    return AuditLogger.get_instance()


# ============================================================================
# Convenience functions for specific event types
# ============================================================================


def log_session_created(session: Session) -> None:
    """Log session creation event."""
    get_logger().log(
        "session_created",
        session.id,
        {
            "name": session.name,
            "script_path": session.script_path,
            "commands_count": len(session.commands),
            "writes_count": len(session.pending_writes),
            "deletions_count": len(session.pending_deletions),
        },
        target=session.target,
    )


def log_session_loaded(session: Session) -> None:
    """Log session load event."""
    get_logger().log(
        "session_loaded",
        session.id,
        {
            "status": session.status,
            "commands_count": len(session.commands),
            "writes_count": len(session.pending_writes),
            "deletions_count": len(session.pending_deletions),
        },
        target=session.target,
    )


def log_session_status_changed(session: Session, old_status: str, new_status: str) -> None:
    """Log session status change event."""
    get_logger().log(
        "session_status_changed",
        session.id,
        {
            "old_status": old_status,
            "new_status": new_status,
        },
        target=session.target,
    )


def log_command_decision(
    session_id: str | None,
    command: str,
    decision: Literal["allow", "deny", "queue"],
    reason: str,
    base_command: str,
    target: str | None = None,
) -> None:
    """Log command permission decision."""
    get_logger().log(
        "command_decision",
        session_id,
        {
            "command": command,
            "decision": decision,
            "reason": reason,
            "base_command": base_command,
        },
        target=target,
    )


def log_file_write_queued(
    session_id: str | None,
    path: str,
    size_bytes: int,
    is_new_file: bool,
    remote: bool,
    target: str | None = None,
) -> None:
    """Log file write queueing event."""
    get_logger().log(
        "file_write_queued",
        session_id,
        {
            "path": path,
            "size_bytes": size_bytes,
            "is_new_file": is_new_file,
            "remote": remote,
        },
        target=target,
    )


def log_file_deletion_queued(
    session_id: str | None,
    path: str,
    target_type: str,
    size_bytes: int,
    remote: bool,
    target: str | None = None,
) -> None:
    """Log file/directory deletion queueing event."""
    get_logger().log(
        "file_deletion_queued",
        session_id,
        {
            "path": path,
            "target_type": target_type,
            "size_bytes": size_bytes,
            "remote": remote,
        },
        target=target,
    )


def log_approval_decision(
    sessions: list[Session],
    action: Literal["approved", "rejected"],
    source: Literal["tui", "cli", "mcp"],
) -> None:
    """Log approval/rejection decision."""
    get_logger().log(
        "approval_decision",
        None,  # Multiple sessions
        {
            "action": action,
            "sessions": [s.id for s in sessions],
            "session_count": len(sessions),
            "source": source,
        },
    )


def log_execution_started(session: Session) -> None:
    """Log session execution start."""
    get_logger().log(
        "execution_started",
        session.id,
        {
            "commands_to_execute": len(session.commands),
            "writes_to_execute": len(session.pending_writes),
            "deletions_to_execute": len(session.pending_deletions),
        },
        target=session.target,
    )


def log_execution_completed(
    session: Session,
    duration_seconds: float,
    error: str | None = None,
) -> None:
    """Log session execution completion."""
    get_logger().log(
        "execution_completed",
        session.id,
        {
            "status": session.status,
            "exit_code": session.exit_code,
            "duration_seconds": round(duration_seconds, 3),
            "error": error,
        },
        target=session.target,
    )


def log_remote_connection(
    session_id: str | None,
    action: Literal["connected", "disconnected", "failed"],
    target: str,
    port: int,
    error: str | None = None,
) -> None:
    """Log remote connection event."""
    get_logger().log(
        "remote_connection",
        session_id,
        {
            "action": action,
            "port": port,
            "error": error,
        },
        target=target,
    )


def log_remote_deployment(
    session_id: str | None,
    action: Literal["deployed", "verified", "failed"],
    target: str,
    deploy_dir: str | None = None,
    error: str | None = None,
) -> None:
    """Log remote deployment event."""
    get_logger().log(
        "remote_deployment",
        session_id,
        {
            "action": action,
            "deploy_dir": deploy_dir,
            "error": error,
        },
        target=target,
    )


# ============================================================================
# Status helpers
# ============================================================================


def get_today_event_count() -> int:
    """Count events in today's log file."""
    config = load_audit_config()
    log_dir = config.effective_log_dir
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = log_dir / f"audit-{today}.jsonl"
    if not log_file.exists():
        return 0
    try:
        return sum(1 for _ in log_file.open())
    except OSError:
        return 0
