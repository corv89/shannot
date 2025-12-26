# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.6] - 2025-12-26

### Features

- Add macOS binary builds for both Intel (x86_64) and Apple Silicon (arm64)
  - Binaries: `shannot-darwin-x86_64`, `shannot-darwin-arm64`
  - Built with Nuitka `--onefile` mode (same as Linux)
- Auto-download Linux binaries from GitHub releases for remote deployment
  - No longer requires local binary for `shannot setup remote test`
  - Binaries cached locally in `~/.local/share/shannot/binaries/`

## [0.8.5] - 2025-12-26

### Bug Fixes

- Fix broken binaries caused by UPX compression (SIGSEGV on startup)
  - UPX is incompatible with Nuitka's `--onefile` mode (double compression)
  - Keep LTO and module exclusions for size optimization

## [0.8.4] - 2025-12-26 [YANKED]

### Build

- Add UPX compression to reduce binary size by 50-70%
  - Simplify release workflow to use bare binaries instead of tarballs
  - Add LTO (Link Time Optimization) to Nuitka build
  - Add more stdlib exclusions (unittest, pydoc, doctest)

## [0.8.3] - 2025-12-26

### Bug Fixes

- Fix release workflow to create gzip tarballs for remote deployment
  - Binary releases now use format: `shannot-{version}-linux-{arch}.tar.gz`
  - Add `--clobber` flag to handle workflow re-runs
  - Normalize architecture naming to `arm64` consistently

## [0.8.2] - 2025-12-26

### Features

- Add `-c`/`--code` flag to run inline Python code without a script file
  - Scripts are injected directly into VFS (no temp files needed)
  - Works for both local and remote execution
- Add built-in self-test to `shannot status` and `shannot setup remote test`
  - Status command runs minimal script through sandbox when runtime is available
  - Remote test deploys runtime if missing, then verifies sandbox execution
  - Self-test exercises full sandbox path with `platform.node()` call
