"""Audit logging for shannot operations.

Append-only JSONL logging of security-relevant events including:
- Session lifecycle (created, loaded, status changes)
- Command permission decisions (allow, deny, queue)
- File write queueing and execution
- Approval/rejection decisions
- Session execution events
- Remote execution events

Configuration via ~/.config/shannot/audit.json or .shannot/audit.json.
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
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .session import Session

from .config import AUDIT_DIR, CONFIG_DIR, find_project_root

# Constants
AUDIT_CONFIG_FILENAME = "audit.json"
AUDIT_LOG_DIR = AUDIT_DIR

EventType = Literal[
    "session_created",
    "session_loaded",
    "session_status_changed",
    "session_expired",
    "command_decision",
    "file_write_queued",
    "file_write_executed",
    "approval_decision",
    "execution_started",
    "execution_completed",
    "command_executed",
    "remote_connection",
    "remote_deployment",
]

# Map event types to categories for filtering
EVENT_CATEGORY_MAP: dict[str, str] = {
    "session_created": "session_lifecycle",
    "session_loaded": "session_lifecycle",
    "session_status_changed": "session_lifecycle",
    "session_expired": "session_lifecycle",
    "command_decision": "command_decisions",
    "file_write_queued": "file_writes",
    "file_write_executed": "file_writes",
    "approval_decision": "approval_decisions",
    "execution_started": "execution_events",
    "execution_completed": "execution_events",
    "command_executed": "execution_events",
    "remote_connection": "remote_events",
    "remote_deployment": "remote_events",
}

DEFAULT_AUDIT_CONFIG: dict[str, Any] = {
    "enabled": True,  # Opt-out for better security posture
    "log_dir": None,  # Uses AUDIT_LOG_DIR
    "rotation": "daily",
    "max_files": 30,
    "events": {
        "session_lifecycle": True,
        "command_decisions": True,
        "file_writes": True,
        "approval_decisions": True,
        "execution_events": True,
        "remote_events": True,
    },
}


@dataclass
class AuditConfig:
    """Audit logging configuration."""

    enabled: bool = True
    log_dir: Path | None = None
    rotation: Literal["daily", "session", "none"] = "daily"
    max_files: int = 30
    events: dict[str, bool] = field(
        default_factory=lambda: {
            "session_lifecycle": True,
            "command_decisions": True,
            "file_writes": True,
            "approval_decisions": True,
            "execution_events": True,
            "remote_events": True,
        }
    )

    @property
    def effective_log_dir(self) -> Path:
        """Return configured log_dir or default."""
        return self.log_dir or AUDIT_LOG_DIR

    def is_event_enabled(self, event_type: str) -> bool:
        """Check if a specific event type is enabled."""
        category = EVENT_CATEGORY_MAP.get(event_type, "session_lifecycle")
        return self.events.get(category, True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "enabled": self.enabled,
            "log_dir": str(self.log_dir) if self.log_dir else None,
            "rotation": self.rotation,
            "max_files": self.max_files,
            "events": self.events.copy(),
        }


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


def get_audit_config_path() -> Path | None:
    """
    Get audit config path with precedence.

    1. .shannot/audit.json in project root
    2. ~/.config/shannot/audit.json (global)

    Returns path if exists, None otherwise.
    """
    # Check project-local first
    project_dir = find_project_root()
    if project_dir:
        project_config = project_dir / AUDIT_CONFIG_FILENAME
        if project_config.exists():
            return project_config

    # Fall back to global
    global_config = CONFIG_DIR / AUDIT_CONFIG_FILENAME
    if global_config.exists():
        return global_config

    return None


def load_audit_config() -> AuditConfig:
    """Load audit configuration from file or return defaults."""
    config_path = get_audit_config_path()
    if config_path is None:
        return AuditConfig()

    try:
        data = json.loads(config_path.read_text())
        log_dir = data.get("log_dir")
        return AuditConfig(
            enabled=data.get("enabled", True),
            log_dir=Path(log_dir) if log_dir else None,
            rotation=data.get("rotation", "daily"),
            max_files=data.get("max_files", 30),
            events=data.get("events", DEFAULT_AUDIT_CONFIG["events"]),
        )
    except (OSError, json.JSONDecodeError):
        return AuditConfig()


def save_audit_config(config: AuditConfig) -> None:
    """Save audit configuration to global config file."""
    config_path = CONFIG_DIR / AUDIT_CONFIG_FILENAME
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config.to_dict(), indent=2) + "\n")


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
