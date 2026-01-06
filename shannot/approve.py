#!/usr/bin/env python3
"""
shannot approve: Interactive approval tool for sandbox sessions.

Usage:
    shannot approve              # Interactive session list
    shannot approve list         # List pending sessions
    shannot approve show <id>    # Show session details
    shannot approve execute <id> # Execute specific session
    shannot approve history      # Show recent sessions
"""

from __future__ import annotations

import argparse
import os
import sys
import termios
import tty
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session

from .config import DangerLevel, classify_command_danger, load_config

# Danger level color codes for TUI display
DANGER_COLORS = {
    DangerLevel.SAFE: "\033[2;32m",  # Dim green
    DangerLevel.CAUTION: "\033[33m",  # Yellow
    DangerLevel.DANGER: "\033[31m",  # Red
    DangerLevel.UNKNOWN: "",  # No color
}
COLOR_RESET = "\033[0m"


# ==============================================================================
# Action - uniform return type from views
# ==============================================================================


@dataclass
class Action:
    """Action returned from views to be handled by main loop."""

    name: str  # "execute", "reject", "view", "back", "quit"
    sessions: list[Session] = field(default_factory=list)


# ==============================================================================
# Terminal Utilities
# ==============================================================================


def read_single_key() -> str:
    """Read a single keypress, handling escape sequences properly."""
    import select

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        # Use os.read() directly to bypass Python's buffered I/O
        ch = os.read(fd, 1).decode("utf-8", errors="replace")
        if ch == "\x1b":
            # Read escape sequence - arrow keys are ESC [ A/B/C/D
            while select.select([fd], [], [], 0.02)[0]:
                ch += os.read(fd, 1).decode("utf-8", errors="replace")
                if len(ch) >= 4:
                    break
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def clear_screen():
    sys.stdout.write("\033[2J\033[H")


def clear_line():
    sys.stdout.write("\r\033[K")


def hide_cursor():
    sys.stdout.write("\033[?25l")


def show_cursor():
    sys.stdout.write("\033[?25h")


def get_terminal_size() -> tuple[int, int]:
    """Return (rows, cols)."""
    size = os.get_terminal_size()
    return size.lines, size.columns


# ==============================================================================
# View Base Class
# ==============================================================================


class View:
    """Base class for TUI views."""

    def render(self) -> None:
        """Render the view to the terminal."""
        raise NotImplementedError

    def handle_key(self, key: str) -> Action | View | None:
        """
        Handle keypress.

        Returns:
            An Action to execute, a new View to switch to, or None to stay on this view.
        """
        raise NotImplementedError


# ==============================================================================
# Session List View
# ==============================================================================


class SessionListView(View):
    """Main view showing list of pending sessions with multi-select."""

    def __init__(self, sessions: list[Session] | None = None):
        if sessions is None:
            from .session import Session

            sessions = Session.list_pending()
        self.sessions = sessions
        self.cursor = 0
        self.selected: set[int] = set()

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        print("\033[1m Pending Sessions \033[0m")
        print()

        if not self.sessions:
            print(" No pending sessions.")
            print()
            print(" \033[90mPress q to quit\033[0m")
            return

        for i, session in enumerate(self.sessions):
            marker = "\033[32m*\033[0m" if i in self.selected else " "
            pointer = "\033[36m>\033[0m" if i == self.cursor else " "

            cmd_count = len(session.commands)
            write_count = len(session.pending_writes)
            delete_count = len(session.pending_deletions)
            date = session.created_at[:10]
            name = session.name[:30]

            # Show counts
            counts = f"{cmd_count:>2} cmds"
            if write_count:
                counts += f", {write_count} writes"
            if delete_count:
                counts += f", {delete_count} deletes"

            # Show remote target if present
            remote_tag = ""
            if session.is_remote():
                remote_tag = f" \033[33m@{session.target}\033[0m"

            print(f" {pointer}{marker} {name:<32} ({counts}){remote_tag} {date}")

        print()
        print(" \033[90m[Up/Down] move  [Space] select  [a]ll  [n]one\033[0m")
        print(" \033[90m[Enter] review  [x] execute  [r] reject  [q] quit\033[0m")

    def handle_key(self, key: str) -> Action | View | None:
        if not self.sessions:
            if key in ("q", "\x03"):
                return Action("quit")
            return None

        if key in ("q", "\x03"):
            return Action("quit")

        elif key in ("j", "\x1b[B"):  # Down
            self.cursor = (self.cursor + 1) % len(self.sessions)

        elif key in ("k", "\x1b[A"):  # Up
            self.cursor = (self.cursor - 1) % len(self.sessions)

        elif key == " ":  # Toggle select
            if self.cursor in self.selected:
                self.selected.discard(self.cursor)
            else:
                self.selected.add(self.cursor)

        elif key == "a":  # Select all
            self.selected = set(range(len(self.sessions)))

        elif key == "n":  # Select none
            self.selected.clear()

        elif key == "\r":  # Enter - review current
            return Action("view", [self.sessions[self.cursor]])

        elif key == "x":  # Execute selected
            if self.selected:
                sessions = [self.sessions[i] for i in sorted(self.selected)]
                return Action("execute", sessions)

        elif key == "r":  # Reject selected
            if self.selected:
                sessions = [self.sessions[i] for i in sorted(self.selected)]
                return Action("reject", sessions)

        return None


