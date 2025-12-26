"""Interactive menu utilities for terminal UI."""

from __future__ import annotations

import sys


def clear_screen() -> None:
    """Clear terminal screen and move cursor to top-left."""
    if not sys.stdout.isatty():
        return
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def wait_for_key(message: str = "Press any key to continue...") -> None:
    """Wait for user to press any key before continuing."""
    if not sys.stdin.isatty():
        return
    print(f"\n{message}")
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print()  # Newline after keypress


def select_menu(title: str, options: list[str]) -> int | None:
    """
    Arrow-key menu selector. Falls back to numbered input if no TTY.

    Parameters
    ----------
    title
        Menu title to display.
    options
        List of option labels.

    Returns
    -------
    int | None
        Selected index (0-based), or None if user quit.
    """
    if not sys.stdin.isatty():
        return _numbered_fallback(title, options)

    return _arrow_key_menu(title, options)


def _numbered_fallback(title: str, options: list[str]) -> int | None:
    """Simple numbered menu for non-TTY environments (CI, pipes)."""
    print(f"\n{title}\n")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  q. Quit")

    while True:
        try:
            choice = input("\nSelect option: ").strip().lower()
        except EOFError:
            return None
        if choice == "q":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice) - 1
        print("Invalid choice.")


def _arrow_key_menu(title: str, options: list[str]) -> int | None:
    """Arrow-key menu with inline cursor navigation."""
    import termios
    import tty

    selected = 0

    # Print title before entering raw mode
    print(f"\n{title}\n")

    # Initial render (before raw mode)
    for i, opt in enumerate(options):
        marker = ">" if i == selected else " "
        print(f"  {marker} {opt}")

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x1b":  # Escape sequence
                seq = sys.stdin.read(2)
                if seq == "[A":  # Up
                    selected = (selected - 1) % len(options)
                elif seq == "[B":  # Down
                    selected = (selected + 1) % len(options)
                else:
                    continue
                # Re-render: move up, clear and rewrite each line
                sys.stdout.write(f"\033[{len(options)}A")  # Move cursor up
                for i, opt in enumerate(options):
                    marker = ">" if i == selected else " "
                    # CR, clear to end of line, write content, CRLF
                    sys.stdout.write(f"\r\033[K  {marker} {opt}\r\n")
                sys.stdout.flush()
            elif ch == "\r":  # Enter
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return selected
            elif ch in ("q", "\x03"):  # q or Ctrl+C
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def prompt_input(prompt: str, default: str | None = None) -> str | None:
    """
    Prompt for text input.

    Parameters
    ----------
    prompt
        Prompt text to display.
    default
        Default value shown in brackets, used if user presses Enter.

    Returns
    -------
    str | None
        User input, default value, or None if cancelled.
    """
    if default:
        prompt_text = f"{prompt} [{default}]: "
    else:
        prompt_text = f"{prompt}: "

    try:
        value = input(prompt_text).strip()
        if not value and default:
            return default
        return value if value else None
    except (EOFError, KeyboardInterrupt):
        print()
        return None
