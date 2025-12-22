# Guidelines for AI Agents (Claude & Others)

This document provides comprehensive guidelines for AI agents working with the Shannot codebase. It covers architecture, development workflow, coding standards, and contribution practices for v0.4.0.

## Project Overview

Shannot is a sandboxed system administration tool designed for LLM agents. It uses **PyPy sandbox architecture** to provide secure, isolated execution of Python 3.6-compatible code with syscall-level virtualization.

**Key Philosophy: Zero External Dependencies**
- Pure Python 3.11+ using stdlib only
- No pip-installable runtime dependencies
- PyPy sandbox binary is the only external requirement (auto-downloaded via `shannot setup`)

## Architecture

### PyPy Sandbox Architecture

Shannot v0.4.0 uses PyPy's sandbox mode, which provides security through **syscall interception** rather than Linux containers:

1. **System Call Interception**: PyPy sandbox intercepts all system calls from sandboxed code
2. **Virtual Filesystem (VFS)**: Filesystem operations are virtualized, providing controlled read-only access
3. **Subprocess Virtualization**: Command execution requires approval via session-based workflow
4. **Network Isolation**: Socket operations are virtualized (no actual network access)
5. **Session-Based Approval**: Operations queue in sessions for interactive review before execution

**NOT Used:**
- No bubblewrap (removed in v0.4.0)
- No Linux namespaces/cgroups
- No containers or VMs

### Module Organization

```
shannot/
├── __init__.py              # Exports: VirtualizedProc, signature, sigerror (low-level API)
├── __main__.py              # Package entry point for -m execution
├── cli.py                   # Main CLI (setup, run, approve, execute, remote, status)
├── config.py                # XDG paths, VERSION, profile/remote management
├── virtualizedproc.py       # Core PyPy sandbox process controller
├── session.py               # Session data structures and management
├── run_session.py           # Main session execution logic
├── runtime.py               # PyPy stdlib download and setup
├── approve.py               # Interactive TUI for session approval
├── deploy.py                # Deploy sessions to remote hosts
├── interact.py              # Interactive sandbox shell
├── sandboxio.py             # Low-level I/O protocol handling
├── structs.py               # Data structures (Capture, Pending, etc.)
├── queue.py                 # Session queue management
├── pending_write.py         # Deferred write operations
├── remote.py                # Remote target configuration
├── ssh.py                   # Zero-dependency SSH client (stdlib only)
├── mix_pypy.py              # PyPy sandbox initialization mixin
├── mix_vfs.py               # Virtual filesystem mixin
├── mix_subprocess.py        # Subprocess execution mixin (profiles)
├── mix_remote.py            # Remote execution mixin
├── mix_socket.py            # Socket virtualization mixin
├── mix_accept_input.py      # Input capture mixin
├── mix_dump_output.py       # Output streaming mixin
├── mix_grab_output.py       # Output capture mixin
├── vfs_procfs.py            # Virtual /proc filesystem
├── stubs/
│   ├── __init__.py
│   ├── _signal.py           # Virtualized signal module
│   └── subprocess.py        # Virtualized subprocess module
```

### Directory Structure

- **`shannot/`** - Main package (flat structure except `stubs/`)
- **`test/`** - Test suite (NOTE: `test/`, not `tests/`)
  - `test_pypy.py` - PyPy sandbox tests
  - `test_remote_config.py` - Remote configuration tests
  - `test_structs.py` - Data structure tests
  - `test_vfs.py` - Virtual filesystem tests
  - `support.py` - Shared test fixtures and utilities
- **`docs/`** - MkDocs documentation
- **`build_binary.py`** - Nuitka standalone binary builder

### Configuration & Data Paths

Shannot follows XDG Base Directory specification:

**Configuration:**
- Global profile: `~/.config/shannot/profile.json`
- Project profile: `.shannot/profile.json`
- Remote targets: `~/.config/shannot/remotes.toml`

**Data:**
- Runtime (PyPy stdlib): `~/.local/share/shannot/runtime/`
- Sessions: `~/.local/share/shannot/sessions/`
- PyPy sandbox binary: `~/.local/share/shannot/runtime/pypy-sandbox` (or from PATH)

**Profile Structure (Command Approval):**
```json
{
  "auto_approve": [
    "cat", "ls", "find", "grep", "head", "tail", "wc", "du", "df"
  ],
  "always_deny": [
    "rm -rf /",
    "dd if=/dev/zero",
    ":(){ :|:& };:"
  ]
}
```

## CLI Commands Reference