# ==============================================================================
# Session Detail View
# ==============================================================================


class SessionDetailView(View):
    """Detailed view of a single session."""

    def __init__(self, session: Session):
        self.session = session
        self.scroll = 0

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        s = self.session
        print(f"\033[1m Session: {s.name} \033[0m")
        print(f" ID: {s.id}")
        print(f" Script: {s.script_path}")
        if s.is_remote():
            print(f" Target: \033[33m{s.target}\033[0m")
        print(f" Created: {s.created_at}")
        print()

        if s.analysis:
            print(" \033[1mAnalysis:\033[0m")
            for line in s.analysis.split("\n")[:5]:
                print(f"   {line[: cols - 4]}")
            print()

        print(f" \033[1mCommands ({len(s.commands)}):\033[0m")

        # Scrollable command list
        visible_rows = rows - 18 - (3 if s.pending_writes else 0)
        if visible_rows < 3:
            visible_rows = 3
        visible_cmds = s.commands[self.scroll : self.scroll + visible_rows]

        # Load profile once for danger classification
        profile = load_config().profile

        for i, cmd in enumerate(visible_cmds):
            idx = self.scroll + i + 1
            display = cmd[: cols - 10]
            if len(cmd) > cols - 10:
                display += "..."

            # Classify and color the command
            danger = classify_command_danger(cmd, profile)
            color = DANGER_COLORS.get(danger, "")
            reset = COLOR_RESET if color else ""
            print(f"   {idx:>3}. {color}{display}{reset}")

        remaining = len(s.commands) - self.scroll - len(visible_cmds)
        if remaining > 0:
            print(f"       ... ({remaining} more)")

        # Show pending writes summary
        if s.pending_writes:
            import base64

            large_file_threshold = 5 * 1024 * 1024  # 5 MB
            print()
            print(f" \033[1mFile Writes ({len(s.pending_writes)}):\033[0m")
            for i, write_data in enumerate(s.pending_writes[:3]):
                path = write_data.get("path", "?")
                remote = " \033[33m[remote]\033[0m" if write_data.get("remote") else ""
                # Check size for large file warning
                try:
                    size = len(base64.b64decode(write_data.get("content_b64", "")))
                    warn = " \033[33m⚠ large\033[0m" if size > large_file_threshold else ""
                except (ValueError, TypeError):
                    warn = ""
                print(f"   {i + 1:>3}. {path}{remote}{warn}")
            if len(s.pending_writes) > 3:
                print(f"       ... ({len(s.pending_writes) - 3} more)")

        # Show pending deletions summary (collapsed by directory)
        if s.pending_deletions:
            from .pending_deletion import format_size, summarize_deletions

            print()
            total_size = sum(d.get("size", 0) for d in s.pending_deletions)
            count = len(s.pending_deletions)
            print(f" \033[1mDeletions ({count} items, {format_size(total_size)}):\033[0m")

            # Group by root directory
            summaries = summarize_deletions(s.pending_deletions)
            for i, summary in enumerate(summaries[:3]):
                root = summary["root"]
                file_count = summary["file_count"]
                dir_count = summary["dir_count"]
                size = summary["total_size"]

                parts = []
                if file_count:
                    parts.append(f"{file_count} files")
                if dir_count:
                    parts.append(f"{dir_count} dirs")
                detail = ", ".join(parts)

                size_str = format_size(size)
                print(f"   {i + 1:>3}. \033[31mDELETE\033[0m {root} ({detail}, {size_str})")
            if len(summaries) > 3:
                print(f"       ... ({len(summaries) - 3} more directories)")

        print()
        help_text = " \033[90m[Up/Down] scroll  [v] view script"
        if s.pending_writes:
            help_text += "  [w] view writes"
        if s.pending_deletions:
            help_text += "  [d] view deletes"
        help_text += "  [x] execute  [r] reject  [Esc] back\033[0m"
        print(help_text)

    def handle_key(self, key: str) -> Action | View | None:
        rows, _ = get_terminal_size()
        visible_rows = max(3, rows - 18)
        max_scroll = max(0, len(self.session.commands) - visible_rows)

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.scroll = min(self.scroll + 1, max_scroll)

        elif key in ("k", "\x1b[A"):
            self.scroll = max(self.scroll - 1, 0)

        elif key in ("v", "\r"):
            return ScriptView(self.session)

        elif key == "w" and self.session.pending_writes:
            return PendingWritesListView(self.session)

        elif key == "d" and self.session.pending_deletions:
            return PendingDeletionsListView(self.session)

        elif key == "x":
            return Action("execute", [self.session])

        elif key == "r":
            return Action("reject", [self.session])

        return None


