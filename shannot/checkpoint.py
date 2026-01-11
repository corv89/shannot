"""Checkpoint and rollback functionality for session execution."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session

# Limits for directory deletion checkpointing
CHECKPOINT_MAX_FILES = 100
CHECKPOINT_MAX_SIZE = 50 * 1024 * 1024  # 50MB


def _hash_content(content: bytes) -> str:
    """Return SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def _blob_name(content_hash: str) -> str:
    """Return blob filename from content hash."""
    return f"{content_hash[:8]}.blob"


def create_checkpoint(session: Session) -> dict:
    """
    Create checkpoint from session's pending writes and deletions.

    Captures original file content before execution so files can be
    restored via rollback. Content is stored as blob files in the
    session's checkpoint directory.

    Parameters
    ----------
    session
        Session with pending_writes and pending_deletions to checkpoint.

    Returns
    -------
    dict
        Checkpoint data: {path: {blob, size, original_hash, was_created}}
    """
    checkpoint_dir = session.checkpoint_dir
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    checkpoint: dict[str, dict] = {}

    # Checkpoint original content from pending writes
    for write_data in session.pending_writes:
        path = write_data.get("path", "")
        original_b64 = write_data.get("original_b64")
        original_hash = write_data.get("original_hash")

        if original_b64:
            # File existed - checkpoint original content
            original = base64.b64decode(original_b64)
            blob_name = _blob_name(original_hash or _hash_content(original))
            blob_path = checkpoint_dir / blob_name
            blob_path.write_bytes(original)

            checkpoint[path] = {
                "blob": blob_name,
                "size": len(original),
                "original_hash": original_hash,
                "was_created": False,
            }
        else:
            # New file - mark as created (will be deleted on rollback)
            checkpoint[path] = {
                "blob": None,
                "size": 0,
                "original_hash": None,
                "was_created": True,
            }

    # Checkpoint files being deleted by reading from real filesystem
    for del_data in session.pending_deletions:
        path = del_data.get("path", "")
        target_type = del_data.get("target_type", "file")

        if target_type == "directory":
            # Checkpoint directory contents with limits
            _checkpoint_directory(path, checkpoint_dir, checkpoint)
        else:
            # Checkpoint single file
            _checkpoint_file(path, checkpoint_dir, checkpoint)

    session.checkpoint = checkpoint
    session.checkpoint_created_at = datetime.now().isoformat()

    return checkpoint


def _checkpoint_file(path: str, checkpoint_dir: Path, checkpoint: dict) -> bool:
    """
    Checkpoint a single file.

    Returns True if file was checkpointed, False if skipped.
    """
    real_path = Path(path)
    if not real_path.exists() or not real_path.is_file():
        return False

    try:
        content = real_path.read_bytes()
        content_hash = _hash_content(content)
        blob_name = _blob_name(content_hash)
        blob_path = checkpoint_dir / blob_name

        # Don't re-write blob if already exists (same content)
        if not blob_path.exists():
            blob_path.write_bytes(content)

        checkpoint[path] = {
            "blob": blob_name,
            "size": len(content),
            "original_hash": content_hash,
            "was_deleted": True,
        }
        return True
    except (OSError, PermissionError):
        return False


def _checkpoint_directory(path: str, checkpoint_dir: Path, checkpoint: dict) -> dict:
    """
    Checkpoint a directory's contents with limits.

    Returns dict with 'partial' and 'warning' if limits exceeded.
    """
    real_path = Path(path)
    if not real_path.exists() or not real_path.is_dir():
        return {}

    files = []
    total_size = 0

    try:
        for f in real_path.rglob("*"):
            if f.is_file():
                try:
                    size = f.stat().st_size
                    files.append((f, size))
                    total_size += size
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        return {"partial": True, "warning": f"Cannot read directory: {path}"}

    # Check limits
    if len(files) > CHECKPOINT_MAX_FILES or total_size > CHECKPOINT_MAX_SIZE:
        # Mark directory as partial checkpoint only
        checkpoint[path] = {
            "blob": None,
            "size": 0,
            "original_hash": None,
            "was_deleted": True,
            "partial": True,
            "file_count": len(files),
            "total_size": total_size,
        }
        return {
            "partial": True,
            "warning": f"Directory {path} too large ({len(files)} files, {total_size} bytes)",
        }

    # Checkpoint all files
    for f, _size in files:
        _checkpoint_file(str(f), checkpoint_dir, checkpoint)

    # Mark directory itself
    checkpoint[path] = {
        "blob": None,
        "size": 0,
        "original_hash": None,
        "was_deleted": True,
        "is_directory": True,
    }

    return {}


