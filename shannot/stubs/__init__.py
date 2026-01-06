"""Virtual stubs injected into sandbox VFS."""

from __future__ import annotations

from importlib.resources import files


def load_stub(name: str) -> bytes:
    """Load a stub file as bytes."""
    return files("shannot.stubs").joinpath(name).read_bytes()


def get_stubs() -> dict[str, bytes]:
    """Return all stubs as {filename: content}.

    Stubs are overlaid on lib_pypy which is searched before lib-python/3.
    """
    return {
        "_bootlocale.py": load_stub("_bootlocale.py"),
        "_signal.py": load_stub("_signal.py"),
        "pwd.py": load_stub("pwd.py"),
        "subprocess.py": load_stub("subprocess.py"),
    }