- Implement `uname` syscall for sandbox (closes #69)
  - Enables `os.uname()`, `platform.node()`, `platform.machine()`
  - Returns virtualized system info: sysname="Linux", nodename="sandbox"
  - Machine architecture detected dynamically from host

## [0.8.1] - 2025-12-26

### Features

- Add real-time danger highlighting to approval TUI
  - Safe commands (dim green): matches `auto_approve` patterns
  - Caution commands (yellow): state-modifying (chmod, mount, service)
  - Danger commands (red): destructive (rm, kill, dd, mkfs)
  - Unknown commands: no color
- Expand default `auto_approve` list (20 → 70+ commands)
  - Filesystem, file viewing, search, text processing
  - Process, system, user, network diagnostics
  - Service status, checksums, help commands
- Expand default `always_deny` list (5 → 25+ patterns)
  - Recursive destruction, disk destruction, fork bombs
  - Remote code execution (curl/wget | sh)
  - Permission bombs, history destruction, system shutdown

## [0.8.0] - 2025-12-26

### Features

- Add interactive arrow-key menu for `shannot setup`
- Restructure CLI: reduce top-level commands to 4 (run, approve, status, setup)
- Move `remote` and `mcp` commands under `setup` subcommand
- Hide `execute` command from help (internal use only)
- Auto-detect MCP CLI path at `~/.claude/local` for installation
- Add TTY-aware menu utilities with fallback to numbered input

### Documentation

- Update all docs to use unified `config.toml` format
- Replace `profile.json` and `remotes.toml` references

## [0.7.1] - 2025-12-25

### Bug Fixes

- Fix arrow keys not working reliably in approval TUI on some terminals (Ghostty)
  - Use `os.read()` instead of `sys.stdin.read()` to bypass Python's buffered I/O

## [0.7.0] - 2025-12-25

### Breaking Changes

- Configuration consolidated to single `config.toml` file
  - Replaces: `profile.json`, `remotes.toml`, `audit.json`
  - Project-local: `.shannot/config.toml` (for profile and audit)
  - Global: `~/.config/shannot/config.toml` (for all settings including remotes)
- Remotes remain global-only (not read from project-local config)
- `Remote` dataclass no longer has `name` field (name is the dict key)

### Features

- Unified TOML configuration with sections: `[profile]`, `[audit]`, `[remotes.*]`
- Human-editable config with comments support
- Consistent precedence: project-local overrides global

## [0.6.0] - 2025-12-25

### Features

- Add append-only JSONL audit logging for security-relevant operations
- Log session lifecycle, command decisions, file writes, approvals, and remote events
- Per-file sequence numbers for tamper detection
- fcntl file locking for concurrent write safety
- Daily log rotation with configurable retention
- Audit status shown in `shannot status` output

## [0.5.2] - 2025-12-23

### Features

- Add automatic sandbox binary download to `shannot setup`
- Download pre-built PyPy sandbox from GitHub releases with SHA256 verification
- Support Linux amd64 and arm64 platforms

### Enhancements

- `shannot setup --status` shows both stdlib and sandbox status
- Graceful failure on unsupported platforms with build-from-source instructions

## [0.5.1] - 2025-12-23

### Bug Fixes

- Fix ruff lint errors and apply formatting

### Dependencies

- Bump version to 0.5.1

### Enhancements

- Update MCP documentation for v0.5.0

### Features

- Add MCP integration to SKILL.md and update README
- Add .ruff_cache to .gitignore
- Add MCP support for remote SSH targets

## [0.5.0] - 2025-12-23

### Dependencies

- Bump version to 0.5.0

### Features

- Add session TTL and expiry management
- Add MCP protocol implementation with zero dependencies
- Add MCP server infrastructure and request routing
- Add Shannot MCP server with script-based execution
- Add MCP entry point and CLI integration
- Add comprehensive MCP test suite

## [0.4.0] - 2025-12-22

### Bug Fixes

- Fix until pypy-c-sandbox and pypy3-c-sandbox load again
- Fix ruff linter errors
- Fix additional ruff linter errors
- Fix code quality issues across codebase

### Enhancements

- Improve code quality and test coverage
- Update documentation for v0.4.0 PyPy architecture
- Update CI/CD and project metadata for v0.4.0

### Features

- Add support for select and socket modules
- Add --raw-stdout
- Add MIT license
- Add virtual /proc and /sys filesystems to VFS
- Add tiered subprocess security mixin
- Add command queue persistence and interactive approval CLI
- Add session-based approval workflow
- Add PyPy lib_pypy stubs and OverlayDir for VFS
- Add shannot CLI with runtime setup and auto-detection
- Add SSH remote support for sandboxed script execution
- Add README and SKILL documentation
- Add remote-first execution architecture
- Add CLI subcommands for SSH remote management
- Add status subcommand for system health checks
- Add Nuitka standalone binary build support

## [0.3.0] - 2025-11-07

### Bug Fixes

- Fix import order in test_config.py (ruff format)
- Fix type errors in test_config.py by adding isinstance checks
- Fix ruff line length violations in error messages

### Dependencies

- Bump github/codeql-action from 3 to 4 ([#5](https://github.com/corv89/shannot/pull/5))
- Bump actions/setup-python from 5 to 6 ([#3](https://github.com/corv89/shannot/pull/3))
- Bump actions/github-script from 7 to 8 ([#24](https://github.com/corv89/shannot/pull/24))
- Bump actions/download-artifact from 5 to 6 ([#26](https://github.com/corv89/shannot/pull/26))
- Bump actions/upload-pages-artifact from 3 to 4 ([#28](https://github.com/corv89/shannot/pull/28))
- Bump astral-sh/setup-uv from 5 to 7 ([#27](https://github.com/corv89/shannot/pull/27))
- Bump actions/checkout from 4 to 5 ([#31](https://github.com/corv89/shannot/pull/31))
- Bump sigstore/gh-action-sigstore-python from 3.0.1 to 3.1.0 ([#34](https://github.com/corv89/shannot/pull/34))
- Bump actions/upload-artifact from 4 to 5 ([#33](https://github.com/corv89/shannot/pull/33))
- Bump actions/setup-python from 5 to 6 ([#32](https://github.com/corv89/shannot/pull/32))

### Enhancements

- Improve error messages
- Update GitHub Actions to use pip instead of removed install.sh
- Update license format in pyproject.toml
- Update tests for granular namespace isolation flags
- Improve README.md for clarity and user focus
- Improve formatting in README.md
- Improve README formatting for MCP integration
- Improve DX via Makefile ([#20](https://github.com/corv89/shannot/pull/20))
- Improve Validation ([#38](https://github.com/corv89/shannot/pull/38))

### Features

- Add configuration system with TOML and remote execution
- Add UV support and improve installation experience
- Add configurable user namespace isolation and enhanced error diagnostics
- Add comprehensive troubleshooting guide and improve README
- Add --version flag to CLI and bump version to 0.1.1
- Add remote MCP support ([#14](https://github.com/corv89/shannot/pull/14))
- Add security policy and changelog ([#22](https://github.com/corv89/shannot/pull/22))
- Add Prompts ([#30](https://github.com/corv89/shannot/pull/30))

## [0.1.1] - 2025-10-20

### Bug Fixes

- Fix GitHub Release: Update sigstore action to v3 and add checkout step

### Dependencies

- Bump actions/download-artifact from 4 to 5
- Bump actions/checkout from 4 to 5

## [0.1.0] - 2025-10-20

### Bug Fixes

- Fix ruff and type checking issues
- Fix CI: Install MCP and remote extras for tests
- Fix circular import between execution.py and sandbox.py
- Fix CodeQL warnings
- Fix CI: test-installation only verifies CLI, not sandbox execution

### Dependencies

- Bump sigstore/gh-action-sigstore-python from 2.1.1 to 3.0.1

### Enhancements

- Update Python requirement to 3.10+ and add asyncssh dependency
- Update GitHub Actions to Python 3.10+

### Features

- Add CI/CD, Codespaces, enhanced testing infrastructure
- Add executor abstraction for local and remote execution
- Add comprehensive executor tests and improve test fixtures
- Add Lima VM configuration for testing
- Add manual SSH executor test script for Lima VM

<!-- generated by git-cliff -->
