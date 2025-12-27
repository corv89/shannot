"""Pending write tracking for approval system."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class PendingWrite:
    """
    A file write awaiting approval.

    Tracks the path, new content, and original content (if any) for
    generating diffs and executing approved writes.
    """

    path: str  # Virtual/remote path being written
    content: bytes  # New content to write
    original: bytes | None = None  # Original content (if file existed)
    remote: bool = False  # Whether this is a remote (SSH) write
    original_hash: str | None = None  # SHA256 of original content (for conflict detection)

    def get_diff(self) -> str:
        """
        Generate unified diff for preview.

        Returns a unified diff string showing changes. For new files,
        shows all lines as additions.
        """
        try:
            new_text = self.content.decode("utf-8")
        except UnicodeDecodeError:
            return f"[Binary file: {len(self.content)} bytes]"

        if self.original is None:
            # New file - show all lines as additions
            lines = [f"+{line}" for line in new_text.splitlines()]
            header = f"+++ {self.path} (new file)\n"
            return header + "\n".join(lines)

        try:
            original_text = self.original.decode("utf-8")
        except UnicodeDecodeError:
            return f"[Binary file modification: {len(self.original)} -> {len(self.content)} bytes]"

        original_lines = original_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"{self.path} (original)",
            tofile=f"{self.path} (modified)",
        )
        return "".join(diff)

    def get_preview(self, max_lines: int = 20) -> str:
        """
        Get a preview suitable for approval display.

        Truncates long diffs with a "more lines" indicator.
        """
        diff = self.get_diff()
        lines = diff.splitlines()
        if len(lines) > max_lines:
            return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
        return diff

    def size_human(self) -> str:
        """Return human-readable size string."""
        size = len(self.content)
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        import base64

        return {
            "path": self.path,
            "content_b64": base64.b64encode(self.content).decode(),
            "original_b64": base64.b64encode(self.original).decode() if self.original else None,
            "remote": self.remote,
            "original_hash": self.original_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PendingWrite:
        """Deserialize from dict."""
        import base64

        return cls(
            path=data["path"],
            content=base64.b64decode(data["content_b64"]),
            original=base64.b64decode(data["original_b64"]) if data.get("original_b64") else None,
            remote=data.get("remote", False),
            original_hash=data.get("original_hash"),
        )
