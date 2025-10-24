"""Configuration management for Shannot.

This module handles loading and managing executor configurations from TOML files.
"""

import os
import sys
from pathlib import Path
from typing import Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(  # type: ignore[unreachable]
            "tomli is required for Python < 3.11. Install with: pip install tomli"
        ) from exc

from pydantic import BaseModel, Field, field_validator

from .execution import SandboxExecutor

ExecutorType = Literal["local", "ssh"]


class ExecutorConfig(BaseModel):
    """Base configuration for an executor."""

    type: ExecutorType
    profile: str | None = None  # Default profile for this executor


class LocalExecutorConfig(ExecutorConfig):
    """Configuration for local executor."""

    type: Literal["local"] = "local"  # type: ignore[assignment]
    bwrap_path: Path | None = None  # Explicit path to bwrap if needed


class SSHExecutorConfig(ExecutorConfig):
    """Configuration for SSH executor."""

    type: Literal["ssh"] = "ssh"  # type: ignore[assignment]
    host: str
    username: str | None = None
    key_file: Path | None = None
    port: int = 22
    connection_pool_size: int = 5
    known_hosts: Path | None = None
    strict_host_key: bool = True

    @field_validator("key_file", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path | None) -> Path | None:
        """Expand ~ in paths."""
        if v is None:
            return None
        path = Path(v)
        return path.expanduser()

    @field_validator("known_hosts", mode="before")
    @classmethod
    def expand_known_hosts(cls, v: str | Path | None) -> Path | None:
        """Expand ~ in known_hosts paths."""
        if v is None:
            return None
        return Path(v).expanduser()


class ShannotConfig(BaseModel):
    """Complete Shannot configuration."""

    default_executor: str = "local"
    executor: dict[str, LocalExecutorConfig | SSHExecutorConfig] = Field(default_factory=dict)

    def get_executor_config(
        self, name: str | None = None
    ) -> LocalExecutorConfig | SSHExecutorConfig:
        """Get executor config by name, or default if name is None."""
        executor_name = name or self.default_executor

        if executor_name not in self.executor:
            available = ", ".join(self.executor.keys())
            raise ValueError(
                f"Executor '{executor_name}' not found in config. Available executors: {available}"
            )

        return self.executor[executor_name]


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
        return ShannotConfig.model_validate(data)
    except Exception as e:
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

    # Convert to TOML format manually (Pydantic doesn't have TOML export)
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
        raise ValueError(f"Unknown executor type: {executor_config.type}")


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
