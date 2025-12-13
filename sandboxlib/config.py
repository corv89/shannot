"""Centralized configuration paths for shannot."""
from __future__ import annotations

import json
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

# Profile configuration
PROFILE_FILENAME = "profile.json"

DEFAULT_PROFILE = {
    "auto_approve": [
        "cat", "head", "tail", "less",
        "ls", "find", "stat", "file",
        "df", "du", "free", "uptime",
        "ps", "top", "htop", "pgrep",
        "systemctl status", "journalctl",
        "uname", "hostname", "whoami", "id",
        "env", "printenv",
        "ip", "ss", "netstat",
        "date", "cal",
    ],
    "always_deny": [
        "rm -rf /",
        "dd if=/dev/zero",
        "mkfs",
        ":(){ :|:& };:",
        "> /dev/sda",
    ],
}


def find_project_root() -> Path | None:
    """Walk up from cwd to find .shannot directory."""
    current = Path.cwd()
    while current != current.parent:
        shannot_dir = current / ".shannot"
        if shannot_dir.is_dir():
            return shannot_dir
        current = current.parent
    return None


def get_profile_path() -> Path | None:
    """
    Get profile path with precedence:
    1. .shannot/profile.json in project root
    2. ~/.config/shannot/profile.json (global)

    Returns path if exists, None otherwise.
    """
    # Check project-local first
    project_dir = find_project_root()
    if project_dir:
        project_profile = project_dir / PROFILE_FILENAME
        if project_profile.exists():
            return project_profile

    # Fall back to global
    global_profile = CONFIG_DIR / PROFILE_FILENAME
    if global_profile.exists():
        return global_profile

    return None


def load_profile() -> dict:
    """
    Load security profile from file.

    Returns dict with:
        - auto_approve: list[str] - commands to execute immediately
        - always_deny: list[str] - commands to never execute

    Uses DEFAULT_PROFILE if no profile file found.
    """
    profile_path = get_profile_path()
    if profile_path is None:
        return DEFAULT_PROFILE.copy()

    try:
        data = json.loads(profile_path.read_text())
        return {
            "auto_approve": data.get("auto_approve", []),
            "always_deny": data.get("always_deny", []),
        }
    except (json.JSONDecodeError, IOError):
        return DEFAULT_PROFILE.copy()