def update_post_exec_hashes(session: Session) -> None:
    """
    Record post-execution hashes for conflict detection during rollback.

    Called after commit_writes() to capture the new file state.
    """
    if not session.checkpoint:
        return

    for path, entry in session.checkpoint.items():
        if entry.get("was_created") or not entry.get("was_deleted"):
            # For created/modified files, hash the new content
            real_path = Path(path)
            if real_path.exists() and real_path.is_file():
                try:
                    content = real_path.read_bytes()
                    entry["post_exec_hash"] = _hash_content(content)
                except (OSError, PermissionError):
                    # Skip unreadable files - conflict detection is best-effort
                    pass


def rollback_local(session: Session, *, force: bool = False) -> list[dict]:
    """
    Rollback session changes on local filesystem.

    Parameters
    ----------
    session
        Executed session to rollback.
    force
        If True, skip conflict detection and restore anyway.

    Returns
    -------
    list[dict]
        Results: [{path, action, success, error?}]
    """
    if not session.checkpoint:
        return [{"path": "", "action": "rollback", "success": False, "error": "No checkpoint"}]

    results = []
    conflicts = []

    # First pass: detect conflicts
    if not force:
        for path, entry in session.checkpoint.items():
            post_exec_hash = entry.get("post_exec_hash")
            if post_exec_hash:
                real_path = Path(path)
                if real_path.exists() and real_path.is_file():
                    try:
                        current_hash = _hash_content(real_path.read_bytes())
                        if current_hash != post_exec_hash:
                            conflicts.append(path)
                    except (OSError, PermissionError):
                        # Skip unreadable files - don't block rollback on read errors
                        pass

    if conflicts:
        return [
            {
                "path": p,
                "action": "conflict",
                "success": False,
                "error": "File modified since execution",
            }
            for p in conflicts
        ]

    checkpoint_dir = session.checkpoint_dir

    # Restore files
    for path, entry in session.checkpoint.items():
        blob_name = entry.get("blob")
        was_created = entry.get("was_created", False)
        was_deleted = entry.get("was_deleted", False)
        is_directory = entry.get("is_directory", False)
        partial = entry.get("partial", False)

        try:
            real_path = Path(path)

            if was_created:
                # File was created by session - delete it
                if real_path.exists():
                    real_path.unlink()
                results.append({"path": path, "action": "deleted", "success": True})

            elif was_deleted:
                if partial:
                    # Partial checkpoint - skip with warning
                    results.append(
                        {
                            "path": path,
                            "action": "skipped",
                            "success": False,
                            "error": "Partial checkpoint - directory too large",
                        }
                    )
                elif is_directory:
                    # Recreate directory (files inside restored separately)
                    real_path.mkdir(parents=True, exist_ok=True)
                    results.append({"path": path, "action": "recreated_dir", "success": True})
                elif blob_name:
                    # Recreate deleted file from blob
                    blob_path = checkpoint_dir / blob_name
                    if blob_path.exists():
                        real_path.parent.mkdir(parents=True, exist_ok=True)
                        real_path.write_bytes(blob_path.read_bytes())
                        results.append({"path": path, "action": "recreated", "success": True})
                    else:
                        results.append(
                            {
                                "path": path,
                                "action": "recreate",
                                "success": False,
                                "error": "Blob not found",
                            }
                        )

            elif blob_name:
                # File was modified - restore original content
                blob_path = checkpoint_dir / blob_name
                if blob_path.exists():
                    real_path.parent.mkdir(parents=True, exist_ok=True)
                    real_path.write_bytes(blob_path.read_bytes())
                    results.append({"path": path, "action": "restored", "success": True})
                else:
                    results.append(
                        {
                            "path": path,
                            "action": "restore",
                            "success": False,
                            "error": "Blob not found",
                        }
                    )

        except Exception as e:
            results.append({"path": path, "action": "rollback", "success": False, "error": str(e)})

    return results


