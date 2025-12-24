"""Unit tests for MCP server implementation."""

from __future__ import annotations

import json
from pathlib import Path

from shannot.mcp.server import MCPServer
from shannot.mcp.server_impl import ShannotMCPServer
from shannot.mcp.types import TextContent


class TestMCPServer:
    """Tests for base MCPServer class."""

    def test_initialization(self):
        """Test server initializes with correct metadata."""
        server = MCPServer(name="test", version="1.0.0")

        assert server.server_info.name == "test"
        assert server.server_info.version == "1.0.0"
        assert isinstance(server.tools, dict)
        assert isinstance(server.resources, dict)

    def test_register_tool(self):
        """Test tool registration."""
        server = MCPServer(name="test", version="1.0.0")

        def test_handler(args):
            return TextContent(text="result")

        server.register_tool(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            handler=test_handler,
        )

        assert "test_tool" in server.tools
        assert server.tools["test_tool"].name == "test_tool"
        assert "test_tool" in server.tool_handlers

    def test_register_resource(self):
        """Test resource registration."""
        server = MCPServer(name="test", version="1.0.0")

        def test_handler():
            return "resource content"

        server.register_resource(
            uri="test://resource",
            name="Test Resource",
            description="Test description",
            mime_type="text/plain",
            handler=test_handler,
        )

        assert "test://resource" in server.resources
        assert server.resources["test://resource"].uri == "test://resource"
        assert "test://resource" in server.resource_handlers

    def test_handle_initialize(self):
        """Test initialize request handling."""
        server = MCPServer(name="test", version="1.0.0")

        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 1,
        }

        response = server.handle_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "test"
        assert response["result"]["serverInfo"]["version"] == "1.0.0"

    def test_handle_ping(self):
        """Test ping request handling."""
        server = MCPServer(name="test", version="1.0.0")

        request = {"jsonrpc": "2.0", "method": "ping", "id": 1}

        response = server.handle_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {}

    def test_handle_list_tools(self):
        """Test tools/list request handling."""
        server = MCPServer(name="test", version="1.0.0")

        server.register_tool(
            name="tool1",
            description="Tool 1",
            input_schema={"type": "object"},
            handler=lambda args: TextContent(text="result"),
        )

        request = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}

        response = server.handle_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 1
        assert response["result"]["tools"][0]["name"] == "tool1"

    def test_handle_call_tool(self):
        """Test tools/call request handling."""
        server = MCPServer(name="test", version="1.0.0")

        def test_handler(args):
            return TextContent(text=f"executed: {args.get('arg1')}")

        server.register_tool(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            handler=test_handler,
        )

        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {"arg1": "value1"}},
            "id": 1,
        }

        response = server.handle_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert "content" in response["result"]
        assert response["result"]["content"][0]["text"] == "executed: value1"

    def test_handle_unknown_method(self):
        """Test unknown method returns error."""
        server = MCPServer(name="test", version="1.0.0")

        request = {"jsonrpc": "2.0", "method": "unknown", "id": 1}

        response = server.handle_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert "Unknown method" in response["error"]["message"]


class TestShannotMCPServer:
    """Tests for ShannotMCPServer class."""

    def test_initialization_with_defaults(self):
        """Test server initializes with default profiles."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        assert "minimal" in server.profiles
        assert "readonly" in server.profiles
        assert "diagnostics" in server.profiles

    def test_default_profiles_structure(self):
        """Test default profiles have correct structure."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        for profile in server.profiles.values():
            assert "auto_approve" in profile
            assert "always_deny" in profile
            assert isinstance(profile["auto_approve"], list)
            assert isinstance(profile["always_deny"], list)

    def test_sandbox_run_tool_registered(self):
        """Test sandbox_run tool is registered."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        assert "sandbox_run" in server.tools
        assert "session_result" in server.tools

        tool = server.tools["sandbox_run"]
        assert tool.name == "sandbox_run"
        assert "script" in tool.inputSchema["properties"]
        assert "profile" in tool.inputSchema["properties"]
        assert "name" in tool.inputSchema["properties"]

        session_tool = server.tools["session_result"]
        assert session_tool.name == "session_result"
        assert "session_id" in session_tool.inputSchema["properties"]

    def test_resources_registered(self):
        """Test resources are registered."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        assert "sandbox://profiles" in server.resources
        assert "sandbox://status" in server.resources
        assert "sandbox://profiles/minimal" in server.resources

    def test_analyze_script_best_effort(self):
        """Test AST-based script analysis."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Test subprocess.call detection
        script = """
