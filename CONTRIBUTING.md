# Contributing to Shannot

Thank you for your interest in contributing to Shannot! This document provides guidelines and instructions for contributing.

## Quick Start

The easiest way to start contributing is using GitHub Codespaces:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/corv89/shannot?quickstart=1)

Click the badge above to get a fully configured development environment with all dependencies pre-installed.

## Development Setup

### Prerequisites

- **Python 3.11+ with [uv](https://docs.astral.sh/uv/)** - Manages the project virtual environment
- **PyPy sandbox** - The underlying sandboxing tool (auto-downloaded on first run via `shannot setup`)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/corv89/shannot.git
cd shannot

# Install uv if it's not already available
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a local virtual environment, install dev + optional extras, and set up git hooks
make install-dev

# Install PyPy sandbox runtime
shannot setup
```

### Verify Installation

```bash
# Verify runtime is installed
shannot status --runtime

# Run the test suite
make test

# Run only unit or integration suites as needed (hooks already installed by make install-dev)
make test-unit
make test-integration

# Run linter and formatter
make lint
make format

# Run type checker
make type-check

# Optional: run tests with coverage or reinstall hooks
make test-coverage
make pre-commit-install  # re-install hooks after changing environments
```

## Architecture

### PyPy Sandbox Architecture

Shannot uses PyPy's sandbox mode for security through **syscall interception** rather than Linux containers:

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

### Configuration & Data Paths

Shannot follows XDG Base Directory specification:

**Configuration:**
- Global config: `~/.config/shannot/config.toml`
- Project config: `.shannot/config.toml`

**Data:**
- Runtime (PyPy stdlib): `~/.local/share/shannot/runtime/`
- Sessions: `~/.local/share/shannot/sessions/`
- Audit logs: `~/.local/share/shannot/audit/`
- PyPy sandbox binary: `~/.local/share/shannot/runtime/pypy-sandbox` (or from PATH)

**Config Structure:**
```toml
[profile]
auto_approve = [
    "cat", "ls", "find", "grep", "head", "tail", "wc", "du", "df",
]
always_deny = [
    "rm -rf /",
    "dd if=/dev/zero",
    ":(){ :|:& };:",
]

[audit]
enabled = true

[remotes.prod]
host = "example.com"
user = "deploy"
```

### Zero Dependencies Philosophy

Shannot maintains **zero runtime dependencies** to maximize portability and minimize attack surface:

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

### Session-Based Approval Workflow

Understanding the session workflow is critical for working with Shannot:

**Workflow Phases:**
1. **Dry-run**: Sandboxed code executes, operations are captured but not performed
2. **Review**: User reviews captured operations via `shannot approve`
3. **Execute**: Approved operations run on host system

**Session Lifecycle:**
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

**Key Modules:**
- `run_session.py`: Orchestrates session execution
- `session.py`: Session data structures (`SessionData`, `SessionMetadata`)
- `approve.py`: Interactive TUI for review
- `queue.py`: Session queue management
- `pending_write.py`: Deferred write operations
- `mix_subprocess.py`: Command approval profile matching

### Virtual Filesystem (VFS)

The VFS system provides controlled, read-only access to the host filesystem:

**How It Works:**
1. **Syscall Interception**: File operations (open, stat, listdir) are intercepted
2. **Path Mapping**: Virtual paths map to real filesystem locations
3. **Read-Only**: Write operations are captured, not performed (session workflow)
4. **Selective Access**: Only explicitly mapped paths are accessible

**Key Implementation** (`mix_vfs.py`):
```python
# VFS configuration (typically set during initialization)
vfs_config = {
    "/": "/",                    # Root mapped to host root (read-only)
    "/tmp": session_tmp_dir,     # /tmp mapped to session temp directory
}
```

**Special Paths:**
- `/proc`: Virtual `/proc` filesystem (`vfs_procfs.py`)
- `/tmp`: Session-isolated temp directory (writable during approval)
- Other paths: Read-only access to host filesystem

### Remote Execution

Shannot can execute sessions on remote Linux hosts via SSH (zero-dependency implementation):

**Architecture:**
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

**Configuration** (`~/.config/shannot/config.toml`):
```toml
[remotes.prod]
host = "prod.example.com"
user = "admin"

[remotes.staging]
host = "staging.example.com"
user = "deploy"
```

**Key Modules:**
- `remote.py`: Remote target configuration
- `deploy.py`: Deploy sessions to remote hosts
- `ssh.py`: Zero-dependency SSH using stdlib `subprocess`
- `mix_remote.py`: Remote execution mixin

### Common Patterns & Gotchas

**Path Handling:**
```python
from pathlib import Path

# ✅ Good: Use Path for filesystem operations
config_dir = Path("~/.config/shannot").expanduser()
session_file = config_dir / "session.json"

# ❌ Bad: String concatenation
config_dir = os.path.expanduser("~/.config/shannot")
session_file = config_dir + "/session.json"
```

**Error Handling:**
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

**Version Detection:**
```python
# ✅ Good: Use importlib.metadata with fallback
from importlib.metadata import version

try:
    VERSION = version("shannot")
except Exception:
    VERSION = "0.4.0-dev"  # Fallback for development
```

**PyPy Sandbox Binary Detection:**
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
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

Follow these guidelines:

- **Code Style**: We use `ruff` for linting and formatting
- **Type Hints**: All code should have type annotations (checked with `basedpyright`)
- **Documentation**: Update docstrings and documentation as needed
- **Tests**: Add tests for new features or bug fixes

### 3. Run Quality Checks

Before committing, ensure all checks pass:

```bash
# Format code
make format

# Check linting
make lint

# Run type checker
make type-check

# Run tests
make test

# Run tests with coverage (and re-install hooks if needed)
make test-coverage
make pre-commit-install

# Build documentation
make docs
# Or serve documentation locally at http://127.0.0.1:8000
make docs-serve
```

### 4. Update the Changelog

After making your changes, update the changelog:

```bash
# Automatically regenerate CHANGELOG.md from git history
make changelog
```

This uses [git-cliff](https://git-cliff.org/) to generate the changelog from commit messages. The CHANGELOG.md file will be automatically updated to include all commits since the last release.

**Note:** The CI will check that CHANGELOG.md is up to date on pull requests.

### 5. Commit Your Changes

Write clear, descriptive commit messages that will appear in the changelog:

```bash
git add .
git commit -m "Add feature: brief description of what you did"
```

Good commit message examples:
- `Add support for seccomp filters in profiles`
- `Fix path resolution bug in SandboxBind validation`
- `Update documentation for profile configuration`
- `Add integration tests for network isolation`

**Commit Message Guidelines:**
- Start with a verb: `Add`, `Fix`, `Update`, `Improve`, `Remove`, etc.
- Be concise but descriptive
- Use present tense ("Add feature" not "Added feature")
- Reference issues when applicable (e.g., "Fix #123: ...")

Your commits are automatically categorized in the changelog:
- `Add`/`feat` → Features
- `Fix` → Bug Fixes
- `Doc`/`Improve doc` → Documentation
- `Improve`/`Update` → Improvements
- `Bump`/`Dependency` → Dependencies

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear description of what the PR does
- Reference any related issues (e.g., "Fixes #123")
- Screenshots or examples if applicable

## Testing Guidelines

### Test Categories

We have two main types of tests:

1. **Unit Tests** - Fast, test individual components and functions
2. **Integration Tests** - Test PyPy sandbox integration and end-to-end functionality

### Running Tests

```bash
# Run all tests
make test  # full suite

# Run only unit tests (skip integration tests)
make test-unit

# Run only integration tests
make test-integration

# Run with coverage report
make test-coverage
make pre-commit-install
uv run --frozen --extra dev --extra all pytest --cov=shannot --cov-report=html
# Open htmlcov/index.html to view coverage
```

### Writing Tests

When adding new features:

1. Add unit tests in the appropriate `test/test_*.py` file
2. Add integration tests for features requiring PyPy sandbox execution
3. Use the fixtures from `test/support.py` for common test setup
4. Example test structure:

```python
import pytest
from test.support import run_sandboxed

def test_my_feature():
    """Test description."""
    # Your test code
    result = run_sandboxed("test_script.py")
    assert result.succeeded()
```

## Code Style

### Python Style

- Follow PEP 8 (enforced by `ruff`)
- Maximum line length: 100 characters
- Use double quotes for strings
- Use type hints for all function signatures

### Type Hints

All code must be fully typed:

```python
from __future__ import annotations
from typing import Sequence

def execute_sandboxed(script: str, args: Sequence[str] | None = None) -> dict[str, str]:
    """Execute a script in the sandbox with optional arguments."""
    ...
```

### Documentation

- All public functions, classes, and methods must have docstrings
- Use Google-style docstrings or NumPy-style docstrings
- Include type information in docstrings for clarity
- Documentation supports Markdown formatting

Example:

```python
from pathlib import Path

def load_runtime_config(runtime_dir: Path | str | None = None) -> dict[str, Path]:
    """
    Load PyPy sandbox runtime configuration.

    Parameters
    ----------
    runtime_dir:
        Path to the runtime directory. If None, uses default location
        (~/.local/share/shannot/runtime/).

    Returns
    -------
    dict[str, Path]
        Dictionary containing paths to lib-python and lib_pypy directories.

    Raises
    ------
    RuntimeError
        If the runtime is not installed or configuration is invalid.
    """
```

### Generating Documentation

The project uses [MkDocs](https://www.mkdocs.org/) with [Material theme](https://squidfunk.github.io/mkdocs-material/) and [mkdocstrings](https://mkdocstrings.github.io/) to generate beautiful documentation that combines narrative guides with API references.

#### Quick Start

```bash
# Build documentation (output to site/)
make docs

# Start a local documentation server at http://127.0.0.1:8000
make docs-serve

# Clean generated documentation
make docs-clean
```

#### Manual Commands

If you prefer not to use the Makefile:

```bash
# Build documentation
mkdocs build

# Start development server with live reload
mkdocs serve
```

#### Documentation Structure

- **`docs/*.md`** - Narrative documentation (guides, tutorials)
- **`docs/reference/*.md`** - API reference pages (auto-generated from docstrings)
- **`mkdocs.yml`** - MkDocs configuration and navigation

#### Adding New Pages

To add a new documentation page:

1. Create a markdown file in `docs/` (e.g., `docs/new-guide.md`)
2. Add it to the `nav` section in `mkdocs.yml`
3. Run `make docs-serve` to preview

#### Documentation Best Practices

1. **Keep docstrings up-to-date** - Update docstrings when changing function signatures
2. **Include examples** - Add code examples in docstrings for complex functions
3. **Document exceptions** - List all exceptions that can be raised
4. **Use Markdown** - Leverage Markdown formatting for better readability
5. **Link to related items** - Reference related functions/classes in docstrings
6. **Test your changes** - Run `make docs-serve` to preview before committing

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass (`make test`)
- [ ] Code is formatted (`make format`)
- [ ] No linting errors (`make lint`)
- [ ] Type checking passes (`make type-check`)
- [ ] Documentation is updated (`make docs-serve` to preview)
- [ ] Changelog is updated (`make changelog`)
- [ ] New features have tests
- [ ] Commit messages are clear and descriptive

### PR Description

Include in your PR description:

1. **What** - What does this PR do?
2. **Why** - Why is this change needed?
3. **How** - How does it work? (for complex changes)
4. **Testing** - How was this tested?
5. **Screenshots** - If UI/output changes, include examples

### Review Process

1. Automated tests will run via GitHub Actions
2. A maintainer will review your code
3. Address any feedback or requested changes
4. Once approved, your PR will be merged

## Release Process

Releases are automated via GitHub Actions:

1. Update version in `pyproject.toml`
2. Create a git tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
3. Push tag: `git push origin v0.2.0`
4. Create a GitHub release for the tag
5. GitHub Actions will automatically build and publish to PyPI

## Project Structure

```
shannot/
├── .github/
│   └── workflows/          # GitHub Actions CI/CD
├── docs/                   # Documentation
├── shannot/                # Main package
│   ├── __init__.py        # Package exports: VirtualizedProc, signature, sigerror
│   ├── __main__.py        # CLI entry point
│   ├── cli.py             # Command-line interface (setup, run, approve, execute, remote, status)
│   ├── config.py          # Configuration and VERSION
│   ├── virtualizedproc.py # Core PyPy sandbox process controller
│   ├── approve.py         # Interactive TUI for session approval
│   ├── deploy.py          # Deployment functionality
│   ├── interact.py        # Sandbox process controller
│   ├── remote.py          # Remote execution via SSH
│   ├── runtime.py         # Runtime setup and installation
│   ├── session.py         # Session persistence and execution
│   ├── pending_write.py   # Pending file write tracking
│   ├── queue.py           # Command queue management
│   ├── mix_accept_input.py  # Input handling mixin
│   ├── mix_dump_output.py   # Output dumping mixin
│   ├── mix_grab_output.py   # Output grabbing mixin
│   ├── mix_pypy.py          # PyPy-specific mixin
│   ├── mix_remote.py        # Remote execution mixin
│   ├── mix_socket.py        # Socket handling mixin
│   ├── mix_subprocess.py    # Subprocess execution mixin (profiles)
│   ├── mix_vfs.py           # Virtual filesystem mixin
│   ├── sandboxio.py       # Sandbox I/O protocol
│   ├── ssh.py             # SSH connection handling
│   ├── structs.py         # Data structure definitions
│   ├── vfs_procfs.py      # Virtual /proc filesystem
│   ├── run_session.py     # Session execution runner
│   └── stubs/             # Python stubs for sandbox
│       ├── __init__.py
│       ├── _signal.py
│       └── subprocess.py
├── test/                   # Test suite (note: test/ not tests/)
│   ├── support.py         # Test support utilities
│   ├── test_pypy.py       # PyPy sandbox tests
│   ├── test_remote_config.py # Remote configuration tests
│   ├── test_structs.py    # Data structure tests
│   └── test_vfs.py        # Virtual filesystem tests
└── pyproject.toml         # Project configuration
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/corv89/shannot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/corv89/shannot/discussions)
- **Documentation**: [https://corv89.github.io/shannot/](https://corv89.github.io/shannot/)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Assume good intentions

## License

By contributing to Shannot, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to Shannot! 🎉
