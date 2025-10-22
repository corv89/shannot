# Shannot Executor Architecture

## Overview

Shannot supports multiple execution strategies through a unified `SandboxExecutor` interface, enabling flexible deployment across platforms and environments.

**Key Requirements**:
- Support macOS/Windows clients executing on Linux remotes
- Support native Linux execution when bubblewrap is available
- Use SSH for remote execution (no custom protocols)
- Zero deployment to remote systems (only bubblewrap + sshd needed)

## Executor Types

```
┌─────────────────────────────────────────────────────────────┐
│                    SandboxExecutor (ABC)                     │
│  ┌────────────────────────────────────────────────────┐     │
│  │  async def run_command(profile, command) -> Result │     │
│  │  async def read_file(profile, path) -> str         │     │
│  │  async def cleanup()                               │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ implements
                     ┌──────┴──────┐
                     │             │
              ┌──────▼──────┐  ┌──▼────────┐
              │   Local     │  │    SSH    │
              │  Executor   │  │  Executor │
              └─────────────┘  └───────────┘
```

## Platform Support Matrix

| Platform | Local Executor | SSH Executor | Remote Target |
|----------|----------------|--------------|---------------|
| **Linux (with bwrap)** | ✅ Yes | ✅ Yes | ✅ Can be remote |
| **Linux (no bwrap)** | ❌ No | ✅ Yes | ✅ Can be remote |
| **macOS** | ❌ No | ✅ Yes | ❌ Must be Linux |
| **Windows** | ❌ No | ✅ Yes | ❌ Must be Linux |

## Architecture by Use Case

### Use Case 1: Linux Developer with Local Workstation

```
┌────────────────────────────────────┐
│  Linux Laptop (bubblewrap)         │
│                                    │
│  shannot (Local Executor)          │
│    ↓                               │
│  bubblewrap                        │
│    ↓                               │
│  Sandboxed execution               │
└────────────────────────────────────┘

Execution path: Python → bubblewrap → sandbox
Latency: ~5ms
Network: None
Deployment: Just install bubblewrap
```

**Example:**
```bash
# Linux user with bubblewrap installed
pip install shannot
shannot run ls /          # Uses LocalExecutor by default
shannot mcp install       # MCP server uses LocalExecutor
```

---

### Use Case 2: macOS Developer → Linux Servers

```
┌─────────────────────────────────────┐
│  macOS (Claude Desktop)             │
│                                     │
│  shannot (SSH Executor)             │
│    ↓                                │
│  SSH client                         │
└─────────────────────────────────────┘
              ↓ SSH (port 22)
┌─────────────────────────────────────┐
│  Linux Server (prod)                │
│                                     │
│  sshd                               │
│    ↓                                │
│  bubblewrap                         │
│    ↓                                │
│  Sandboxed execution                │
└─────────────────────────────────────┘

Execution path: Python → SSH → bubblewrap → sandbox
Latency: ~50-200ms
Network: SSH (port 22)
Deployment: Only bubblewrap on remote
```

**Example:**
```bash
# macOS user managing Linux servers
pip install shannot[mcp]
shannot remote add prod --host prod.example.com
shannot remote prod run -- ls /
shannot mcp install --remote prod

# Claude Desktop on macOS now controls Linux servers!
```

---

### Use Case 3: Windows Developer → Linux Servers

```
┌─────────────────────────────────────┐
│  Windows (Claude Desktop)           │
│                                     │
│  shannot (SSH Executor)             │
│    ↓                                │
│  OpenSSH client                     │
└─────────────────────────────────────┘
              ↓ SSH
┌─────────────────────────────────────┐
│  Linux Server (prod)                │
│                                     │
│  sshd → bubblewrap → sandbox        │
└─────────────────────────────────────┘

Same as macOS use case
```

**Example:**
```powershell
# Windows user with Python and OpenSSH
pip install shannot[mcp]
shannot remote add prod --host prod.example.com
shannot remote prod run -- ls /
```

---

### Use Case 4: Linux Developer → Multiple Remotes

```
┌────────────────────────────────────────┐
│  Linux Laptop                          │
│                                        │
│  shannot (Multiple Executors)          │
│    ├─ Local → bubblewrap (local)       │
│    ├─ SSH → prod1 (via SSH)            │
│    ├─ SSH → prod2 (via SSH)            │
│    └─ SSH → staging (via SSH)          │
└────────────────────────────────────────┘
         │         │        │         │
         │         │        │         └──→ SSH
         │         │        └──────────→ SSH
         │         └───────────────────→ SSH
         └─────────────────────────────→ Local
```

