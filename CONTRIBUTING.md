# Contributing to Shannot

Thank you for your interest in contributing to Shannot! This document provides guidelines and instructions for contributing.

## Quick Start

The easiest way to start contributing is using GitHub Codespaces:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/corv89/shannot?quickstart=1)

Click the badge above to get a fully configured development environment with bubblewrap and all dependencies pre-installed.

## Development Setup

### Prerequisites

- **Linux** - Shannot requires Linux for development and testing (bubblewrap is Linux-only)
- **Python 3.10+ with [uv](https://docs.astral.sh/uv/)** - Manages the project virtual environment
- **bubblewrap** - The underlying sandboxing tool

### Local Setup

```bash
# Clone the repository
git clone https://github.com/corv89/shannot.git
cd shannot

# Install uv if it's not already available
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install bubblewrap
# Debian/Ubuntu
sudo apt install bubblewrap

# Fedora/RHEL
sudo dnf install bubblewrap

# Arch Linux
sudo pacman -S bubblewrap

# Create a local virtual environment, install dev + optional extras, and set up git hooks
make install-dev
```

### Verify Installation

```bash
# Verify bubblewrap is available
bwrap --version

# Run the test suite (integration tests require Linux + bubblewrap)
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

We have three types of tests:

1. **Unit Tests** - Fast, no external dependencies, run on all platforms
2. **Integration Tests** - Require Linux + bubblewrap, marked with `@pytest.mark.integration`
3. **Platform-Specific Tests** - Marked with `@pytest.mark.linux_only`

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

**Note on Network Isolation:** Integration tests use `network_isolation=False` in test profiles to ensure compatibility with CI environments (GitHub Actions) that don't provide the `CAP_NET_ADMIN` capability. Network isolation features work correctly in production when run with appropriate privileges.

### Writing Tests

When adding new features:

1. Add unit tests in the appropriate `tests/test_*.py` file
2. Add integration tests in `tests/test_integration.py` if the feature requires actual sandbox execution
3. Use the fixtures from `tests/conftest.py` for common test setup
4. Mark platform-specific tests appropriately:

```python
import pytest

@pytest.mark.linux_only
@pytest.mark.requires_bwrap
@pytest.mark.integration
def test_my_feature(minimal_profile, bwrap_path):
    """Test description."""
    # Your test code
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

def process_command(args: Sequence[str], *, timeout: float | None = None) -> ProcessResult:
    """Process a command with optional timeout."""
    ...
```

### Documentation

- All public functions, classes, and methods must have docstrings
- Use Google-style docstrings or NumPy-style docstrings
- Include type information in docstrings for clarity
- Documentation supports Markdown formatting

Example:

```python
def load_profile_from_path(path: Union[Path, str]) -> SandboxProfile:
    """
    Load a SandboxProfile from a JSON configuration file.

    Parameters
    ----------
    path:
        Path to the JSON profile file. Supports tilde expansion.

    Returns
    -------
    SandboxProfile
        The loaded and validated profile.

    Raises
    ------
    SandboxError
        If the file cannot be read or contains invalid configuration.
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
├── .devcontainer/          # GitHub Codespaces configuration
├── .github/
│   └── workflows/          # GitHub Actions CI/CD
├── docs/                   # Documentation
├── profiles/               # Example sandbox profiles
├── shannot/                # Main package
│   ├── __init__.py        # Package exports
│   ├── cli.py             # Command-line interface
│   ├── process.py         # Process execution utilities
│   └── sandbox.py         # Core sandbox implementation
├── tests/                  # Test suite
│   ├── conftest.py        # Pytest fixtures and configuration
│   ├── test_cli.py        # CLI tests
│   ├── test_integration.py # Integration tests
│   └── test_sandbox.py    # Unit tests
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
