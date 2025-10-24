"""Unit tests for shannot.tools module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

pytest.importorskip("pydantic")

from shannot import ProcessResult, SandboxProfile  # noqa: E402
from shannot.tools import (  # noqa: E402
    CommandInput,
    CommandOutput,
    DirectoryListInput,
    FileReadInput,
    SandboxDeps,
    check_disk_usage,
    check_memory,
    grep_content,
    list_directory,
    read_file,
    run_command,
    search_files,
)


@pytest.fixture
def mock_profile():
    """Create a mock sandbox profile."""
    return SandboxProfile(
        name="test-profile",
        allowed_commands=["ls", "cat", "grep", "find", "df", "free"],
        binds=[],
        tmpfs_paths=[Path("/tmp")],
        environment={"PATH": "/usr/bin:/bin"},
        network_isolation=True,
    )


@pytest.fixture
def mock_manager(mock_profile):
    """Create a mock sandbox manager."""
    manager = Mock()
    manager.profile = mock_profile
    return manager


@pytest.fixture
def sandbox_deps(mock_profile, mock_manager):
    """Create sandbox dependencies with mocked components."""
    deps = Mock(spec=SandboxDeps)
    deps.profile = mock_profile
    deps.manager = mock_manager
    deps.executor = None  # Default to None, matches backward compatibility mode
    return deps


class TestSandboxDeps:
    """Test SandboxDeps initialization."""

    @pytest.mark.requires_bwrap
    def test_init_with_profile_path(self, profile_json_minimal):
        """Test initializing with explicit profile path."""
        deps = SandboxDeps(profile_path=profile_json_minimal)
        assert deps.profile.name == "test-minimal"
        assert "ls" in deps.profile.allowed_commands

    def test_init_with_invalid_profile_path(self):
        """Test initializing with non-existent profile path."""
        from shannot.sandbox import SandboxError

        with pytest.raises(SandboxError):
            SandboxDeps(profile_path=Path("/nonexistent/profile.json"))


class TestCommandInput:
    """Test CommandInput model validation."""

    def test_valid_command(self):
        """Test valid command input."""
        cmd = CommandInput(command=["ls", "-l"])
        assert cmd.command == ["ls", "-l"]

    def test_empty_command(self):
        """Test that empty command list is allowed (validation happens at runtime)."""
        cmd = CommandInput(command=[])
        assert cmd.command == []

    def test_command_with_args(self):
        """Test command with multiple arguments."""
        cmd = CommandInput(command=["grep", "-r", "pattern", "/path"])
        assert len(cmd.command) == 4


class TestCommandOutput:
    """Test CommandOutput model."""

    def test_successful_output(self):
        """Test command output for successful execution."""
        output = CommandOutput(
            stdout="test output",
            stderr="",
            returncode=0,
            duration=0.5,
            succeeded=True,
        )
        assert output.succeeded is True
        assert output.returncode == 0

    def test_failed_output(self):
        """Test command output for failed execution."""
        output = CommandOutput(
            stdout="",
            stderr="error message",
            returncode=1,
            duration=0.1,
            succeeded=False,
        )
        assert output.succeeded is False
        assert output.returncode == 1


class TestFileReadInput:
    """Test FileReadInput model validation."""

    def test_valid_path(self):
        """Test valid file path."""
        input_data = FileReadInput(path="/etc/hosts")
        assert input_data.path == "/etc/hosts"

    def test_relative_path(self):
        """Test that relative paths are allowed (sandbox will handle them)."""
        input_data = FileReadInput(path="relative/path")
        assert input_data.path == "relative/path"


class TestDirectoryListInput:
    """Test DirectoryListInput model validation."""

    def test_default_options(self):
        """Test default directory listing options."""
        input_data = DirectoryListInput(path="/tmp")
        assert input_data.path == "/tmp"
        assert input_data.long_format is False
        assert input_data.show_hidden is False

    def test_with_options(self):
        """Test directory listing with options enabled."""
        input_data = DirectoryListInput(path="/var", long_format=True, show_hidden=True)
        assert input_data.long_format is True
        assert input_data.show_hidden is True


class TestRunCommand:
    """Test run_command tool."""

    @pytest.mark.asyncio
    async def test_successful_command(self, sandbox_deps):
        """Test successful command execution."""
        # Mock successful result
        mock_result = ProcessResult(
            command=("ls", "/"),
            stdout="output",
            stderr="",
            returncode=0,
            duration=0.5,
        )
        sandbox_deps.manager.run.return_value = mock_result

        cmd_input = CommandInput(command=["ls", "/"])
        result = await run_command(sandbox_deps, cmd_input)

        assert result.succeeded is True
        assert result.returncode == 0
        assert result.stdout == "output"
        sandbox_deps.manager.run.assert_called_once_with(["ls", "/"])

    @pytest.mark.asyncio
    async def test_failed_command(self, sandbox_deps):
        """Test failed command execution."""
        # Mock failed result
        mock_result = ProcessResult(
            command=("test",),
            stdout="",
            stderr="command not found",
            returncode=127,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        cmd_input = CommandInput(command=["nonexistent"])
        result = await run_command(sandbox_deps, cmd_input)

        assert result.succeeded is False
        assert result.returncode == 127
        assert "command not found" in result.stderr


class TestReadFile:
    """Test read_file tool."""

    @pytest.mark.asyncio
    async def test_successful_read(self, sandbox_deps):
        """Test successful file read."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="file contents",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        file_input = FileReadInput(path="/etc/hostname")
        content = await read_file(sandbox_deps, file_input)

        assert content == "file contents"
        sandbox_deps.manager.run.assert_called_once_with(["cat", "/etc/hostname"])

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, sandbox_deps):
        """Test reading non-existent file."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="",
            stderr="cat: /nonexistent: No such file or directory",
            returncode=1,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        file_input = FileReadInput(path="/nonexistent")
        content = await read_file(sandbox_deps, file_input)

        assert "Error reading file:" in content
        assert "No such file or directory" in content


class TestListDirectory:
    """Test list_directory tool."""

    @pytest.mark.asyncio
    async def test_simple_list(self, sandbox_deps):
        """Test simple directory listing."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="file1\nfile2\nfile3",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        dir_input = DirectoryListInput(path="/tmp")
        listing = await list_directory(sandbox_deps, dir_input)

        assert "file1" in listing
        sandbox_deps.manager.run.assert_called_once_with(["ls", "/tmp"])

    @pytest.mark.asyncio
    async def test_long_format_list(self, sandbox_deps):
        """Test directory listing with long format."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="drwxr-xr-x 2 user group 4096 Jan 1 file1",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        dir_input = DirectoryListInput(path="/tmp", long_format=True)
        listing = await list_directory(sandbox_deps, dir_input)

        assert "drwxr-xr-x" in listing
        sandbox_deps.manager.run.assert_called_once_with(["ls", "-l", "/tmp"])

    @pytest.mark.asyncio
    async def test_show_hidden(self, sandbox_deps):
        """Test directory listing with hidden files."""
        mock_result = ProcessResult(
            command=("test",),
            stdout=".hidden\nvisible",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        dir_input = DirectoryListInput(path="/tmp", show_hidden=True)
        listing = await list_directory(sandbox_deps, dir_input)

        assert ".hidden" in listing
        sandbox_deps.manager.run.assert_called_once_with(["ls", "-a", "/tmp"])

    @pytest.mark.asyncio
    async def test_all_options(self, sandbox_deps):
        """Test directory listing with all options."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="output",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        dir_input = DirectoryListInput(path="/tmp", long_format=True, show_hidden=True)
        await list_directory(sandbox_deps, dir_input)

        sandbox_deps.manager.run.assert_called_once_with(["ls", "-l", "-a", "/tmp"])


