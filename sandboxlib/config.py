"""Centralized configuration paths for shannot."""
from __future__ import annotations

import os
from pathlib import Path


def _xdg_data_home() -> Path:
    """XDG data directory (~/.local/share or $XDG_DATA_HOME)."""
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


def _xdg_config_home() -> Path:
    """XDG config directory (~/.config or $XDG_CONFIG_HOME)."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


# Data directories
DATA_DIR = _xdg_data_home() / "shannot"
SESSIONS_DIR = DATA_DIR / "sessions"
RUNTIME_DIR = DATA_DIR / "runtime"

# Runtime paths (after setup)
RUNTIME_LIB_PYTHON = RUNTIME_DIR / "lib-python"
RUNTIME_LIB_PYPY = RUNTIME_DIR / "lib_pypy"

# Config directories
CONFIG_DIR = _xdg_config_home() / "shannot"

# PyPy download source
PYPY_VERSION = "7.3.3"
PYPY_DOWNLOAD_URL = "https://downloads.python.org/pypy/pypy3.6-v7.3.3-src.tar.bz2"
PYPY_SHA256 = "a23d21ca0de0f613732af4b4abb0b0db1cc56134b5bf0e33614eca87ab8805af"
