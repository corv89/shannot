#!/usr/bin/env python3
"""
shannot-approve: Interactive approval tool for pending sandbox commands.

Usage:
    shannot-approve [--queue=FILE] [--list] [--persist]
"""
from __future__ import annotations

import sys
import tty
import termios
import argparse

from .queue import (
    read_pending,
    write_approvals,
    append_persistent,
    DEFAULT_QUEUE,
)


def read_single_key():
    """Read a single keypress."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrows)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def clear_line():
    sys.stdout.write('\r\033[K')


def move_cursor_up(n=1):
    sys.stdout.write(f'\033[{n}A')


def interactive_select(items: list) -> list:
    """
    Interactive multi-select with arrow keys and space to toggle.

    Controls:
        up/down or j/k  - Move cursor
        Space           - Toggle selection
        a               - Select all
        n               - Select none
        Enter           - Confirm
        q/Esc           - Cancel
    """
    if not items:
        print("No pending commands.")
        return []

    selected = set()
    cursor = 0

    def render():
        for i, item in enumerate(items):
            marker = "\033[32m●\033[0m" if i in selected else "○"
            pointer = "\033[36m→\033[0m" if i == cursor else " "
            # Truncate long commands
            display = item[:70] + "..." if len(item) > 70 else item
            print(f" {pointer} {marker} {display}")
        print()
        print(" \033[90m[Space] toggle  [a]ll  [n]one  [Enter] confirm  [q] cancel\033[0m")

    def clear_render():
        # Move up and clear all lines
        move_cursor_up(len(items) + 2)
        for _ in range(len(items) + 2):
            clear_line()
            sys.stdout.write('\n')
        move_cursor_up(len(items) + 2)

    print("\n Pending commands for approval:\n")
    render()

    while True:
        sys.stdout.flush()
        key = read_single_key()

        if key in ('q', '\x1b', '\x03'):  # q, Esc, Ctrl-C
            clear_render()
            print(" Cancelled.\n")
            return []

        elif key == '\r':  # Enter
            clear_render()
            return [items[i] for i in sorted(selected)]

        elif key == ' ':  # Space - toggle
            if cursor in selected:
                selected.discard(cursor)
            else:
                selected.add(cursor)

        elif key == 'a':  # Select all
            selected = set(range(len(items)))

        elif key == 'n':  # Select none
            selected = set()

        elif key in ('k', '\x1b[A'):  # Up
            cursor = (cursor - 1) % len(items)

        elif key in ('j', '\x1b[B'):  # Down
            cursor = (cursor + 1) % len(items)

        clear_render()
        render()


def main():
    parser = argparse.ArgumentParser(
        description="Approve pending sandbox commands",
        prog="shannot-approve",
    )
    parser.add_argument(
        '--queue',
        type=str,
        default=str(DEFAULT_QUEUE),
        help=f'Pending commands file (default: {DEFAULT_QUEUE})',
    )
    parser.add_argument(
        '--list',
        action='store_true',
        dest='list_only',
        help='Just list pending, no interaction',
    )
    parser.add_argument(
        '--persist',
        action='store_true',
        help='Add approved commands to persistent allowlist',
    )
    args = parser.parse_args()

    from pathlib import Path
    queue_path = Path(args.queue)

    # Read pending commands
    pending = read_pending(queue_path)

    if not pending:
        print("No pending commands.")
        return 0

    if args.list_only:
        print("Pending commands:")
        for i, cmd in enumerate(pending):
            print(f"  [{i}] {cmd}")
        return 0

    # Interactive selection
    approved = interactive_select(pending)

    if not approved:
        print("No commands approved.")
        return 0

    # Write session approvals
    write_approvals(approved)

    # Optionally persist to permanent allowlist
    if args.persist:
        append_persistent(approved)

    print(f"Approved {len(approved)} command(s):")
    for cmd in approved:
        print(f"  \033[32m✓\033[0m {cmd}")

    if args.persist:
        from .queue import DEFAULT_PERSISTENT_ALLOWLIST
        print(f"\nAdded to persistent allowlist: {DEFAULT_PERSISTENT_ALLOWLIST}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
