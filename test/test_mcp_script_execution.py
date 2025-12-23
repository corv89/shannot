"""Integration tests for MCP script execution workflow.

Tests the complete flow of script execution through the MCP server,
including fast path, review path, and blocked path execution.
"""

from __future__ import annotations

import json
from pathlib import Path

from shannot.mcp.server_impl import ShannotMCPServer
from shannot.mcp.types import TextContent
from shannot.session import Session


class TestScriptExecutionWorkflow:
    """Test complete script execution workflows."""

    def test_fast_path_simple_script(self):
        """Test fast path with simple allowed script (no subprocess)."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Simple script with no subprocess calls (should be empty detected_ops)
        script = "print('hello world')"
        arguments = {"script": script, "profile": "minimal"}

        # Mock runtime to avoid actual execution
        server.runtime = None

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)

        # Empty detected_ops triggers review path (not fast path)
        # because all_allowed check requires detected_ops to be truthy
        assert data["status"] == "pending_approval"

    def test_fast_path_allowed_operations(self):
        """Test fast path with script containing only allowed operations."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script with allowed operations
        script = """
import subprocess
subprocess.call(['ls', '/tmp'])
subprocess.call(['cat', '/etc/hosts'])
"""
        arguments = {"script": script, "profile": "minimal"}

        # Mock runtime to prevent actual execution
        server.runtime = None

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)

        # Should attempt fast path but fail due to no runtime
        assert data["status"] == "error"
        assert "runtime not found" in data["error"].lower()

    def test_blocked_path_denied_operation(self):
        """Test blocked path with denied operation."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script with denied operation
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
        assert "detected_operations" in data

    def test_review_path_unapproved_operation(self):
        """Test review path with operation not in allowlist."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script with operation not in auto_approve
        script = """
import subprocess
subprocess.call(['curl', 'https://example.com'])
"""
        arguments = {"script": script, "profile": "minimal", "name": "curl-test"}

        result = server._handle_sandbox_run(arguments)

        assert isinstance(result, TextContent)
        data = json.loads(result.text)

        # Should create session
        assert data["status"] == "pending_approval"
        assert "session_id" in data
        assert "detected_operations" in data
        assert "instructions" in data
        assert "curl https://example.com" in data["detected_operations"]

        # Verify session was created
        session_id = data["session_id"]
        session = Session.load(session_id)
        assert session.status == "pending"
        assert session.name == "curl-test"
        assert "curl https://example.com" in session.commands

        # Clean up
        session.delete()

    def test_session_result_pending(self):
        """Test session_result tool with pending session."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Create a session via review path
        script = """
import subprocess
subprocess.call(['wget', 'https://example.com'])
"""
        arguments = {"script": script, "profile": "minimal"}

        create_result = server._handle_sandbox_run(arguments)
        create_data = json.loads(create_result.text)
        session_id = create_data["session_id"]

        # Poll session result
        poll_result = server._handle_session_result({"session_id": session_id})
        poll_data = json.loads(poll_result.text)

        assert poll_data["session_id"] == session_id
        assert poll_data["status"] == "pending"
        assert "expires_at" in poll_data
        assert "instructions" in poll_data

        # Clean up
        Session.load(session_id).delete()

    def test_session_result_expired(self):
        """Test session_result with expired session."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Create a session and manually expire it
        script = """
import subprocess
subprocess.call(['ping', 'example.com'])
"""
        arguments = {"script": script, "profile": "minimal"}

        create_result = server._handle_sandbox_run(arguments)
        create_data = json.loads(create_result.text)
        session_id = create_data["session_id"]

        # Manually mark as expired
        session = Session.load(session_id)
        session.expires_at = "2020-01-01T00:00:00"  # Past date
        session.save()

        # Poll session result
        poll_result = server._handle_session_result({"session_id": session_id})
        poll_data = json.loads(poll_result.text)

        assert poll_data["session_id"] == session_id
        assert poll_data["status"] == "expired"
        assert "expired" in poll_data["message"].lower()

        # Clean up
        session.delete()

    def test_ast_analysis_multiple_subprocess_calls(self):
        """Test AST analysis detects multiple subprocess calls."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        script = """
import subprocess

# Test different subprocess methods
subprocess.call(['ls', '/'])
subprocess.run(['cat', 'file.txt'])
subprocess.check_output(['grep', 'pattern', 'file'])
subprocess.Popen(['find', '/tmp'])
"""

        detected = server._analyze_script_best_effort(script)

        assert "ls /" in detected
        assert "cat file.txt" in detected
        assert "grep pattern file" in detected
        assert "find /tmp" in detected
        assert len(detected) == 4

    def test_ast_analysis_dynamic_command_not_detected(self):
        """Test AST analysis doesn't detect dynamic commands (expected limitation)."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Dynamic command construction (won't be detected)
        script = """
import subprocess
cmd = ['rm', '-rf', '/']
subprocess.call(cmd)
"""

        detected = server._analyze_script_best_effort(script)

        # Should be empty (can't extract variable reference)
        assert len(detected) == 0

    def test_profile_validation(self):
        """Test different profiles have different allowlists."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script with diagnostic commands
        script = """
