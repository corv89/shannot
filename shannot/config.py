"""Configuration management for Shannot.

This module handles loading and managing executor configurations from TOML files.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(  # type: ignore[unreachable]
            "tomli is required for Python < 3.11. Install with: pip install tomli"
        ) from exc

from .execution import SandboxExecutor
from .validation import (
    ValidationError,
    validate_bool,
    validate_int_range,
    validate_literal,
    validate_path,
    validate_type,
)

ExecutorType = Literal["local", "ssh"]


@dataclass
class ExecutorConfig:
    """Base configuration for an executor."""

    type: ExecutorType
    profile: str | None = None  # Default profile for this executor

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutorConfig":
        """Create ExecutorConfig from dictionary.

        Args:
            data: Dictionary containing configuration

        Returns:
            ExecutorConfig instance

        Raises:
            ValidationError: If validation fails
        """
        # Discriminate based on type field
        exec_type = data.get("type")
        if exec_type == "local":
            return LocalExecutorConfig.from_dict(data)
        elif exec_type == "ssh":
            return SSHExecutorConfig.from_dict(data)
        else:
            raise ValidationError(
                f"type must be 'local' or 'ssh', got {exec_type!r}",
                "type",
            )


@dataclass
class LocalExecutorConfig(ExecutorConfig):
    """Configuration for local executor."""

    type: Literal["local"] = "local"  # type: ignore[assignment]
    bwrap_path: Path | None = None  # Explicit path to bwrap if needed

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocalExecutorConfig":
        """Create LocalExecutorConfig from dictionary.

        Args:
            data: Dictionary containing configuration

        Returns:
            LocalExecutorConfig instance

        Raises:
            ValidationError: If validation fails
        """
        exec_type = data.get("type", "local")
        validate_literal(exec_type, ("local",), "type")

        profile = data.get("profile")
        if profile is not None:
            validate_type(profile, str, "profile")

        bwrap_path_raw = data.get("bwrap_path")
        bwrap_path = (
            validate_path(bwrap_path_raw, "bwrap_path", expand=True) if bwrap_path_raw else None
        )

        return cls(
            type="local",
            profile=profile,
            bwrap_path=bwrap_path,
        )


@dataclass
class SSHExecutorConfig(ExecutorConfig):
    """Configuration for SSH executor."""

    type: Literal["ssh"] = "ssh"  # type: ignore[assignment]
    host: str = ""
    username: str | None = None
    key_file: Path | None = None
    port: int = 22
    connection_pool_size: int = 5
    known_hosts: Path | None = None
    strict_host_key: bool = True

    def __post_init__(self):
        """Expand paths after initialization."""
        if self.key_file is not None:
            self.key_file = self.key_file.expanduser()
        if self.known_hosts is not None:
            self.known_hosts = self.known_hosts.expanduser()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SSHExecutorConfig":
        """Create SSHExecutorConfig from dictionary.

        Args:
            data: Dictionary containing configuration

        Returns:
            SSHExecutorConfig instance

        Raises:
            ValidationError: If validation fails
        """
        exec_type = data.get("type", "ssh")
        validate_literal(exec_type, ("ssh",), "type")

        profile = data.get("profile")
        if profile is not None:
            validate_type(profile, str, "profile")

        host = data.get("host")
        if not host:
            raise ValidationError("host is required for SSH executor", "host")
        validate_type(host, str, "host")

        username = data.get("username")
        if username is not None:
            validate_type(username, str, "username")

        key_file_raw = data.get("key_file")
        key_file = validate_path(key_file_raw, "key_file", expand=True) if key_file_raw else None

        port = data.get("port", 22)
        validate_int_range(port, "port", min_val=1, max_val=65535)

        connection_pool_size = data.get("connection_pool_size", 5)
        validate_int_range(connection_pool_size, "connection_pool_size", min_val=1)

        known_hosts_raw = data.get("known_hosts")
        known_hosts = (
            validate_path(known_hosts_raw, "known_hosts", expand=True) if known_hosts_raw else None
        )

        strict_host_key = data.get("strict_host_key", True)
        validate_bool(strict_host_key, "strict_host_key")

        return cls(
            type="ssh",
            profile=profile,
            host=host,
            username=username,
            key_file=key_file,
            port=port,
            connection_pool_size=connection_pool_size,
            known_hosts=known_hosts,
            strict_host_key=strict_host_key,
        )


@dataclass
class ShannotConfig:
    """Complete Shannot configuration."""

    default_executor: str = "local"
    executor: dict[str, LocalExecutorConfig | SSHExecutorConfig] = field(default_factory=dict)

    def get_executor_config(
        self, name: str | None = None
    ) -> LocalExecutorConfig | SSHExecutorConfig:
        """Get executor config by name, or default if name is None."""
        executor_name = name or self.default_executor

        if executor_name not in self.executor:
            available = ", ".join(self.executor.keys())
            raise ValidationError(
                f"'{executor_name}' not found. Available executors: {available}", "executor"
            )

        return self.executor[executor_name]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShannotConfig":
        """Create ShannotConfig from dictionary.

        Args:
            data: Dictionary containing configuration

        Returns:
            ShannotConfig instance

        Raises:
            ValidationError: If validation fails
        """
        default_executor = data.get("default_executor", "local")
        validate_type(default_executor, str, "default_executor")

        executor_data = data.get("executor", {})
        if not isinstance(executor_data, dict):
            raise ValidationError(
                f"expected dict, got {type(executor_data).__name__}",
                "executor",
            )

        executors: dict[str, LocalExecutorConfig | SSHExecutorConfig] = {}
        for name, exec_config_data in executor_data.items():
            if not isinstance(name, str):
                raise ValidationError(
                    f"executor keys must be strings, got {type(name).__name__}",
                    "executor",
                )
            if not isinstance(exec_config_data, dict):
                raise ValidationError(
                    f"executor values must be dicts, got {type(exec_config_data).__name__}",
                    f"executor.{name}",
                )

            try:
                executors[name] = ExecutorConfig.from_dict(exec_config_data)  # type: ignore[assignment]
            except ValidationError as e:
                # Re-raise with context about which executor failed
                raise ValidationError(str(e), f"executor.{name}") from e

        return cls(
            default_executor=default_executor,
            executor=executors,
        )


def get_config_path() -> Path:
    """Get the path to the Shannot config file.

    Returns:
        Path to ~/.config/shannot/config.toml (or Windows/macOS equivalent)
    """
    if sys.platform == "win32":
        config_dir = Path.home() / "AppData" / "Local" / "shannot"
    elif sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "shannot"
    else:
        # Linux and other Unix-like systems
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
        config_dir = xdg_config / "shannot"

    return config_dir / "config.toml"


def load_config(config_path: Path | None = None) -> ShannotConfig:
    """Load Shannot configuration from TOML file.

    Args:
        config_path: Optional path to config file. If not provided, uses default.

    Returns:
        Loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        # Return default config (local only)
        return ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )

    try:
        with open(config_path, "rb") as f:
            data: dict[str, object] = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse config file {config_path}: {e}") from e

    try:
        return ShannotConfig.from_dict(data)  # type: ignore[arg-type]
    except ValidationError as e:
        raise ValueError(f"Invalid config file {config_path}: {e}") from e


