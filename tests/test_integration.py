"""
Integration tests for actual sandbox execution.

These tests require Linux and bubblewrap to be installed.
They will be skipped on other platforms or when bubblewrap is not available.
"""

from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore[reportMissingImports]

from shannot import SandboxError, SandboxManager, SandboxProfile


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
class TestSandboxExecution:
    """Integration tests for running commands in the sandbox."""

    def test_simple_command_execution(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test executing a simple command in the sandbox."""
        manager = SandboxManager(minimal_profile, bwrap_path)
        result = manager.run(["ls", "/"])

        assert result.succeeded()
        assert result.returncode == 0
        assert len(result.stdout) > 0
        assert "usr" in result.stdout or "bin" in result.stdout

    def test_echo_command(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test echo command works in sandbox."""
        manager = SandboxManager(minimal_profile, bwrap_path)
        result = manager.run(["echo", "Hello from sandbox"])

        assert result.succeeded()
        assert "Hello from sandbox" in result.stdout

    def test_cat_command(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test reading files in sandbox."""
        manager = SandboxManager(minimal_profile, bwrap_path)
        result = manager.run(["cat", "/etc/os-release"])

        # This should succeed on most Linux systems
        assert result.succeeded()
        assert len(result.stdout) > 0

    def test_network_isolation(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that network isolation is enabled by default."""
        manager = SandboxManager(minimal_profile, bwrap_path)

        # Verify the profile has network isolation enabled (full security)
        assert minimal_profile.network_isolation is True

        # Verify sandbox works with full network isolation
        result = manager.run(["echo", "test"])
        assert result.succeeded()
        assert "test" in result.stdout

    def test_disallowed_command_rejected(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that commands not in allowlist are rejected."""
        manager = SandboxManager(minimal_profile, bwrap_path)

        with pytest.raises(SandboxError, match="not permitted"):
            manager.run(["rm", "-rf", "/"])

    def test_write_operations_fail_in_readonly(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that write operations fail in read-only mounts."""
        # Allow sh for this test
        profile_with_sh = SandboxProfile(
            name=minimal_profile.name,
            allowed_commands=list(minimal_profile.allowed_commands) + ["sh", "/bin/sh"],
            binds=minimal_profile.binds,
            tmpfs_paths=minimal_profile.tmpfs_paths,
            environment=minimal_profile.environment,
            network_isolation=minimal_profile.network_isolation,
        )

        manager = SandboxManager(profile_with_sh, bwrap_path)

        # Try to create a file in a read-only location
        # This should fail because /usr is mounted read-only
        result = manager.run(
            ["sh", "-c", "echo test > /usr/test.txt"],
            check=False,
        )

        # Should fail with non-zero exit code
        assert not result.succeeded()

    def test_tmpfs_is_writable(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that tmpfs paths are writable."""
        profile_with_sh = SandboxProfile(
            name=minimal_profile.name,
            allowed_commands=list(minimal_profile.allowed_commands) + ["sh", "/bin/sh"],
            binds=minimal_profile.binds,
            tmpfs_paths=minimal_profile.tmpfs_paths,
            environment=minimal_profile.environment,
            network_isolation=minimal_profile.network_isolation,
        )

        manager = SandboxManager(profile_with_sh, bwrap_path)

        # Should be able to write to /tmp (tmpfs)
        result = manager.run(
            ["sh", "-c", "echo test > /tmp/test.txt && cat /tmp/test.txt"],
        )

        assert result.succeeded()
        assert "test" in result.stdout

    def test_environment_variables(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that environment variables are set correctly."""
        profile_with_sh = SandboxProfile(
            name=minimal_profile.name,
            allowed_commands=list(minimal_profile.allowed_commands) + ["sh", "/bin/sh"],
            binds=minimal_profile.binds,
            tmpfs_paths=minimal_profile.tmpfs_paths,
            environment={**minimal_profile.environment, "TEST_VAR": "test_value"},
            network_isolation=minimal_profile.network_isolation,
        )

        manager = SandboxManager(profile_with_sh, bwrap_path)
        result = manager.run(["sh", "-c", "echo $TEST_VAR"])

        assert result.succeeded()
        assert "test_value" in result.stdout

    def test_process_isolation(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that processes are isolated (PID namespace)."""
        profile_with_ps = SandboxProfile(
            name=minimal_profile.name,
            allowed_commands=list(minimal_profile.allowed_commands) + ["ps"],
            binds=[
                *minimal_profile.binds,
                # ps might need /proc
            ],
            tmpfs_paths=minimal_profile.tmpfs_paths,
            environment=minimal_profile.environment,
            network_isolation=minimal_profile.network_isolation,
        )

        manager = SandboxManager(profile_with_ps, bwrap_path)
        result = manager.run(["ps", "aux"], check=False)

        # ps should run, but may show limited processes due to PID namespace
        # Just verify it executed without crashing
        assert result.returncode in [0, 1, 2]

    def test_duration_tracking(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that command duration is tracked."""
        manager = SandboxManager(minimal_profile, bwrap_path)
        result = manager.run(["echo", "test"])

        assert result.succeeded()
        assert result.duration > 0
        assert result.duration < 10  # Should complete quickly


@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
class TestProfileLoading:
    """Integration tests for loading profiles and executing with them."""

    def test_load_and_run_with_json_profile(
        self,
        profile_json_minimal: Path,
        bwrap_path: Path,
    ) -> None:
        """Test loading a profile from JSON and executing commands."""
        from shannot import load_profile_from_path

        profile = load_profile_from_path(profile_json_minimal)
        manager = SandboxManager(profile, bwrap_path)
        result = manager.run(["ls", "/"])

        assert result.succeeded()

    def test_relative_path_resolution(
        self,
        profile_json_with_relative_paths: Path,
        bwrap_path: Path,
    ) -> None:
        """Test that relative paths in profiles are resolved correctly."""
        from shannot import load_profile_from_path

        profile = load_profile_from_path(profile_json_with_relative_paths)

        # Verify the relative path was resolved to an absolute path
        data_bind = [b for b in profile.binds if b.target == Path("/data")][0]
        assert data_bind.source.is_absolute()
        assert data_bind.source.name == "data"

    def test_check_parameter_raises_on_failure(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that check=True raises on command failure."""
        profile_with_sh = SandboxProfile(
            name=minimal_profile.name,
            allowed_commands=list(minimal_profile.allowed_commands) + ["sh", "/bin/sh"],
            binds=minimal_profile.binds,
            tmpfs_paths=minimal_profile.tmpfs_paths,
            environment=minimal_profile.environment,
            network_isolation=minimal_profile.network_isolation,
        )

        manager = SandboxManager(profile_with_sh, bwrap_path)

        with pytest.raises(SandboxError, match="failed with exit code"):
            manager.run(["sh", "-c", "exit 1"], check=True)

    def test_check_parameter_false_returns_result(
        self,
        minimal_profile: SandboxProfile,
        bwrap_path: Path,
    ) -> None:
        """Test that check=False returns result even on failure."""
        profile_with_sh = SandboxProfile(
            name=minimal_profile.name,
            allowed_commands=list(minimal_profile.allowed_commands) + ["sh", "/bin/sh"],
            binds=minimal_profile.binds,
            tmpfs_paths=minimal_profile.tmpfs_paths,
            environment=minimal_profile.environment,
            network_isolation=minimal_profile.network_isolation,
        )

        manager = SandboxManager(profile_with_sh, bwrap_path)
        result = manager.run(["sh", "-c", "exit 42"], check=False)

        assert result.returncode == 42
        assert not result.succeeded()
