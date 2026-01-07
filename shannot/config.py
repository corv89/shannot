"""Centralized configuration for shannot.

Single unified config file: config.toml
- ~/.config/shannot/config.toml (global)
- .shannot/config.toml (project-local, takes precedence)

Contains sections:
- [profile] - auto_approve and always_deny command lists
- [audit] - audit logging settings
- [remotes.*] - SSH remote targets
"""

from __future__ import annotations

import getpass
import os
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

# Version - lazy loaded from package metadata (pyproject.toml is source of truth)
# This avoids ~88ms importlib.metadata overhead on every CLI invocation
_version_cache: str | None = None


def get_version() -> str:
    """Get shannot version string, lazy-loaded from package metadata."""
    global _version_cache
    if _version_cache is None:
        try:
            from importlib.metadata import version

            _version_cache = version("shannot")
        except Exception:
            # Fallback for development/edge cases
            _version_cache = "dev"
    return _version_cache


# Remote deployment
REMOTE_DEPLOY_DIR = "/tmp/shannot-v{version}"
RELEASE_PATH_ENV = "SHANNOT_RELEASE_PATH"
SHANNOT_RELEASES_URL = "https://github.com/corv89/shannot/releases/download"


def get_remote_deploy_dir() -> str:
    """Get remote deployment directory path with version filled in."""
    return REMOTE_DEPLOY_DIR.format(version=get_version())


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
CONFIG_FILENAME = "config.toml"

# Platform-specific PyPy stdlib (Linux=PyPy 3.6, macOS=PyPy 3.8)
PYPY_CONFIG: dict[str, dict[str, str]] = {
    "linux": {
        "version": "7.3.3",
        "url": "https://downloads.python.org/pypy/pypy3.6-v7.3.3-src.tar.bz2",
        "sha256": "a23d21ca0de0f613732af4b4abb0b0db1cc56134b5bf0e33614eca87ab8805af",
    },
    "darwin": {
        "version": "7.3.11",  # PyPy 3.8
        "url": "https://downloads.python.org/pypy/pypy3.8-v7.3.11-src.tar.bz2",
        "sha256": "4d6769bfca73734e8666fd70503b7ceb06a6e259110e617331bb3899ca4e6058",
    },
}


def get_pypy_config() -> dict[str, str]:
    """Get PyPy stdlib config for current platform."""
    import platform

    system = platform.system().lower()
    return PYPY_CONFIG.get(system, PYPY_CONFIG["linux"])


# Platform-specific sandbox binary configuration
SANDBOX_CONFIG: dict[str, dict[str, str]] = {
    "linux-amd64": {
        "version": "pypy3-sandbox-7.3.6",
        "url": "https://github.com/corv89/pypy/releases/download/pypy3-sandbox-7.3.6/pypy3-sandbox-linux-amd64.tar.gz",
        "sha256": "b5498d3ea1bd3d4d9de337e57e0784ed6bcb5ff669f160f9bc3e789d64aa812a",
    },
    "linux-arm64": {
        "version": "pypy3-sandbox-7.3.6",
        "url": "https://github.com/corv89/pypy/releases/download/pypy3-sandbox-7.3.6/pypy3-sandbox-linux-arm64.tar.gz",
        "sha256": "ee4423ae2fc40ed65bf563568d1c05edfbe4e33e43c958c40f876583005688a6",
    },
    "darwin-amd64": {
        "version": "pypy3.8-sandbox-7.3.17",
        "url": "https://github.com/corv89/pypy/releases/download/pypy3.8-sandbox-7.3.17/pypy3.8-sandbox-darwin-amd64.tar.gz",
        "sha256": "93308fb70339eb1dc6b59c0c5cb57dfe8562a11131f3ebdd5c992dfc7fa3289d",
    },
    "darwin-arm64": {
        "version": "pypy3.8-sandbox-7.3.17",
        "url": "https://github.com/corv89/pypy/releases/download/pypy3.8-sandbox-7.3.17/pypy3.8-sandbox-darwin-arm64.tar.gz",
        "sha256": "f874a0b00283d8abc87ee87b54e01676c639876bf15fd07865b7e5d2b319085c",
    },
}


