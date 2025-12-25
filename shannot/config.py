"""Centralized configuration paths for shannot."""

from __future__ import annotations

import getpass
import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Version - read from package metadata (pyproject.toml is source of truth)
try:
    from importlib.metadata import version

    VERSION = version("shannot")
except Exception:
    # Fallback for development/edge cases
    VERSION = "0.6.0-dev"

# Remote deployment
REMOTE_DEPLOY_DIR = "/tmp/shannot-v{version}"
RELEASE_PATH_ENV = "SHANNOT_RELEASE_PATH"


def get_remote_deploy_dir() -> str:
    """Get remote deployment directory path with version filled in."""
    return REMOTE_DEPLOY_DIR.format(version=VERSION)


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
AUDIT_DIR = DATA_DIR / "audit"

# Runtime paths (after setup)
RUNTIME_LIB_PYTHON = RUNTIME_DIR / "lib-python"
RUNTIME_LIB_PYPY = RUNTIME_DIR / "lib_pypy"

# Config directories
CONFIG_DIR = _xdg_config_home() / "shannot"

# PyPy download source
PYPY_VERSION = "7.3.3"
PYPY_DOWNLOAD_URL = "https://downloads.python.org/pypy/pypy3.6-v7.3.3-src.tar.bz2"
PYPY_SHA256 = "a23d21ca0de0f613732af4b4abb0b0db1cc56134b5bf0e33614eca87ab8805af"

# PyPy sandbox binary download
SANDBOX_VERSION = "pypy3-sandbox-7.3.6"  # Release tag
SANDBOX_RELEASES_URL = "https://github.com/corv89/pypy/releases/download"
SANDBOX_BINARY_NAME = "pypy3-c"  # Binary name inside tarball
SANDBOX_LIB_NAME = "libpypy3-c.so"  # Shared library
SANDBOX_BINARY_PATH = RUNTIME_DIR / SANDBOX_BINARY_NAME
SANDBOX_LIB_PATH = RUNTIME_DIR / SANDBOX_LIB_NAME

# Platform-specific checksums
SANDBOX_CHECKSUMS: dict[str, str] = {
    "linux-amd64": "b5498d3ea1bd3d4d9de337e57e0784ed6bcb5ff669f160f9bc3e789d64aa812a",
    "linux-arm64": "ee4423ae2fc40ed65bf563568d1c05edfbe4e33e43c958c40f876583005688a6",
    # "darwin-arm64": "",  # Future
}

# Profile configuration
PROFILE_FILENAME = "profile.json"

# Remotes configuration
REMOTES_FILENAME = "remotes.toml"


@dataclass
class Remote:
    """SSH remote target configuration."""

    name: str
    host: str
    user: str
    port: int = 22

    @property
    def target_string(self) -> str:
        """Return user@host format."""
        return f"{self.user}@{self.host}"

    def to_dict(self) -> dict:
        """Convert to dictionary for TOML serialization."""
        return {"host": self.host, "user": self.user, "port": self.port}


DEFAULT_PROFILE = {
    "auto_approve": [
        "cat",
        "head",
        "tail",
        "less",
        "ls",
        "find",
        "stat",
        "file",
        "df",
        "du",
        "free",
        "uptime",
        "ps",
        "top",
        "htop",
        "pgrep",
        "systemctl status",
        "journalctl",
        "uname",
        "hostname",
        "whoami",
        "id",
        "env",
        "printenv",
        "ip",
        "ss",
        "netstat",
        "date",
        "cal",
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
    except (OSError, json.JSONDecodeError):
        return DEFAULT_PROFILE.copy()


def get_remotes_path() -> Path:
    """Get path to remotes.toml config file."""
    return CONFIG_DIR / REMOTES_FILENAME


def load_remotes() -> dict[str, Remote]:
    """
    Load remotes from TOML config file.

    Returns:
        Dictionary mapping remote name to Remote object.
    """
    remotes_path = get_remotes_path()
    if not remotes_path.exists():
        return {}

    try:
        with open(remotes_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load remotes.toml: {e}") from e

    remotes: dict[str, Remote] = {}
    for name, config in data.get("remotes", {}).items():
        remotes[name] = Remote(
            name=name,
            host=config.get("host", ""),
            user=config.get("user", getpass.getuser()),
            port=config.get("port", 22),
        )
    return remotes


def save_remotes(remotes: dict[str, Remote]) -> None:
    """
    Save remotes to TOML config file.

    Uses manual TOML formatting to avoid tomli-w dependency.
    """
    remotes_path = get_remotes_path()
    remotes_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# SSH remote targets for shannot", ""]

    for name, remote in sorted(remotes.items()):
        # Quote names that contain dots or special characters
        if "." in name or " " in name or '"' in name:
            quoted_name = f'"{name}"'
        else:
            quoted_name = name
        lines.append(f"[remotes.{quoted_name}]")
        lines.append(f'host = "{remote.host}"')
        lines.append(f'user = "{remote.user}"')
        lines.append(f"port = {remote.port}")
        lines.append("")

    remotes_path.write_text("\n".join(lines))


def add_remote(name: str, host: str, user: str | None = None, port: int = 22) -> Remote:
    """
    Add a new remote to the configuration.

    Args:
        name: Unique name for the remote
        host: Hostname or IP address
        user: SSH user (defaults to current user)
        port: SSH port (defaults to 22)

    Returns:
        The created Remote object.

    Raises:
        ValueError: If remote name already exists.
    """
    remotes = load_remotes()
    if name in remotes:
        raise ValueError(f"Remote '{name}' already exists. Use 'remote remove' first.")

    remote = Remote(
        name=name,
        host=host,
        user=user or getpass.getuser(),
        port=port,
    )
    remotes[name] = remote
    save_remotes(remotes)
    return remote


def remove_remote(name: str) -> bool:
    """
    Remove a remote from the configuration.

    Returns:
        True if remote was removed, False if it didn't exist.
    """
    remotes = load_remotes()
    if name not in remotes:
        return False
    del remotes[name]
    save_remotes(remotes)
    return True


def resolve_target(target: str) -> tuple[str, str, int]:
    """
    Resolve a target string to (user, host, port) tuple.

    Supports:
    - Named remotes from config (e.g., "prod")
    - user@host format (e.g., "admin@prod.example.com")
    - host-only format (e.g., "prod.example.com") - uses current user
    - user@host:port format (e.g., "admin@prod.example.com:2222")

    Returns:
        Tuple of (user, host, port)
    """
    # Check if it's a saved remote name
    remotes = load_remotes()
    if target in remotes:
        r = remotes[target]
        return (r.user, r.host, r.port)

    # Parse user@host:port format
    user = getpass.getuser()
    port = 22
    host = target

    if "@" in target:
        user, host = target.split("@", 1)

    if ":" in host:
        host, port_str = host.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            pass  # Keep default port if parsing fails

    return (user, host, port)