```bash
shannot setup               # Download PyPy 3.6 stdlib to ~/.local/share/shannot/runtime/
shannot run SCRIPT          # Execute Python script in PyPy sandbox
shannot approve [SESSION]   # Interactive TUI for session approval
shannot execute SESSION     # Direct session execution (used by remote protocol)
shannot remote add NAME     # Add SSH remote target
shannot remote list         # List configured remotes
shannot remote test NAME    # Test SSH connection to remote
shannot remote remove NAME  # Remove remote target
shannot status              # Check runtime, targets, pending sessions
```

**Key Options:**
- `--profile PATH` - Use custom approval profile
- `--target NAME` - Execute on remote SSH target
- `--dry-run` - Queue operations without executing
- `--color/--no-color` - Control ANSI color output

## Build, Test, and Development Commands

### Environment Setup

```bash
# Install runtime dependencies only (frozen lockfile)
make install

# Install with dev dependencies + pre-commit hooks
make install-dev

# Manual pre-commit installation
make pre-commit-install
```

All targets use `uv` for environment management. The managed virtualenv is `.venv/`.

### Testing

```bash
# Run all tests (unit + integration)
make test

# Run unit tests only (skip @pytest.mark.integration)
make test-unit

# Run integration tests only (require PyPy sandbox)
make test-integration

# Run with coverage reporting
make test-coverage
```

**Important Notes:**
- Test directory is `test/` (not `tests/`)
- Integration tests require PyPy sandbox binary (will auto-skip if unavailable)
- Use fixtures from `test/support.py` rather than reimplementing setup

**Test Markers:**
- `@pytest.mark.integration` - Requires PyPy sandbox, may be slower
- Tests are configured via `pyproject.toml` under `[tool.pytest.ini_options]`

### Code Quality

```bash
# Lint with Ruff
make lint

# Format with Ruff
make format

# Type check with Basedpyright
make type-check
```

### Documentation

```bash
# Build MkDocs documentation (output to site/)
make docs

# Serve documentation locally at http://127.0.0.1:8000
make docs-serve

# Clean generated documentation
make docs-clean
```

### Building & Distribution

```bash
# Clean build artifacts, __pycache__, *.pyc
make clean

# Build distribution packages (wheel + sdist)
make build

# Build standalone Nuitka binary (Linux recommended)
make build-binary
```

**Binary Building Notes:**
- See `BUILDING.md` for comprehensive Nuitka build guide
- Functional binaries should be built on Linux (PyPy sandbox requirement)
- macOS builds work for development but may have stdout/stderr issues

### Changelog

```bash
# Update CHANGELOG.md from git history (requires git-cliff)
make changelog
```

## Coding Style & Naming Conventions

### Language & Compatibility

- **Host code**: Python 3.11+ syntax (match statements, union types, etc.)
- **Sandboxed code**: Must be Python 3.6 compatible (PyPy sandbox limitation)
- Four-space indents, 100-character line limit (enforced by Ruff)
- Double quotes for strings (single quotes allowed for inner strings)

### Type Annotations

```python
from pathlib import Path
from typing import Any

def load_runtime_config(runtime_dir: Path | str | None = None) -> dict[str, Path]:
    """
    Load PyPy sandbox runtime configuration.

    Parameters
    ----------
    runtime_dir : Path | str | None
        Optional runtime directory path. If None, uses XDG default.

    Returns
    -------
    dict[str, Path]
        Dictionary containing paths to lib-python and lib_pypy directories.

    Raises
    ------
    RuntimeError
        If runtime directory is not properly configured.
    """
    ...
```

**Requirements:**
- Exhaustively annotate all functions (parameters, return types)
- Use modern union syntax: `Path | str` (not `Union[Path, str]`)
- Use `dict[K, V]`, `list[T]` (not `Dict`, `List` from typing)
- Unresolved types will surface as Basedpyright warnings

### Naming Conventions

- Modules: `snake_case` (e.g., `virtualizedproc.py`, `run_session.py`)
- Classes: `PascalCase` (e.g., `VirtualizedProc`, `SessionData`)
- Functions/variables: `snake_case` (e.g., `load_runtime_config`, `session_id`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `VERSION`, `DEFAULT_PROFILE`)
- CLI commands: lowercase with hyphens (e.g., `shannot remote add`)

### Module Structure

