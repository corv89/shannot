"""
Shannot - bubblewrap-based sandbox for read-only system access.

This package provides a simple, secure way to execute commands in a read-only
sandbox using Linux's bubblewrap (bwrap) tool. It's designed for remote system
diagnostics and monitoring, particularly with LLM-based agents where strict
read-only enforcement is critical.

Quick Start
-----------
Command-line usage::

    $ shannot run ls /
    $ shannot verify
    $ shannot export

Python API::

    from shannot import SandboxManager, load_profile_from_path

    profile = load_profile_from_path("~/.config/shannot/profile.json")
    manager = SandboxManager(profile, Path("/usr/bin/bwrap"))
    result = manager.run(["ls", "/"])
    print(result.stdout)

Main Components
---------------
- SandboxProfile: Declarative sandbox configuration
- SandboxManager: Execute commands in the sandbox
- SandboxBind: Define filesystem bind mounts
- BubblewrapCommandBuilder: Low-level bwrap command construction

---

.. include:: ../docs/README.md
"""

from .process import ProcessResult, ensure_tool_available, run_process
from .sandbox import (
    BubblewrapCommandBuilder,
    SandboxBind,
    SandboxError,
    SandboxManager,
    SandboxProfile,
    load_profile_from_mapping,
    load_profile_from_path,
)

__version__ = "0.1.1"
__all__ = [
    "BubblewrapCommandBuilder",
    "SandboxBind",
    "SandboxError",
    "SandboxManager",
    "SandboxProfile",
    "ProcessResult",
    "load_profile_from_mapping",
    "load_profile_from_path",
    "ensure_tool_available",
    "run_process",
]
