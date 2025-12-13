"""Session management for script-level command approval."""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

SessionStatus = Literal["pending", "approved", "rejected", "executed", "failed"]

SESSIONS_DIR = Path.home() / ".local/share/shannot/sessions"


@dataclass
class Session:
    """Represents a sandboxed script execution session."""

    id: str  # "20240115-fix-nginx-a3f2"
    name: str  # Human-readable name
    script_path: str  # Original script path
    commands: list[str] = field(default_factory=list)  # Queued commands
    analysis: str = ""  # Description of what script does
    status: SessionStatus = "pending"
    created_at: str = ""  # ISO timestamp
    executed_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    stdout: str | None = None  # Captured stdout from execution
    stderr: str | None = None  # Captured stderr from execution
    sandbox_args: dict = field(default_factory=dict)  # Structured args for re-execution

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def session_dir(self) -> Path:
        """Directory storing this session's data."""
        return SESSIONS_DIR / self.id

    def save(self) -> None:
        """Persist session to disk."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self.session_dir / "session.json"
        metadata_path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, session_id: str) -> Session:
        """Load session from disk."""
        session_dir = SESSIONS_DIR / session_id
        metadata_path = session_dir / "session.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        data = json.loads(metadata_path.read_text())
        return cls(**data)

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
        from sandboxlib.stubs import get_stubs

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
                        sessions.append(Session.load(session_dir.name))
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
        # Sort by creation date, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[:limit]


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
) -> Session:
    """Create a new session from a dry-run execution."""
    if name is None:
        name = Path(script_path).stem

    session = Session(
        id=generate_session_id(name),
        name=name,
        script_path=script_path,
        commands=commands,
        analysis=analysis,
        sandbox_args=sandbox_args or {},
    )
    session.save()
    session.save_stubs()

    if script_content:
        session.save_script(script_content)

    return session


def execute_session(session: Session) -> int:
    """
    Execute an approved session by re-running through the sandbox.

    This function delegates to run_session module to reconstruct
    the sandbox invocation with pre-approved commands.

    Returns the exit code.
    """
    import subprocess
    import sys

    if session.status not in ("approved", "pending"):
        raise ValueError(f"Cannot execute session with status: {session.status}")

    session.executed_at = datetime.now().isoformat()

    try:
        # Delegate to run_session module
        result = subprocess.run(
            [sys.executable, "-m", "sandboxlib.run_session", session.id],
            capture_output=True,
            text=True,
        )
        # run_session updates session status, but we capture output here too
        # in case run_session fails to do so
        session = Session.load(session.id)  # Reload to get updates from run_session
        return session.exit_code or result.returncode
    except Exception as e:
        session.status = "failed"
        session.error = str(e)
        session.exit_code = 1
        session.save()
        return 1
