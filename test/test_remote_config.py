"""Tests for remote configuration management."""

import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from shannot.config import (
    Config,
    Remote,
    add_remote,
    load_remotes,
    remove_remote,
    resolve_target,
    save_config,
)


class TestRemote:
    """Tests for Remote dataclass."""

    def test_target_string(self):
        r = Remote(host="example.com", user="admin", port=22)
        assert r.target_string == "admin@example.com"

    def test_default_port(self):
        r = Remote(host="example.com", user="admin")
        assert r.port == 22


class TestRemotesConfig:
    """Tests for config.toml file operations."""

    def setup_method(self):
        """Create temp config directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir_patch = mock.patch("shannot.config.CONFIG_DIR", Path(self.tmpdir))
        self.config_dir_patch.start()

    def teardown_method(self):
        """Clean up temp directory."""
        self.config_dir_patch.stop()
        shutil.rmtree(self.tmpdir)

    def test_load_empty(self):
        """Loading non-existent file returns empty dict."""
        remotes = load_remotes()
        assert remotes == {}

    def test_save_and_load(self):
        """Round-trip save and load."""
        config = Config()
        config.remotes = {
            "prod": Remote(host="prod.example.com", user="admin", port=22),
            "staging": Remote(host="staging.example.com", user="deploy", port=2222),
        }
        save_config(config)
        loaded = load_remotes()

        assert len(loaded) == 2
        assert loaded["prod"].host == "prod.example.com"
        assert loaded["prod"].user == "admin"
        assert loaded["prod"].port == 22
        assert loaded["staging"].port == 2222

    def test_add_remote(self):
        """Adding a remote persists it."""
        remote = add_remote("prod", "prod.example.com", user="admin")

        assert remote.host == "prod.example.com"
        assert remote.user == "admin"
        assert remote.port == 22

        # Verify persistence
        loaded = load_remotes()
        assert "prod" in loaded
        assert loaded["prod"].host == "prod.example.com"

    def test_add_remote_with_port(self):
        """Adding a remote with custom port."""
        remote = add_remote("staging", "staging.example.com", user="deploy", port=2222)

        assert remote.port == 2222

        loaded = load_remotes()
        assert loaded["staging"].port == 2222

    def test_add_duplicate_fails(self):
        """Cannot add remote with existing name."""
        add_remote("prod", "example.com")

        with pytest.raises(ValueError, match="already exists"):
            add_remote("prod", "other.com")

    def test_remove_remote(self):
        """Removing a remote deletes it."""
        add_remote("prod", "example.com")
        assert remove_remote("prod") is True
        assert load_remotes() == {}

    def test_remove_nonexistent(self):
        """Removing non-existent remote returns False."""
        assert remove_remote("nonexistent") is False


class TestResolveTarget:
    """Tests for resolve_target function."""

    def setup_method(self):
        """Create temp config directory."""
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir_patch = mock.patch("shannot.config.CONFIG_DIR", Path(self.tmpdir))
        self.config_dir_patch.start()

    def teardown_method(self):
        """Clean up temp directory."""
        self.config_dir_patch.stop()
        shutil.rmtree(self.tmpdir)

    def test_resolve_named_remote(self):
        """Resolves saved remote by name."""
        add_remote("prod", "prod.example.com", user="admin", port=2222)

        user, host, port = resolve_target("prod")

        assert user == "admin"
        assert host == "prod.example.com"
        assert port == 2222

    def test_resolve_user_at_host(self):
        """Resolves user@host format."""
        user, host, port = resolve_target("admin@example.com")

        assert user == "admin"
        assert host == "example.com"
        assert port == 22

    def test_resolve_user_at_host_port(self):
        """Resolves user@host:port format."""
        user, host, port = resolve_target("admin@example.com:2222")

        assert user == "admin"
        assert host == "example.com"
        assert port == 2222

    @mock.patch("shannot.config.getpass.getuser", return_value="testuser")
    def test_resolve_host_only(self, mock_getuser):
        """Resolves host-only format with current user."""
        user, host, port = resolve_target("example.com")

        assert user == "testuser"
        assert host == "example.com"
        assert port == 22

    def test_resolve_invalid_port_uses_default(self):
        """Invalid port string falls back to default port."""
        user, host, port = resolve_target("admin@example.com:notaport")

        assert user == "admin"
        assert host == "example.com"
        assert port == 22

    def test_named_remote_takes_precedence(self):
        """Named remote takes precedence over hostname parsing."""
        # Add a remote with a name that looks like a hostname
        add_remote("example.com", "real-host.internal", user="admin", port=2222)

        user, host, port = resolve_target("example.com")

        # Should resolve to the saved remote, not parse as hostname
        assert user == "admin"
        assert host == "real-host.internal"
        assert port == 2222
