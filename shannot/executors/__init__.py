"""Executor implementations for sandbox command execution.

This package provides different execution strategies for running
sandboxed commands:

- LocalExecutor: Execute on local Linux system with bubblewrap
- SSHExecutor: Execute on remote Linux system via SSH

All executors implement the SandboxExecutor interface defined in
shannot.execution, ensuring consistent behavior regardless of
execution strategy.

Example:
    Local execution (Linux only):
        >>> from shannot.executors import LocalExecutor
        >>> executor = LocalExecutor()
        >>> result = await executor.run_command(profile, ["ls", "/"])

    Remote execution (any platform):
        >>> from shannot.executors import SSHExecutor
        >>> executor = SSHExecutor(host="prod.example.com")
        >>> result = await executor.run_command(profile, ["ls", "/"])
"""

from shannot.executors.local import LocalExecutor

__all__ = ["LocalExecutor"]

# SSHExecutor is imported conditionally since it requires asyncssh
try:
    from shannot.executors.ssh import SSHExecutor  # noqa: F401

    __all__.append("SSHExecutor")
except ImportError:
    # asyncssh not installed - SSH executor not available
    pass