def get_sandbox_lib_name() -> str:
    """Get platform-specific shared library name."""
    import platform

    if platform.system() == "Darwin":
        return "libpypy3-c.dylib"
    return "libpypy3-c.so"


# Sandbox binary paths
SANDBOX_BINARY_NAME = "pypy3-c"  # Binary name inside tarball
SANDBOX_LIB_NAME = get_sandbox_lib_name()
SANDBOX_BINARY_PATH = RUNTIME_DIR / SANDBOX_BINARY_NAME
SANDBOX_LIB_PATH = RUNTIME_DIR / SANDBOX_LIB_NAME


# ============================================================================
# Default values
# ============================================================================

DEFAULT_AUTO_APPROVE = [
    # Filesystem info
    "ls",
    "tree",
    "pwd",
    "file",
    "stat",
    "du",
    "df",
    # File viewing
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "tac",
    "nl",
    "zcat",
    "zless",
    # Search & filter
    "grep",
    "egrep",
    "fgrep",
    "find",
    "locate",
    "which",
    "whereis",
    "type",
    # Text processing (read-only, no -i flags)
    "wc",
    "sort",
    "uniq",
    "cut",
    "diff",
    "cmp",
    # Path introspection
    "realpath",
    "readlink",
    "basename",
    "dirname",
    # Process info
    "ps",
    "top",
    "htop",
    "pgrep",
    "pstree",
    "lsof",
    # System info
    "uname",
    "hostname",
    "uptime",
    "date",
    "free",
    "vmstat",
    "iostat",
    "mpstat",
    "sar",
    "lsblk",
    "lscpu",
    "lsmem",
    "lspci",
    "lsusb",
    "dmesg",
    # User info
    "whoami",
    "who",
    "w",
    "id",
    "groups",
    # Network diagnostics
    "ping",
    "traceroute",
    "mtr",
    "netstat",
    "ss",
    "ip addr",
    "ip route",
    "dig",
    "nslookup",
    "host",
    # Service status (read-only)
    "systemctl status",
    "systemctl is-active",
    "systemctl is-enabled",
    "systemctl list-units",
    "journalctl",
    "service --status-all",
    # Environment
    "env",
    "printenv",
    # Checksums
    "md5sum",
    "sha256sum",
    "sha1sum",
    "cksum",
    # Help
    "man",
    "help",
    "info",
]

DEFAULT_ALWAYS_DENY = [
    # Recursive destruction
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf .",
    "rm -rf ..",
    # Disk destruction
    "dd if=",
    "mkfs",
    "fdisk",
    "parted",
    "wipefs",
    # Fork bombs & resource exhaustion
    ":(){ :|:& };:",
    # Remote code execution
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
    "curl -s | sh",
    "curl -s | bash",
    "wget -q | sh",
    "wget -q | bash",
    # Permission bombs
    "chmod -R 777 /",
    "chmod -R 777 ~",
    "chown -R",
    # History destruction
    "history -c",
    "> /var/log",
    # System shutdown (should require human approval)
    "shutdown",
    "reboot",
    "poweroff",
    "init 0",
    "init 6",
]


# ============================================================================
# Command danger classification
# ============================================================================


class DangerLevel(Enum):
    """Danger classification for command display in TUI."""

    SAFE = "safe"  # Green/dim - matches auto_approve
    CAUTION = "caution"  # Yellow - state-modifying
    DANGER = "danger"  # Red - destructive
    UNKNOWN = "unknown"  # No color - unclassified


# Commands that modify system state but are not destructive (yellow in TUI)
STATE_MODIFYING_COMMANDS = {
    "chmod",
    "chown",
    "chgrp",
    "crontab",
    "groupadd",
    "groupdel",
    "init",
    "mount",
    "passwd",
    "service",
    "shutdown",
    "reboot",
    "umount",
    "useradd",
    "userdel",
    "usermod",
}

