# MCP Dependency Reduction Analysis

**Date**: 2025-11-13
**Branch**: `claude/reduce-mcp-dependencies-011CV51ZoZXnPhe3rpqPCMcF`
**Objective**: Reduce MCP-related dependencies while preserving local (stdin/stdout) MCP server capability

## Executive Summary

The current dependency structure includes **3 packages** as core dependencies (`mcp`, `asyncssh`, `tomli`/`tomli-w`) that were moved from optional extras to core in commit 8e6cbe0.

**Key Finding**: For local stdin/stdout MCP servers, only the `mcp` package is required. The other dependencies (`asyncssh`, `tomli`, `tomli-w`) support **remote execution features**, not core MCP functionality.

## Current Dependency Structure

### Core Dependencies (pyproject.toml)

```toml
dependencies = [
    "mcp>=1.18.0",          # MCP protocol implementation
    "asyncssh>=2.14.0",     # SSH connections for remote execution
    "tomli>=2.0.0; python_version < '3.11'",   # TOML reading (config files)
    "tomli-w>=1.0.0",       # TOML writing (config files)
]
```

### Historical Context

**Commit 8e6cbe0** (Nov 8, 2025): "Invert extra dependencies"
- **Before**: Had `[mcp]` and `[remote]` optional extras
- **After**: Moved all MCP and remote dependencies to core
- **Rationale**: Simplified installation (no need for `pip install shannot[mcp]`)

## Dependency Usage Analysis

### 1. `mcp` Package (Required for Local MCP)

**Usage Locations**:
- `shannot/mcp_server.py` (lines 14-28): Core MCP types and server
  ```python
  from mcp.server import InitializationOptions, Server
  from mcp.server.stdio import stdio_server
  from mcp.types import Tool, TextContent, Resource, Prompt, ...
  ```
- `shannot/mcp_main.py`: MCP server entrypoint

**Functionality**:
- Implements MCP protocol over stdin/stdout
- Provides tool, resource, and prompt capabilities
- **ESSENTIAL** for any MCP functionality (local or remote)

**Size/Complexity**: Lightweight protocol implementation with minimal sub-dependencies

---

### 2. `asyncssh` Package (NOT Required for Local MCP)

**Usage Location**: `shannot/executors/ssh.py` (line 31)
```python
try:
    import asyncssh
except ImportError:
    raise ImportError(
        "asyncssh required for SSH execution. Install with: pip install shannot[remote]"
    ) from None
```

**Functionality**:
- SSH connection pooling for remote command execution
- Only used when `--target` flag specifies a remote executor
- Allows running MCP server on macOS/Windows while executing commands on remote Linux

**Local MCP Impact**: **NONE** - Local MCP servers use `LocalExecutor`, not `SSHExecutor`

**Current Handling**: Already has try/except with helpful error message

---

### 3. `tomli` / `tomli-w` Packages (NOT Required for Local MCP)

**Usage Locations**:
- `shannot/config.py` (line 15): Reading `~/.config/shannot/config.toml`
- `shannot/cli.py` (lines 34, 40): CLI config file operations

**Functionality**:
- Parse TOML configuration files for remote executors
- Example config:
  ```toml
  default_executor = "production"

  [executor.production]
  type = "ssh"
  host = "prod.example.com"
  username = "admin"
  ```

**Local MCP Impact**: **NONE** - Config files only needed for remote execution setup

**Python 3.11+ Note**: `tomllib` is built-in for reading (but not writing) TOML

**Current Handling**: Already has try/except fallback in cli.py (lines 30-42)

---

## MCP Server Execution Flow

### Local stdin/stdout MCP Server
```
shannot-mcp [--profile diagnostics]
    ↓
ShannotMCPServer.__init__()
    ↓
Loads profiles (JSON files)
    ↓
Creates LocalExecutor (default)
    ↓
Runs stdio_server() from mcp.server.stdio
    ↓
Communicates via stdin/stdout
```

**Dependencies Used**: `mcp` only

### Remote MCP Server
```
shannot-mcp --target production
    ↓
Loads config from ~/.config/shannot/config.toml  ← tomli/tomllib
    ↓
Creates SSHExecutor(host="prod.example.com")     ← asyncssh
    ↓
Runs stdio_server() locally                      ← mcp
    ↓
Executes commands on remote host via SSH         ← asyncssh
```

**Dependencies Used**: `mcp`, `asyncssh`, `tomli`

---

## Recommendations