**Example:**
```bash
# Linux user with local + remote execution
shannot run ls /                    # Local (fastest)
shannot remote prod1 run -- ls /    # SSH to prod1
shannot remote prod2 run -- ls /    # SSH to prod2
shannot remote staging run -- ls /  # SSH to staging
```

---

## Code Architecture

### Executor Interface

```python
# shannot/execution.py
from abc import ABC, abstractmethod
from typing import Literal

ExecutorType = Literal["local", "ssh"]

class SandboxExecutor(ABC):
    """Abstract base for all execution strategies"""

    @abstractmethod
    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        """Execute command in sandbox

        Args:
            profile: Sandbox profile configuration
            command: Command to execute as list of strings
            timeout: Timeout in seconds

        Returns:
            ProcessResult with stdout, stderr, returncode, duration

        Raises:
            TimeoutError: Command exceeded timeout
            RuntimeError: Execution error (SSH connection, etc.)
        """
        ...

    async def read_file(
        self,
        profile: SandboxProfile,
        path: str
    ) -> str:
        """Read file (default: cat via run_command)"""
        result = await self.run_command(profile, ["cat", path])
        if result.returncode != 0:
            raise FileNotFoundError(path)
        return result.stdout

    async def cleanup(self):
        """Cleanup resources (override if needed)"""
        pass
```

### Local Executor

```python
# shannot/executors/local.py
from shannot.execution import SandboxExecutor
from shannot.sandbox import BubblewrapCommandBuilder
from shannot.process import run_process

class LocalExecutor(SandboxExecutor):
    """Execute on local Linux system using bubblewrap

    Requires:
        - Linux operating system
        - bubblewrap installed and in PATH

    This executor runs commands directly on the local system using
    bubblewrap for sandboxing. It's the fastest option but only works
    on Linux with bubblewrap installed.
    """

    def __init__(self, bwrap_path: Optional[Path] = None):
        """Initialize local executor

        Args:
            bwrap_path: Optional explicit path to bwrap binary.
                       If None, searches PATH.
        """
        self.bwrap_path = bwrap_path or self._find_bwrap()

    def _find_bwrap(self) -> Path:
        """Locate bubblewrap executable"""
        import shutil
        path = shutil.which("bwrap")
        if not path:
            raise RuntimeError("bubblewrap not found in PATH")
        return Path(path)

    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        # Build bubblewrap command
        builder = BubblewrapCommandBuilder(profile)
        bwrap_cmd = builder.build(command)

        # Execute locally
        return await run_process(bwrap_cmd, timeout=timeout)
```

**Requirements:**
- Linux operating system
- `bubblewrap` installed
- No network needed

**When to use:**
- Linux workstation/laptop
- Development/testing
- Fastest execution (no network overhead)

---

### SSH Executor

