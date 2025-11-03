"""Tests for `shannot mcp install` command."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("pydantic")

from shannot.cli import _handle_mcp_install  # noqa: E402


class DummyArgs(Namespace):
    """Simple namespace mimicking argparse Namespace."""

    def __init__(self, **kwargs: object):
        defaults: dict[str, object] = {
            "target": None,
            "client": "claude-desktop",
            "config_path": None,
            "yes": False,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _patch_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect Path.home() to a temporary directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


def test_mcp_install_uses_absolute_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """When shannot-mcp is discoverable, its absolute path is written."""
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: "/opt/tools/shannot-mcp")
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.delenv("SSH_AGENT_PID", raising=False)

    config_file = (
        tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    )

    assert _handle_mcp_install(DummyArgs(target=None)) == 0

    data = json.loads(config_file.read_text())
    assert data["mcpServers"]["shannot"]["command"] == "/opt/tools/shannot-mcp"
    assert data["mcpServers"]["shannot"]["args"] == []
    assert "env" not in data["mcpServers"]["shannot"]


def test_mcp_install_falls_back_to_python_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """If binary is missing, fallback to `python -m shannot.mcp_main`."""
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: None)
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.delenv("SSH_AGENT_PID", raising=False)

    config_file = (
        tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    )

    result = _handle_mcp_install(DummyArgs(target=None))
    assert result == 0

    data = json.loads(config_file.read_text())
    assert data["mcpServers"]["shannot"]["command"] == sys.executable
    assert data["mcpServers"]["shannot"]["args"] == ["-m", "shannot.mcp_main"]
    assert "env" not in data["mcpServers"]["shannot"]


def test_mcp_install_with_target_appends_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Ensure --target is appended whether using binary or fallback."""
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    # Simulate fallback path so args already populated
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: None)
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/agent.sock")
    monkeypatch.setenv("SSH_AGENT_PID", "12345")

    dummy_config = SimpleNamespace(
        executor={
            "remote": SimpleNamespace(profile="minimal"),
        },
        default_executor="local",
    )

    monkeypatch.setattr("shannot.config.load_config", lambda: dummy_config)
    monkeypatch.setattr(
        "shannot.config.create_executor",
        lambda _config, _name: object(),
        raising=False,
    )

    config_file = (
        tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    )

    assert _handle_mcp_install(DummyArgs(target="remote")) == 0

    data = json.loads(config_file.read_text())
    assert data["mcpServers"]["shannot"]["command"] == sys.executable
    assert data["mcpServers"]["shannot"]["args"] == ["-m", "shannot.mcp_main", "--target", "remote"]
    assert data["mcpServers"]["shannot"]["env"] == {
        "SSH_AUTH_SOCK": "/tmp/agent.sock",
        "SSH_AGENT_PID": "12345",
    }


def test_mcp_install_supports_claude_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Installing for Claude Code should target the CLI user config."""
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: "/opt/tools/shannot-mcp")
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.delenv("SSH_AGENT_PID", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    # Claude Code uses CLI user config at ~/.claude.json
    config_file = tmp_path / ".claude.json"

    assert _handle_mcp_install(DummyArgs(client="claude-code")) == 0

    data = json.loads(config_file.read_text())
    assert data["mcpServers"]["shannot"]["type"] == "stdio"
    assert data["mcpServers"]["shannot"]["command"] == "/opt/tools/shannot-mcp"
    assert data["mcpServers"]["shannot"]["args"] == []


def test_mcp_install_claude_code_prefers_existing_alternate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Claude Code CLI config preserves existing configuration."""
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: "/opt/tools/shannot-mcp")
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.delenv("SSH_AGENT_PID", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    # Create existing CLI config with some data
    cli_config = tmp_path / ".claude.json"
    cli_config.write_text(json.dumps({"existingKey": "existingValue"}))

    assert _handle_mcp_install(DummyArgs(client="claude-code")) == 0

    data = json.loads(cli_config.read_text())
    assert data["existingKey"] == "existingValue"  # Preserved
    assert data["mcpServers"]["shannot"]["command"] == "/opt/tools/shannot-mcp"


def test_mcp_install_supports_codex_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Installing for Codex CLI should use TOML config."""
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: "/opt/tools/shannot-mcp")
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    monkeypatch.delenv("SSH_AGENT_PID", raising=False)

    # Codex now prefers TOML config
    config_file = tmp_path / ".codex" / "config.toml"

    assert _handle_mcp_install(DummyArgs(client="codex")) == 0

    # Verify TOML file was created with correct structure
    # Use tomllib (Python 3.11+) or tomli (Python 3.10)
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(config_file, "rb") as f:
        data = tomllib.load(f)
    assert data["mcp_servers"]["shannot"]["command"] == "/opt/tools/shannot-mcp"
    assert data["mcp_servers"]["shannot"]["args"] == []
    assert data["mcp_servers"]["shannot"]["enabled"] is True


def test_mcp_install_updates_claude_code_user_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Claude Code user config should receive stdio server (available across all projects)."""
    _patch_home(monkeypatch, tmp_path)
    claude_config = tmp_path / ".claude.json"
    claude_config.write_text(json.dumps({}, indent=2))

    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr("shannot.cli.shutil.which", lambda _: "/opt/tools/shannot-mcp")
    monkeypatch.delenv("SSH_AGENT_PID", raising=False)
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/agent.sock")

    result = _handle_mcp_install(DummyArgs(client="claude-code"))
    assert result == 0

    config_data = json.loads(claude_config.read_text())
    # User scope: top-level mcpServers
    server_entry = config_data["mcpServers"]["shannot"]
    assert server_entry["type"] == "stdio"
    assert server_entry["command"] == "/opt/tools/shannot-mcp"
    assert server_entry.get("args", []) == []
    assert server_entry.get("env") == {"SSH_AUTH_SOCK": "/tmp/agent.sock"}
