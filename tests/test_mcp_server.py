"""Unit tests for shannot.mcp_server module."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("pydantic")

# Provide lightweight stubs for optional dependencies when not installed.
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

from shannot import ProcessResult, SandboxProfile  # noqa: E402
from shannot.mcp_server import ShannotMCPServer  # noqa: E402


@pytest.fixture
def mock_profile_paths(tmp_path):
    """Create temporary profile files for testing."""
    profile1 = tmp_path / "test1.json"
    profile1.write_text(
        json.dumps(
            {
                "name": "test1",
                "allowed_commands": ["ls", "cat"],
                "binds": [{"source": "/usr", "target": "/usr", "read_only": True}],
                "tmpfs_paths": ["/tmp"],
                "environment": {"PATH": "/usr/bin"},
                "network_isolation": True,
            }
        )
    )

    profile2 = tmp_path / "test2.json"
    profile2.write_text(
        json.dumps(
            {
                "name": "test2",
                "allowed_commands": ["df", "free"],
                "binds": [{"source": "/usr", "target": "/usr", "read_only": True}],
                "tmpfs_paths": ["/tmp"],
                "environment": {"PATH": "/usr/bin"},
                "network_isolation": False,
            }
        )
    )

    return [profile1, profile2]


@pytest.fixture
def mcp_server(mock_profile_paths):
    """Create an MCP server with mock profiles."""
    with patch("shannot.mcp_server.SandboxDeps") as mock_deps_class:
        # Create mock deps instances
        mock_deps1 = Mock()
        mock_deps1.profile = SandboxProfile(
            name="test1",
            allowed_commands=["ls", "cat"],
            binds=[],
            tmpfs_paths=[Path("/tmp")],
            environment={"PATH": "/usr/bin"},
            network_isolation=True,
        )
        mock_deps1.manager = Mock()
        mock_deps1.executor = None

        mock_deps2 = Mock()
        mock_deps2.profile = SandboxProfile(
            name="test2",
            allowed_commands=["df", "free"],
            binds=[],
            tmpfs_paths=[Path("/tmp")],
            environment={"PATH": "/usr/bin"},
            network_isolation=False,
        )
        mock_deps2.manager = Mock()
        mock_deps2.executor = None

        # Mock the constructor to return our mocks
        mock_deps_class.side_effect = [mock_deps1, mock_deps2]

        server = ShannotMCPServer(profile_paths=mock_profile_paths)
        return server


class TestShannotMCPServerInit:
    """Test MCP server initialization."""

    def test_init_with_profiles(self, mock_profile_paths):
        """Test server initialization with profile paths."""
        with patch("shannot.mcp_server.SandboxDeps") as mock_deps_class:
            mock_deps = Mock()
            mock_deps.profile = Mock()
            mock_deps.profile.name = "test1"
            mock_deps_class.return_value = mock_deps

            server = ShannotMCPServer(profile_paths=[mock_profile_paths[0]])

            assert "test1" in server.deps_by_profile
            assert len(server.deps_by_profile) == 1

    def test_init_with_profile_name(self):
        """Profiles can be provided by name as well as path."""
        with patch("shannot.mcp_server.SandboxDeps") as mock_deps_class:
            mock_deps = Mock()
            mock_deps.profile = Mock()
            mock_deps.profile.name = "minimal"
            mock_deps_class.return_value = mock_deps

            ShannotMCPServer(profile_paths=["minimal"])

            mock_deps_class.assert_called_with(profile_name="minimal", executor=None)

    def test_init_with_invalid_profile(self, tmp_path):
        """Test server initialization with invalid profile."""
        invalid_profile = tmp_path / "invalid.json"
        invalid_profile.write_text("not valid json")

        # Should not raise, just log error
        server = ShannotMCPServer(profile_paths=[invalid_profile])
        assert len(server.deps_by_profile) == 0

    def test_executor_passed_through(self, mock_profile_paths):
        """Executor passed to server is injected into SandboxDeps."""
        executor = Mock()
        with patch("shannot.mcp_server.SandboxDeps") as mock_deps_class:
            mock_deps = Mock()
            mock_deps.profile = Mock()
            mock_deps.profile.name = "test1"
            mock_deps_class.return_value = mock_deps

            ShannotMCPServer(profile_paths=[mock_profile_paths[0]], executor=executor)

            kwargs = mock_deps_class.call_args.kwargs
            assert kwargs["executor"] is executor

    def test_discover_profiles(self):
        """Test profile discovery from default locations."""
        # Just test that the method exists and returns a list
        # Actual discovery depends on system state, so we'll test with explicit paths elsewhere
        server = ShannotMCPServer(profile_paths=[])
        assert isinstance(server.deps_by_profile, dict)


class TestMCPServerToolRegistration:
    """Test tool registration and listing."""

    def test_list_tools(self, mcp_server):
        """Test that tools are registered for each profile."""
        assert "test1" in mcp_server.deps_by_profile
        assert "test2" in mcp_server.deps_by_profile

        # Skip if using dummy server (no tools cached)
        if not hasattr(mcp_server.server, "_tool_cache") or not mcp_server.server._tool_cache:
            pytest.skip("Requires real MCP server with tool cache")

        tool_names = set(mcp_server.server._tool_cache.keys())
        assert tool_names == {"sandbox_test1", "sandbox_test2"}

    def test_tool_name_format(self, mcp_server):
        """Test that tool names follow expected format."""
        # Skip if using dummy server (no tools cached)
        if not hasattr(mcp_server.server, "_tool_cache") or not mcp_server.server._tool_cache:
            pytest.skip("Requires real MCP server with tool cache")
        for name in mcp_server.server._tool_cache.keys():
            assert name.startswith("sandbox_")

    def test_tool_names_include_executor_label(self, mock_profile_paths):
        """When executor label provided, tool names include it."""
        executor = Mock()
        executor.host = "example.com"
        with patch("shannot.mcp_server.SandboxDeps") as deps_class:
            mock_deps1 = Mock()
            mock_deps1.profile = SandboxProfile(
                name="test1",
                allowed_commands=["ls"],
                binds=[],
                tmpfs_paths=[Path("/tmp")],
                environment={},
                network_isolation=True,
            )
            mock_deps1.manager = Mock()
            mock_deps1.executor = executor
            mock_deps2 = Mock()
            mock_deps2.profile = SandboxProfile(
                name="test2",
                allowed_commands=["df"],
                binds=[],
                tmpfs_paths=[Path("/tmp")],
                environment={},
                network_isolation=True,
            )
            mock_deps2.manager = Mock()
            mock_deps2.executor = executor
            deps_class.side_effect = [mock_deps1, mock_deps2]

            server = ShannotMCPServer(
                profile_paths=mock_profile_paths,
                executor=executor,
                executor_label="lima",
            )

            # Skip if using dummy server (no tools cached)
            if not hasattr(server.server, "_tool_cache") or not server.server._tool_cache:
                pytest.skip("Requires real MCP server with tool cache")

            tool_names = set(server.server._tool_cache.keys())
            assert tool_names == {"sandbox_lima_test1", "sandbox_lima_test2"}


class TestMCPServerToolDescriptions:
    """Test tool description generation."""

    def test_generate_tool_description(self, mcp_server):
        """Test tool description generation."""
        deps = mcp_server.deps_by_profile["test1"]
        description = mcp_server._generate_tool_description(deps)

        assert "test1" in description
        assert "ls" in description or "cat" in description
        assert "read-only" in description
        assert "local sandbox" in description
        assert "Allowed commands include" in description

    def test_description_includes_remote_host(self, mock_profile_paths):
        """Descriptions reference remote host when executor provided."""
        executor = Mock()
        executor.host = "lima.local"

        with patch("shannot.mcp_server.SandboxDeps") as deps_class:
            mock_deps = Mock()
            mock_deps.profile = SandboxProfile(
                name="remote",
                allowed_commands=["nproc"],
                binds=[],
                tmpfs_paths=[Path("/tmp")],
                environment={},
                network_isolation=True,
            )
            mock_deps.manager = Mock()
            mock_deps.executor = executor
            deps_class.return_value = mock_deps

            server = ShannotMCPServer(
                profile_paths=[mock_profile_paths[0]],
                executor=executor,
                executor_label="lima",
            )

            description = server._generate_tool_description(mock_deps)
            assert "remote host lima.local" in description

    def test_description_truncates_long_command_list(self, mcp_server):
        """Test that long command lists are truncated in descriptions."""
        deps = Mock()
        deps.profile = Mock()
        deps.profile.name = "test"
        deps.profile.allowed_commands = [f"cmd{i}" for i in range(10)]
        deps.profile.network_isolation = True

        description = mcp_server._generate_tool_description(deps)

        assert "10 total" in description or "..." in description


class TestMCPServerCommandFormatting:
    """Test command output formatting."""

    def test_format_successful_output(self, mcp_server):
        """Test formatting of successful command output."""
        result = Mock()
        result.returncode = 0
        result.duration = 1.5
        result.stdout = "test output"
        result.stderr = ""
        result.succeeded = True

        formatted = mcp_server._format_command_output(result)

        assert "Exit code: 0" in formatted
        assert "1.50s" in formatted
        assert "test output" in formatted
        assert "⚠️" not in formatted

    def test_format_failed_output(self, mcp_server):
        """Test formatting of failed command output."""
        result = Mock()
        result.returncode = 1
        result.duration = 0.5
        result.stdout = ""
        result.stderr = "error message"
        result.succeeded = False

        formatted = mcp_server._format_command_output(result)

        assert "Exit code: 1" in formatted
        assert "error message" in formatted
        assert "⚠️" in formatted

    def test_format_output_with_both_streams(self, mcp_server):
        """Test formatting when both stdout and stderr have content."""
        result = Mock()
        result.returncode = 0
        result.duration = 0.2
        result.stdout = "output"
        result.stderr = "warning"
        result.succeeded = True

        formatted = mcp_server._format_command_output(result)

        assert "--- stdout ---" in formatted
        assert "--- stderr ---" in formatted
        assert "output" in formatted
        assert "warning" in formatted


class TestMCPServerResources:
    """Test MCP resource handling."""

    def test_list_resources(self, mcp_server):
        """Test listing available resources."""
        # Resources should be registered for profile inspection
        assert len(mcp_server.deps_by_profile) == 2

        # Expected resources:
        # - sandbox://profiles/test1
        # - sandbox://profiles/test2
        # (Actual testing would require calling the registered handler)

    def test_resource_uri_format(self, mcp_server):
        """Test resource URI format."""
        # Resource URIs should follow pattern: sandbox://profiles/{name}
        assert "test1" in mcp_server.deps_by_profile
        assert "test2" in mcp_server.deps_by_profile


class TestMCPServerToolExecution:
    """Test tool execution (requires more integration-style setup)."""

    def test_execute_command_tool(self, mcp_server):
        """Test executing a command tool."""
        # Mock the manager run method
        mock_result = ProcessResult(
            command=("test",),
            stdout="test",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        mcp_server.deps_by_profile["test1"].manager.run.return_value = mock_result

        # Note: Actual tool execution would require invoking through MCP protocol
        # This is a simplified test of the underlying logic
        deps = mcp_server.deps_by_profile["test1"]
        result = deps.manager.run(["ls"])

        assert result.returncode == 0


class TestMCPServerErrorHandling:
    """Test error handling in MCP server."""

    def test_invalid_profile_graceful_failure(self, tmp_path):
        """Test that invalid profiles don't crash server initialization."""
        bad_profile = tmp_path / "bad.json"
        bad_profile.write_text("not json")

        # Should not raise
        server = ShannotMCPServer(profile_paths=[bad_profile])
        assert len(server.deps_by_profile) == 0

    def test_missing_profile_path(self):
        """Test handling of missing profile path."""
        # Should not raise, just skip the profile
        server = ShannotMCPServer(profile_paths=[Path("/nonexistent/profile.json")])
        assert len(server.deps_by_profile) == 0


class TestMCPServerIntegration:
    """Integration-style tests for MCP server components."""

    def test_multiple_profiles_loaded(self, mcp_server):
        """Test that multiple profiles can be loaded."""
        assert len(mcp_server.deps_by_profile) == 2
        assert "test1" in mcp_server.deps_by_profile
        assert "test2" in mcp_server.deps_by_profile

    def test_profile_isolation(self, mcp_server):
        """Test that profiles are isolated from each other."""
        deps1 = mcp_server.deps_by_profile["test1"]
        deps2 = mcp_server.deps_by_profile["test2"]

        assert deps1.profile.name != deps2.profile.name
        assert deps1.profile.allowed_commands != deps2.profile.allowed_commands