# ==============================================================================
# Script View
# ==============================================================================


class ScriptView(View):
    """Scrollable view of script content."""

    def __init__(self, session: Session):
        self.session = session
        self.scroll = 0
        self.content = session.load_script() or "(Script content not available)"
        self.lines = self.content.split("\n")

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        print(f"\033[1m Script: {self.session.script_path} \033[0m")
        print()

        visible_rows = rows - 6
        if visible_rows < 3:
            visible_rows = 3
        visible_lines = self.lines[self.scroll : self.scroll + visible_rows]

        for i, line in enumerate(visible_lines):
            lineno = self.scroll + i + 1
            display = line[: cols - 8]
            print(f" \033[90m{lineno:>4}\033[0m {display}")

        print()
        print(" \033[90m[Up/Down] scroll  [x] execute  [r] reject  [Esc] back\033[0m")

    def handle_key(self, key: str) -> Action | None:
        rows, _ = get_terminal_size()
        visible_rows = max(3, rows - 6)
        max_scroll = max(0, len(self.lines) - visible_rows)

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.scroll = min(self.scroll + 1, max_scroll)

        elif key in ("k", "\x1b[A"):
            self.scroll = max(self.scroll - 1, 0)

        elif key == "x":
            return Action("execute", [self.session])

        elif key == "r":
            return Action("reject", [self.session])

        return None


# ==============================================================================
# Pending Writes List View
# ==============================================================================


