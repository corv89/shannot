"""Tests for shannot.mcp_main entrypoint."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("pydantic")

if "mcp.server" not in sys.modules:
    mcp_module = types.ModuleType("mcp")
    server_module = types.ModuleType("mcp.server")
    stdio_module = types.ModuleType("mcp.server.stdio")

    class _DummyServer:
        def __init__(self, _name: str):
            self._name = _name
            self._tool_cache = {}

        def list_tools(self):
            def decorator(func):
                return func

            return decorator

        def call_tool(self):
            return self.list_tools()

        def list_resources(self):
            return self.list_tools()

        def read_resource(self):
            return self.list_tools()

        async def run(self, *args, **kwargs):
            return None

    class _DummyInitOptions:
        def __init__(self, **kwargs: object):
            self.__dict__.update(kwargs)

    class _DummyServerCapabilities:
        pass

    async def _dummy_stdio_server():
        class _DummyStream:
            pass

        yield _DummyStream(), _DummyStream()

    server_module.Server = _DummyServer  # type: ignore[attr-defined]
    server_module.InitializationOptions = _DummyInitOptions  # type: ignore[attr-defined]
    server_module.ServerCapabilities = _DummyServerCapabilities  # type: ignore[attr-defined]
    stdio_module.stdio_server = _dummy_stdio_server  # type: ignore[attr-defined]
    sys.modules["mcp"] = mcp_module
    sys.modules["mcp.server"] = server_module
    sys.modules["mcp.server.stdio"] = stdio_module
    mcp_module.server = server_module  # type: ignore[attr-defined]
    server_module.stdio = stdio_module  # type: ignore[attr-defined]

if "mcp.types" not in sys.modules:
    types_module = types.ModuleType("mcp.types")

    class _SimpleType:
        def __init__(self, **kwargs: object):
            self.__dict__.update(kwargs)

    types_module.Resource = _SimpleType  # type: ignore[attr-defined]
    types_module.TextContent = _SimpleType  # type: ignore[attr-defined]
    types_module.Tool = _SimpleType  # type: ignore[attr-defined]
    types_module.ServerCapabilities = _SimpleType  # type: ignore[attr-defined]

    sys.modules["mcp.types"] = types_module
    sys.modules["mcp"].types = types_module  # type: ignore[attr-defined]

from shannot import SandboxProfile  # noqa: E402
from shannot.mcp_main import main as mcp_main  # noqa: E402


class DummyServer:
    """Simple MCP server stub for testing."""

    def __init__(self, profile_specs, executor, executor_label=None):
        self.profile_specs = profile_specs
        self.executor = executor
        self.executor_label = executor_label
        self.deps_by_profile = {
            "default": SandboxProfile(
                name="default",
                allowed_commands=["ls"],
                binds=[],
                tmpfs_paths=[],
                environment={},
                network_isolation=True,
            )
        }
        self.run_called = False
        self.cleanup_called = False

    async def run(self):
        self.run_called = True

    async def cleanup(self):
        self.cleanup_called = True


def test_main_without_target(monkeypatch):
    """Default invocation uses auto-discovered profiles and no executor."""
    stub = DummyServer(profile_specs=None, executor=None)

    monkeypatch.setattr(
        "shannot.mcp_main.ShannotMCPServer", lambda profiles, executor, executor_label=None: stub
    )

    asyncio.run(mcp_main([]))

    assert stub.profile_specs is None
    assert stub.executor is None
    assert stub.run_called
    assert stub.cleanup_called


def test_main_with_target_uses_executor(monkeypatch):
    """Target flag loads executor from config and biases profile selection."""
    executor_obj = object()
    config = SimpleNamespace(
        executor={
            "remote": SimpleNamespace(profile="minimal"),
        }
    )

    create_executor = Mock(return_value=executor_obj)

    monkeypatch.setattr("shannot.mcp_main.load_config", lambda: config)
    monkeypatch.setattr("shannot.mcp_main.create_executor", create_executor)
    monkeypatch.setattr(
        "shannot.mcp_main.ShannotMCPServer",
        lambda profiles, executor, executor_label=None: DummyServer(
            profiles, executor, executor_label
        ),
    )

    result_server = _run_main_collect_server(monkeypatch, ["--target", "remote"])

    assert result_server.profile_specs == ["minimal"]
    assert result_server.executor is executor_obj
    create_executor.assert_called_once_with(config, "remote")
    assert result_server.executor_label == "remote"
    assert result_server.run_called
    assert result_server.cleanup_called


def test_main_with_cli_profile_overrides_config(monkeypatch, tmp_path):
    """Explicit --profile overrides configured executor profile."""
    executor_obj = object()
    config = SimpleNamespace(
        executor={
            "remote": SimpleNamespace(profile="minimal"),
        }
    )

    create_executor = Mock(return_value=executor_obj)
    profile_file = tmp_path / "custom.json"
    profile_file.write_text("{}")

    monkeypatch.setattr("shannot.mcp_main.load_config", lambda: config)
    monkeypatch.setattr("shannot.mcp_main.create_executor", create_executor)
    monkeypatch.setattr(
        "shannot.mcp_main.ShannotMCPServer",
        lambda profiles, executor, executor_label=None: DummyServer(
            profiles, executor, executor_label
        ),
    )

    result_server = _run_main_collect_server(
        monkeypatch,
        ["--target", "remote", "--profile", str(profile_file)],
    )

    assert result_server.profile_specs == [profile_file]
    assert result_server.executor is executor_obj


def test_main_missing_target_errors(monkeypatch):
    """Unknown target should terminate with SystemExit."""
    config = SimpleNamespace(executor={"local": SimpleNamespace(profile=None)})

    monkeypatch.setattr("shannot.mcp_main.load_config", lambda: config)

    with pytest.raises(SystemExit):
        asyncio.run(mcp_main(["--target", "remote"]))


def _run_main_collect_server(monkeypatch, args):
    """Utility to run main() and return the created DummyServer."""
    created_server: DummyServer | None = None

    def factory(profiles, executor, executor_label=None):
        nonlocal created_server
        created_server = DummyServer(profiles, executor, executor_label)
        return created_server

    monkeypatch.setattr("shannot.mcp_main.ShannotMCPServer", factory)

    asyncio.run(mcp_main(args))
    assert created_server is not None
    return created_server