```python
"""Module docstring explaining purpose."""

from __future__ import annotations  # For forward references

# stdlib imports (grouped, sorted)
import os
import sys
from pathlib import Path
from typing import Any

# Local imports (relative)
from .config import get_runtime_dir
from .structs import SessionData

# Constants
DEFAULT_TIMEOUT = 30

# Classes
class VirtualizedProc:
    """Class for managing PyPy sandbox processes."""
    ...

# Functions
def load_session(session_id: str) -> SessionData:
    """Load session data from disk."""
    ...
```

## Testing Guidelines

### Test Organization

- Store all tests in `test/` directory (NOTE: `test/`, not `tests/`)
- Name test files `test_*.py` (e.g., `test_vfs.py`, `test_pypy.py`)
- Name test functions `test_*` (e.g., `test_vfs_read_file`, `test_session_approval`)
- Group related tests in classes: `class TestVirtualFilesystem:`

### Integration vs Unit Tests

```python
import pytest

# Unit test - no external dependencies
def test_parse_session_id():
    """Test session ID parsing logic."""
    assert parse_session_id("20250101_120000") == ...

# Integration test - requires PyPy sandbox
@pytest.mark.integration
def test_sandbox_execution():
    """Test actual PyPy sandbox process execution."""
    proc = VirtualizedProc(...)
    result = proc.run_script("print('hello')")
    assert result.stdout == "hello\n"
```

**Mark integration tests with `@pytest.mark.integration`:**
- Tests that require PyPy sandbox binary
- Tests that may be slower or require external resources
- Tests that interact with actual filesystem/processes

### Using Test Fixtures

Reuse fixtures from `test/support.py` rather than reimplementing setup:

```python
from test.support import tmp_runtime_dir, sample_profile

def test_with_runtime(tmp_runtime_dir):
    """Test using temporary runtime directory."""
    config = load_runtime_config(tmp_runtime_dir)
    assert config["lib_python"].exists()

def test_with_profile(sample_profile):
    """Test using sample approval profile."""
    assert "cat" in sample_profile["auto_approve"]
```

### Coverage

```bash
# Run with coverage reporting
pytest --cov=shannot --cov-report=term

# Or use make target
make test-coverage
```

**Coverage Goals:**
- Aim for >80% coverage on core modules
- 100% coverage not required for CLI/interactive components
- Focus on testing business logic and critical paths

## Commit & Pull Request Guidelines

### Commit Messages

Use short, imperative commit subjects mirroring existing history:

```
Add support for remote session execution via SSH
Fix approval profile loading from project directory
Update documentation for PyPy sandbox architecture
Remove deprecated bubblewrap integration
```

**Format:**
- Subject: Imperative mood, <72 chars, no period
- Body: Explain motivation, context, breaking changes (wrap at 72 chars)
- Reference issues: `Closes #123`, `Fixes #456`

**Examples from history:**
- `Merge sandboxlib: PyPy sandbox architecture`
- `Fix code quality issues across codebase`
- `Replace setup.py with pyproject.toml`
- `Add status subcommand for system health checks`

### Pull Requests

**PR Description Template:**

```markdown
## Motivation
Why is this change needed? What problem does it solve?

## Changes
- List key changes made
- Highlight risky or complex modifications
- Note any breaking changes

## Testing
Commands to validate the changes:
```bash
make test
shannot run examples/test.py
```

## Checklist
- [ ] Tests pass locally
- [ ] Code formatted with `make format`
- [ ] Type checking passes (`make type-check`)
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG.md updated (if user-facing change)
```

**Pre-merge:**
- Squash WIP commits into logical units
- Ensure CI passes (though integration tests may be skipped on macOS)
- Address review feedback

**For Documentation/UX Changes:**
- Attach CLI logs or screenshots
- Explain expected agent behavior changes
- Verify examples actually work

## Zero Dependencies Philosophy

Shannot v0.4.0 maintains **zero runtime dependencies** to maximize portability and minimize attack surface:

**What This Means:**
- Only Python 3.11+ stdlib is used (no pip packages at runtime)
- PyPy sandbox binary is the only external requirement
- SSH implemented using stdlib `subprocess` + `shlex` (no paramiko/fabric)
- No networking libraries (requests, httpx, etc.)
- No serialization libraries beyond stdlib (json, pickle)

**Development Dependencies Are OK:**
- Pytest, Ruff, Basedpyright for testing/linting
- MkDocs for documentation
- Nuitka for binary building
- Pre-commit for git hooks

**Adding New Features:**
- Always prefer stdlib solutions
- If stdlib is insufficient, reconsider the feature's necessity
- Document any deviation from zero-dependency policy

## Session-Based Approval Workflow

Understanding the session workflow is critical for working with Shannot:

### Workflow Phases