class TestCheckDiskUsage:
    """Test check_disk_usage tool."""

    @pytest.mark.asyncio
    async def test_disk_usage(self, sandbox_deps):
        """Test disk usage check."""
        mock_result = ProcessResult(
            command=("test",),
            stdout=(
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1       100G   50G   50G  50% /"
            ),
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        usage = await check_disk_usage(sandbox_deps)

        assert "Filesystem" in usage
        assert "50%" in usage
        sandbox_deps.manager.run.assert_called_once_with(["df", "-h"])

    @pytest.mark.asyncio
    async def test_disk_usage_error(self, sandbox_deps):
        """Test disk usage check with error."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="",
            stderr="df: cannot access '/': Permission denied",
            returncode=1,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        usage = await check_disk_usage(sandbox_deps)

        assert "Permission denied" in usage


class TestCheckMemory:
    """Test check_memory tool."""

    @pytest.mark.asyncio
    async def test_memory_check(self, sandbox_deps):
        """Test memory usage check."""
        mock_result = ProcessResult(
            command=("test",),
            stdout=(
                "              total        used        free\n"
                "Mem:           16Gi       8Gi        8Gi"
            ),
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        usage = await check_memory(sandbox_deps)

        assert "total" in usage
        assert "16Gi" in usage
        sandbox_deps.manager.run.assert_called_once_with(["free", "-h"])


class TestSearchFiles:
    """Test search_files tool."""

    @pytest.mark.asyncio
    async def test_search_files(self, sandbox_deps):
        """Test file search."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="/var/log/syslog\n/var/log/auth.log",
            stderr="",
            returncode=0,
            duration=0.5,
        )
        sandbox_deps.manager.run.return_value = mock_result

        results = await search_files(sandbox_deps, pattern="*.log")

        assert "/var/log/syslog" in results
        sandbox_deps.manager.run.assert_called_once_with(["find", "/", "-name", "*.log"])


class TestGrepContent:
    """Test grep_content tool."""

    @pytest.mark.asyncio
    async def test_grep_simple(self, sandbox_deps):
        """Test simple grep search."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="line with pattern",
            stderr="",
            returncode=0,
            duration=0.1,
        )
        sandbox_deps.manager.run.return_value = mock_result

        results = await grep_content(
            sandbox_deps, pattern="pattern", path="/etc/hosts", recursive=False
        )

        assert "pattern" in results
        sandbox_deps.manager.run.assert_called_once_with(["grep", "pattern", "/etc/hosts"])

    @pytest.mark.asyncio
    async def test_grep_recursive(self, sandbox_deps):
        """Test recursive grep search."""
        mock_result = ProcessResult(
            command=("test",),
            stdout="/etc/file1:match\n/etc/file2:match",
            stderr="",
            returncode=0,
            duration=0.2,
        )
        sandbox_deps.manager.run.return_value = mock_result

        results = await grep_content(sandbox_deps, pattern="pattern", path="/etc", recursive=True)

        assert "/etc/file1" in results
        sandbox_deps.manager.run.assert_called_once_with(["grep", "-r", "pattern", "/etc"])
