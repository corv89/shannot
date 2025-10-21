"""Tests for executor abstraction and implementations.

This module tests the SandboxExecutor interface and its implementations
(LocalExecutor and SSHExecutor).
"""

import platform
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shannot.execution import SandboxExecutor
from shannot.process import ProcessResult
from shannot.sandbox import SandboxProfile


# Mock executor for testing interface
class MockExecutor(SandboxExecutor):
    """Mock executor for testing the interface."""

    def __init__(self):
        self.commands_run = []

    async def run_command(
        self, profile: SandboxProfile, command: list[str], timeout: int = 30
    ) -> ProcessResult:
        self.commands_run.append(command)
        return ProcessResult(
            command=tuple(command), returncode=0, stdout="mock output\n", stderr="", duration=0.1
        )


class TestSandboxExecutorInterface:
    """Tests for the SandboxExecutor abstract interface."""

    @pytest.mark.asyncio
    async def test_executor_interface_run_command(self):
        """Test basic executor interface."""
        executor = MockExecutor()
        profile = SandboxProfile(name="test", allowed_commands=["echo"])

        result = await executor.run_command(profile, ["echo", "hello"])

        assert result.returncode == 0
        assert result.stdout == "mock output\n"
        assert executor.commands_run == [["echo", "hello"]]

    @pytest.mark.asyncio
    async def test_executor_read_file_default_implementation(self):
        """Test default read_file implementation uses cat."""
        executor = MockExecutor()
        profile = SandboxProfile(name="test", allowed_commands=["cat"])

        content = await executor.read_file(profile, "/etc/os-release")

        # Default implementation calls 'cat'
        assert executor.commands_run == [["cat", "/etc/os-release"]]
        assert content == "mock output\n"

    @pytest.mark.asyncio
    async def test_executor_cleanup_default(self):
        """Test default cleanup method does nothing."""
        executor = MockExecutor()
        await executor.cleanup()  # Should not raise


class TestLocalExecutor:
    """Tests for LocalExecutor."""

    @pytest.mark.skipif(platform.system() != "Linux", reason="LocalExecutor requires Linux")
    def test_local_executor_init_on_linux(self):
        """Test LocalExecutor initialization on Linux."""
        try:
            from shannot.executors import LocalExecutor

            executor = LocalExecutor()
            assert executor.bwrap_path.exists()
            assert executor.bwrap_path.name == "bwrap"
        except RuntimeError as e:
            # bubblewrap might not be installed
            if "not found" not in str(e):
                raise

    @pytest.mark.skipif(platform.system() == "Linux", reason="Test non-Linux rejection")
    def test_local_executor_rejects_non_linux(self):
        """Test that LocalExecutor raises on non-Linux platforms."""
        from shannot.executors import LocalExecutor

        with pytest.raises(RuntimeError, match="requires Linux"):
            LocalExecutor()

    @pytest.mark.skipif(platform.system() != "Linux", reason="LocalExecutor requires Linux")
    def test_local_executor_with_explicit_path(self, tmp_path):
        """Test LocalExecutor with explicit bwrap path."""
        from shannot.executors import LocalExecutor

        # Create a fake bwrap executable
        bwrap_path = tmp_path / "bwrap"
        bwrap_path.write_text("#!/bin/sh\n")
        bwrap_path.chmod(0o755)

        executor = LocalExecutor(bwrap_path=bwrap_path)
        assert executor.bwrap_path == bwrap_path

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() != "Linux", reason="LocalExecutor requires Linux")
    @pytest.mark.requires_bwrap
    async def test_local_executor_run_command(self):
        """Test running a command with LocalExecutor."""
        from shannot import SandboxBind
        from shannot.executors import LocalExecutor

        executor = LocalExecutor()
        profile = SandboxProfile(
            name="test",
            allowed_commands=["echo"],
            binds=[
                SandboxBind(source=Path("/usr"), target=Path("/usr"), read_only=True),
                SandboxBind(source=Path("/bin"), target=Path("/bin"), read_only=True),
                SandboxBind(source=Path("/lib"), target=Path("/lib"), read_only=True),
                SandboxBind(source=Path("/lib64"), target=Path("/lib64"), read_only=True),
            ],
            tmpfs_paths=[Path("/tmp")],
        )

        result = await executor.run_command(profile, ["echo", "hello world"], timeout=10)

        assert result.returncode == 0
        assert "hello world" in result.stdout