1. **Dry-run**: Sandboxed code executes, operations are captured but not performed
2. **Review**: User reviews captured operations via `shannot approve`
3. **Execute**: Approved operations run on host system

### Session Lifecycle

```python
# 1. User runs script in dry-run mode (default)
shannot run script.py

# Creates session: ~/.local/share/shannot/sessions/20250122_143022/
# - session.json: Metadata (script, profile, timestamp)
# - pending_writes.json: Captured write operations
# - subprocess_calls.json: Captured subprocess executions

# 2. User reviews session
shannot approve 20250122_143022

# Interactive TUI shows:
# - Subprocess commands to execute (with approval profile matching)
# - File writes to perform
# - User can approve/deny individual operations

# 3. Operations execute on host
# - Auto-approved commands run immediately
# - Denied operations are skipped
# - Results captured in session/output/
```

### Implementation Details

**Key Modules:**
- `run_session.py`: Orchestrates session execution
- `session.py`: Session data structures (`SessionData`, `SessionMetadata`)
- `approve.py`: Interactive TUI for review
- `queue.py`: Session queue management
- `pending_write.py`: Deferred write operations
- `mix_subprocess.py`: Command approval profile matching

**Approval Profiles:**
- `auto_approve`: List of command patterns (executed immediately)
- `always_deny`: List of dangerous patterns (always blocked)
- Commands not matching either require interactive approval

## Virtual Filesystem (VFS)

The VFS system provides controlled, read-only access to the host filesystem:

### How It Works

1. **Syscall Interception**: File operations (open, stat, listdir) are intercepted
2. **Path Mapping**: Virtual paths map to real filesystem locations
3. **Read-Only**: Write operations are captured, not performed (session workflow)
4. **Selective Access**: Only explicitly mapped paths are accessible

### Key Implementation

**Module**: `mix_vfs.py`

```python
# VFS configuration (typically set during initialization)
vfs_config = {
    "/": "/",                    # Root mapped to host root (read-only)
    "/tmp": session_tmp_dir,     # /tmp mapped to session temp directory
}

# When sandboxed code calls: open("/etc/passwd", "r")
# VFS intercepts and maps to: real_open("/etc/passwd", "r")
# Result sent back to sandbox

# When sandboxed code calls: open("/tmp/file", "w", data)
# VFS intercepts, captures write to pending_writes.json
# Returns success to sandbox without performing write
```

### Special Paths

- `/proc`: Virtual `/proc` filesystem (`vfs_procfs.py`)
- `/tmp`: Session-isolated temp directory (writable during approval)
- Other paths: Read-only access to host filesystem

## Remote Execution

Shannot can execute sessions on remote Linux hosts via SSH (zero-dependency implementation):

### Architecture

```
Local Host                          Remote Host
----------                          -----------
shannot run --target prod script.py
    ↓
Create session locally
    ↓
shannot deploy prod SESSION_ID
    ↓
SSH (stdlib subprocess) --------→  scp session files
                                   ↓
                                   shannot execute SESSION_ID
                                   ↓
                                   Run in PyPy sandbox
                                   ↓
                       ←---------- scp results back
    ↓
Display results locally
```

### Configuration

**Remote targets**: `~/.config/shannot/remotes.toml`

```toml
[targets.prod]
host = "prod.example.com"
user = "admin"
profile = "diagnostics"  # Optional: use specific profile on remote

[targets.staging]
host = "staging.example.com"
user = "deploy"
```

### Implementation

**Key Modules:**
- `remote.py`: Remote target configuration
- `deploy.py`: Deploy sessions to remote hosts
- `ssh.py`: Zero-dependency SSH using stdlib `subprocess`
- `mix_remote.py`: Remote execution mixin

**SSH Implementation:**
- Uses `subprocess.run(['ssh', host, command])`
- No paramiko, fabric, or external libraries
- Relies on local SSH client and agent for authentication

## Common Patterns & Gotchas

### Path Handling

```python
from pathlib import Path

# ✅ Good: Use Path for filesystem operations
config_dir = Path("~/.config/shannot").expanduser()
session_file = config_dir / "session.json"

# ❌ Bad: String concatenation
config_dir = os.path.expanduser("~/.config/shannot")
session_file = config_dir + "/session.json"
```

### Error Handling

```python
# ✅ Good: Specific exceptions with context
try:
    session = load_session(session_id)
except FileNotFoundError:
    raise RuntimeError(f"Session {session_id} not found in {SESSION_DIR}")

# ❌ Bad: Bare except or generic exceptions
try:
    session = load_session(session_id)
except Exception:
    raise Exception("Failed to load session")
```