# Baseline destructive commands (red in TUI, supplements always_deny)
DESTRUCTIVE_COMMANDS = {
    "dd",
    "fdisk",
    "kill",
    "killall",
    "mkfs",
    "parted",
    "pkill",
    "rm",
    "rmdir",
    "shred",
    "truncate",
    "wipefs",
}


def _normalize_command(cmd: str) -> str:
    """
    Strip sudo, doas, and env vars for classification.

    Examples
    --------
    >>> _normalize_command("sudo rm -rf /tmp")
    'rm -rf /tmp'
    >>> _normalize_command("FOO=bar cat file")
    'cat file'
    """
    cmd = cmd.strip()
    if not cmd:
        return ""

    # Strip leading env vars: VAR=val cmd → cmd
    parts = cmd.split()
    while parts and "=" in parts[0] and not parts[0].startswith("-"):
        parts = parts[1:]

    if not parts:
        return ""

    cmd = " ".join(parts)

    # Strip sudo/doas prefix
    for prefix in ("sudo ", "doas "):
        if cmd.startswith(prefix):
            cmd = cmd[len(prefix) :]

    return cmd


def _extract_base_command(cmd: str) -> str:
    """
    Get base command name (first word after normalize, strip path).

    Examples
    --------
    >>> _extract_base_command("sudo /usr/bin/rm -rf /tmp")
    'rm'
    >>> _extract_base_command("cat file | grep foo")
    'cat'
    """
    normalized = _normalize_command(cmd)
    if not normalized:
        return ""

    # Take first command in pipeline
    if "|" in normalized:
        normalized = normalized.split("|")[0].strip()

    parts = normalized.split()
    if not parts:
        return ""

    first = parts[0]

    # Strip path: /usr/bin/cat → cat
    return first.rsplit("/", 1)[-1]


def _matches_deny_pattern(cmd: str, patterns: list[str]) -> bool:
    """
    Check if command matches any deny pattern (substring match).

    Examples
    --------
    >>> _matches_deny_pattern("rm -rf /", ["rm -rf /"])
    True
    >>> _matches_deny_pattern("rm -rf /tmp", ["rm -rf /"])
    False
    """
    normalized = _normalize_command(cmd)
    for pattern in patterns:
        if pattern in normalized:
            return True
    return False


def _matches_prefix(cmd: str, patterns: list[str]) -> bool:
    """
    Check if normalized command starts with any pattern.

    Examples
    --------
    >>> _matches_prefix("systemctl status nginx", ["systemctl status"])
    True
    >>> _matches_prefix("systemctl restart nginx", ["systemctl status"])
    False
    """
    normalized = _normalize_command(cmd)
    for pattern in patterns:
        if normalized.startswith(pattern):
            return True
    return False


def classify_command_danger(cmd: str, profile: ProfileConfig) -> DangerLevel:
    """
    Classify a command's danger level for TUI display.

    Classification precedence (first match wins):
    1. always_deny patterns (substring match) → DANGER
    2. DESTRUCTIVE_COMMANDS (base command) → DANGER
    3. STATE_MODIFYING_COMMANDS (base command) → CAUTION
    4. auto_approve patterns (prefix match) → SAFE
    5. Everything else → UNKNOWN

    Parameters
    ----------
    cmd
        The full command string to classify
    profile
        ProfileConfig with auto_approve and always_deny lists

    Returns
    -------
    DangerLevel
        The danger classification for display coloring
    """
    # 1. Check always_deny patterns (substring match)
    if _matches_deny_pattern(cmd, profile.always_deny):
        return DangerLevel.DANGER

    base = _extract_base_command(cmd)

    # 2. Check hardcoded destructive commands
    if base in DESTRUCTIVE_COMMANDS:
        return DangerLevel.DANGER

    # 3. Check state-modifying commands
    if base in STATE_MODIFYING_COMMANDS:
        return DangerLevel.CAUTION

    # 4. Check auto_approve (prefix match for multi-word patterns)
    if base in profile.auto_approve or _matches_prefix(cmd, profile.auto_approve):
        return DangerLevel.SAFE

    return DangerLevel.UNKNOWN