```python
# shannot/executors/ssh.py
import asyncio
import asyncssh
import shlex
from pathlib import Path
from typing import Optional

from shannot.execution import SandboxExecutor
from shannot.sandbox import BubblewrapCommandBuilder, SandboxProfile
from shannot.process import ProcessResult

class SSHExecutor(SandboxExecutor):
    """Execute on remote Linux system via SSH

    This executor builds bubblewrap commands locally, then executes
    them on a remote Linux system via SSH. The remote system only
    needs bubblewrap and sshd - no Python or Shannot installation.

    Features:
        - Connection pooling for performance
        - SSH key authentication
        - Timeout handling
        - Works from any platform (Linux, macOS, Windows)
    """

    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        key_file: Optional[Path] = None,
        port: int = 22,
        connection_pool_size: int = 5
    ):
        """Initialize SSH executor

        Args:
            host: Remote hostname or IP
            username: SSH username (None = use current user)
            key_file: Path to SSH private key (None = use SSH config/agent)
            port: SSH port
            connection_pool_size: Max pooled connections
        """
        self.host = host
        self.username = username
        self.key_file = key_file
        self.port = port
        self._connection_pool: list[asyncssh.SSHClientConnection] = []
        self._pool_size = connection_pool_size
        self._lock = asyncio.Lock()

    async def _get_connection(self) -> asyncssh.SSHClientConnection:
        """Get or create SSH connection from pool"""
        async with self._lock:
            if self._connection_pool:
                return self._connection_pool.pop()

            return await asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                client_keys=[str(self.key_file)] if self.key_file else None,
                known_hosts=None  # TODO: Proper host key validation
            )

    async def _release_connection(self, conn: asyncssh.SSHClientConnection):
        """Return connection to pool or close if pool full"""
        async with self._lock:
            if len(self._connection_pool) < self._pool_size:
                self._connection_pool.append(conn)
            else:
                conn.close()

    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        # Build bubblewrap command locally
        builder = BubblewrapCommandBuilder(profile)
        bwrap_cmd = builder.build(command)

        # Execute via SSH
        conn = await self._get_connection()
        try:
            result = await conn.run(
                shlex.join(bwrap_cmd),
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )

            return ProcessResult(
                command=tuple(command),
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.exit_status or 0,
                duration=0.0  # asyncssh doesn't track timing
            )
        except asyncssh.TimeoutError as e:
            raise TimeoutError(f"Command timed out after {timeout}s") from e
        except asyncssh.Error as e:
            raise RuntimeError(f"SSH error: {e}") from e
        finally:
            await self._release_connection(conn)

    async def cleanup(self):
        """Close all pooled SSH connections"""
        async with self._lock:
            for conn in self._connection_pool:
                conn.close()
            self._connection_pool.clear()
```

**Requirements:**
- SSH client (available on all platforms)
- SSH access to Linux server
- `bubblewrap` on remote server
- Network connectivity

**When to use:**
- macOS/Windows controlling Linux servers
- Zero deployment to remote
- Leveraging existing SSH infrastructure
- Remote diagnostics from any platform

---

## Integration with MCP/Pydantic-AI

### Tools Layer

```python
# shannot/tools.py
from pydantic_ai import Agent, RunContext

class SandboxDeps:
    """Dependencies supporting any executor"""

    def __init__(
        self,
        profile: SandboxProfile,
        executor: SandboxExecutor  # Can be Local, SSH, or HTTP!
    ):
        self.profile = profile
        self.executor = executor

@agent.tool
async def run_command(
    ctx: RunContext[SandboxDeps],
    command: str
) -> str:
    """Execute command (works with any executor)"""
    result = await ctx.deps.executor.run_command(
        ctx.deps.profile,
        command.split()
    )
    return result.stdout

# Usage with different executors:

# Local (Linux only)
local_deps = SandboxDeps(
    profile=minimal_profile,
    executor=LocalExecutor()
)

# SSH (any platform → Linux)
ssh_deps = SandboxDeps(
    profile=minimal_profile,
    executor=SSHExecutor(host="prod.example.com")
)

# HTTP (any platform → agent)
http_deps = SandboxDeps(
    profile=minimal_profile,
    executor=HTTPExecutor(base_url="http://agent:8080")
)

# All use same tools!
agent = Agent("claude-3-7-sonnet", deps_type=SandboxDeps, tools=[run_command])
result = await agent.run("Check disk space", deps=ssh_deps)
```

### MCP Server

```python
# shannot/mcp_server.py
class ShannotMCPServer:
    def __init__(
        self,
        profiles: list[Path],
        executor_type: ExecutorType = "local",
        executor_config: dict = None
    ):
        self.profiles = profiles

        # Create executor based on type
        if executor_type == "local":
            self.executor = LocalExecutor()
        elif executor_type == "ssh":
            self.executor = SSHExecutor(**executor_config)
        elif executor_type == "http":
            self.executor = HTTPExecutor(**executor_config)

    async def call_tool(self, name: str, arguments: dict):
        """Tool calls use configured executor"""
        profile = self._get_profile(name)
        result = await self.executor.run_command(
            profile,
            arguments["command"].split()
        )
        return {"stdout": result.stdout}

# CLI integration
# shannot-mcp --executor local                    # Linux only
# shannot-mcp --executor ssh --host prod.example  # Any platform
# shannot-mcp --executor http --url http://agent  # Any platform
```

## Platform Detection