def save_config(config: ShannotConfig, config_path: Path | None = None) -> None:
    """Save Shannot configuration to TOML file.

    Args:
        config: Configuration to save
        config_path: Optional path to config file. If not provided, uses default.
    """
    if config_path is None:
        config_path = get_config_path()

    # Ensure directory exists
    _ = config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to TOML format manually
    lines = [
        f'default_executor = "{config.default_executor}"',
        "",
    ]

    for name, executor_config in config.executor.items():
        lines.append(f"[executor.{name}]")
        lines.append(f'type = "{executor_config.type}"')

        if executor_config.profile:
            lines.append(f'profile = "{executor_config.profile}"')

        if isinstance(executor_config, SSHExecutorConfig):
            lines.append(f'host = "{executor_config.host}"')
            if executor_config.username:
                lines.append(f'username = "{executor_config.username}"')
            if executor_config.key_file:
                lines.append(f'key_file = "{executor_config.key_file}"')
            if executor_config.port != 22:
                lines.append(f"port = {executor_config.port}")
            if executor_config.connection_pool_size != 5:
                lines.append(f"connection_pool_size = {executor_config.connection_pool_size}")
            if executor_config.known_hosts:
                lines.append(f'known_hosts = "{executor_config.known_hosts}"')
            if not executor_config.strict_host_key:
                lines.append("strict_host_key = false")
        elif isinstance(executor_config, LocalExecutorConfig):
            if executor_config.bwrap_path:
                lines.append(f'bwrap_path = "{executor_config.bwrap_path}"')

        lines.append("")

    with open(config_path, "w") as f:
        f.write("\n".join(lines))


def create_executor(config: ShannotConfig, executor_name: str | None = None) -> SandboxExecutor:
    """Create an executor from configuration.

    Args:
        config: Shannot configuration
        executor_name: Name of executor to create, or None for default

    Returns:
        Initialized executor

    Raises:
        ValueError: If executor config is invalid or executor not found
    """
    executor_config = config.get_executor_config(executor_name)

    if executor_config.type == "local":
        from .executors import LocalExecutor

        return LocalExecutor(bwrap_path=executor_config.bwrap_path)
    elif executor_config.type == "ssh":
        try:
            from .executors import SSHExecutor
        except ImportError as exc:
            message = (
                "SSH executor requires the 'asyncssh' dependency. "
                "Install with: pip install shannot[remote]"
            )
            raise RuntimeError(message) from exc

        return SSHExecutor(
            host=executor_config.host,
            username=executor_config.username,
            key_file=executor_config.key_file,
            port=executor_config.port,
            connection_pool_size=executor_config.connection_pool_size,
            known_hosts=executor_config.known_hosts,
            strict_host_key=executor_config.strict_host_key,
        )
    else:
        raise ValidationError(f"Unknown executor type: {executor_config.type}", "type")


def get_executor(
    executor_name: str | None = None, config_path: Path | None = None
) -> SandboxExecutor:
    """Convenience function to load config and create executor.

    Args:
        executor_name: Name of executor to create, or None for default
        config_path: Optional path to config file

    Returns:
        Initialized executor
    """
    config = load_config(config_path)
    return create_executor(config, executor_name)