class PendingWritesListView(View):
    """List of pending file writes for a session."""

    def __init__(self, session: Session):
        self.session = session
        self.cursor = 0

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        print(f"\033[1m Pending Writes: {self.session.name} \033[0m")
        print()

        if not self.session.pending_writes:
            print(" No pending writes.")
            print()
            print(" \033[90m[Esc] back\033[0m")
            return

        visible_rows = rows - 8
        if visible_rows < 3:
            visible_rows = 3

        start = max(0, self.cursor - visible_rows // 2)
        visible = self.session.pending_writes[start : start + visible_rows]

        large_file_threshold = 5 * 1024 * 1024  # 5 MB

        for i, write_data in enumerate(visible):
            idx = start + i
            pointer = "\033[36m>\033[0m" if idx == self.cursor else " "
            path = write_data.get("path", "?")
            remote = "\033[33m[R]\033[0m" if write_data.get("remote") else "   "

            # Calculate size
            content_b64 = write_data.get("content_b64", "")
            import base64

            try:
                size = len(base64.b64decode(content_b64))
                if size >= 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                elif size >= 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size:,} B"
            except (ValueError, TypeError):
                size = 0
                size_str = "?"  # Invalid base64 data

            # Large file warning
            if size > large_file_threshold:
                warn = "\033[33m⚠\033[0m "
            else:
                warn = "  "

            display_path = path[: cols - 30]
            if len(path) > cols - 30:
                display_path += "..."

            print(f" {pointer} {warn}{remote} {display_path:<50} {size_str:>10}")

        print()
        print(" \033[90m[Up/Down] select  [Enter] view diff  [Esc] back\033[0m")

    def handle_key(self, key: str) -> Action | View | None:
        if not self.session.pending_writes:
            if key in ("b", "\x1b"):
                return Action("back")
            return None

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.cursor = (self.cursor + 1) % len(self.session.pending_writes)

        elif key in ("k", "\x1b[A"):
            self.cursor = (self.cursor - 1) % len(self.session.pending_writes)

        elif key == "\r":
            return PendingWriteDiffView(self.session, self.cursor)

        return None


# ==============================================================================
# Pending Deletions List View
# ==============================================================================