```python
# shannot/platform.py
import platform
import shutil

def get_available_executors() -> dict[str, bool]:
    """Detect available execution methods"""
    system = platform.system()

    return {
        "local": system == "Linux" and shutil.which("bwrap") is not None,
        "ssh": True,  # SSH client available on all platforms
        "http": True  # HTTP client available on all platforms
    }

def get_recommended_executor() -> ExecutorType:
    """Get recommended executor for this platform"""
    if get_available_executors()["local"]:
        return "local"  # Prefer local on Linux
    else:
        return "ssh"  # Fall back to SSH on macOS/Windows

# CLI usage
def main():
    available = get_available_executors()

    if not available["local"]:
        print(f"Running on {platform.system()}")
        print("Local execution not available (bubblewrap requires Linux)")
        print("Configure a remote: shannot remote add <name> --host <host>")
        return

    # Continue with local execution...
```

## Configuration

```toml
# ~/.config/shannot/config.toml

# Default executor (auto-detected if omitted)
# - On Linux with bubblewrap: "local"
# - On macOS/Windows: must configure SSH executor
default_executor = "local"

# Local executor (Linux with bubblewrap only)
[executor.local]
type = "local"
# Optional: explicit path to bubblewrap
# bwrap_path = "/usr/bin/bwrap"

# SSH executors for remote Linux systems
[executor.prod]
type = "ssh"
host = "prod-server.example.com"
username = "admin"
key_file = "~/.ssh/id_ed25519"
port = 22

[executor.staging]
type = "ssh"
host = "staging.example.com"
username = "deploy"
key_file = "~/.ssh/id_ed25519"

[executor.dev]
type = "ssh"
host = "dev.example.com"
# Uses default SSH config for auth (no key_file specified)
```

**Configuration Loading:**

```python
# shannot/config.py
import tomli
from pathlib import Path
from typing import Dict

def load_config() -> Dict:
    """Load configuration from standard locations"""
    config_paths = [
        Path.home() / ".config" / "shannot" / "config.toml",
        Path("/etc/shannot/config.toml"),
    ]

    for path in config_paths:
        if path.exists():
            with open(path, "rb") as f:
                return tomli.load(f)

    return {}

def create_executor_from_config(name: str) -> SandboxExecutor:
    """Create executor from configuration"""
    config = load_config()
    executor_config = config.get("executor", {}).get(name)

    if not executor_config:
        raise ValueError(f"Executor '{name}' not found in config")

    executor_type = executor_config["type"]

    if executor_type == "local":
        return LocalExecutor(
            bwrap_path=executor_config.get("bwrap_path")
        )
    elif executor_type == "ssh":
        return SSHExecutor(
            host=executor_config["host"],
            username=executor_config.get("username"),
            key_file=Path(executor_config["key_file"])
                if "key_file" in executor_config else None,
            port=executor_config.get("port", 22)
        )
    else:
        raise ValueError(f"Unknown executor type: {executor_type}")
```

## Decision Flow

```
User runs: shannot run ls /
    ↓
Is platform Linux?
    ├─ No (macOS/Windows)
    │   ↓
    │   Error: "Local execution requires Linux"
    │   Suggest: "Use --remote <name> or configure default remote"
    │
    └─ Yes (Linux)
        ↓
        Is bubblewrap installed?
            ├─ No
            │   ↓
            │   Error: "bubblewrap not found"
            │   Suggest: "apt-get install bubblewrap"
            │
            └─ Yes
                ↓
                Execute with LocalExecutor
                Success!

User runs: shannot remote prod run -- ls /
    ↓
Load remote config for "prod"
    ↓
Create SSHExecutor(host=prod.example.com)
    ↓
Execute via SSH
    ↓
Success! (works on any platform)
```

## Summary

| Aspect | Local | SSH |
|--------|-------|-----|
| **Client Platforms** | Linux only | Linux, macOS, Windows |
| **Remote Requirements** | bubblewrap (local) | bubblewrap + sshd |
| **Latency** | ~5-10ms | ~50-200ms |
| **Network** | None | SSH (port 22) |
| **Security** | Process isolation | SSH + process isolation |
| **Deployment** | Zero (bubblewrap only) | Zero (uses existing SSH) |
| **Best For** | Linux workstation | macOS/Windows → servers |
| **Authentication** | None | SSH keys/agent |

**Key principles**:
- Same `SandboxExecutor` interface for both local and SSH execution
- Tools/MCP code unchanged regardless of executor
- Bubblewrap command built locally, executed locally or remotely
- Remote systems need only bubblewrap + SSH (no Python/Shannot)
