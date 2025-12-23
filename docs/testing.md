# Testing Guide

Guide to testing Shannot - running tests, writing new tests, and ensuring code quality.

## Quick Start

```bash
# Install dev dependencies
make install-dev

# Run all tests
make test

# Run unit tests only (skip integration tests)
make test-unit

# Run integration tests (requires PyPy sandbox)
make test-integration

# Run with coverage
make test-coverage
```

## Test Structure

```
test/
├── support.py               # Shared fixtures and utilities
├── test_pypy.py             # PyPy sandbox tests
├── test_remote_config.py    # Remote configuration tests
├── test_structs.py          # Data structure tests
├── test_vfs.py              # Virtual filesystem tests
└── test_mcp.py              # MCP server tests
```

**Note:** Test directory is `test/` (not `tests/`).

## Running Tests

### All Tests

```bash
# Via make
make test

# Via pytest directly
uv run pytest
```

### Unit Tests Only

```bash
# Skip integration tests (no PyPy sandbox required)
make test-unit

# Or directly
uv run pytest -m "not integration"
```

### Integration Tests

Integration tests require PyPy sandbox binary:

```bash
# Setup PyPy runtime first
shannot setup

# Run integration tests
make test-integration

# Or directly
uv run pytest -m integration
```

### Specific Tests

```bash
# Run specific file
uv run pytest test/test_vfs.py

# Run specific test
uv run pytest test/test_vfs.py::test_vfs_read_file

# Run tests matching pattern
uv run pytest -k "vfs"
```

## Test Categories

### Unit Tests

Tests that don't require PyPy sandbox:

```python
def test_session_id_parsing():
    """Test session ID generation."""
    from shannot.session import generate_session_id
    session_id = generate_session_id("test-script")
    assert "test-script" in session_id
```

### Integration Tests

Tests that require PyPy sandbox:

```python
import pytest

@pytest.mark.integration
def test_sandbox_execution(pypy_sandbox):
    """Test actual sandbox execution."""
    result = pypy_sandbox.run_script("print('hello')")
    assert "hello" in result.stdout
```

## Test Fixtures

### Available Fixtures (from test/support.py)

```python
@pytest.fixture
def tmp_runtime_dir() -> Path:
    """Temporary runtime directory."""

@pytest.fixture
def sample_profile() -> dict:
    """Sample approval profile."""

@pytest.fixture
def pypy_sandbox():
    """PyPy sandbox instance (integration tests)."""
```

### Using Fixtures

```python
def test_with_profile(sample_profile):
    """Test using sample profile."""
    assert "cat" in sample_profile["auto_approve"]

@pytest.mark.integration
def test_with_sandbox(pypy_sandbox):
    """Test with real sandbox."""
    result = pypy_sandbox.run_script("print(1+1)")
    assert "2" in result.stdout
```

## Code Quality

### Linting

```bash
make lint
# Or: uv run ruff check .
```

### Formatting

```bash
make format
# Or: uv run ruff format .
```

### Type Checking

```bash
make type-check
# Or: uv run basedpyright
```

## Coverage

```bash
# Run with coverage
make test-coverage

# Or directly
uv run pytest --cov=shannot --cov-report=term --cov-report=html

# Open HTML report
open htmlcov/index.html
```

## Writing Tests

### Test File Structure

```python
"""Tests for module_name."""

import pytest
from shannot.module_name import function_to_test


class TestFunctionName:
    """Tests for function_name."""

    def test_basic_case(self):
        """Test basic functionality."""
        result = function_to_test("input")
        assert result == "expected"

    def test_error_case(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            function_to_test("invalid")
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
def test_sandbox_feature(pypy_sandbox):
    """Test feature in real sandbox."""
    script = '''
import subprocess
subprocess.call(["ls", "/"])
'''
    result = pypy_sandbox.run_script(script)
    assert result.returncode == 0
```

## Debugging Tests

### Verbose Output

```bash
# Show full output
uv run pytest -v -s

# Show local variables on failure
uv run pytest -l

# Drop into debugger on failure
uv run pytest --pdb
```

### Common Issues

#### "PyPy sandbox not found"

Integration tests require PyPy sandbox:

```bash
# Install runtime
shannot setup

# Or skip integration tests
uv run pytest -m "not integration"
```

#### "Test directory not found"

Ensure you're using `test/` (not `tests/`):

```bash
uv run pytest test/
```

## Continuous Integration

Tests run on GitHub Actions:

- **Unit tests**: All platforms (Linux, macOS, Windows)
- **Integration tests**: Linux only (requires PyPy sandbox)

See `.github/workflows/` for CI configuration.

## Best Practices

### Do

- Use fixtures from `test/support.py`
- Mark integration tests with `@pytest.mark.integration`
- Test error cases as well as success cases
- Add descriptive docstrings to tests
- Run `make lint` before committing

### Don't

- Skip test markers without good reason
- Hardcode paths (use fixtures)
- Make tests depend on each other
- Test implementation details (test behavior)

## See Also

- [CONTRIBUTING.md](https://github.com/corv89/shannot/blob/main/CONTRIBUTING.md) - Contributor guidelines
- [Configuration](configuration.md) - Test configuration
