"""Tests for configuration management."""

import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("pydantic")

from shannot.config import (
    LocalExecutorConfig,
    ShannotConfig,
    SSHExecutorConfig,
    create_executor,
    get_config_path,
    load_config,
    save_config,
)


class TestExecutorConfig:
    """Tests for executor configuration models."""

    def test_local_executor_config(self):
        """Test local executor configuration."""
        config = LocalExecutorConfig(type="local")
        assert config.type == "local"
        assert config.profile is None
        assert config.bwrap_path is None

    def test_local_executor_config_with_bwrap_path(self):
        """Test local executor with explicit bwrap path."""
        config = LocalExecutorConfig(type="local", bwrap_path=Path("/usr/bin/bwrap"))
        assert config.bwrap_path == Path("/usr/bin/bwrap")

    def test_ssh_executor_config(self):
        """Test SSH executor configuration."""
        config = SSHExecutorConfig(
            type="ssh",
            host="example.com",
            username="user",
            key_file=Path("~/.ssh/id_rsa"),
            port=22,
            known_hosts=Path("~/.ssh/known_hosts"),
            strict_host_key=False,
        )
        assert config.type == "ssh"
        assert config.host == "example.com"
        assert config.username == "user"
        assert config.port == 22
        # Key file should be expanded
        assert config.key_file == Path.home() / ".ssh" / "id_rsa"
        assert config.known_hosts == Path.home() / ".ssh" / "known_hosts"
        assert config.strict_host_key is False

    def test_ssh_executor_config_defaults(self):
        """Test SSH executor with default values."""
        config = SSHExecutorConfig(type="ssh", host="example.com")
        assert config.username is None
        assert config.key_file is None
        assert config.port == 22
        assert config.connection_pool_size == 5
        assert config.known_hosts is None
        assert config.strict_host_key is True

    def test_ssh_executor_config_path_expansion(self):
        """Test that paths are expanded."""
        config = SSHExecutorConfig(
            type="ssh",
            host="example.com",
            key_file=Path("~/test/key"),
            known_hosts=Path("~/test/known_hosts"),
        )
        assert config.key_file == Path.home() / "test" / "key"
        assert config.known_hosts == Path.home() / "test" / "known_hosts"


class TestShannotConfig:
    """Tests for main Shannot configuration."""

    def test_empty_config(self):
        """Test empty configuration."""
        config = ShannotConfig()
        assert config.default_executor == "local"
        assert config.executor == {}

    def test_config_with_executors(self):
        """Test configuration with multiple executors."""
        config = ShannotConfig(
            default_executor="local",
            executor={
                "local": LocalExecutorConfig(type="local"),
                "prod": SSHExecutorConfig(type="ssh", host="prod.example.com"),
            },
        )
        assert config.default_executor == "local"
        assert "local" in config.executor
        assert "prod" in config.executor

    def test_get_executor_config_default(self):
        """Test getting default executor config."""
        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )
        executor_config = config.get_executor_config()
        assert executor_config.type == "local"

    def test_get_executor_config_by_name(self):
        """Test getting executor config by name."""
        config = ShannotConfig(
            default_executor="local",
            executor={
                "local": LocalExecutorConfig(type="local"),
                "prod": SSHExecutorConfig(type="ssh", host="prod.example.com"),
            },
        )
        executor_config = config.get_executor_config("prod")
        assert executor_config.type == "ssh"
        assert executor_config.host == "prod.example.com"

    def test_get_executor_config_not_found(self):
        """Test getting non-existent executor."""
        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )
        with pytest.raises(ValueError, match="Executor 'prod' not found"):
            config.get_executor_config("prod")


class TestConfigPath:
    """Tests for configuration path resolution."""

    @patch("sys.platform", "linux")
    def test_config_path_linux(self):
        """Test config path on Linux."""
        path = get_config_path()
        expected = Path.home() / ".config" / "shannot" / "config.toml"
        assert path == expected

    @patch("sys.platform", "darwin")
    def test_config_path_macos(self):
        """Test config path on macOS."""
        path = get_config_path()
        expected = Path.home() / "Library" / "Application Support" / "shannot" / "config.toml"
        assert path == expected

    @patch("sys.platform", "win32")
    def test_config_path_windows(self):
        """Test config path on Windows."""
        path = get_config_path()
        expected = Path.home() / "AppData" / "Local" / "shannot" / "config.toml"
        assert path == expected


class TestLoadSaveConfig:
    """Tests for loading and saving configuration."""

    def test_load_config_nonexistent(self, tmp_path):
        """Test loading when config file doesn't exist."""
        config_path = tmp_path / "config.toml"
        config = load_config(config_path)

        # Should return default config
        assert config.default_executor == "local"
        assert "local" in config.executor
        assert config.executor["local"].type == "local"

    def test_save_and_load_config(self, tmp_path):
        """Test saving and loading configuration."""
        config_path = tmp_path / "config.toml"

        # Create config
        original_config = ShannotConfig(
            default_executor="local",
            executor={
                "local": LocalExecutorConfig(type="local"),
                "prod": SSHExecutorConfig(
                    type="ssh",
                    host="prod.example.com",
                    username="admin",
                    key_file=Path("/home/user/.ssh/id_rsa"),
                    port=22,
                    known_hosts=Path("/home/user/.ssh/known_hosts"),
                    strict_host_key=False,
                ),
            },
        )

        # Save
        save_config(original_config, config_path)
        assert config_path.exists()

        # Load
        loaded_config = load_config(config_path)
        assert loaded_config.default_executor == "local"
        assert "local" in loaded_config.executor
        assert "prod" in loaded_config.executor

        prod_config = loaded_config.executor["prod"]
        assert prod_config.type == "ssh"
        assert prod_config.host == "prod.example.com"
        assert prod_config.username == "admin"
        assert prod_config.known_hosts == Path("/home/user/.ssh/known_hosts")
        assert prod_config.strict_host_key is False

    def test_save_config_creates_directory(self, tmp_path):
        """Test that save_config creates parent directories."""
        config_path = tmp_path / "subdir" / "config.toml"
        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )

        save_config(config, config_path)
        assert config_path.exists()
        assert config_path.parent.exists()

    def test_load_invalid_toml(self, tmp_path):
        """Test loading invalid TOML file."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("invalid { toml")

        with pytest.raises(ValueError, match="Failed to parse config"):
            load_config(config_path)

    def test_load_invalid_schema(self, tmp_path):
        """Test loading TOML with invalid schema."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("default_executor = 123\n")  # Should be string

        with pytest.raises(ValueError, match="Invalid config"):
            load_config(config_path)


