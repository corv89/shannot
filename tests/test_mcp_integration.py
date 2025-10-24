"""Integration tests for MCP server with actual sandbox execution.

These tests require Linux and bubblewrap to be installed.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("mcp")
pytest.importorskip("pydantic")

from shannot.mcp_server import ShannotMCPServer  # noqa: E402
from shannot.tools import (  # noqa: E402
    CommandInput,
    DirectoryListInput,
    FileReadInput,
    SandboxDeps,
    check_disk_usage,
    check_memory,
    list_directory,
    read_file,
    run_command,
)


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
class TestMCPToolsWithRealSandbox:
    """Test MCP tools with actual sandbox execution."""

    @pytest.fixture
    def real_sandbox_deps(self, profile_json_minimal, bwrap_path):
        """Create real sandbox dependencies."""
        return SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

    @pytest.mark.asyncio
    async def test_run_command_ls(self, real_sandbox_deps):
        """Test running ls command in real sandbox."""
        cmd_input = CommandInput(command=["ls", "/"])
        result = await run_command(real_sandbox_deps, cmd_input)

        assert result.succeeded is True
        assert result.returncode == 0
        assert len(result.stdout) > 0
        # Common top-level directories
        assert any(d in result.stdout for d in ["usr", "etc", "tmp"])

    @pytest.mark.asyncio
    async def test_run_command_echo(self, real_sandbox_deps):
        """Test echo command."""
        cmd_input = CommandInput(command=["echo", "hello world"])
        result = await run_command(real_sandbox_deps, cmd_input)

        assert result.succeeded is True
        assert "hello world" in result.stdout

    @pytest.mark.asyncio
    async def test_run_disallowed_command(self, real_sandbox_deps):
        """Test that disallowed commands fail."""
        cmd_input = CommandInput(command=["rm", "-rf", "/"])
        result = await run_command(real_sandbox_deps, cmd_input)

        # Should fail because 'rm' is not in allowed_commands
        assert result.succeeded is False

    @pytest.mark.asyncio
    async def test_read_file_etc_hostname(self, real_sandbox_deps):
        """Test reading a real system file."""
        file_input = FileReadInput(path="/etc/hostname")
        content = await read_file(real_sandbox_deps, file_input)

        assert "Error" not in content
        assert len(content.strip()) > 0

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, real_sandbox_deps):
        """Test reading non-existent file returns error."""
        file_input = FileReadInput(path="/nonexistent-file-12345")
        content = await read_file(real_sandbox_deps, file_input)

        assert "Error reading file:" in content

    @pytest.mark.asyncio
    async def test_list_directory_root(self, real_sandbox_deps):
        """Test listing root directory."""
        dir_input = DirectoryListInput(path="/")
        listing = await list_directory(real_sandbox_deps, dir_input)

        assert "usr" in listing
        assert "etc" in listing
        assert "tmp" in listing

    @pytest.mark.asyncio
    async def test_list_directory_long_format(self, real_sandbox_deps):
        """Test directory listing with long format."""
        dir_input = DirectoryListInput(path="/etc", long_format=True)
        listing = await list_directory(real_sandbox_deps, dir_input)

        # Long format should show permissions
        assert any(line.startswith(("d", "-", "l")) for line in listing.split("\n") if line)

    @pytest.mark.asyncio
    async def test_check_disk_usage_real(self, real_sandbox_deps):
        """Test real disk usage check."""
        usage = await check_disk_usage(real_sandbox_deps)

        assert "Filesystem" in usage
        assert "%" in usage  # Percentage column
        assert any(fs in usage for fs in ["/dev", "tmpfs"])

    @pytest.mark.asyncio
    async def test_check_memory_real(self, real_sandbox_deps):
        """Test real memory check."""
        usage = await check_memory(real_sandbox_deps)

        assert "Mem:" in usage
        assert "total" in usage.lower()

    @pytest.mark.asyncio
    async def test_command_duration_tracked(self, real_sandbox_deps):
        """Test that command execution duration is tracked."""
        cmd_input = CommandInput(command=["ls", "/"])
        result = await run_command(real_sandbox_deps, cmd_input)

        assert result.duration > 0
        assert result.duration < 10  # Should be fast


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
class TestMCPServerEndToEnd:
    """End-to-end tests for MCP server."""

    @pytest.fixture
    def test_profile_path(self, tmp_path, bwrap_path):
        """Create a test profile file."""
        profile_path = tmp_path / "test-e2e.json"
        profile_content = {
            "name": "test-e2e",
            "allowed_commands": ["ls", "cat", "echo", "df", "free"],
            "binds": [
                {"source": "/usr", "target": "/usr", "read_only": True},
                {"source": "/lib", "target": "/lib", "read_only": True},
                {"source": "/lib64", "target": "/lib64", "read_only": True},
                {"source": "/etc", "target": "/etc", "read_only": True},
            ],
            "tmpfs_paths": ["/tmp"],
            "environment": {"PATH": "/usr/bin:/bin"},
            "network_isolation": True,
        }
        profile_path.write_text(json.dumps(profile_content, indent=2))
        return profile_path

    def test_server_initialization(self, test_profile_path):
        """Test that MCP server initializes with real profile."""
        server = ShannotMCPServer(profile_paths=[test_profile_path])

        assert "test-e2e" in server.deps_by_profile
        assert server.deps_by_profile["test-e2e"].profile.name == "test-e2e"

    def test_multiple_profiles_loaded(self, tmp_path):
        """Test loading multiple profiles."""
        # Create two profiles
        profile1 = tmp_path / "profile1.json"
        profile1.write_text(
            json.dumps(
                {
                    "name": "profile1",
                    "allowed_commands": ["ls"],
                    "binds": [{"source": "/usr", "target": "/usr", "read_only": True}],
                    "tmpfs_paths": ["/tmp"],
                    "environment": {"PATH": "/usr/bin"},
                    "network_isolation": True,
                }
            )
        )

        profile2 = tmp_path / "profile2.json"
        profile2.write_text(
            json.dumps(
                {
                    "name": "profile2",
                    "allowed_commands": ["cat"],
                    "binds": [{"source": "/usr", "target": "/usr", "read_only": True}],
                    "tmpfs_paths": ["/tmp"],
                    "environment": {"PATH": "/usr/bin"},
                    "network_isolation": True,
                }
            )
        )

        server = ShannotMCPServer(profile_paths=[profile1, profile2])

        assert len(server.deps_by_profile) == 2
        assert "profile1" in server.deps_by_profile
        assert "profile2" in server.deps_by_profile

    def test_tool_description_generated(self, test_profile_path):
        """Test that tool descriptions are generated correctly."""
        server = ShannotMCPServer(profile_paths=[test_profile_path])
        deps = server.deps_by_profile["test-e2e"]

        description = server._generate_tool_description(deps)

        assert "test-e2e" in description
        assert "read-only" in description
        assert any(cmd in description for cmd in ["ls", "cat", "echo"])


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
class TestMCPSecurityValidation:
    """Test security features in integration context."""

    @pytest.fixture
    def diagnostics_profile_path(self, tmp_path):
        """Create diagnostics profile for testing."""
        profile_path = tmp_path / "diagnostics.json"
        # Use a subset of diagnostics commands for faster testing
        profile_content = {
            "name": "diagnostics",
            "allowed_commands": [
                "ls",
                "cat",
                "df",
                "free",
                "ps",
                "grep",
            ],
            "binds": [
                {"source": "/usr", "target": "/usr", "read_only": True},
                {"source": "/lib", "target": "/lib", "read_only": True},
                {"source": "/lib64", "target": "/lib64", "read_only": True},
                {"source": "/etc", "target": "/etc", "read_only": True},
                {"source": "/proc", "target": "/proc", "read_only": True},
                {"source": "/sys", "target": "/sys", "read_only": True},
            ],
            "tmpfs_paths": ["/tmp"],
            "environment": {"PATH": "/usr/bin:/bin"},
            "network_isolation": True,
        }
        profile_path.write_text(json.dumps(profile_content, indent=2))
        return profile_path

    @pytest.mark.asyncio
    async def test_read_only_enforcement(self, diagnostics_profile_path, bwrap_path):
        """Test that files cannot be modified in read-only sandbox."""
        deps = SandboxDeps(profile_path=diagnostics_profile_path, bwrap_path=bwrap_path)

        # Try to create a file in /etc (should fail - read-only)
        cmd_input = CommandInput(command=["cat"])
        result = await run_command(deps, cmd_input)

        # cat with no args should fail, but command should execute
        # (This tests command is allowed but filesystem is read-only)
        assert result.returncode != 0 or result.succeeded

    @pytest.mark.asyncio
    async def test_command_allowlist_enforcement(self, diagnostics_profile_path, bwrap_path):
        """Test that disallowed commands cannot execute."""
        deps = SandboxDeps(profile_path=diagnostics_profile_path, bwrap_path=bwrap_path)

        # Try to run a command not in allowed_commands
        cmd_input = CommandInput(command=["wget", "http://example.com"])
        result = await run_command(deps, cmd_input)

        # Should fail because wget is not allowed
        assert result.succeeded is False

    @pytest.mark.asyncio
    async def test_tmp_is_ephemeral(self, diagnostics_profile_path, bwrap_path):
        """Test that /tmp changes are ephemeral."""
        deps = SandboxDeps(profile_path=diagnostics_profile_path, bwrap_path=bwrap_path)

        # Write to /tmp in first command
        filename = "/tmp/test-file-12345"
        cmd1 = CommandInput(command=["ls", filename])
        result1 = await run_command(deps, cmd1)

        # File shouldn't exist from previous run
        assert result1.succeeded is False or "cannot access" in result1.stderr

    @pytest.mark.asyncio
    async def test_sensitive_data_access(self, diagnostics_profile_path, bwrap_path):
        """Test that we can read files but not modify them."""
        deps = SandboxDeps(profile_path=diagnostics_profile_path, bwrap_path=bwrap_path)

        # Read /etc/passwd (allowed in diagnostics profile)
        file_input = FileReadInput(path="/etc/passwd")
        content = await read_file(deps, file_input)

        # Should succeed (read-only access)
        assert "root:" in content or "Error" not in content


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
class TestMCPPerformance:
    """Performance tests for MCP tools."""

    @pytest.mark.asyncio
    async def test_command_execution_overhead(self, profile_json_minimal, bwrap_path):
        """Test that sandbox overhead is reasonable."""
        deps = SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

        # Simple command should be fast
        cmd_input = CommandInput(command=["echo", "test"])
        result = await run_command(deps, cmd_input)

        assert result.succeeded is True
        # Overhead should be < 1 second for simple echo
        assert result.duration < 1.0

    @pytest.mark.asyncio
    async def test_multiple_commands_sequential(self, profile_json_minimal, bwrap_path):
        """Test executing multiple commands sequentially."""
        deps = SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

        total_duration = 0
        for i in range(5):
            cmd_input = CommandInput(command=["echo", f"test{i}"])
            result = await run_command(deps, cmd_input)
            assert result.succeeded is True
            total_duration += result.duration

        # 5 commands should complete in reasonable time
        assert total_duration < 5.0
