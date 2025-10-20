"""Pydantic-AI tools for sandbox operations.

This module provides type-safe, reusable tools for interacting with the Shannot sandbox.
These tools can be used standalone, in MCP servers, or with Pydantic-AI agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from shannot import SandboxManager, load_profile_from_path


# Dependencies injected into tools
class SandboxDeps:
    """Dependencies for sandbox tools."""

    def __init__(
        self,
        profile_name: str = "readonly",
        profile_path: Optional[Path] = None,
        bwrap_path: Path = Path("/usr/bin/bwrap"),
    ):
        """Initialize sandbox dependencies.

        Args:
            profile_name: Name of profile to load from ~/.config/shannot/
            profile_path: Explicit path to profile (overrides profile_name)
            bwrap_path: Path to bubblewrap executable
        """
        if profile_path:
            self.profile = load_profile_from_path(profile_path)
        else:
            # Try user config first
            user_profile = Path.home() / ".config" / "shannot" / f"{profile_name}.json"
            if user_profile.exists():
                self.profile = load_profile_from_path(user_profile)
            else:
                # Fall back to bundled profiles
                bundled_profile = Path(__file__).parent.parent / "profiles" / f"{profile_name}.json"
                self.profile = load_profile_from_path(bundled_profile)

        self.manager = SandboxManager(self.profile, bwrap_path)


# Input/Output Models


class CommandInput(BaseModel):
    """Input for running a command in the sandbox."""

    command: list[str] = Field(
        description="Command and arguments to execute (e.g., ['ls', '-l', '/'])"
    )


class CommandOutput(BaseModel):
    """Output from sandbox command execution."""

    stdout: str = Field(description="Standard output from the command")
    stderr: str = Field(description="Standard error from the command")
    returncode: int = Field(description="Exit code (0 = success)")
    duration: float = Field(description="Execution time in seconds")
    succeeded: bool = Field(description="Whether the command succeeded")


class FileReadInput(BaseModel):
    """Input for reading a file."""

    path: str = Field(description="Absolute path to the file to read")


class DirectoryListInput(BaseModel):
    """Input for listing a directory."""

    path: str = Field(description="Absolute path to the directory to list")
    long_format: bool = Field(default=False, description="Show detailed information (ls -l)")
    show_hidden: bool = Field(default=False, description="Show hidden files (ls -a)")


# Core Tools


async def run_command(deps: SandboxDeps, input: CommandInput) -> CommandOutput:
    """Execute a command in the read-only sandbox.

    The sandbox provides:
    - Read-only access to system files
    - Network isolation
    - Ephemeral /tmp (changes lost after command exits)
    - Command allowlisting (only approved commands run)

    Use this for:
    - Inspecting files: cat, head, tail, grep
    - Listing directories: ls, find
    - Checking system status: df, free, ps

    Args:
        deps: Sandbox dependencies (profile, manager)
        input: Command to execute

    Returns:
        CommandOutput with stdout, stderr, returncode, duration, and success status
    """
    result = deps.manager.run(input.command)

    return CommandOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        duration=result.duration,
        succeeded=result.succeeded(),
    )


async def read_file(deps: SandboxDeps, input: FileReadInput) -> str:
    """Read the contents of a file from the system.

    Args:
        deps: Sandbox dependencies
        input: Path to file

    Returns:
        File contents as string, or error message if failed
    """
    result = deps.manager.run(["cat", input.path])
    if result.succeeded():
        return result.stdout
    else:
        return f"Error reading file: {result.stderr}"


async def list_directory(deps: SandboxDeps, input: DirectoryListInput) -> str:
    """List contents of a directory.

    Args:
        deps: Sandbox dependencies
        input: Directory path and options

    Returns:
        Directory listing as string, or error message if failed
    """
    cmd = ["ls"]
    if input.long_format:
        cmd.append("-l")
    if input.show_hidden:
        cmd.append("-a")
    cmd.append(input.path)

    result = deps.manager.run(cmd)
    return result.stdout if result.succeeded() else result.stderr


async def check_disk_usage(deps: SandboxDeps) -> str:
    """Get disk usage information for all mounted filesystems.

    Returns:
        Human-readable disk usage output (df -h), or error message if failed
    """
    result = deps.manager.run(["df", "-h"])
    return result.stdout if result.succeeded() else result.stderr


async def check_memory(deps: SandboxDeps) -> str:
    """Get memory usage information.

    Returns:
        Human-readable memory info (free -h), or error message if failed
    """
    result = deps.manager.run(["free", "-h"])
    return result.stdout if result.succeeded() else result.stderr


async def search_files(
    deps: SandboxDeps, pattern: str = Field(description="Filename pattern to search for")
) -> str:
    """Find files matching a pattern.

    Args:
        deps: Sandbox dependencies
        pattern: Pattern to search for (e.g., "*.log")

    Returns:
        List of matching file paths, or error message if failed
    """
    result = deps.manager.run(["find", "/", "-name", pattern])
    return result.stdout if result.succeeded() else result.stderr


async def grep_content(
    deps: SandboxDeps,
    pattern: str = Field(description="Text pattern to search for"),
    path: str = Field(description="File or directory to search in"),
    recursive: bool = Field(default=False, description="Search recursively in directories"),
) -> str:
    """Search for text pattern in files.

    Args:
        deps: Sandbox dependencies
        pattern: Text pattern to search for
        path: File or directory to search
        recursive: Whether to search recursively

    Returns:
        Matching lines, or error message if failed
    """
    cmd = ["grep"]
    if recursive:
        cmd.append("-r")
    cmd.extend([pattern, path])

    result = deps.manager.run(cmd)
    return result.stdout if result.succeeded() else result.stderr


# Export all tools and models
__all__ = [
    "SandboxDeps",
    "CommandInput",
    "CommandOutput",
    "FileReadInput",
    "DirectoryListInput",
    "run_command",
    "read_file",
    "list_directory",
    "check_disk_usage",
    "check_memory",
    "search_files",
    "grep_content",
]
