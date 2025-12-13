#!/usr/bin/env python3
"""
shannot-approve: Interactive approval tool for sandbox sessions.

Usage:
    shannot-approve              # Interactive session list
    shannot-approve list         # List pending sessions
    shannot-approve show <id>    # Show session details
    shannot-approve execute <id> # Execute specific session
    shannot-approve history      # Show recent sessions
"""
from __future__ import annotations

import argparse
import os
import sys
import termios
import tty
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import Session


# ==============================================================================
# Action - uniform return type from views
# ==============================================================================


@dataclass
class Action:
    """Action returned from views to be handled by main loop."""
    name: str  # "execute", "reject", "view", "back", "quit"
    sessions: list["Session"] = None

    def __post_init__(self):
        if self.sessions is None:
            self.sessions = []


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
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Check if more data is available (arrow key sequence)
            # Use a short timeout to distinguish Esc from arrow keys
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch += sys.stdin.read(2)
            # else: just Esc key
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

    def handle_key(self, key: str) -> "View | None":
        """
        Handle keypress.

        Returns:
            A new View to switch to, or None to stay on this view.
        """
        raise NotImplementedError


# ==============================================================================
# Session List View
# ==============================================================================


class SessionListView(View):
    """Main view showing list of pending sessions with multi-select."""

    def __init__(self, sessions: list["Session"] = None):
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
            date = session.created_at[:10]
            name = session.name[:30]

            print(f" {pointer}{marker} {name:<32} ({cmd_count:>2} cmds) {date}")

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

    def __init__(self, session: "Session"):
        self.session = session
        self.scroll = 0

    def render(self) -> None:
        clear_screen()
        rows, cols = get_terminal_size()

        s = self.session
        print(f"\033[1m Session: {s.name} \033[0m")
        print(f" ID: {s.id}")
        print(f" Script: {s.script_path}")
        print(f" Created: {s.created_at}")
        print()

        if s.analysis:
            print(" \033[1mAnalysis:\033[0m")
            for line in s.analysis.split("\n")[:5]:
                print(f"   {line[:cols - 4]}")
            print()

        print(f" \033[1mCommands ({len(s.commands)}):\033[0m")

        # Scrollable command list
        visible_rows = rows - 15
        if visible_rows < 3:
            visible_rows = 3
        visible_cmds = s.commands[self.scroll : self.scroll + visible_rows]

        for i, cmd in enumerate(visible_cmds):
            idx = self.scroll + i + 1
            display = cmd[: cols - 10]
            if len(cmd) > cols - 10:
                display += "..."
            print(f"   {idx:>3}. {display}")

        remaining = len(s.commands) - self.scroll - len(visible_cmds)
        if remaining > 0:
            print(f"       ... ({remaining} more)")

        print()
        print(
            " \033[90m[Up/Down] scroll  [v] view script  [x] execute  [r] reject  [Esc] back\033[0m"
        )

    def handle_key(self, key: str) -> Action | View | None:
        rows, _ = get_terminal_size()
        visible_rows = max(3, rows - 15)
        max_scroll = max(0, len(self.session.commands) - visible_rows)

        if key in ("b", "\x1b"):
            return Action("back")

        elif key in ("j", "\x1b[B"):
            self.scroll = min(self.scroll + 1, max_scroll)

        elif key in ("k", "\x1b[A"):
            self.scroll = max(self.scroll - 1, 0)

        elif key == "v":
            return ScriptView(self.session)

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

    def __init__(self, session: "Session"):
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
# Confirm View
# ==============================================================================


class ConfirmView(View):
    """Simple yes/no confirmation."""

    def __init__(self, message: str, sessions: list["Session"]):
        self.message = message
        self.sessions = sessions

    def render(self) -> None:
        clear_screen()
        print(f"\033[1m {self.message} \033[0m")
        print()

        for s in self.sessions:
            print(f"   - {s.name} ({len(s.commands)} commands)")

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

    def __init__(self, results: list[tuple["Session", int]]):
        self.results = results
        self.cursor = 0

    def render(self) -> None:
        clear_screen()
        print("\033[1m Execution Results \033[0m")
        print()

        for i, (session, code) in enumerate(self.results):
            pointer = "\033[36m>\033[0m" if i == self.cursor else " "
            if code == 0:
                status = "\033[32m+\033[0m"
            else:
                status = "\033[31mx\033[0m"
            print(f" {pointer} {status} {session.name:<30} exit {code}")

        print()
        success = sum(1 for _, c in self.results if c == 0)
        print(f" {success}/{len(self.results)} succeeded")
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

    def __init__(self, session: "Session"):
        self.session = session
        self.scroll = 0
        self.lines = self._build_lines()

    def _build_lines(self) -> list[str]:
        lines = []
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


def execute_sessions(sessions: list["Session"]) -> list[tuple["Session", int]]:
    """Execute sessions and return results."""
    from .session import Session, execute_session

    results = []
    for session in sessions:
        session.status = "approved"
        session.save()
        exit_code = execute_session(session)
        # Reload to get updated stdout/stderr
        session = Session.load(session.id)
        results.append((session, exit_code))
    return results


def reject_sessions(sessions: list["Session"]) -> None:
    """Mark sessions as rejected."""
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
                    push_view(ConfirmView(f"Execute {len(result.sessions)} session(s)?", result.sessions))

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
        prog="shannot-approve",
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
            print("Usage: shannot-approve show <session_id>")
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
        print(f"Created: {session.created_at}")
        if session.analysis:
            print(f"Analysis: {session.analysis}")
        print(f"\nCommands ({len(session.commands)}):")
        for i, cmd in enumerate(session.commands, 1):
            print(f"  {i}. {cmd}")
        return 0

    # Execute mode
    if args.action == "execute":
        if not args.args:
            print("Usage: shannot-approve execute <session_id> [session_id...]")
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
                print(f"  + Completed successfully")
            else:
                print(f"  x Failed (exit {exit_code})")
        return 0

    # Default: interactive TUI
    run_tui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
