# Remote Execution Architecture for Shannot

This document outlines strategies for executing sandboxed commands on remote systems without deploying the full Shannot Python stack.

## Problem Statement

With LLM/MCP integration (see [LLM.md](LLM.md) and [MCP.md](MCP.md)), Shannot now has significant Python dependencies:
- `pydantic >= 2.0` (Rust core, ~10MB)
- `httpx` + transitive deps (~15MB)
- `mcp >= 1.0` (MCP SDK)
- Future: LLM client libraries

**Challenge**: How to keep remote systems lightweight while running rich LLM integrations locally?

## Architecture Options

### Option 1: Local-Only (Current)

```
┌──────────────────────────────┐
│  Local System                │
│  - Full shannot with deps    │
│  - MCP server                │
│  - LLM integration           │
│  - Local execution only      │
└──────────────────────────────┘
```

**Pros**:
- Simple, no network
- Fast execution
- Easy debugging

**Cons**:
- Can only sandbox local system
- No remote diagnostics
- Limited to one machine

**Verdict**: Good for development, insufficient for production monitoring.

---

### Option 2: SSH-Based Remote Execution (Recommended)

```
┌────────────────────────────────────────┐
│  Local System                          │
│  ┌──────────────────────────────┐     │
│  │  shannot-full                │     │
│  │  - All Python dependencies   │     │
│  │  - MCP server                │     │
│  │  - LLM agents                │     │
│  │  - SSH client                │     │
│  └──────────────────────────────┘     │
└────────────────────────────────────────┘
              ↓ SSH (port 22)
┌────────────────────────────────────────┐
│  Remote System                         │
│  Requirements:                         │
│  - bubblewrap (apt install bubblewrap) │
│  - SSH server (sshd)                   │
│  - No Python needed                    │
│  - No Shannot installation needed      │
└────────────────────────────────────────┘
```

#### How It Works

1. **Local System**: Builds bubblewrap command from profile
2. **SSH Transport**: Sends command to remote via SSH
3. **Remote Execution**: Runs `bwrap` command, returns output
4. **Local Processing**: LLM receives results, continues conversation

#### Implementation

```python
# shannot/remote_ssh.py
import asyncio
import asyncssh
import shlex
from pathlib import Path
from typing import Optional

class SSHSandboxExecutor:
    """Execute sandbox commands on remote system via SSH"""
    
    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        key_file: Optional[Path] = None,
        port: int = 22,
        connection_pool_size: int = 5
    ):
        self.host = host
        self.username = username
        self.key_file = key_file
        self.port = port
        self._connection_pool: list[asyncssh.SSHClientConnection] = []
        self._pool_size = connection_pool_size
        self._lock = asyncio.Lock()
    
    async def connect(self) -> asyncssh.SSHClientConnection:
        """Get or create SSH connection from pool"""
        async with self._lock:
            if self._connection_pool:
                return self._connection_pool.pop()
            
            return await asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                client_keys=[str(self.key_file)] if self.key_file else None,
                known_hosts=None  # Or: Path.home() / ".ssh" / "known_hosts"
            )
    
    async def release(self, conn: asyncssh.SSHClientConnection):
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
        """Execute command in sandbox on remote system"""
        # Build bwrap command locally using profile
        builder = BubblewrapCommandBuilder(profile)
        bwrap_cmd = builder.build(command)
        
        # Execute via SSH
        conn = await self.connect()
        try:
            result = await conn.run(
                shlex.join(bwrap_cmd),
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )
            
            return ProcessResult(
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_status or 0,
                duration=0  # asyncssh doesn't track timing
            )
        except asyncssh.TimeoutError as e:
            raise TimeoutError(f"Command timed out after {timeout}s") from e
        except asyncssh.Error as e:
            raise RuntimeError(f"SSH error: {e}") from e
        finally:
            await self.release(conn)
    
    async def read_file(
        self,
        profile: SandboxProfile,
        path: str
    ) -> str:
        """Read file from remote system via sandbox"""
        result = await self.run_command(profile, ["cat", path])
        if result.exit_code != 0:
            raise FileNotFoundError(
                f"Cannot read {path}: {result.stderr}"
            )
        return result.stdout
    
    async def list_directory(
        self,
        profile: SandboxProfile,
        path: str,
        long_format: bool = False,
        show_hidden: bool = False
    ) -> str:
        """List directory on remote system"""
        cmd = ["ls"]
        if long_format:
            cmd.append("-l")
        if show_hidden:
            cmd.append("-a")
        cmd.append(path)
        
        result = await self.run_command(profile, cmd)
        return result.stdout
    
    async def close(self):
        """Close all pooled SSH connections"""
        async with self._lock:
            for conn in self._connection_pool:
                conn.close()
            self._connection_pool.clear()

# Usage example
async def main():
    executor = SSHSandboxExecutor(
        host="prod-server.example.com",
        username="admin",
        key_file=Path.home() / ".ssh" / "id_ed25519"
    )
    
    try:
        profile = SandboxProfile.load("minimal")
        result = await executor.run_command(profile, ["ls", "/"])
        print(result.stdout)
    finally:
        await executor.close()
```

