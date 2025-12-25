# Guidelines for AI Agents (Claude & Others)

Quick reference for AI agents working with the Shannot codebase. For detailed architecture and contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Project Overview

Shannot is a sandboxed system administration tool for LLM agents using **PyPy sandbox architecture** with syscall-level virtualization.

**Key Facts:**
- Python 3.11+ host code, Python 3.6 sandboxed code
- Zero runtime dependencies (stdlib only)
- Test directory is `test/` (not `tests/`)

## CLI Commands

```bash
shannot setup               # Download PyPy 3.6 stdlib
shannot run SCRIPT          # Execute Python script in sandbox
shannot approve [SESSION]   # Interactive approval TUI
shannot execute SESSION     # Direct session execution
shannot remote add NAME     # Add SSH remote target
shannot remote list         # List configured remotes
shannot remote test NAME    # Test SSH connection
shannot status              # Check runtime and pending sessions
```

**Key Options:** `--profile PATH`, `--target NAME`, `--dry-run`, `--color/--no-color`

## Development Commands

```bash
# Environment
make install                # Install runtime dependencies
make install-dev            # Install with dev dependencies + hooks

# Testing
make test                   # Run all tests
make test-unit              # Skip integration tests
make test-integration       # Integration tests only (requires PyPy)
make test-coverage          # Run with coverage

# Code Quality
make lint                   # Lint with Ruff
make format                 # Format with Ruff
make type-check             # Type check with Basedpyright

# Documentation
make docs                   # Build MkDocs (output to site/)
make docs-serve             # Serve at http://127.0.0.1:8000

# Building
make clean                  # Clean build artifacts
make build                  # Build wheel + sdist
make build-binary           # Build Nuitka binary (Linux)
```

## Coding Quick Reference

```python
# Use modern Python 3.11+ syntax
from pathlib import Path

def example(path: Path | str | None = None) -> dict[str, Path]:
    """Use numpy-style docstrings with full type annotations."""
    ...
```

**Style:**
- 4-space indents, 100-char line limit
- Double quotes for strings
- Use `Path` for filesystem ops (not string concatenation)
- Use `@pytest.mark.integration` for tests requiring PyPy sandbox

## Best Practices for AI Agents

### When Reading Code
1. Check module docstrings for high-level purpose
2. Verify import structure - stdlib vs local imports
3. Look for type annotations to understand data flow
4. Check `__init__.py` for public API exports

### When Writing Code
1. Read existing code first - match patterns and style
2. Run tests after changes - `make test`
3. Format before committing - `make format` + `make lint`
4. Update documentation if adding features
5. Add tests - unit for logic, integration for PyPy sandbox

### When Reviewing Changes
1. Verify zero-dependency policy - no new pip requirements at runtime
2. Check backward compatibility
3. Validate test coverage
4. Review security implications
5. Ensure documentation accuracy

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.config/shannot/profile.json` | Global approval profile |
| `.shannot/profile.json` | Project approval profile |
| `~/.config/shannot/remotes.toml` | SSH remote targets |
| `~/.config/shannot/audit.json` | Audit logging config |
| `~/.local/share/shannot/runtime/` | PyPy stdlib |
| `~/.local/share/shannot/sessions/` | Session data |
| `~/.local/share/shannot/audit/` | Audit logs (JSONL) |

## References

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Architecture, module details, coding patterns
- **[README.md](README.md)** - User documentation and quick start
- **[BUILDING.md](BUILDING.md)** - Nuitka binary build guide
- **[docs/](docs/)** - Full MkDocs documentation

## Questions?

- Bug reports: https://github.com/corv89/shannot/issues
- Discussions: https://github.com/corv89/shannot/discussions