import subprocess
subprocess.call(['ps', 'aux'])
subprocess.call(['df', '-h'])
"""

        # minimal profile doesn't include ps/df
        result_minimal = server._handle_sandbox_run({"script": script, "profile": "minimal"})
        data_minimal = json.loads(result_minimal.text)
        assert data_minimal["status"] == "pending_approval"

        # diagnostics profile includes ps/df
        result_diagnostics = server._handle_sandbox_run(
            {"script": script, "profile": "diagnostics"}
        )
        data_diagnostics = json.loads(result_diagnostics.text)

        # Should attempt fast path (but fail due to no runtime)
        server.runtime = None
        result_diagnostics = server._handle_sandbox_run(
            {"script": script, "profile": "diagnostics"}
        )
        data_diagnostics = json.loads(result_diagnostics.text)
        assert data_diagnostics["status"] == "error"
        assert "runtime not found" in data_diagnostics["error"].lower()

        # Clean up sessions if any were created
        if data_minimal["status"] == "pending_approval":
            Session.load(data_minimal["session_id"]).delete()

    def test_custom_profile(self, tmp_path):
        """Test loading custom profile from file."""
        # Create custom profile
        profile_data = {
            "auto_approve": ["echo", "printf"],
            "always_deny": ["eval", "exec"],
        }
        profile_path = tmp_path / "custom.json"
        profile_path.write_text(json.dumps(profile_data))

        server = ShannotMCPServer(profile_paths=[profile_path], verbose=False)

        # Verify custom profile loaded
        assert "custom" in server.profiles
        assert server.profiles["custom"]["auto_approve"] == ["echo", "printf"]

        # Test with custom profile
        script = """
import subprocess
subprocess.call(['echo', 'hello'])
"""
        arguments = {"script": script, "profile": "custom"}

        # Mock runtime
        server.runtime = None

        result = server._handle_sandbox_run(arguments)
        data = json.loads(result.text)

        # Should attempt fast path (echo is in auto_approve)
        assert data["status"] == "error"
        assert "runtime not found" in data["error"].lower()

    def test_session_name_customization(self):
        """Test custom session naming."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        script = """
import subprocess
subprocess.call(['whoami'])
"""
        arguments = {
            "script": script,
            "profile": "minimal",
            "name": "identity-check",
        }

        result = server._handle_sandbox_run(arguments)
        data = json.loads(result.text)

        assert data["status"] == "pending_approval"
        session = Session.load(data["session_id"])
        assert session.name == "identity-check"

        # Clean up
        session.delete()

    def test_error_handling_invalid_script_type(self):
        """Test error handling for invalid script parameter."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Script is not a string
        arguments = {"script": ["not", "a", "string"], "profile": "minimal"}

        result = server._handle_sandbox_run(arguments)
        data = json.loads(result.text)

        assert data["status"] == "error"
        assert "script" in data["error"].lower()

    def test_error_handling_invalid_profile(self):
        """Test error handling for non-existent profile."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        arguments = {"script": "print('test')", "profile": "nonexistent"}

        result = server._handle_sandbox_run(arguments)
        data = json.loads(result.text)

        assert data["status"] == "error"
        assert "Unknown profile" in data["error"]

    def test_session_cleanup_on_expiry(self):
        """Test session expiry cleanup."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        # Create session
        script = """
import subprocess
subprocess.call(['uptime'])
"""
        arguments = {"script": script, "profile": "minimal"}

        result = server._handle_sandbox_run(arguments)
        data = json.loads(result.text)
        session_id = data["session_id"]

        # Manually expire
        session = Session.load(session_id)
        session.expires_at = "2020-01-01T00:00:00"
        session.save()

        # Cleanup expired sessions
        count = Session.cleanup_expired()
        assert count >= 1

        # Reload and check status
        session = Session.load(session_id)
        assert session.status == "expired"

        # Clean up
        session.delete()


class TestMCPServerResources:
    """Test MCP resource endpoints."""

    def test_profiles_resource_lists_all_profiles(self):
        """Test sandbox://profiles resource."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_list_profiles()
        profiles = json.loads(result)

        assert isinstance(profiles, list)
        assert "minimal" in profiles
        assert "readonly" in profiles
        assert "diagnostics" in profiles

    def test_profile_resource_shows_configuration(self):
        """Test sandbox://profiles/{name} resource."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_get_profile("minimal")
        profile = json.loads(result)

        assert "auto_approve" in profile
        assert "always_deny" in profile
        assert "ls" in profile["auto_approve"]
        assert "rm -rf /" in profile["always_deny"]

    def test_status_resource_shows_runtime_info(self):
        """Test sandbox://status resource."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        result = server._handle_status()
        status = json.loads(result)

        assert "version" in status
        assert "runtime_available" in status
        assert "profiles" in status
        assert isinstance(status["profiles"], list)

    def test_status_resource_with_runtime(self):
        """Test status resource includes runtime paths when available."""
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
        assert status["runtime"]["pypy_sandbox"] == "/usr/bin/pypy-sandbox"


class TestMCPToolSchemas:
    """Test tool schema correctness."""

    def test_sandbox_run_schema_includes_python36_warning(self):
        """Test sandbox_run schema warns about Python 3.6 syntax."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        tool = server.tools["sandbox_run"]

        # Check description mentions Python 3.6
        assert "3.6" in tool.description

        # Check script parameter mentions Python 3.6 limitations
        script_desc = tool.inputSchema["properties"]["script"]["description"]
        assert "3.6" in script_desc
        assert "f-string" in script_desc.lower() or "walrus" in script_desc.lower()

    def test_sandbox_run_schema_profiles_dynamic(self):
        """Test sandbox_run schema doesn't hardcode profile enum."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        tool = server.tools["sandbox_run"]
        profile_prop = tool.inputSchema["properties"]["profile"]

        # Should not have hardcoded enum (use description instead)
        assert "enum" not in profile_prop
        assert "description" in profile_prop
        assert "minimal" in profile_prop["description"]

    def test_session_result_schema(self):
        """Test session_result tool schema."""
        server = ShannotMCPServer(profile_paths=None, verbose=False)

        tool = server.tools["session_result"]

        assert tool.name == "session_result"
        assert "session_id" in tool.inputSchema["properties"]
        assert tool.inputSchema["required"] == ["session_id"]
        assert "poll" in tool.description.lower()