#### MCP Integration

```python
# shannot/tools.py (additions)
from typing import Literal

class SandboxDeps:
    """Dependencies for sandbox tools"""
    
    def __init__(
        self,
        profile_path: Path,
        executor: Literal["local", "ssh"] = "local",
        ssh_host: Optional[str] = None,
        ssh_username: Optional[str] = None,
        ssh_key_file: Optional[Path] = None
    ):
        self.profile = SandboxProfile.load(profile_path)
        
        if executor == "local":
            self.executor = LocalSandboxExecutor()
        elif executor == "ssh":
            if not ssh_host:
                raise ValueError("ssh_host required for SSH executor")
            self.executor = SSHSandboxExecutor(
                host=ssh_host,
                username=ssh_username,
                key_file=ssh_key_file
            )
        else:
            raise ValueError(f"Unknown executor: {executor}")
    
    async def cleanup(self):
        """Cleanup resources (close SSH connections, etc.)"""
        if hasattr(self.executor, "close"):
            await self.executor.close()

# Tools now work with any executor!
@agent.tool
async def run_command(
    ctx: RunContext[SandboxDeps],
    input: CommandInput
) -> CommandOutput:
    """Execute command in sandbox (local or remote)"""
    result = await ctx.deps.executor.run_command(
        ctx.deps.profile,
        input.command
    )
    return CommandOutput(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code
    )

# Configure for remote execution
deps = SandboxDeps(
    profile_path=Path("~/.config/shannot/minimal.json"),
    executor="ssh",
    ssh_host="prod.example.com",
    ssh_username="admin"
)

agent = Agent("claude-3-7-sonnet", deps_type=SandboxDeps, tools=[...])
result = await agent.run("Check disk space on prod server", deps=deps)
```

#### Configuration

```json
// ~/.config/shannot/remote.json
{
  "remotes": {
    "prod": {
      "type": "ssh",
      "host": "prod-server.example.com",
      "username": "admin",
      "key_file": "~/.ssh/id_ed25519",
      "profile": "minimal"
    },
    "staging": {
      "type": "ssh",
      "host": "staging-server.example.com",
      "username": "admin",
      "key_file": "~/.ssh/id_ed25519",
      "profile": "diagnostics"
    }
  }
}
```

```bash
# CLI usage
shannot remote prod run -- ls /
shannot remote prod read-file /etc/os-release
shannot remote staging check-disk
```

#### Pros

- ✅ **Zero deployment to remote** (only bubblewrap needed)
- ✅ **Leverages existing SSH infrastructure**
- ✅ **All Python deps stay local**
- ✅ **SSH authentication/encryption built-in**
- ✅ **Works with SSH tunnels, bastion hosts**
- ✅ **No firewall rules needed** (SSH already open)
- ✅ **Simple mental model** (SSH + bubblewrap)
- ✅ **Nuitka still beneficial for local binary**

#### Cons

