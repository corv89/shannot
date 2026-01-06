"""Pending deletion tracking for approval system."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

DeletionType = Literal["file", "directory"]


@dataclass
class PendingDeletion:
    """
    A file or directory deletion awaiting approval.

    Tracks the path, type (file/directory), and size for generating
    previews and executing approved deletions.
    """

    path: str  # Virtual/remote path to delete
    target_type: DeletionType  # "file" or "directory"
    size: int = 0  # Size in bytes (files only)
    remote: bool = False  # Whether this is a remote (SSH) deletion

    def get_preview(self) -> str:
        """Get a preview suitable for approval display."""
        type_label = "directory" if self.target_type == "directory" else "file"
        remote_tag = " [remote]" if self.remote else ""
        if self.size > 0:
            size_str = self.size_human()
            return f"DELETE {type_label}: {self.path} ({size_str}){remote_tag}"
        return f"DELETE {type_label}: {self.path}{remote_tag}"

    def size_human(self) -> str:
        """Return human-readable size string."""
        size = self.size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "path": self.path,
            "target_type": self.target_type,
            "size": self.size,
            "remote": self.remote,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PendingDeletion:
        """Deserialize from dict."""
        return cls(
            path=data["path"],
            target_type=data.get("target_type", "file"),
            size=data.get("size", 0),
            remote=data.get("remote", False),
        )


def summarize_deletions(deletions: list[dict]) -> list[dict]:
    """
    Group deletions by root directory for TUI display.

    Parameters
    ----------
    deletions
        List of deletion dicts (from PendingDeletion.to_dict())

    Returns
    -------
    list[dict]
        Grouped summaries: [{root, file_count, dir_count, total_size}, ...]
    """
    if not deletions:
        return []

    # Find common prefixes to group deletions
    groups: dict[str, dict] = defaultdict(
        lambda: {"file_count": 0, "dir_count": 0, "total_size": 0, "paths": []}
    )

    for d in deletions:
        path = d.get("path", "")
        target_type = d.get("target_type", "file")
        size = d.get("size", 0)

        # Find the root directory (first two components after home)
        # e.g., ~/.cache/uv/cache/xyz -> ~/.cache/uv/
        parts = PurePosixPath(path).parts
        if len(parts) >= 3:
            # Take first 3 parts: ('/', 'Users', 'name', '.cache', 'uv', ...)
            # We want the directory being deleted, e.g., ~/.cache/uv/
            home_idx = None
            for i, p in enumerate(parts):
                if p.startswith("."):  # Found dotfile/dotdir
                    home_idx = i
                    break
            if home_idx is not None and home_idx + 1 < len(parts):
                root = str(PurePosixPath(*parts[: home_idx + 2])) + "/"
            else:
                root = str(PurePosixPath(*parts[:3])) + "/"
        else:
            root = path

        groups[root]["paths"].append(path)
        groups[root]["total_size"] += size
        if target_type == "directory":
            groups[root]["dir_count"] += 1
        else:
            groups[root]["file_count"] += 1

    # Convert to list and sort by total size descending
    result = [
        {
            "root": root,
            "file_count": data["file_count"],
            "dir_count": data["dir_count"],
            "total_size": data["total_size"],
        }
        for root, data in groups.items()
    ]
    result.sort(key=lambda x: x["total_size"], reverse=True)
    return result


def format_size(size: int) -> str:
    """Format size in bytes to human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"