def rollback_remote(session: Session, ssh: object, *, force: bool = False) -> list[dict]:
    """
    Rollback session changes on remote filesystem via SSH.

    Parameters
    ----------
    session
        Executed session to rollback.
    ssh
        SSHConnection instance.
    force
        If True, skip conflict detection.

    Returns
    -------
    list[dict]
        Results: [{path, action, success, error?}]
    """
    import shlex

    if not session.checkpoint:
        return [{"path": "", "action": "rollback", "success": False, "error": "No checkpoint"}]

    results = []
    conflicts = []

    # First pass: detect conflicts via SSH
    if not force:
        for path, entry in session.checkpoint.items():
            post_exec_hash = entry.get("post_exec_hash")
            if post_exec_hash:
                try:
                    result = ssh.run(  # type: ignore[union-attr]
                        f"sha256sum {shlex.quote(path)} 2>/dev/null || echo NOTFOUND"
                    )
                    stdout_str = result.stdout.decode("utf-8", errors="replace")
                    if "NOTFOUND" not in stdout_str:
                        current_hash = stdout_str.split()[0]
                        if current_hash != post_exec_hash:
                            conflicts.append(path)
                except Exception:
                    # Skip on SSH/network errors - don't block rollback on transient failures
                    pass

    if conflicts:
        return [
            {
                "path": p,
                "action": "conflict",
                "success": False,
                "error": "File modified since execution",
            }
            for p in conflicts
        ]

    checkpoint_dir = session.checkpoint_dir

    # Restore files via SSH
    for path, entry in session.checkpoint.items():
        blob_name = entry.get("blob")
        was_created = entry.get("was_created", False)
        was_deleted = entry.get("was_deleted", False)
        is_directory = entry.get("is_directory", False)
        partial = entry.get("partial", False)

        try:
            if was_created:
                # File was created - delete it via SSH
                ssh.run(f"rm -f {shlex.quote(path)}")  # type: ignore[union-attr]
                results.append({"path": path, "action": "deleted", "success": True})

            elif was_deleted:
                if partial:
                    results.append(
                        {
                            "path": path,
                            "action": "skipped",
                            "success": False,
                            "error": "Partial checkpoint - directory too large",
                        }
                    )
                elif is_directory:
                    ssh.run(f"mkdir -p {shlex.quote(path)}")  # type: ignore[union-attr]
                    results.append({"path": path, "action": "recreated_dir", "success": True})
                elif blob_name:
                    blob_path = checkpoint_dir / blob_name
                    if blob_path.exists():
                        content = blob_path.read_bytes()
                        parent = str(Path(path).parent)
                        if parent != "/":
                            ssh.run(f"mkdir -p {shlex.quote(parent)}")  # type: ignore[union-attr]
                        ssh.write_file(path, content)  # type: ignore[union-attr]
                        results.append({"path": path, "action": "recreated", "success": True})
                    else:
                        results.append(
                            {
                                "path": path,
                                "action": "recreate",
                                "success": False,
                                "error": "Blob not found",
                            }
                        )

            elif blob_name:
                blob_path = checkpoint_dir / blob_name
                if blob_path.exists():
                    content = blob_path.read_bytes()
                    parent = str(Path(path).parent)
                    if parent != "/":
                        ssh.run(f"mkdir -p {shlex.quote(parent)}")  # type: ignore[union-attr]
                    ssh.write_file(path, content)  # type: ignore[union-attr]
                    results.append({"path": path, "action": "restored", "success": True})
                else:
                    results.append(
                        {
                            "path": path,
                            "action": "restore",
                            "success": False,
                            "error": "Blob not found",
                        }
                    )

        except Exception as e:
            results.append({"path": path, "action": "rollback", "success": False, "error": str(e)})

    return results


def list_checkpoints() -> list[tuple]:
    """
    List all sessions with checkpoints.

    Returns
    -------
    list[tuple]
        List of (Session, checkpoint_info) tuples.
    """
    from .session import Session

    result = []
    for session in Session.list_all():
        if session.checkpoint_created_at and session.checkpoint:
            file_count = len(session.checkpoint)
            total_size = sum(e.get("size", 0) for e in session.checkpoint.values())
            result.append(
                (
                    session,
                    {
                        "file_count": file_count,
                        "total_size": total_size,
                        "created_at": session.checkpoint_created_at,
                    },
                )
            )
    return result