### Option 1: Restore Optional Extras (Recommended)

**Implementation**:
```toml
# pyproject.toml
dependencies = [
    "mcp>=1.18.0",
]

[project.optional-dependencies]
minimal = []  # MCP-only, no remote
remote = [
    "asyncssh>=2.14.0",
    "tomli>=2.0.0; python_version < '3.11'",
    "tomli-w>=1.0.0",
]
dev = [...]
```

**Installation**:
- Default: `pip install shannot` → MCP + local execution only
- Remote: `pip install shannot[remote]` → Full features

**Impact**:
- ✅ Reduces default installation size
- ✅ Clearer dependency purpose
- ✅ Preserves all functionality
- ✅ Already supported by existing error handling
- ⚠️ Requires updating documentation
- ⚠️ User must know to install `[remote]` extra

**Documentation Changes Required**:
- README.md: Restore `[remote]` installation instructions
- docs/installation.md: Clarify extras
- docs/configuration.md: Note config requires `[remote]`
- Error messages: Already present (ssh.py:34, config.py:389)

---

### Option 2: Lazy Imports with Runtime Checks (Alternative)

**Implementation**: Keep dependencies optional in pyproject.toml, but defer imports

```python
# shannot/executors/__init__.py
def get_ssh_executor(*args, **kwargs):
    """Factory that lazy-imports SSHExecutor"""
    try:
        from .ssh import SSHExecutor
        return SSHExecutor(*args, **kwargs)
    except ImportError as e:
        raise ImportError(
            "SSH executor requires: pip install shannot[remote]"
        ) from e
```

**Impact**:
- ✅ Similar to Option 1
- ⚠️ More complex code structure
- ⚠️ Less explicit in dependency declaration

---

### Option 3: Keep Current Structure (Not Recommended)

**Rationale Against**:
- Users who only need local MCP still install asyncssh (large, with crypto dependencies)
- Violates principle of minimal dependencies
- Commit 8e6cbe0 was for convenience, but standard practice is optional extras

---

## Size Impact Analysis

### Package Sizes (Approximate)
- `mcp`: ~150KB (lightweight)
- `asyncssh`: ~2.5MB with dependencies (cryptography, pyOpenSSL, etc.)
- `tomli`: ~15KB
- `tomli-w`: ~10KB

**Total Reduction**: ~2.5MB for users who don't need remote execution

---

## Migration Path (Option 1)

### Phase 1: Code Changes
1. Update `pyproject.toml`:
   - Move `asyncssh`, `tomli`, `tomli-w` to `[remote]` extra
   - Keep `mcp` in core dependencies
2. Verify existing error handling still works:
   - `shannot/executors/ssh.py:34` ✓ (already has try/except)
   - `shannot/config.py:389` ✓ (already has helpful message)
   - `shannot/cli.py:30-42` ✓ (already has tomli fallback)

### Phase 2: Documentation Updates
1. Update installation docs:
   - Default: `pip install shannot` (MCP + local only)
   - Remote: `pip install shannot[remote]` (full features)
2. Update MCP installation guide
3. Update remote execution docs
4. Update README.md

### Phase 3: Testing
1. Test local MCP: `pip install shannot` → `shannot-mcp` should work
2. Test remote: `pip install shannot[remote]` → `shannot-mcp --target X` should work
3. Test error messages: Without `[remote]`, should get clear install instructions

### Phase 4: Communication
1. Add to CHANGELOG.md
2. Note in release notes that `[remote]` extra now needed for SSH

---

## Code Locations Reference

### Files Using Each Dependency

**`mcp` package**:
- `shannot/mcp_server.py` (essential)
- `shannot/mcp_main.py` (essential)

**`asyncssh` package**:
- `shannot/executors/ssh.py:31` (isolated)

**`tomli` / `tomli-w` packages**:
- `shannot/config.py:15` (config loading)
- `shannot/cli.py:34,40` (config save/load)

All remote-specific code is already isolated and has error handling!

---

## Conclusion

**Recommended Action**: Implement **Option 1** (Restore Optional Extras)

**Justification**:
1. Clear separation of concerns (MCP vs remote execution)
2. Minimal code changes (error handling already exists)
3. Reduces installation size for MCP-only users
4. Standard Python packaging practice
5. Preserves all functionality

**Next Steps**:
1. Review this analysis with maintainers
2. If approved, create PR with changes
3. Update documentation
4. Test both installation modes
5. Release as minor version (breaking change for remote users)