- ⚠️ **SSH connection overhead** (~50-200ms per command)
- ⚠️ **Requires SSH access** (users need keys configured)
- ⚠️ **Network dependency** (doesn't work offline)
- ⚠️ **Error attribution complexity** (SSH vs command errors)
- ⚠️ **Connection pooling needed** for good performance

#### Verdict

**RECOMMENDED** for Shannot's use case:
- LLM diagnostics (occasional, not high-frequency)
- Interactive Claude sessions
- System administrators (already use SSH)
- SSH latency acceptable for human-in-loop

---

### Option 3: Split Architecture (Agent + Backend)

```
┌──────────────────────────────────────┐
│  Local System (Backend)              │
│  ┌────────────────────────────┐     │
│  │  shannot-backend (Python)  │     │
│  │  - All dependencies        │     │
│  │  - MCP server              │     │
│  │  - LLM agents              │     │
│  │  - HTTP/gRPC client        │     │
│  └────────────────────────────┘     │
└──────────────────────────────────────┘
         ↓ HTTP/gRPC (custom port)
┌──────────────────────────────────────┐
│  Remote System (Agent)               │
│  ┌────────────────────────────┐     │
│  │  shannot-agent (5MB binary)│     │
│  │  - Compiled with Nuitka    │     │
│  │  - Minimal HTTP server     │     │
│  │  - Sandbox execution only  │     │
│  │  - No Python runtime       │     │
│  └────────────────────────────┘     │
└──────────────────────────────────────┘
```

#### How It Works

**Remote Agent** (compiled binary):
```python
# shannot_agent/server.py (stdlib only, compiles to 5MB)
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
from shannot.sandbox import SandboxProfile, BubblewrapCommandBuilder
from shannot.process import run_process

class SandboxAPIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/execute":
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))
            
            # Load profile, build command, execute
            profile = SandboxProfile.load(Path(body['profile']))
            builder = BubblewrapCommandBuilder(profile)
            bwrap_cmd = builder.build(body['command'])
            result = run_process(bwrap_cmd)
            
            # Return result
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.exit_code
            }
            self.wfile.write(json.dumps(response).encode())

# Run server
server = HTTPServer(('0.0.0.0', 8080), SandboxAPIHandler)
server.serve_forever()
```

**Local Backend**:
```python
# shannot/remote_http.py
import httpx

class HTTPSandboxExecutor:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token
    
    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str]
    ) -> ProcessResult:
        async with httpx.AsyncClient() as client:
            headers = {}
            if self.token:
                headers['Authorization'] = f'Bearer {self.token}'
            
            response = await client.post(
                f"{self.base_url}/execute",
                json={
                    'profile': str(profile.path),
                    'command': command
                },
                headers=headers
            )
            
            data = response.json()
            return ProcessResult(
                stdout=data['stdout'],
                stderr=data['stderr'],
                exit_code=data['exit_code']
            )
```

#### Pros

- ✅ **No Python needed on remote** (compiled binary)
- ✅ **Custom protocol** (optimize for your use case)
- ✅ **Multiple backends can share agents**
- ✅ **Lower latency than SSH** (persistent connection)
- ✅ **Nuitka compilation highly beneficial** (5MB binary)

#### Cons

- ⚠️ **Two components to deploy** (agent + backend)
- ⚠️ **Need to secure HTTP endpoint** (TLS, auth, firewall)
- ⚠️ **Custom protocol maintenance**
- ⚠️ **More complex debugging**
- ⚠️ **Firewall rules needed** (new port)

#### Verdict

**ALTERNATIVE** if SSH is not available or latency is critical.

---

### Option 4: Hybrid (All Executors)

Support all execution methods via common interface:

```python
# shannot/execution.py
from abc import ABC, abstractmethod
from typing import Literal

ExecutorType = Literal["local", "ssh", "http"]

class SandboxExecutor(ABC):
    """Abstract base for all execution strategies"""
    
    @abstractmethod
    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        """Execute command in sandbox"""
        ...
    
    async def read_file(
        self,
        profile: SandboxProfile,
        path: str
    ) -> str:
        """Read file from filesystem"""
        result = await self.run_command(profile, ["cat", path])
        if result.exit_code != 0:
            raise FileNotFoundError(path)
        return result.stdout
    
    async def cleanup(self):
        """Cleanup resources (override if needed)"""
        pass

class LocalExecutor(SandboxExecutor):
    """Execute on local system"""
    
    async def run_command(
        self,
        profile: SandboxProfile,
        command: list[str],
        timeout: int = 30
    ) -> ProcessResult:
        builder = BubblewrapCommandBuilder(profile)
        return await run_process(builder.build(command), timeout=timeout)

class SSHExecutor(SandboxExecutor):
    """Execute via SSH (see Option 2)"""
    # ... implementation from Option 2 ...

class HTTPExecutor(SandboxExecutor):
    """Execute via HTTP (see Option 3)"""
    # ... implementation from Option 3 ...

# Factory function
def create_executor(
    executor_type: ExecutorType,
    **kwargs
) -> SandboxExecutor:
    """Create executor from configuration"""
    if executor_type == "local":
        return LocalExecutor()
    elif executor_type == "ssh":
        return SSHExecutor(**kwargs)
    elif executor_type == "http":
        return HTTPExecutor(**kwargs)
    else:
        raise ValueError(f"Unknown executor: {executor_type}")

# Usage - all executors have same interface!
executors = {
    "local": create_executor("local"),
    "prod": create_executor("ssh", host="prod.example.com"),
    "staging": create_executor("http", base_url="http://staging:8080")
}

for name, executor in executors.items():
    result = await executor.run_command(
        minimal_profile,
        ["ls", "/"]
    )
    print(f"{name}: {result.stdout}")
```

#### Configuration

```toml
# ~/.config/shannot/config.toml
[executor.local]
type = "local"

[executor.prod]
type = "ssh"
host = "prod.example.com"
username = "admin"
key_file = "~/.ssh/id_ed25519"

[executor.staging]
type = "http"
base_url = "http://staging-server:8080"
token = "${SHANNOT_STAGING_TOKEN}"

[executor.ci]
type = "http"
base_url = "http://ci-runner:8080"
```

```python
# Auto-load from config
from shannot.config import load_executors

executors = load_executors()  # Loads from ~/.config/shannot/config.toml

# Use by name
result = await executors["prod"].run_command(...)
```

---

## Recommendation Matrix

| Use Case | Recommended Approach | Rationale |
|----------|---------------------|-----------|
| **LLM diagnostics (Claude Desktop)** | SSH Executor | No deployment, uses existing SSH, perfect for interactive |
| **High-frequency monitoring** | HTTP Agent | Lower latency, persistent connections |
| **Development/testing** | Local Executor | Simplest, fastest, no network |
| **Airgapped environments** | Local Executor | No network dependency |
| **Multi-tenant SaaS** | HTTP Agent | Scalable, centralized control |
| **Hobbyist/personal use** | SSH Executor | Easiest setup, zero remote deployment |

## Implementation Roadmap

### Phase 1: SSH Executor (Week 1-2)

**Goal**: Enable remote execution via SSH with zero remote deployment.

Tasks:
- [ ] Implement `SSHSandboxExecutor` with connection pooling
- [ ] Add `SandboxExecutor` abstract base class
- [ ] Update `SandboxDeps` to support executors
- [ ] Add CLI commands: `shannot remote add`, `shannot remote run`
- [ ] Write integration tests (requires SSH server)
- [ ] Document SSH setup in `docs/remote-ssh.md`

### Phase 2: Configuration & Multi-Remote (Week 3)

**Goal**: Support multiple remote systems with easy configuration.

Tasks:
- [ ] Add `~/.config/shannot/remote.json` support
- [ ] Implement `load_executors()` from config
- [ ] Add `shannot remote list` command
- [ ] Add MCP resource for listing remotes
- [ ] Update MCP tools to accept remote parameter
- [ ] Document configuration in `docs/remote-ssh.md`

### Phase 3: HTTP Agent (Week 4-5) - Optional

**Goal**: Deploy lightweight agent for low-latency execution.

Tasks:
- [ ] Implement `shannot_agent/server.py` (stdlib only)
- [ ] Compile with Nuitka to single binary
- [ ] Implement `HTTPSandboxExecutor`
- [ ] Add authentication (Bearer token)
- [ ] Add TLS support
- [ ] Write systemd service file
- [ ] Document deployment in `docs/remote-http.md`

### Phase 4: Nuitka Benefits (Week 6)

**Goal**: Leverage Nuitka for local binary OR remote agent.

Two paths:

**Path A: Local Binary Only**
- Compile full shannot with all deps (60-100MB)
- Distribute via GitHub releases
- SSH executor talks to remote bubblewrap

**Path B: Remote Agent Only**
- Keep local as Python package
- Compile minimal agent (5MB)
- HTTP executor talks to remote agent

**Path C: Both**
- Offer compiled local binary for users without Python
- Offer compiled agent for users wanting lowest remote footprint

See [NUITKA.md](NUITKA.md) for compilation details.

## Security Considerations

### SSH Executor

**Threats**:
- SSH key compromise
- Command injection via SSH
- Man-in-the-middle attacks

**Mitigations**:
- Use SSH key authentication (not passwords)
- Validate SSH host keys
- Use `shlex.join()` for command construction
- All existing sandbox security applies

### HTTP Agent

**Threats**:
- Network eavesdropping
- Unauthorized access
- Command injection
- DoS attacks

**Mitigations**:
- TLS required (HTTPS)
- Bearer token authentication
- Rate limiting
- Input validation (reject shell metacharacters)
- Firewall rules (restrict source IPs)
- All existing sandbox security applies

## Testing Strategy

### SSH Executor Tests

```python
# tests/test_remote_ssh.py
import pytest
from shannot.remote_ssh import SSHSandboxExecutor

@pytest.fixture
async def ssh_executor():
    executor = SSHSandboxExecutor(
        host="localhost",  # Test against local SSH
        username="testuser",
        key_file=Path("/tmp/test_key")
    )
    yield executor
    await executor.close()

@pytest.mark.asyncio
async def test_ssh_run_command(ssh_executor, minimal_profile):
    result = await ssh_executor.run_command(
        minimal_profile,
        ["echo", "hello"]
    )
    assert result.stdout == "hello\n"
    assert result.exit_code == 0

@pytest.mark.asyncio
async def test_ssh_connection_pooling(ssh_executor, minimal_profile):
    # Run 10 commands, verify reuse
    for i in range(10):
        result = await ssh_executor.run_command(
            minimal_profile,
            ["echo", str(i)]
        )
        assert result.exit_code == 0
    
    # Should have reused connections
    assert len(ssh_executor._connection_pool) > 0
```

### HTTP Agent Tests

```python
# tests/test_remote_http.py
import pytest
from shannot_agent.server import create_app

@pytest.fixture
async def agent_server():
    app = create_app()
    # Start server on random port
    # ... setup ...
    yield server_url
    # ... teardown ...

@pytest.mark.asyncio
async def test_http_execute(agent_server):
    executor = HTTPExecutor(base_url=agent_server)
    result = await executor.run_command(
        minimal_profile,
        ["echo", "hello"]
    )
    assert result.stdout == "hello\n"
```

## FAQ

### Q: Should I use SSH or HTTP executor?

**A**: Start with **SSH** because:
- Zero deployment needed
- Uses existing infrastructure
- Good enough for interactive LLM use

Upgrade to **HTTP agent** if:
- SSH latency too high (>200ms)
- Need high-frequency monitoring
- SSH not available

### Q: Can I use both local and remote execution?

**A**: Yes! The `SandboxExecutor` abstraction supports all types. Configure multiple executors and choose at runtime.

### Q: Does Nuitka compilation still make sense?

**A**: Yes, but different benefits:

**For local binary**: Still beneficial if you want single-file distribution without Python. But now the binary is 60-100MB (with all deps).

**For remote agent**: Highly beneficial! Compile minimal agent to 5MB, deploy anywhere with just bubblewrap.

### Q: How do I handle SSH authentication?

**A**: Use SSH keys (recommended):
```bash
# Generate key if needed
ssh-keygen -t ed25519 -f ~/.ssh/shannot_key

# Copy to remote
ssh-copy-id -i ~/.ssh/shannot_key user@remote

# Configure shannot
shannot remote add prod \
  --type ssh \
  --host remote \
  --username user \
  --key-file ~/.ssh/shannot_key
```

### Q: Can I use SSH tunnels or bastion hosts?

**A**: Yes! Configure SSH config:

```
# ~/.ssh/config
Host prod
  HostName prod-internal.example.com
  User admin
  IdentityFile ~/.ssh/shannot_key
  ProxyJump bastion.example.com
```

Then use `ssh://prod` as the host.

### Q: What about Windows remote systems?

**A**: Shannot requires Linux (bubblewrap is Linux-only). You could:
- WSL2 on Windows (bubblewrap works in WSL)
- Run Linux VMs
- Use different sandboxing (e.g., Docker)

## Conclusion

**For Shannot's LLM integration use case, we recommend:**

1. **Primary**: SSH-based remote execution (Option 2)
   - Zero deployment to remote
   - Leverages existing SSH
   - Perfect for interactive LLM diagnostics

2. **Secondary**: Hybrid executor support (Option 4)
   - Allows local, SSH, and HTTP
   - Users choose based on needs
   - Future-proof architecture

3. **Optional**: Compile HTTP agent with Nuitka (Option 3)
   - For users wanting lowest remote footprint
   - 5MB binary vs. Python stack
   - Deploy when SSH not available

**Implementation priority**:
1. SSH executor (solves immediate need)
2. Configuration & multi-remote
3. HTTP agent (if needed)
4. Nuitka compilation (for agent or local binary)

This approach keeps the backend rich (full Python, all deps) while keeping remote systems minimal (just bubblewrap + SSH).

---

**Next Steps**:
1. Review this architecture
2. Decide: SSH-only, or hybrid with HTTP agent?
3. Start Phase 1 implementation (SSH executor)
4. Update LLM.md and MCP.md to reference remote execution

