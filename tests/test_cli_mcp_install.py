"""Tests for `shannot mcp install` command."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("pydantic")

from shannot.cli import _handle_mcp_install


class DummyArgs(Namespace):
    """Simple namespace mimicking argparse Namespace."""

    def __init__(self, **kwargs: object):
        super().__init__(**kwargs)


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
