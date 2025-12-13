"""Virtual stubs injected into sandbox VFS."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

_STUBS_DIR = Path(__file__).parent


def load_stub(name: str) -> bytes:
    """Load a stub file as bytes."""
    return (_STUBS_DIR / name).read_bytes()


def get_stubs() -> Dict[str, bytes]:
    """Return all stubs as {filename: content}."""
    return {
        "_signal.py": load_stub("_signal.py"),
        "subprocess.py": load_stub("subprocess.py"),
    }