@pytest.mark.skipif(sys.platform != "linux", reason="LocalExecutor requires Linux")
class TestCreateExecutor:
    """Tests for executor creation from configuration."""

    def test_create_local_executor(self):
        """Test creating local executor."""
        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )

        executor = create_executor(config, "local")
        from shannot.executors import LocalExecutor

        assert isinstance(executor, LocalExecutor)

    def test_create_local_executor_default(self):
        """Test creating default executor."""
        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )

        executor = create_executor(config)
        from shannot.executors import LocalExecutor

        assert isinstance(executor, LocalExecutor)

    def test_create_ssh_executor(self):
        """Test creating SSH executor."""
        config = ShannotConfig(
            default_executor="local",
            executor={
                "prod": SSHExecutorConfig(
                    type="ssh",
                    host="prod.example.com",
                    username="admin",
                ),
            },
        )

        executor = create_executor(config, "prod")
        from shannot.executors import SSHExecutor

        assert isinstance(executor, SSHExecutor)

    def test_create_executor_not_found(self):
        """Test creating non-existent executor."""
        config = ShannotConfig(
            default_executor="local",
            executor={"local": LocalExecutorConfig(type="local")},
        )

        with pytest.raises(ValueError, match="Executor 'prod' not found"):
            create_executor(config, "prod")


class TestCreateExecutorErrors:
    """Test error handling when creating executors."""

    def test_create_ssh_executor_missing_asyncssh(self, monkeypatch):
        """Ensure helpful message when asyncssh is unavailable."""
        config = ShannotConfig(
            default_executor="local",
            executor={
                "prod": SSHExecutorConfig(
                    type="ssh",
                    host="prod.example.com",
                ),
            },
        )

        fake_module = types.ModuleType("shannot.executors")
        fake_module.__file__ = "shannot/executors/__init__.py"
        monkeypatch.setitem(sys.modules, "shannot.executors", fake_module)

        with pytest.raises(RuntimeError, match="pip install shannot\\[remote\\]"):
            create_executor(config, "prod")

        monkeypatch.delitem(sys.modules, "shannot.executors", raising=False)


class TestConfigRoundTrip:
    """Tests for configuration round-trip (save → load → save)."""

    def test_roundtrip_preserves_data(self, tmp_path):
        """Test that saving and loading preserves all data."""
        config_path = tmp_path / "config.toml"

        original = ShannotConfig(
            default_executor="prod",
            executor={
                "local": LocalExecutorConfig(type="local"),
                "prod": SSHExecutorConfig(
                    type="ssh",
                    host="prod.example.com",
                    username="admin",
                    key_file=Path("/home/user/.ssh/id_rsa"),
                    port=2222,
                    connection_pool_size=10,
                    profile="diagnostics",
                    known_hosts=Path("/home/user/.ssh/known_hosts"),
                    strict_host_key=False,
                ),
                "staging": SSHExecutorConfig(
                    type="ssh",
                    host="staging.example.com",
                    strict_host_key=True,
                ),
            },
        )

        # Save
        save_config(original, config_path)

        # Load
        loaded = load_config(config_path)

        # Verify
        assert loaded.default_executor == "prod"
        assert set(loaded.executor.keys()) == {"local", "prod", "staging"}

        prod = loaded.executor["prod"]
        assert isinstance(prod, SSHExecutorConfig)
        assert prod.host == "prod.example.com"
        assert prod.username == "admin"
        assert prod.port == 2222
        assert prod.connection_pool_size == 10
        assert prod.profile == "diagnostics"
        assert prod.known_hosts == Path("/home/user/.ssh/known_hosts")
        assert prod.strict_host_key is False

        staging = loaded.executor["staging"]
        assert isinstance(staging, SSHExecutorConfig)
        assert staging.host == "staging.example.com"
        assert staging.username is None
        assert staging.port == 22  # default
        assert staging.strict_host_key is True

    def test_roundtrip_toml_format(self, tmp_path):
        """Test that generated TOML is well-formatted."""
        config_path = tmp_path / "config.toml"

        config = ShannotConfig(
            default_executor="local",
            executor={
                "local": LocalExecutorConfig(type="local"),
                "prod": SSHExecutorConfig(
                    type="ssh",
                    host="prod.example.com",
                    username="admin",
                ),
            },
        )

        save_config(config, config_path)

        # Check TOML content
        content = config_path.read_text()
        assert 'default_executor = "local"' in content
        assert "[executor.local]" in content
        assert 'type = "local"' in content
        assert "[executor.prod]" in content
        assert 'type = "ssh"' in content
        assert 'host = "prod.example.com"' in content
        assert 'username = "admin"' in content
