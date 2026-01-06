"""Session management for script-level command approval."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from .config import SESSIONS_DIR

SessionStatus = Literal[
    "pending", "approved", "rejected", "executed", "failed", "cancelled", "expired"
]

# Session TTL - pending sessions expire after this duration
SESSION_TTL = timedelta(hours=1)


@dataclass
class Session:
    """Represents a sandboxed script execution session."""

    id: str  # "20240115-fix-nginx-a3f2"
    name: str  # Human-readable name
    script_path: str  # Original script path
    commands: list[str] = field(default_factory=list)  # Queued commands
    pending_writes: list[dict] = field(default_factory=list)  # Queued file writes
    pending_deletions: list[dict] = field(default_factory=list)  # Queued file/dir deletions
    analysis: str = ""  # Description of what script does
    status: SessionStatus = "pending"
    created_at: str = ""  # ISO timestamp
    expires_at: str = ""  # ISO timestamp - when pending session expires
    executed_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    stdout: str | None = None  # Captured stdout from execution
    stderr: str | None = None  # Captured stderr from execution
    sandbox_args: dict = field(default_factory=dict)  # Structured args for re-execution

    # Execution tracking (populated after execution completes)
    executed_commands: list[dict] = field(default_factory=list)  # {cmd, exit_code}
    completed_writes: list[dict] = field(default_factory=list)  # {path, success, size/error}
    completed_deletions: list[dict] = field(default_factory=list)  # {path, success, target_type}

    # Remote execution fields
    target: str | None = None  # SSH target (user@host) if remote
    remote_session_id: str | None = None  # Session ID on remote

    def is_remote(self) -> bool:
        """Check if this is a remote session."""
        return self.target is not None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.expires_at:
            # Set expiry time for new sessions
            expiry = datetime.now() + SESSION_TTL
            self.expires_at = expiry.isoformat()

    def is_expired(self) -> bool:
        """Check if session has expired.

        Returns
        -------
        bool
            True if current time is past expires_at timestamp.
        """
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now() > expiry
        except (ValueError, TypeError):
            return False

    def commit_writes(self) -> list[dict]:
        """
        Commit pending writes to real filesystem.

        Returns list of results: {path, success, size} or {path, success, error}
        """
        import base64
        import hashlib

        results = []
        for write_data in self.pending_writes:
            path = write_data.get("path", "")
            content_b64 = write_data.get("content_b64", "")
            original_hash = write_data.get("original_hash")

            try:
                content = base64.b64decode(content_b64)
                target_path = Path(path)

                # Conflict detection: verify file hasn't changed since dry-run
                if original_hash is not None and target_path.exists():
                    current_content = target_path.read_bytes()
                    current_hash = hashlib.sha256(current_content).hexdigest()
                    if current_hash != original_hash:
                        results.append(
                            {
                                "path": path,
                                "success": False,
                                "error": "conflict: file modified since dry-run",
                            }
                        )
                        continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(content)
                results.append(
                    {
                        "path": path,
                        "success": True,
                        "size": len(content),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "path": path,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def commit_deletions(self) -> list[dict]:
        """
        Commit pending deletions to real filesystem.

        Deletions are processed in order (files before parent directories,
        as captured by rmtree). Already-deleted items are skipped.

        Returns list of results: {path, success, target_type} or {path, success, error}
        """
        results = []
        for del_data in self.pending_deletions:
            path = del_data.get("path", "")
            target_type = del_data.get("target_type", "file")

            try:
                target_path = Path(path)

                if not target_path.exists():
                    # Already deleted (e.g., parent rmtree already removed it)
                    results.append(
                        {
                            "path": path,
                            "success": True,
                            "target_type": target_type,
                            "skipped": True,
                        }
                    )
                    continue

                if target_type == "directory":
                    target_path.rmdir()
                else:
                    target_path.unlink()

                results.append(
                    {
                        "path": path,
                        "success": True,
                        "target_type": target_type,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "path": path,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def commit_deletions_remote(self, ssh: object) -> list[dict]:
        """
        Commit pending deletions to remote filesystem via SSH.

        Parameters
        ----------
        ssh
            An SSHConnection instance with run() method.

        Returns
        -------
        list[dict]
            List of results: {path, success, target_type} or {path, success, error}
        """
        import shlex

        results = []
        for del_data in self.pending_deletions:
            path = del_data.get("path", "")
            target_type = del_data.get("target_type", "file")

            try:
                if target_type == "directory":
                    result = ssh.run(f"rmdir {shlex.quote(path)} 2>/dev/null || true")  # type: ignore[union-attr]
                else:
                    result = ssh.run(f"rm -f {shlex.quote(path)}")  # type: ignore[union-attr]

                if result.returncode == 0:
                    results.append(
                        {
                            "path": path,
                            "success": True,
                            "target_type": target_type,
                        }
                    )
                else:
                    stderr = result.stderr.decode("utf-8", errors="replace").strip()
                    results.append(
                        {
                            "path": path,
                            "success": False,
                            "error": stderr or "deletion failed",
                        }
                    )
            except Exception as e:
                results.append(
                    {
                        "path": path,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def commit_writes_remote(self, ssh: object) -> list[dict]:
        """
        Commit pending writes to remote filesystem via SSH.

        Parameters
        ----------
        ssh
            An SSHConnection instance with run() and write_file() methods.

        Returns
        -------
        list[dict]
            List of results: {path, success, size} or {path, success, error}
        """
        import base64
        import shlex

        results = []
        for write_data in self.pending_writes:
            path = write_data.get("path", "")
            content_b64 = write_data.get("content_b64", "")
            original_hash = write_data.get("original_hash")

            try:
                content = base64.b64decode(content_b64)

                # Conflict detection via SSH hash check
                if original_hash is not None:
                    result = ssh.run(  # type: ignore[union-attr]
                        f"sha256sum {shlex.quote(path)} 2>/dev/null || echo NOTFOUND"
                    )
                    stdout_str = result.stdout.decode("utf-8", errors="replace")
                    if "NOTFOUND" not in stdout_str:
                        current_hash = stdout_str.split()[0]
                        if current_hash != original_hash:
                            results.append(
                                {
                                    "path": path,
                                    "success": False,
                                    "error": "conflict: file modified since dry-run",
                                }
                            )
                            continue

                # Create parent directories
                parent = str(Path(path).parent)
                if parent != "/":
                    ssh.run(f"mkdir -p {shlex.quote(parent)}")  # type: ignore[union-attr]

                # Write via SSH
                ssh.write_file(path, content)  # type: ignore[union-attr]
                results.append(
                    {
                        "path": path,
                        "success": True,
                        "size": len(content),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "path": path,
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    @property
    def session_dir(self) -> Path:
        """Directory storing this session's data."""
        return SESSIONS_DIR / self.id

    def save(self) -> None:
        """Persist session to disk."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self.session_dir / "session.json"

        # Detect status change for audit logging
        old_status = None
        if metadata_path.exists():
            try:
                old_data = json.loads(metadata_path.read_text())
                old_status = old_data.get("status")
            except (OSError, json.JSONDecodeError):
                pass  # Ignore if file doesn't exist or is corrupt

        metadata_path.write_text(json.dumps(asdict(self), indent=2))

        # Log status change if detected
        if old_status and old_status != self.status:
            from .audit import log_session_status_changed

            log_session_status_changed(self, old_status, self.status)

    @classmethod
    def load(cls, session_id: str, *, audit: bool = True) -> Session:
        """Load session from disk.

        Parameters
        ----------
        session_id
            The session ID to load
        audit
            Whether to log this load to audit log. Set False for
            read-only queries like status display.
        """
        session_dir = SESSIONS_DIR / session_id
        metadata_path = session_dir / "session.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        data = json.loads(metadata_path.read_text())
        session = cls(**data)

        if audit:
            from .audit import log_session_loaded

            log_session_loaded(session)

        return session

    def save_script(self, content: str) -> None:
        """Save the script content to session directory."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.session_dir / "script.py"
        script_path.write_text(content)

    def load_script(self) -> str | None:
        """Load script content from session directory."""
        script_path = self.session_dir / "script.py"
        if script_path.exists():
            return script_path.read_text()
        return None

    def save_stubs(self) -> None:
        """Copy stubs to session directory for reproducibility."""
        from shannot.stubs import get_stubs

        stubs_dir = self.session_dir / "lib_pypy"
        stubs_dir.mkdir(parents=True, exist_ok=True)
        for name, content in get_stubs().items():
            (stubs_dir / name).write_bytes(content)

    def delete(self) -> None:
        """Remove session from disk."""
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)

    @staticmethod
    def list_pending() -> list[Session]:
        """List all pending sessions."""
        return [s for s in Session.list_all() if s.status == "pending"]

    @staticmethod
    def list_all(limit: int = 50) -> list[Session]:
        """List all sessions, newest first."""
        sessions = []
        if SESSIONS_DIR.exists():
            for session_dir in SESSIONS_DIR.iterdir():
                if session_dir.is_dir():
                    try:
                        sessions.append(Session.load(session_dir.name, audit=False))
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
        # Sort by creation date, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[:limit]

    @classmethod
    def cleanup_expired(cls) -> int:
        """Mark expired pending sessions as expired.

        Returns
        -------
        int
            Number of sessions marked as expired.
        """
        count = 0
        for session in cls.list_pending():
            if session.is_expired():
                session.status = "expired"
                session.save()
                count += 1
        return count


