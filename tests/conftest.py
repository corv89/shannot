"""
Pytest configuration and shared fixtures for shannot tests.
"""

from __future__ import annotations

import platform
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest  # type: ignore[reportMissingImports]

from shannot import SandboxBind, SandboxProfile


def is_linux() -> bool:
    """Check if running on Linux."""
    return platform.system() == "Linux"


def has_bubblewrap() -> bool:
    """Check if bubblewrap is available on the system."""
    return shutil.which("bwrap") is not None


# Pytest markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "linux_only: mark test as requiring Linux platform",
    )
    config.addinivalue_line(
        "markers",
        "requires_bwrap: mark test as requiring bubblewrap to be installed",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (may be slower)",
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip tests based on platform and requirements."""
    if "linux_only" in [mark.name for mark in item.iter_markers()]:
        if not is_linux():
            pytest.skip("Test requires Linux platform")

    if "requires_bwrap" in [mark.name for mark in item.iter_markers()]:
        if not has_bubblewrap():
            pytest.skip("Test requires bubblewrap (bwrap) to be installed")


# Shared fixtures
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory that's cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def minimal_profile() -> SandboxProfile:
    """Provide a minimal valid sandbox profile for testing."""
    return SandboxProfile(
        name="test-minimal",
        allowed_commands=["ls", "cat", "echo"],
        binds=[
            SandboxBind(
                source=Path("/usr"),
                target=Path("/usr"),
                read_only=True,
                create_target=False,
            ),
            SandboxBind(
                source=Path("/lib"),
                target=Path("/lib"),
                read_only=True,
                create_target=False,
            ),
            SandboxBind(
                source=Path("/lib64"),
                target=Path("/lib64"),
                read_only=True,
                create_target=False,
            ),
            SandboxBind(
                source=Path("/etc"),
                target=Path("/etc"),
                read_only=True,
                create_target=False,
            ),
        ],
        tmpfs_paths=[Path("/tmp")],
        environment={"PATH": "/usr/bin:/bin"},
        network_isolation=True,  # Full isolation by default
    )


@pytest.fixture
def bwrap_path() -> Path:
    """Provide the path to bubblewrap executable."""
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        pytest.skip("bubblewrap not found in PATH")
        raise RuntimeError("Unreachable")  # Type narrowing helper
    return Path(bwrap)


@pytest.fixture
def profile_json_minimal(temp_dir: Path) -> Path:
    """Create a minimal profile JSON file for testing."""
    profile_path = temp_dir / "minimal.json"
    profile_content = """{
  "name": "test-minimal",
  "allowed_commands": ["ls", "cat", "echo", "df", "free", "find", "grep"],
  "binds": [
    {"source": "/usr", "target": "/usr", "read_only": true},
    {"source": "/lib", "target": "/lib", "read_only": true},
    {"source": "/lib64", "target": "/lib64", "read_only": true},
    {"source": "/etc", "target": "/etc", "read_only": true},
    {"source": "/proc", "target": "/proc", "read_only": true},
    {"source": "/sys", "target": "/sys", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {"PATH": "/usr/bin:/bin"},
  "network_isolation": true
}"""
    profile_path.write_text(profile_content)
    return profile_path


@pytest.fixture
def profile_json_with_relative_paths(temp_dir: Path) -> Path:
    """Create a profile with relative paths for testing path resolution."""
    profile_dir = temp_dir / "profiles"
    profile_dir.mkdir()

    # Create a dummy source directory
    source_dir = profile_dir / "data"
    source_dir.mkdir()

    profile_path = profile_dir / "relative.json"
    profile_content = """{
  "name": "test-relative",
  "allowed_commands": ["ls"],
  "binds": [
    {"source": "data", "target": "/data", "read_only": true},
    {"source": "/usr", "target": "/usr", "read_only": true}
  ],
  "tmpfs_paths": ["/tmp"],
  "environment": {"PATH": "/usr/bin"}
}"""
    profile_path.write_text(profile_content)
    return profile_path