class PendingDeletionsListView(View):
    """List of pending file/directory deletions for a session."""

    def __init__(self, session: Session):
        self.session = session
        self.cursor = 0

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        from .pending_deletion import format_size

        total_size = sum(d.get("size", 0) for d in self.session.pending_deletions)
        print(f"\033[1m Pending Deletions: {self.session.name} ({format_size(total_size)}) \033[0m")
        print()

        if not self.session.pending_deletions:
            print(" No pending deletions.")
            print()
            print(" \033[90m[Esc] back\033[0m")
            return

        visible_rows = rows - 8
        if visible_rows < 3:
            visible_rows = 3

        start = max(0, self.cursor - visible_rows // 2)
        visible = self.session.pending_deletions[start : start + visible_rows]

        for i, del_data in enumerate(visible):
            idx = start + i
            pointer = "\033[36m>\033[0m" if idx == self.cursor else " "
            path = del_data.get("path", "?")
            target_type = del_data.get("target_type", "file")
            size = del_data.get("size", 0)
            remote = "\033[33m[R]\033[0m" if del_data.get("remote") else "   "

            type_icon = "DIR" if target_type == "directory" else "   "
            size_str = format_size(size) if size > 0 else ""

            display_path = path[: cols - 35]
            if len(path) > cols - 35:
                display_path += "..."

            line = f" {pointer} \033[31mDEL\033[0m {type_icon} {remote} {display_path:<50}"
            print(f"{line} {size_str:>10}")

        print()
        remaining = len(self.session.pending_deletions) - start - len(visible)
        if remaining > 0:
            print(f" ... and {remaining} more")
        print()
        print(" \033[90m[Up/Down] scroll  [Esc] back\033[0m")

    def handle_key(self, key: str) -> Action | View | None:
        if not self.session.pending_deletions:
            if key in ("b", "\x1b"):
                return Action("back")
            return None

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.cursor = min(self.cursor + 1, len(self.session.pending_deletions) - 1)

        elif key in ("k", "\x1b[A"):
            self.cursor = max(self.cursor - 1, 0)

        return None


# ==============================================================================
# Pending Write Diff View
# ==============================================================================


class PendingWriteDiffView(View):
    """View diff for a single pending write."""

    def __init__(self, session: Session, write_index: int):
        self.session = session
        self.write_index = write_index
        self.write_data = session.pending_writes[write_index]
        self.scroll = 0
        self._build_diff()

    def _build_diff(self):
        """Build diff lines from write data."""
        from .pending_write import PendingWrite

        pending = PendingWrite.from_dict(self.write_data)
        diff = pending.get_diff()
        self.diff_lines = diff.splitlines()
        self.path = pending.path
        self.is_remote = pending.remote

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        remote_tag = " \033[33m[remote]\033[0m" if self.is_remote else ""
        print(f"\033[1m Write: {self.path}{remote_tag} \033[0m")
        print()

        visible_rows = rows - 6
        if visible_rows < 3:
            visible_rows = 3
        visible_lines = self.diff_lines[self.scroll : self.scroll + visible_rows]

        for line in visible_lines:
            # Colorize diff output
            if line.startswith("+") and not line.startswith("+++"):
                print(f" \033[32m{line[: cols - 2]}\033[0m")
            elif line.startswith("-") and not line.startswith("---"):
                print(f" \033[31m{line[: cols - 2]}\033[0m")
            elif line.startswith("@@"):
                print(f" \033[36m{line[: cols - 2]}\033[0m")
            else:
                print(f" {line[: cols - 2]}")

        print()
        print(" \033[90m[Up/Down] scroll  [Esc] back\033[0m")

    def handle_key(self, key: str) -> Action | None:
        rows, _ = get_terminal_size()
        visible_rows = max(3, rows - 6)
        max_scroll = max(0, len(self.diff_lines) - visible_rows)

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.scroll = min(self.scroll + 1, max_scroll)

        elif key in ("k", "\x1b[A"):
            self.scroll = max(self.scroll - 1, 0)

        return None


# ==============================================================================
# Confirm View
# ==============================================================================


class ConfirmView(View):
    """Simple yes/no confirmation."""

    def __init__(self, message: str, sessions: list[Session]):
        self.message = message
        self.sessions = sessions

    def render(self) -> None:
        clear_screen()
        print(f"\033[1m {self.message} \033[0m")
        print()

        for s in self.sessions:
            counts = f"{len(s.commands)} commands"
            if s.pending_writes:
                counts += f", {len(s.pending_writes)} writes"
            if s.pending_deletions:
                counts += f", {len(s.pending_deletions)} deletes"
            print(f"   - {s.name} ({counts})")

        print()
        print(" \033[90m[y] yes  [n] no\033[0m")

    def handle_key(self, key: str) -> Action | None:
        if key == "y":
            return Action("confirmed", self.sessions)
        elif key in ("n", "\x1b", "q"):
            return Action("cancelled")
        return None


# ==============================================================================
# Result View
# ==============================================================================


class ResultView(View):
    """Post-execution results display."""

    def __init__(self, results: list[tuple[Session, int]]):
        self.results = results
        self.cursor = 0

    def render(self) -> None:
        clear_screen()
        print("\033[1m Execution Results \033[0m")
        print()

        for i, (session, code) in enumerate(self.results):
            pointer = "\033[36m>\033[0m" if i == self.cursor else " "
            if code == 0:
                status = "\033[32m✓\033[0m"
            else:
                status = "\033[31m✗\033[0m"
            print(f" {pointer} {status} {session.name:<30} exit {code}")

        print()
        success = sum(1 for _, c in self.results if c == 0)
        print(f" {success}/{len(self.results)} succeeded")

        # Collect and display write conflicts
        conflicts = []
        for session, _ in self.results:
            if session.completed_writes:
                for write in session.completed_writes:
                    if not write.get("success", True):
                        conflicts.append(write.get("path", "unknown"))

        if conflicts:
            print()
            noun = "conflict" if len(conflicts) == 1 else "conflicts"
            print(f"\033[33m⚠ {len(conflicts)} write {noun} — file changed since dry-run\033[0m")
            for path in conflicts[:3]:
                print(f"  {path}")
            if len(conflicts) > 3:
                print(f"  ... and {len(conflicts) - 3} more")

        print()
        print(" \033[90m[Up/Down] select  [v] view output  [Esc] back  [q] quit\033[0m")

    def handle_key(self, key: str) -> Action | View | None:
        if key in ("q", "\x03"):
            return Action("quit")

        elif key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.cursor = (self.cursor + 1) % len(self.results)

        elif key in ("k", "\x1b[A"):
            self.cursor = (self.cursor - 1) % len(self.results)

        elif key == "v":
            session, _ = self.results[self.cursor]
            return OutputView(session)

        return None


# ==============================================================================
# Output View
# ==============================================================================


class OutputView(View):
    """View captured stdout/stderr for a session."""

    def __init__(self, session: Session):
        self.session = session
        self.scroll = 0
        self.lines = self._build_lines()

    def _build_lines(self) -> list[str]:
        lines = []

        # Show completed writes first (if any)
        if self.session.completed_writes:
            lines.append("--- writes ---")
            for write_info in self.session.completed_writes:
                path = write_info.get("path", "")
                if write_info.get("success"):
                    size = write_info.get("size", 0)
                    lines.append(f"✓ {path} ({size} bytes)")
                else:
                    error = write_info.get("error", "unknown")
                    lines.append(f"✗ {path} ({error})")
            lines.append("")

        # Show completed deletions (if any)
        if self.session.completed_deletions:
            lines.append("--- deletions ---")
            for del_info in self.session.completed_deletions:
                path = del_info.get("path", "")
                if del_info.get("skipped"):
                    continue  # Don't show skipped items
                if del_info.get("success"):
                    target_type = del_info.get("target_type", "file")
                    type_label = " [dir]" if target_type == "directory" else ""
                    lines.append(f"✓ {path}{type_label}")
                else:
                    error = del_info.get("error", "unknown")
                    lines.append(f"✗ {path} ({error})")
            lines.append("")

        lines.append("--- stdout ---")
        if self.session.stdout:
            lines.extend(self.session.stdout.split("\n"))
        else:
            lines.append("(empty)")
        lines.append("")
        lines.append("--- stderr ---")
        if self.session.stderr:
            lines.extend(self.session.stderr.split("\n"))
        else:
            lines.append("(empty)")
        return lines

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        print(f"\033[1m Output: {self.session.name} \033[0m")
        print()

        visible_rows = rows - 6
        if visible_rows < 3:
            visible_rows = 3
        visible_lines = self.lines[self.scroll : self.scroll + visible_rows]

        for line in visible_lines:
            display = line[: cols - 2]
            print(f" {display}")

        print()
        print(" \033[90m[Up/Down] scroll  [Esc] back\033[0m")

    def handle_key(self, key: str) -> Action | None:
        rows, _ = get_terminal_size()
        visible_rows = max(3, rows - 6)
        max_scroll = max(0, len(self.lines) - visible_rows)

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.scroll = min(self.scroll + 1, max_scroll)

        elif key in ("k", "\x1b[A"):
            self.scroll = max(self.scroll - 1, 0)

        return None


# ==============================================================================
# Action Handlers
# ==============================================================================


def execute_sessions(sessions: list[Session]) -> list[tuple[Session, int]]:
    """Execute sessions and return results."""
    import time

    from .audit import (
        log_approval_decision,
        log_execution_completed,
        log_execution_started,
    )
    from .session import Session, execute_session

    # Audit log approval decision
    log_approval_decision(sessions, "approved", "tui")

    results = []
    for session in sessions:
        session.status = "approved"
        session.save()

        # Audit log execution start
        log_execution_started(session)
        start_time = time.time()

        exit_code = execute_session(session)

        # Reload to get updated stdout/stderr
        session = Session.load(session.id, audit=False)

        # Audit log execution complete
        duration = time.time() - start_time
        log_execution_completed(session, duration, session.error)

        results.append((session, exit_code))
    return results


def reject_sessions(sessions: list[Session]) -> None:
    """Mark sessions as rejected."""
    from .audit import log_approval_decision

    # Audit log rejection decision
    log_approval_decision(sessions, "rejected", "tui")

    for session in sessions:
        session.status = "rejected"
        session.save()


# ==============================================================================
# Main TUI Loop
# ==============================================================================


def run_tui():
    """Main TUI event loop with unified action handling."""
    from .session import Session

    # View stack for navigation
    view_stack: list[View] = [SessionListView()]

    def current_view() -> View:
        return view_stack[-1]

    def push_view(v: View):
        view_stack.append(v)

    def pop_view():
        if len(view_stack) > 1:
            view_stack.pop()

    def refresh_list():
        """Refresh the session list at bottom of stack."""
        sessions = Session.list_pending()
        view_stack[0] = SessionListView(sessions)

    hide_cursor()
    try:
        while True:
            current_view().render()
            sys.stdout.flush()

            key = read_single_key()
            result = current_view().handle_key(key)

            # Handle View returns (for nested views like OutputView)
            if isinstance(result, View):
                push_view(result)
                continue

            # Handle Action returns
            if isinstance(result, Action):
                if result.name == "quit":
                    break

                elif result.name == "back":
                    pop_view()

                elif result.name == "view":
                    # View session details
                    push_view(SessionDetailView(result.sessions[0]))

                elif result.name == "execute":
                    # Confirm then execute
                    push_view(
                        ConfirmView(
                            f"Execute {len(result.sessions)} session(s)?",
                            result.sessions,
                        )
                    )

                elif result.name == "confirmed":
                    # User confirmed execution
                    pop_view()  # Remove confirm view
                    clear_screen()
                    print("\033[1m Executing... \033[0m")
                    print()
                    sys.stdout.flush()

                    results = execute_sessions(result.sessions)
                    refresh_list()
                    push_view(ResultView(results))

                elif result.name == "cancelled":
                    pop_view()

                elif result.name == "reject":
                    reject_sessions(result.sessions)
                    refresh_list()
                    # Go back to list
                    while len(view_stack) > 1:
                        view_stack.pop()

    finally:
        show_cursor()
        clear_screen()


# ==============================================================================
# CLI Entry Point
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Approve pending sandbox sessions",
        prog="shannot approve",
    )
    parser.add_argument(
        "action",
        nargs="?",
        default=None,
        choices=["list", "show", "execute", "history"],
        help="Action to perform",
    )
    parser.add_argument("args", nargs="*", help="Action arguments (session IDs)")

    args = parser.parse_args()

    from .session import Session, execute_session

    # List mode
    if args.action == "list":
        sessions = Session.list_pending()
        if not sessions:
            print("No pending sessions.")
            return 0

        print(f"Pending sessions ({len(sessions)}):\n")
        for s in sessions:
            print(f"  {s.id}")
            print(f"    {s.name} ({len(s.commands)} commands)")
            print()
        return 0

    # History mode
    if args.action == "history":
        sessions = Session.list_all(limit=20)
        if not sessions:
            print("No sessions found.")
            return 0

        print("Recent sessions:\n")
        for s in sessions:
            status_icon = {
                "pending": "o",
                "approved": "-",
                "executed": "+",
                "rejected": "x",
                "failed": "!",
            }.get(s.status, "?")
            print(f"  {status_icon} {s.id}")
            print(f"      {s.name} [{s.status}]")
            print()
        return 0

    # Show mode
    if args.action == "show":
        if not args.args:
            print("Usage: shannot approve show <session_id>")
            return 1

        try:
            session = Session.load(args.args[0])
        except FileNotFoundError:
            print(f"Session not found: {args.args[0]}")
            return 1

        print(f"Session: {session.name}")
        print(f"ID: {session.id}")
        print(f"Status: {session.status}")
        print(f"Script: {session.script_path}")
        if session.is_remote():
            print(f"Target: {session.target}")
        print(f"Created: {session.created_at}")
        if session.analysis:
            print(f"Analysis: {session.analysis}")
        print(f"\nCommands ({len(session.commands)}):")
        for i, cmd in enumerate(session.commands, 1):
            print(f"  {i}. {cmd}")

        if session.pending_writes:
            print(f"\nFile Writes ({len(session.pending_writes)}):")
            for i, write_data in enumerate(session.pending_writes, 1):
                path = write_data.get("path", "?")
                remote = " [remote]" if write_data.get("remote") else ""
                print(f"  {i}. {path}{remote}")
        return 0

    # Execute mode
    if args.action == "execute":
        if not args.args:
            print("Usage: shannot approve execute <session_id> [session_id...]")
            return 1

        for session_id in args.args:
            try:
                session = Session.load(session_id)
            except FileNotFoundError:
                print(f"Session not found: {session_id}")
                continue

            print(f"Executing {session.name}...")
            session.status = "approved"
            session.save()
            exit_code = execute_session(session)
            if exit_code == 0:
                print("  + Completed successfully")
            else:
                print(f"  x Failed (exit {exit_code})")
        return 0

    # Default: interactive TUI
    run_tui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