def generate_session_id(name: str = "") -> str:
    """Generate a unique session ID like '20240115-fix-nginx-a3f2'."""
    date_part = datetime.now().strftime("%Y%m%d")
    slug = name.lower().replace(" ", "-")[:20] if name else "session"
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-") or "session"
    uuid_part = uuid.uuid4().hex[:4]
    return f"{date_part}-{slug}-{uuid_part}"


def create_session(
    script_path: str,
    commands: list[str],
    script_content: str | None = None,
    name: str | None = None,
    analysis: str = "",
    sandbox_args: dict | None = None,
    pending_writes: list[dict] | None = None,
    pending_deletions: list[dict] | None = None,
) -> Session:
    """Create a new session from a dry-run execution."""
    if name is None:
        name = Path(script_path).stem

    session = Session(
        id=generate_session_id(name),
        name=name,
        script_path=script_path,
        commands=commands,
        pending_writes=pending_writes or [],
        pending_deletions=pending_deletions or [],
        analysis=analysis,
        sandbox_args=sandbox_args or {},
    )
    session.save()
    session.save_stubs()

    if script_content:
        session.save_script(script_content)

    # Audit log session creation
    from .audit import log_session_created

    log_session_created(session)

    return session


def execute_session(session: Session) -> int:
    """
    Execute an approved session by re-running through the sandbox.

    This function delegates to run_session module for local sessions,
    or to remote module for remote sessions.

    Returns the exit code.
    """
    if session.status not in ("approved", "pending"):
        raise ValueError(f"Cannot execute session with status: {session.status}")

    session.executed_at = datetime.now().isoformat()

    # Handle remote sessions
    if session.is_remote():
        from .remote import execute_remote_session

        return execute_remote_session(session)

    # Local execution - call run_session directly (subprocess doesn't work with Nuitka)
    try:
        from .run_session import execute_session_direct

        exit_code = execute_session_direct(session)
        return exit_code
    except Exception as e:
        session.status = "failed"
        session.error = str(e)
        session.exit_code = 1
        session.save()
        return 1