### Version Detection

```python
# ✅ Good: Use importlib.metadata with fallback
from importlib.metadata import version

try:
    VERSION = version("shannot")
except Exception:
    VERSION = "0.4.0-dev"  # Fallback for development

# ❌ Bad: Hardcoded version string everywhere
VERSION = "0.4.0"  # Will get out of sync
```

### PyPy Sandbox Binary Detection

```python
# ✅ Good: Check multiple locations
def find_pypy_sandbox() -> Path | None:
    """Find PyPy sandbox binary from PATH or runtime dir."""
    # Check PATH first
    result = subprocess.run(["which", "pypy-sandbox"], capture_output=True)
    if result.returncode == 0:
        return Path(result.stdout.decode().strip())

    # Check runtime directory
    runtime_bin = get_runtime_dir() / "pypy-sandbox"
    if runtime_bin.exists():
        return runtime_bin

    return None

# ❌ Bad: Assume fixed location
PYPY_SANDBOX = Path("/usr/local/bin/pypy-sandbox")
```

## Troubleshooting Development Issues

### "PyPy sandbox binary not found"

```bash
# Download and setup PyPy sandbox
shannot setup

# Or manually specify binary location
shannot run --pypy-bin /path/to/pypy-sandbox script.py
```

### "Tests fail with integration marker"

Integration tests require PyPy sandbox and will auto-skip if unavailable:

```bash
# Run unit tests only
make test-unit

# Install PyPy sandbox for integration tests
shannot setup
make test-integration
```

### "Type checking fails"

```bash
# Ensure dev environment is set up
make install-dev

# Run type checker
make type-check

# Common issues:
# - Missing type annotations
# - Wrong import types (use Path | str, not Union[Path, str])
# - Missing __future__ import for forward references
```

### "Pre-commit hooks fail"

```bash
# Reinstall hooks
make pre-commit-install

# Run manually to see what's failing
pre-commit run --all-files

# Common issues:
# - Ruff formatting (run make format)
# - Trailing whitespace
# - Missing final newline
```

## Best Practices for AI Agents

### When Reading Code

1. **Check module docstrings** for high-level purpose
2. **Verify import structure** - stdlib vs local imports
3. **Look for type annotations** to understand data flow
4. **Check `__init__.py`** for public API exports

### When Writing Code

1. **Read existing code first** - match patterns and style
2. **Run tests after changes** - `make test` to verify
3. **Format before committing** - `make format` + `make lint`
4. **Update documentation** - If adding features, update README/docs
5. **Add tests** - Unit tests for logic, integration for PyPy sandbox interaction

### When Reviewing Changes

1. **Verify zero-dependency policy** - No new pip requirements at runtime
2. **Check backward compatibility** - Will this break existing users?
3. **Validate test coverage** - New code should have tests
4. **Review security implications** - Does this expand attack surface?
5. **Ensure documentation accuracy** - Do examples actually work?

## Version & Release Management

**Version Location:**
- **Source of truth**: `pyproject.toml` (`version = "0.4.0"`)
- **Fallback**: `shannot/config.py` (`VERSION = "0.4.0-dev"`)
- **Lock file**: `uv.lock` (auto-updated)

**Release Process:**
1. Update `pyproject.toml` version
2. Update `CHANGELOG.md` (via `make changelog`)
3. Commit: `git commit -m "Release v0.4.0"`
4. Tag: `git tag -a v0.4.0 -m "Release v0.4.0"`
5. Push: `git push && git push --tags`
6. Build binaries (on Linux): `make build-binary`
7. Create GitHub release with binaries

**Semantic Versioning:**
- v0.4.x - Current PyPy sandbox architecture (no MCP)
- v0.5.x - Planned: MCP support restoration
- v1.0.0 - Eventual: Stable API

## References

- **README.md** - User-facing documentation and quick start
- **BUILDING.md** - Nuitka binary build guide
- **CONTRIBUTING.md** - Contribution workflow
- **SECURITY.md** - Security policy and threat model
- **docs/** - Comprehensive MkDocs documentation (some pages historical reference)

## Questions or Issues?

- **Bug reports**: https://github.com/corv89/shannot/issues
- **Discussions**: https://github.com/corv89/shannot/discussions
- **Documentation**: https://github.com/corv89/shannot/tree/main/docs

---

*This document is authoritative for v0.4.0. If you find discrepancies between this document and the code, the code is the source of truth - please update this document accordingly.*
