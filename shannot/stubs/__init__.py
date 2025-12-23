"""Virtual stubs injected into sandbox VFS."""

from __future__ import annotations

from importlib.resources import files


def load_stub(name: str) -> bytes:
    """Load a stub file as bytes."""
    return files("shannot.stubs").joinpath(name).read_bytes()


def get_stubs() -> dict[str, bytes]:
    """Return all stubs as {filename: content}."""
    return {
        "_signal.py": load_stub("_signal.py"),
        "subprocess.py": load_stub("subprocess.py"),
    }
