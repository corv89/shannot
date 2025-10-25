# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2025-10-25

### Bug Fixes

- Fix MCP server capabilities declaration for Claude Code

- Add proper ServerCapabilities with ToolsCapability and ResourcesCapability
- Import new capability types from mcp.types
- Update test stubs to include new capability types
- Fixes 'Capabilities: none' issue in Claude Code /mcp interface
- Server now properly advertises that it provides tools and resources
- Fix profile package distribution

- Include profiles/*.json in package data (pyproject.toml)
- Add GitHub workflow verification for bundled profiles
- Ensures minimal.json, readonly.json, diagnostics.json are accessible after installation

### Changes

- Change Claude Code MCP install to use user scope instead of local

- Changed _update_claude_cli_local_server to _update_claude_cli_user_server
- Now writes to top-level mcpServers (user scope) instead of projects.{cwd}.mcpServers
- Makes MCP server available across all projects instead of just one
- Updated test to reflect user scope behavior
- Fixed line length lint error in test docstring
- Added noqa comment for E402 (import after importorskip is intentional)

### Dependencies

- Bump github/codeql-action from 3 to 4 ([#5](https://github.com/corv89/shannot/issues/5))

Bumps [github/codeql-action](https://github.com/github/codeql-action) from 3 to 4.
- [Release notes](https://github.com/github/codeql-action/releases)
- [Changelog](https://github.com/github/codeql-action/blob/main/CHANGELOG.md)
- [Commits](https://github.com/github/codeql-action/compare/v3...v4)

---
updated-dependencies:
- dependency-name: github/codeql-action
  dependency-version: '4'
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
Co-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>
Co-authored-by: Corv <corv89@users.noreply.github.com>
- Bump actions/setup-python from 5 to 6 ([#3](https://github.com/corv89/shannot/issues/3))

Bumps [actions/setup-python](https://github.com/actions/setup-python) from 5 to 6.
- [Release notes](https://github.com/actions/setup-python/releases)
- [Commits](https://github.com/actions/setup-python/compare/v5...v6)

---
updated-dependencies:
- dependency-name: actions/setup-python
  dependency-version: '6'
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
Co-authored-by: dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>
Co-authored-by: Corv <corv89@users.noreply.github.com>
- Bump version to 0.2.1

### Documentation

- Improve MCP documentation for Claude Code integration

Major improvements:
- Add platform-specific Quick Start sections (macOS/Windows vs Linux)
- Document user scope as default for Claude Code (available across all projects)
- Add 'claude mcp add' command examples for native CLI usage
- Explain all three scopes: local, user, and project
- Add team collaboration section with .mcp.json workflow
- Add Claude Code-specific troubleshooting section
- Add Quick Reference section with common commands
- Clarify that macOS/Windows require remote Linux targets
- Add verification steps using /mcp command

Fixes:
- Remove confusing section numbering after adding Quick Starts
- Add Windows/macOS platform notes early in the document
- Provide clear guidance on when to use each installation method
- Enhance API reference documentation with usage examples and context

Add comprehensive introductory sections to all API reference docs:
- Overview of each module's purpose and key components
- Common usage patterns with code examples
- Links to related documentation and tutorials
- Quick start examples for each module

Enhanced modules:
- sandbox.md: Core sandbox operations and profile management
- cli.md: Command-line interface and subcommands
- process.md: Subprocess execution utilities
- tools.md: Pydantic-AI tools for MCP integration
- execution.md: Executor abstraction and remote execution
- config.md: Configuration management and TOML format
- mcp_server.md: MCP server implementation and integration
- mcp_main.md: MCP server CLI and lifecycle

Addresses incomplete API reference documentation issue by providing
context, examples, and cross-references instead of bare stubs.

### Features

- Add remote MCP support ([#14](https://github.com/corv89/shannot/issues/14))

* MCP Remote Wiring & Tool Simplification

- Add executor-aware tool names/descriptions in mcp_server.py
  - Tool names now include executor label (e.g., sandbox_prod_minimal)
  - Descriptions include remote host information
- Pass SSH agent env vars when generating Claude config in cli.py
  - MCP install now passes SSH_AUTH_SOCK and SSH_AGENT_PID to server
- Update docs and tests to reflect single-tool-per-profile model
  - MCP server exposes one generic command tool per profile
  - Tests verify executor label integration and tool naming

* Strict SSH Host-Key Support

- Extend SSHExecutor and config models with known_hosts / strict_host_key
  - Add known_hosts and strict_host_key fields to SSHExecutorConfig
  - Implement host key validation in SSHExecutor
  - Default strict_host_key=True for security
- Persist new options in TOML I/O and guard executor creation
  - Config save/load handles known_hosts and strict_host_key
  - Path expansion for known_hosts file
- Cover host-key behavior in docs and unit tests
  - Document host key verification in configuration.md
  - Add tests for config round-trip with host key settings
  - Add SSH executor tests for host key validation

* Dependency & Packaging Updates

- Promote pydantic>=2 to a core dependency in pyproject.toml
  - Move pydantic from optional to required dependencies
  - Ensures config models always available
- Fold asyncssh into the mcp extra
  - asyncssh now part of [mcp] optional dependencies
  - Remote execution requires [mcp] or [remote] extra
- Update lockfile and formatting fixes
  - Regenerate uv.lock with new dependencies
  - Fix trailing whitespace in docs

* Fix basedpyright type errors

* Fix basedpyright errors in test files

- Add type ignore comments for dynamic module attribute assignments
- Add type annotation for _SimpleType __init__ kwargs parameter
- Suppress attr-defined errors for mcp module monkeypatching
- Add noqa comments for E402 (module imports after setup code)

Resolves remaining 12 basedpyright errors from CI.

* Fix failing tests

- Add pytest.importorskip for optional dependencies (mcp, pydantic)
- Add complete dummy MCP server stubs (InitializationOptions, ServerCapabilities, stdio_server)
- Fix mock fixtures to include executor=None attribute
- Add _tool_cache to dummy server
- Skip tests requiring real MCP server when using mocks
- Add noqa comments for E402 (imports after pytest.importorskip)

All tests now pass: 97 passed, 48 skipped

* Fix test skip conditions for tool cache tests

Replace static skipif decorators with runtime skip checks.
Tests now skip if _tool_cache is empty (dummy server) rather than
trying to detect if real MCP SDK is installed.

This fixes failures in CI where real MCP is installed but the
mocks still result in empty tool cache.
- Add py.typed marker file for PEP 561 compliance

- Creates shannot/py.typed to mark package as typed
- Enables type checkers and IDEs to recognize Shannot as a typed library
- Required by pyproject.toml package_data declaration (line 81)
- Allows downstream users to benefit from Shannot's type annotations

Per PEP 561, this empty file signals that the package supports type checking
and that inline type hints should be used by static type checkers.
- Add CHANGELOG.md and git-cliff automation

Implements changelog generation and automation:

CHANGELOG.md:
- Generated comprehensive changelog from git history
- Documents all changes since v0.1.0 through current unreleased changes
- Follows 'Keep a Changelog' format with semantic versioning
- Organized by release with sections: Features, Bug Fixes, Documentation, etc.

git-cliff configuration (cliff.toml):
- Custom parsers to categorize commits by message patterns
- Works with existing commit style (not strictly conventional commits)
- Automatically links issue references to GitHub
- Skips merge commits and internal chores

CI automation (.github/workflows/changelog.yml):
- Checks CHANGELOG.md is up to date on pull requests
- Auto-comments on PRs if changelog needs updating
- Ensures changelog stays current with development

Developer tooling (Makefile):
- Added 'make changelog' target for easy updates
- Checks for git-cliff installation
- Provides helpful error messages and instructions

Documentation (CONTRIBUTING.md):
- Added changelog update step to development workflow
- Documents commit message guidelines for better changelog entries
- Explains automatic categorization of commits
- Updated PR checklist to include changelog verification

Addresses missing CHANGELOG.md issue by providing:
1. Complete historical changelog
2. Automated generation from git history
3. CI verification to keep it current
4. Developer-friendly tooling
- Add SECURITY.md with vulnerability reporting and security policy

Implements comprehensive security policy documentation:

Vulnerability Reporting:
- Private disclosure process via email and GitHub Security Advisory
- Clear response timeline expectations (48hr ack, 7-30 day fixes)
- Coordinated disclosure process with security researchers

Supported Versions:
- Documents which versions receive security updates (0.1.x, 0.2.x)
- Clear EOL policy for unsupported versions

Security Considerations:
- Known limitations and risks clearly documented
- Kernel exploits and sandbox escape possibilities
- Information disclosure through read-only access
- Resource exhaustion (no built-in limits)
- Side-channel attacks and privilege escalation risks
- Bubblewrap dependency security

Mitigation Strategies:
- Concrete examples for each risk category
- Defense-in-depth recommendations
- Seccomp filter guidance with doc references
- systemd resource limit configurations
- SELinux/AppArmor integration suggestions

Security Best Practices:
- Profile configuration guidance (least privilege)
- Production deployment patterns
- SSH remote execution security
- Monitoring and audit recommendations
- Update management procedures

Developer Guidelines:
- Security review process for contributions
- Testing requirements for security features
- Secure coding practices

External Resources:
- Links to Bubblewrap, Linux namespaces, seccomp docs
- References to existing security documentation
- Security advisory publication process

Addresses missing SECURITY.md issue by providing:
1. Responsible disclosure process
2. Clear security boundaries and limitations
3. Practical mitigation strategies
4. Best practices for secure deployment
5. Links to detailed security documentation

### Improvements

- Improve developer tooling with UV-backed make targets
- Improve DX via Makefile ([#20](https://github.com/corv89/shannot/issues/20))

* Improve developer tooling with UV-backed make targets

## [0.2.0] - 2025-10-24

### Bug Fixes

- Fix import order in test_config.py (ruff format)
- Fix type errors in test_config.py by adding isinstance checks
- Fix: Update license format in pyproject.toml

Remove deprecated license format {text = "Apache-2.0"} in favor of
simple string "Apache-2.0" to comply with PEP 621.
- Fix: Complete overhaul of install.sh installation logic

Major fixes to install script that was failing in CI:

1. **Fixed pipx installation path bug**: If pipx was installed, the entire
   installation was silently skipped due to inverted logic in elif condition.
   Restructured to properly handle: uv → pipx → offer uv install → pip fallback.

2. **Create ~/.local/bin directory**: uv/pipx/pip don't create this directory,
   causing installations to succeed but executables to be inaccessible.
   Now create the directory before all installation methods.

3. **Add Python user scripts dir to PATH**: pip --user installs to different
   locations per platform. Use sysconfig to detect and add to PATH during
   verification.

4. **Fix pip error handling**: pip output was piped to grep, hiding both
   success and non-PEP668 errors. Now capture output, check exit code,
   and show appropriate messages.

5. **Fix CI PATH setup**: Add ~/.local/bin to GITHUB_PATH so subsequent
   workflow steps can find shannot command.

6. **Fix escape codes**: Use echo -e to properly display bold text in
   installation success message.

The installation now works correctly with uv, pipx, or pip on all platforms.
- Fix basedpyright type errors
- Fix basedpyright errors in test files

- Add type ignore comments for dynamic module attribute assignments
- Add type annotation for _SimpleType __init__ kwargs parameter
- Suppress attr-defined errors for mcp module monkeypatching
- Add noqa comments for E402 (module imports after setup code)

Resolves remaining 12 basedpyright errors from CI.
- Fix failing tests

- Add pytest.importorskip for optional dependencies (mcp, pydantic)
- Add complete dummy MCP server stubs (InitializationOptions, ServerCapabilities, stdio_server)
- Fix mock fixtures to include executor=None attribute
- Add _tool_cache to dummy server
- Skip tests requiring real MCP server when using mocks
- Add noqa comments for E402 (imports after pytest.importorskip)

All tests now pass: 97 passed, 48 skipped
- Fix test skip conditions for tool cache tests

Replace static skipif decorators with runtime skip checks.
Tests now skip if _tool_cache is empty (dummy server) rather than
trying to detect if real MCP SDK is installed.

This fixes failures in CI where real MCP is installed but the
mocks still result in empty tool cache.

### Dependencies

- Dependency & Packaging Updates

- Promote pydantic>=2 to a core dependency in pyproject.toml
  - Move pydantic from optional to required dependencies
  - Ensures config models always available
- Fold asyncssh into the mcp extra
  - asyncssh now part of [mcp] optional dependencies
  - Remote execution requires [mcp] or [remote] extra
- Update lockfile and formatting fixes
  - Regenerate uv.lock with new dependencies
  - Fix trailing whitespace in docs
- Bump version to 0.2.0

### Documentation

- Docs: Add comprehensive troubleshooting guide and improve README

New troubleshooting guide (docs/troubleshooting.md):
- User namespace permission issues (Ubuntu AppArmor, kernel settings)
- Container/VM environment limitations
- Lima VM specific issues (writable mounts, AppArmor)
- UV tool wrapper stderr truncation workaround
- Security considerations and setuid explanation
- Verification steps and getting help resources

README improvements (README.md):
- Restructure Installation section with clear steps
- Add Option A (install script) and Option B (manual) labels
- Document -y/--yes flag for non-interactive installation
- Add alternative invocation method for UV wrapper truncation issue
- Link to troubleshooting guide
- Improve overall clarity and user experience

Removes minimal-no-isolation.json profile as it defeats the purpose of
secure sandboxing. Users can create custom insecure profiles if needed.

### Features

- Add configuration system with TOML and remote execution

- Add shannot/config.py: TOML-based configuration with Pydantic models
- Add tests/test_config.py: Comprehensive configuration tests
- Add docs/configuration.md: Complete configuration and remote setup guide
- Add 'shannot remote add/list/test/remove' CLI commands
- Add smart argument parsing to allow 'shannot ls /' without 'run'
- Rename --executor to --target throughout for better UX
- Add pydantic and tomli dependencies to pyproject.toml
- Support SSH remote execution (macOS/Windows → Linux)
- ~2,100 lines of new code with 126+ tests
- Feat: Add UV support and improve installation experience

- Add UV as primary installation method with automatic fallback to pipx/pip
- Implement -y/--yes flag for non-interactive/automated installations
- Add detection for local source vs remote installation
- Download profile.json from GitHub for remote installs (no hardcoded fallback)
- Improve error messages and user feedback throughout installation
- Handle PEP 668 externally-managed-environment errors gracefully

This significantly improves the installation experience on modern Python
distributions (Ubuntu 24.04+, etc.) that restrict pip system-wide installs.
- Feat: Add configurable user namespace isolation and enhanced error diagnostics

Sandbox changes (sandbox.py):
- Add user_namespace_isolation field to SandboxProfile (defaults to true)
- Replace --unshare-all with granular namespace flags for better control
- Add comprehensive error detection for user namespace permission issues
- Provide actionable error messages with Ubuntu AppArmor solutions
- Include kernel configuration guidance in error output

This addresses Ubuntu 24.04+ AppArmor restrictions on unprivileged user
namespaces while maintaining security-first defaults. Users can now
diagnose and fix namespace issues with clear, helpful error messages.

Note: Enhanced error messages work correctly but may be truncated by the
UV tool wrapper. See troubleshooting.md for workaround.
- Add --version flag to CLI and bump version to 0.1.1

- Add --version argument to CLI parser using argparse action='version'
- Import __version__ from package in cli.py
- Version now displays as: 'shannot 0.1.1'
- Bump version from 0.1.0 to 0.1.1 in preparation for release

### Improvements

- Improve error messages
- Update GitHub Actions to use pip instead of removed install.sh

- Replace install.sh test with direct pip installation
- Add $HOME/.local/bin to PATH for user installs
- Install shannot[all] for complete feature testing
- Remove obsolete 'shannot run --help' test (run is optional now)
- Improve README.md for clarity and user focus

- Rewrite tagline to emphasize LLM safety use case
- Reorganize Features section with user benefits and emojis
- Streamline Installation section (client vs target distinction)
- Condense Use Cases, Configuration, and API sections
- Simplify Development, Documentation, and Contributing sections
- Tighten Security Considerations and Credits
- Overall reduction of ~40% while maintaining all essential info
- Improve formatting in README.md

Formatted feature list and installation instructions for clarity.
- Improve README formatting for MCP integration

Reformat MCP integration section for clarity.

### Styling

- Style: Fix ruff line length violations in error messages

Break long lines in user namespace error messages to comply with
100 character line limit (E501).

### Testing

- Test: Update tests for granular namespace isolation flags

- Replace --unshare-all checks with granular flag checks
- Update test_basic_command_building to verify all namespace flags
- Fix test_network_isolation_optional to verify conditional --unshare-net
- Add test_user_namespace_isolation_optional for new field

Tests now correctly verify the granular namespace isolation approach
introduced in commit 4ad5ed2.

## [0.1.1] - 2025-10-20

### Bug Fixes

- Fix GitHub Release: Update sigstore action to v3 and add checkout step

The github-release job was failing because:
1. sigstore/gh-action-sigstore-python@v2.1.1 is outdated
2. Missing checkout step needed for gh CLI

Changes:
- Update sigstore action from v2.1.1 to v3.0.0
- Add checkout step before downloading artifacts
- Ensures gh release upload has repository context

### Dependencies

- Bump actions/download-artifact from 4 to 5

Bumps [actions/download-artifact](https://github.com/actions/download-artifact) from 4 to 5.
- [Release notes](https://github.com/actions/download-artifact/releases)
- [Commits](https://github.com/actions/download-artifact/compare/v4...v5)

---
updated-dependencies:
- dependency-name: actions/download-artifact
  dependency-version: '5'
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>
- Bump actions/checkout from 4 to 5

Bumps [actions/checkout](https://github.com/actions/checkout) from 4 to 5.
- [Release notes](https://github.com/actions/checkout/releases)
- [Changelog](https://github.com/actions/checkout/blob/main/CHANGELOG.md)
- [Commits](https://github.com/actions/checkout/compare/v4...v5)

---
updated-dependencies:
- dependency-name: actions/checkout
  dependency-version: '5'
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>

## [0.1.0] - 2025-10-20

### Bug Fixes

- Fix ruff and type checking issues

- Fix B904: Add 'from None' to ImportError in SSH executor
- Fix F841: Remove unused variable in mcp_server.py
- Fix F401: Remove unused imports in test files
- Fix E501: Break long lines in test_tools.py
- Fix B027: Add concrete implementation to cleanup() method
- Fix B017: Use specific ValidationError instead of Exception
- Fix type errors: Handle asyncssh bytes/None return types in SSH executor
- Add type: ignore comments for intentional test validation errors
- Add type: ignore comments for MCP library integration type mismatches
- Remove documentation markdown files (LLM.md, MCP.md, REMOTE.md) from git

All ruff checks pass, basedpyright has 0 errors (424 warnings acceptable)
- Fix CI: Install MCP and remote extras for tests

Tests were failing because pydantic and mcp modules were not installed.
The test suite includes tests for MCP integration and SSH executors which
require these optional dependencies.

Changed: pip install -e ".[dev]" -> pip install -e ".[dev,mcp,remote]"
- Fix circular import between execution.py and sandbox.py

The circular import occurred because:
- execution.py imported SandboxProfile from sandbox.py
- sandbox.py imported SandboxExecutor from execution.py (in TYPE_CHECKING)

Fixed by moving the SandboxProfile import in execution.py to TYPE_CHECKING
block and adding 'from __future__ import annotations' to make all type
annotations strings at runtime.

This resolves the import cycle while maintaining full type checking support.
- Fix CodeQL warnings

1. Circular import warnings: Keep TYPE_CHECKING imports but rely on
   'from __future__ import annotations' to avoid runtime circular import.
   CodeQL may still flag this, but it's a false positive - TYPE_CHECKING
   guards ensure imports only happen during type checking, not at runtime.

2. Uninitialized variable warnings in tests: Replace try/except ImportError
   with pytest.importorskip() which CodeQL understands better. This properly
   skips tests when asyncssh is not installed without triggering warnings.

3. Statement has no effect: Replace abstract method body '...' with
   'raise NotImplementedError()' which is more explicit and preferred.

All tests pass, ruff passes, imports work correctly without circular issues.
- Fix CI: test-installation only verifies CLI, not sandbox execution

The test-installation job was failing because it tried to run actual
sandbox commands without --privileged flag, causing bwrap to fail with
'Operation not permitted' when creating network namespaces.

Changes:
- Remove 'shannot verify --allowed-command ls /' (requires sandbox execution)
- Remove 'shannot run' tests (require sandbox execution)
- Remove 'shannot export' test (requires profile loading)
- Add verification that all subcommands show help (--help)
- Add verification that shannot is in PATH (which shannot)

This job now only tests that:
1. install.sh successfully installs shannot
2. shannot command is available
3. All CLI subcommands exist and can show help
4. No actual sandbox execution (which requires privileges)

Actual sandbox functionality is already tested in the 'test' job which
runs in a privileged container.

### Dependencies

- Bump sigstore/gh-action-sigstore-python from 2.1.1 to 3.0.1

Bumps [sigstore/gh-action-sigstore-python](https://github.com/sigstore/gh-action-sigstore-python) from 2.1.1 to 3.0.1.
- [Release notes](https://github.com/sigstore/gh-action-sigstore-python/releases)
- [Changelog](https://github.com/sigstore/gh-action-sigstore-python/blob/main/CHANGELOG.md)
- [Commits](https://github.com/sigstore/gh-action-sigstore-python/compare/v2.1.1...v3.0.1)

---
updated-dependencies:
- dependency-name: sigstore/gh-action-sigstore-python
  dependency-version: 3.0.1
  dependency-type: direct:production
  update-type: version-update:semver-major
...

Signed-off-by: dependabot[bot] <support@github.com>

### Features

- Add CI/CD, Codespaces, enhanced testing infrastructure

- Add GitHub Actions workflows for testing and releases
- Add GitHub Codespaces support for instant development
- Add comprehensive integration test suite (29 total tests)
- Fix all type checking errors (basedpyright)
- Add pre-commit hooks and quality tooling
- Update documentation with badges and development guides
- Add executor abstraction for local and remote execution

Implements SandboxExecutor interface with two executors:
- LocalExecutor: Native Linux execution via bubblewrap
- SSHExecutor: Remote Linux execution via SSH with connection pooling

Key features:
- Async-first API using asyncio
- Connection pooling in SSHExecutor for performance
- Backward compatibility with legacy SandboxManager
- BubblewrapCommandBuilder validate_paths parameter for remote execution
- Exception handling in async tools converts SandboxError to failed results

This enables running sandboxed commands on remote Linux servers from
any platform (macOS, Windows, Linux), addressing the cross-platform
limitation of bubblewrap.

Files added:
- shannot/execution.py: Abstract SandboxExecutor interface
- shannot/executors/__init__.py: Package initialization
- shannot/executors/local.py: LocalExecutor implementation
- shannot/executors/ssh.py: SSHExecutor with connection pooling

Files modified:
- shannot/sandbox.py: Added validate_paths param, executor support
- shannot/tools.py: Updated for async execution, exception handling
- Add comprehensive executor tests and improve test fixtures

Test suite additions:
- tests/test_executors.py: 13 tests for executor interface and implementations
  - Interface tests for abstract methods
  - LocalExecutor tests (platform-specific)
  - SSHExecutor tests with mocked asyncssh connections
  - Connection pooling, timeout handling, cleanup tests

Test improvements:
- tests/conftest.py: Enhanced test-minimal profile
  - Added df, free, find, grep commands
  - Added /proc and /sys binds for system diagnostics
  - Enables all MCP integration tests to pass
- tests/test_tools.py: Added executor attribute to mock fixture
  - Maintains compatibility with new async tools

All tests pass on both Linux (124 passed) and macOS (73 passed).
Linux-specific tests properly skipped on macOS.
- Add Lima VM configuration for testing

Adds Fedora 42 Lima VM template for testing Linux functionality:
- lima/fedora.yaml: Minimal VZ-based VM configuration
- Pre-configured with bubblewrap for sandbox testing
- Mounts project directory for development workflow
- Enables testing LocalExecutor and native Linux features on macOS

Usage:
  limactl start lima/fedora.yaml
  limactl shell fedora

This VM was used to verify all 124 Linux tests pass.
- Add manual SSH executor test script for Lima VM

Adds lima/scripts/test_ssh_executor.py for manual testing of
SSHExecutor against a real Lima VM instance.

This script provides end-to-end validation of:
- Real SSH connections (not mocked)
- Remote bubblewrap execution
- Connection pooling behavior
- Network isolation
- Error handling with actual SSH transport

Usage (with Lima VM running):
  cd /Users/corv/Src/shannot
  uv run python lima/scripts/test_ssh_executor.py

Note: Requires SSH key in agent and Lima VM on port 60797.
This is a manual test tool, not part of automated test suite.

### Improvements

- Update Python requirement to 3.10+ and add asyncssh dependency

Python version update:
- requires-python: >=3.9 → >=3.10 (required by mcp package)
- Removed Python 3.9 from classifiers
- Updated ruff target-version: py39 → py310
- Updated basedpyright pythonVersion: 3.9 → 3.10
- Removed Python 3.9-specific lint ignore rules

New dependencies:
- Added asyncssh>=2.14.0 in remote dependency group
- Enables SSH-based remote execution

Updated uv.lock with resolved dependencies for Python 3.10+
- Update GitHub Actions to Python 3.10+

Remove Python 3.9 from CI test matrix to match updated
project requirements (Python 3.10+ required by mcp package).

Tested Python versions in CI:
- 3.10 (minimum supported)
- 3.11
- 3.12
- 3.13

CI runs on Ubuntu with bubblewrap installed, so all Linux-specific
tests will execute. LocalExecutor and integration tests will run
natively in the privileged container environment.

<!-- generated by git-cliff -->