import subprocess
subprocess.call(['ls', '/tmp'])
subprocess.call(['cat', 'file.txt'])
"""
        detected = server._analyze_script_best_effort(script)
        assert "ls /tmp" in detected
        assert "cat file.txt" in detected

    def test_analyze_script_no_subprocess(self):
        """Test script with no subprocess calls."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        script = "print('hello world')"
        detected = server._analyze_script_best_effort(script)
        assert len(detected) == 0

    def test_analyze_script_syntax_error(self):
        """Test script with syntax errors (graceful handling)."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        script = "if True\n  print('invalid syntax')"
        detected = server._analyze_script_best_effort(script)
        # Should return empty list instead of crashing
        assert isinstance(detected, list)

    def test_extract_command_from_ast_list(self):
        """Test command extraction from list literal."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        import ast

        stmt = ast.parse("['ls', '/tmp']").body[0]
        assert isinstance(stmt, ast.Expr)
        cmd = server._extract_command_from_ast(stmt.value)
        assert cmd == "ls /tmp"

    def test_extract_command_from_ast_string(self):
        """Test command extraction from string literal."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        import ast

        stmt = ast.parse("'ls /tmp'").body[0]
        assert isinstance(stmt, ast.Expr)
        cmd = server._extract_command_from_ast(stmt.value)
        assert cmd == "ls /tmp"

    def test_handle_sandbox_run_invalid_script(self):
        """Test sandbox_run with missing script parameter."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        arguments = {"profile": "minimal"}

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        assert data["status"] == "error"
        assert "script" in data["error"].lower()

    def test_handle_sandbox_run_invalid_profile(self):
        """Test sandbox_run with invalid profile."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        arguments = {"script": "print('hello')", "profile": "nonexistent"}

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        assert data["status"] == "error"
        assert "Unknown profile" in data["error"]

    def test_handle_sandbox_run_denied_script(self):
        """Test sandbox_run with denied operations."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script contains "rm -rf /" which is in always_deny
        script = """
import subprocess
subprocess.call(['rm', '-rf', '/'])
"""
        arguments = {"script": script, "profile": "minimal"}

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        assert data["status"] == "denied"
        assert "rm -rf /" in data["reason"]

    def test_handle_sandbox_run_allowed_script(self):
        """Test sandbox_run with allowed operations (fast path)."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script with only allowed operations
        script = """
import subprocess
subprocess.call(['ls', '/tmp'])
"""
        arguments = {"script": script, "profile": "minimal"}

        # Mock runtime to avoid actual execution
        server.runtime = None

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        # Should fail due to no runtime (but passed validation)
        assert data["status"] == "error"
        assert "runtime not found" in data["error"].lower()

    def test_handle_sandbox_run_unapproved_script(self):
        """Test sandbox_run with operations needing approval (review path)."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script with operation not in auto_approve list
        script = """
import subprocess
subprocess.call(['curl', 'https://example.com'])
"""
        arguments = {"script": script, "profile": "minimal", "name": "test-session"}

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        assert data["status"] == "pending_approval"
        assert "session_id" in data
        assert "instructions" in data

    def test_handle_session_result_missing_id(self):
        """Test session_result with missing session_id."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_session_result({})

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        assert data["status"] == "error"
        assert "session_id" in data["error"].lower()

    def test_handle_session_result_not_found(self):
        """Test session_result with non-existent session."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_session_result({"session_id": "nonexistent"})

        assert isinstance(result, TextContent)
        data = json.loads(result.text)
        assert data["status"] == "error"
        assert "not found" in data["error"].lower()

    def test_handle_list_profiles_resource(self):
        """Test sandbox://profiles resource handler."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_list_profiles()
        profiles = json.loads(result)

        assert isinstance(profiles, list)
        assert "minimal" in profiles
        assert "readonly" in profiles
        assert "diagnostics" in profiles

    def test_handle_get_profile_resource(self):
        """Test sandbox://profiles/{name} resource handler."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_get_profile("minimal")
        profile = json.loads(result)

        assert "auto_approve" in profile
        assert "always_deny" in profile

    def test_handle_status_resource(self):
        """Test sandbox://status resource handler."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_status()
        status = json.loads(result)

        assert "version" in status
        assert "runtime_available" in status
        assert "profiles" in status

    def test_handle_status_with_runtime(self):
        """Test status resource includes runtime info when available."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Mock runtime
        server.runtime = {
            "pypy_sandbox": Path("/usr/bin/pypy-sandbox"),
            "lib_python": Path("/usr/lib/pypy/lib-python"),
            "lib_pypy": Path("/usr/lib/pypy/lib_pypy"),
        }

        result = server._handle_status()
        status = json.loads(result)

        assert status["runtime_available"] is True
        assert "runtime" in status
        assert "pypy_sandbox" in status["runtime"]