def _default_audit_events() -> dict[str, bool]:
    return {
        "session": True,
        "command": True,
        "file_write": True,
        "approval": True,
        "execution": True,
        "remote": True,
    }


# ============================================================================
# Configuration dataclasses
# ============================================================================


@dataclass
class ProfileConfig:
    """Command approval profile configuration."""

    auto_approve: list[str] = field(default_factory=lambda: DEFAULT_AUTO_APPROVE.copy())
    always_deny: list[str] = field(default_factory=lambda: DEFAULT_ALWAYS_DENY.copy())


@dataclass
class AuditConfig:
    """Audit logging configuration."""

    enabled: bool = True
    rotation: Literal["daily", "session", "none"] = "daily"
    max_files: int = 30
    events: dict[str, bool] = field(default_factory=_default_audit_events)
    log_dir: Path | None = None  # Override for testing

    @property
    def effective_log_dir(self) -> Path:
        """Return the audit log directory."""
        return self.log_dir if self.log_dir else AUDIT_DIR

    def is_event_enabled(self, event_type: str) -> bool:
        """Check if an event type is enabled based on category mapping."""
        # Map event types to categories
        category_map = {
            "session_created": "session",
            "session_loaded": "session",
            "session_status_changed": "session",
            "session_expired": "session",
            "command_decision": "command",
            "file_write_queued": "file_write",
            "file_write_executed": "file_write",
            "approval_decision": "approval",
            "execution_started": "execution",
            "execution_completed": "execution",
            "command_executed": "execution",
            "remote_connection": "remote",
            "remote_deployment": "remote",
        }
        category = category_map.get(event_type, "session")
        return self.events.get(category, True)


@dataclass
class Remote:
    """SSH remote target configuration."""

    host: str
    user: str
    port: int = 22

    @property
    def target_string(self) -> str:
        """Return user@host format."""
        return f"{self.user}@{self.host}"


@dataclass
class Config:
    """Unified shannot configuration."""

    profile: ProfileConfig = field(default_factory=ProfileConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)
    remotes: dict[str, Remote] = field(default_factory=dict)


# ============================================================================
# Config file loading and saving
# ============================================================================


def find_project_root() -> Path | None:
    """Walk up from cwd to find .shannot directory."""
    current = Path.cwd()
    while current != current.parent:
        shannot_dir = current / ".shannot"
        if shannot_dir.is_dir():
            return shannot_dir
        current = current.parent
    return None


def get_config_path() -> Path | None:
    """
    Get config path with precedence.

    1. .shannot/config.toml in project root
    2. ~/.config/shannot/config.toml (global)

    Returns path if exists, None otherwise.
    """
    # Check project-local first
    project_dir = find_project_root()
    if project_dir:
        project_config = project_dir / CONFIG_FILENAME
        if project_config.exists():
            return project_config

    # Fall back to global
    global_config = CONFIG_DIR / CONFIG_FILENAME
    if global_config.exists():
        return global_config

    return None


def load_config() -> Config:
    """
    Load unified configuration from TOML file.

    Profile and audit settings use precedence:
    1. .shannot/config.toml (project-local)
    2. ~/.config/shannot/config.toml (global)

    Remotes are always loaded from global config only (not project-local).

    Returns Config with defaults if no config file found.
    """
    config_path = get_config_path()

    # Load profile and audit from first available config
    profile = ProfileConfig()
    audit = AuditConfig()

    if config_path:
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            # Parse profile section
            profile_data = data.get("profile", {})
            profile = ProfileConfig(
                auto_approve=profile_data.get("auto_approve", DEFAULT_AUTO_APPROVE.copy()),
                always_deny=profile_data.get("always_deny", DEFAULT_ALWAYS_DENY.copy()),
            )

            # Parse audit section
            audit_data = data.get("audit", {})
            audit = AuditConfig(
                enabled=audit_data.get("enabled", True),
                rotation=audit_data.get("rotation", "daily"),
                max_files=audit_data.get("max_files", 30),
                events=audit_data.get("events", _default_audit_events()),
            )
        except (OSError, tomllib.TOMLDecodeError):
            pass  # Use defaults

    # Remotes are always loaded from global config only
    remotes: dict[str, Remote] = {}
    global_config = CONFIG_DIR / CONFIG_FILENAME
    if global_config.exists():
        try:
            with open(global_config, "rb") as f:
                global_data = tomllib.load(f)
            for name, remote_data in global_data.get("remotes", {}).items():
                remotes[name] = Remote(
                    host=remote_data.get("host", ""),
                    user=remote_data.get("user", getpass.getuser()),
                    port=remote_data.get("port", 22),
                )
        except (OSError, tomllib.TOMLDecodeError):
            pass  # No remotes

    return Config(profile=profile, audit=audit, remotes=remotes)