class TestSSHExecutor:
    """Tests for SSHExecutor with mocked SSH connections."""

    @pytest.fixture
    def mock_ssh_connection(self):
        """Create a mock SSH connection."""
        conn = AsyncMock()
        result = MagicMock()
        result.stdout = "test output\n"
        result.stderr = ""
        result.exit_status = 0
        conn.run = AsyncMock(return_value=result)
        conn.close = MagicMock()
        conn.is_closed = MagicMock(return_value=False)
        conn.wait_closed = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_ssh_executor_init(self):
        """Test SSHExecutor initialization."""
        pytest.importorskip("asyncssh")
        from shannot.executors import SSHExecutor

        executor = SSHExecutor(
            host="test.example.com",
            username="testuser",
            key_file=Path("/tmp/test_key"),
            port=2222,
        )

        assert executor.host == "test.example.com"
        assert executor.username == "testuser"
        assert executor.port == 2222

    @pytest.mark.asyncio
    async def test_ssh_executor_run_command(self, mock_ssh_connection):
        """Test SSH command execution with mocked connection."""
        pytest.importorskip("asyncssh")
        from shannot.executors import SSHExecutor

        executor = SSHExecutor(host="test.example.com")
        profile = SandboxProfile(name="test", allowed_commands=["echo"])

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_ssh_connection):
            result = await executor.run_command(profile, ["echo", "hello"], timeout=10)

        assert result.stdout == "test output\n"
        assert result.returncode == 0
        assert result.command == ("echo", "hello")
        mock_ssh_connection.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_ssh_executor_connection_pooling(self, mock_ssh_connection):
        """Test that SSH connections are pooled and reused."""
        pytest.importorskip("asyncssh")
        from shannot.executors import SSHExecutor

        executor = SSHExecutor(host="test.example.com", connection_pool_size=2)
        profile = SandboxProfile(name="test", allowed_commands=["echo"])

        with patch(
            "asyncssh.connect", new_callable=AsyncMock, return_value=mock_ssh_connection
        ) as mock_connect:
            # Run 5 commands
            for i in range(5):
                await executor.run_command(profile, ["echo", str(i)])

            # Should only create up to pool_size connections
            assert mock_connect.call_count <= 2

        await executor.cleanup()

    @pytest.mark.asyncio
    async def test_ssh_executor_timeout_handling(self, mock_ssh_connection):
        """Test SSH timeout handling."""
        pytest.importorskip("asyncssh")
        from shannot.executors import SSHExecutor

        executor = SSHExecutor(host="test.example.com")
        profile = SandboxProfile(name="test", allowed_commands=["sleep"])

        # Mock timeout error - use generic TimeoutError instead of asyncssh.TimeoutError
        mock_ssh_connection.run = AsyncMock(side_effect=TimeoutError("Command timed out"))

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_ssh_connection):
            with pytest.raises(TimeoutError, match="timed out"):
                await executor.run_command(profile, ["sleep", "100"], timeout=1)

    @pytest.mark.asyncio
    async def test_ssh_executor_cleanup(self, mock_ssh_connection):
        """Test cleanup closes all pooled connections."""
        pytest.importorskip("asyncssh")
        from shannot.executors import SSHExecutor

        executor = SSHExecutor(host="test.example.com")

        with patch("asyncssh.connect", new_callable=AsyncMock, return_value=mock_ssh_connection):
            # Create some connections
            await executor._get_connection()
            await executor._get_connection()

        # Cleanup should close all
        await executor.cleanup()
        assert len(executor._connection_pool) == 0

    @pytest.mark.asyncio
    async def test_ssh_executor_connection_failure(self):
        """Test SSH connection failure handling."""
        pytest.importorskip("asyncssh")
        from shannot.executors import SSHExecutor

        executor = SSHExecutor(host="nonexistent.example.com")
        profile = SandboxProfile(name="test", allowed_commands=["echo"])

        # Use generic Exception instead of asyncssh.Error
        mock_connect = AsyncMock(side_effect=Exception("Connection failed"))
        with patch("asyncssh.connect", mock_connect):
            with pytest.raises(RuntimeError, match="Failed to connect"):
                await executor.run_command(profile, ["echo", "test"])