def save_config(config: Config) -> None:
    """
    Save unified configuration to global TOML file.

    Uses manual TOML formatting to avoid tomli-w dependency.
    Always writes to ~/.config/shannot/config.toml.
    """
    config_path = CONFIG_DIR / CONFIG_FILENAME
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Shannot configuration", "# https://github.com/corv89/shannot", ""]

    # Profile section
    lines.append("[profile]")
    lines.append(_toml_array("auto_approve", config.profile.auto_approve))
    lines.append(_toml_array("always_deny", config.profile.always_deny))
    lines.append("")

    # Audit section
    lines.append("[audit]")
    lines.append(f"enabled = {str(config.audit.enabled).lower()}")
    lines.append(f'rotation = "{config.audit.rotation}"')
    lines.append(f"max_files = {config.audit.max_files}")
    lines.append("")
    lines.append("[audit.events]")
    for event_name, enabled in sorted(config.audit.events.items()):
        lines.append(f"{event_name} = {str(enabled).lower()}")
    lines.append("")

    # Remotes section
    for name, remote in sorted(config.remotes.items()):
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

    config_path.write_text("\n".join(lines))


def _toml_array(key: str, values: list[str]) -> str:
    """Format a TOML array on a single line."""
    escaped = [f'"{v}"' for v in values]
    return f"{key} = [{', '.join(escaped)}]"


# ============================================================================
# Remote management helpers
# ============================================================================


def add_remote(name: str, host: str, user: str | None = None, port: int = 22) -> Remote:
    """
    Add a new remote to the configuration.

    Parameters
    ----------
    name
        Unique name for the remote
    host
        Hostname or IP address
    user
        SSH user (defaults to current user)
    port
        SSH port (defaults to 22)

    Returns
    -------
    Remote
        The created Remote object.

    Raises
    ------
    ValueError
        If remote name already exists.
    """
    config = load_config()
    if name in config.remotes:
        raise ValueError(f"Remote '{name}' already exists. Use 'remote remove' first.")

    remote = Remote(
        host=host,
        user=user or getpass.getuser(),
        port=port,
    )
    config.remotes[name] = remote
    save_config(config)
    return remote


def remove_remote(name: str) -> bool:
    """
    Remove a remote from the configuration.

    Returns
    -------
    bool
        True if remote was removed, False if it didn't exist.
    """
    config = load_config()
    if name not in config.remotes:
        return False
    del config.remotes[name]
    save_config(config)
    return True


def resolve_target(target: str) -> tuple[str, str, int]:
    """
    Resolve a target string to (user, host, port) tuple.

    Supports:
    - Named remotes from config (e.g., "prod")
    - user@host format (e.g., "admin@prod.example.com")
    - host-only format (e.g., "prod.example.com") - uses current user
    - user@host:port format (e.g., "admin@prod.example.com:2222")

    Returns
    -------
    tuple[str, str, int]
        Tuple of (user, host, port)
    """
    # Check if it's a saved remote name
    config = load_config()
    if target in config.remotes:
        r = config.remotes[target]
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


# ============================================================================
# Convenience functions for backward compatibility
# ============================================================================


def load_remotes() -> dict[str, Remote]:
    """Load remotes from config. Convenience wrapper around load_config()."""
    return load_config().remotes


def load_audit_config() -> AuditConfig:
    """Load audit config. Convenience wrapper around load_config()."""
    return load_config().audit
