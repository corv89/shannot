# MCP Server Testing with mcp-probe

> **⚠️ NOTICE: MCP support has been removed in v0.4.0**
>
> This documentation describes MCP testing procedures for Shannot v0.3.0 (bubblewrap-based architecture). MCP support was temporarily removed during the transition to the PyPy sandbox architecture in v0.4.0.
>
> **MCP support will be reintroduced in a future version** with the new PyPy sandbox backend. This documentation is kept for reference and will be updated when MCP functionality is restored.
>
> For current v0.4.0 testing, see test/ directory.

---

# MCP Server Testing with mcp-probe (v0.3.0 - Historical)

This document describes how to test the Shannot MCP server using [mcp-probe](https://github.com/conikeec/mcp-probe), a comprehensive testing tool for Model Context Protocol (MCP) servers.

## Overview

Shannot includes multiple layers of MCP testing:

1. **Unit Tests**: Python unit tests for MCP server components (`tests/test_mcp_server.py`)
2. **Integration Tests**: pytest-based integration tests using mcp-probe (`tests/test_mcp_integration.py`)
3. **CI Script**: Python script for comprehensive testing in CI/CD (`scripts/test_mcp_server.py`)
4. **GitHub Actions**: Automated testing on all pushes and PRs (`.github/workflows/test-mcp.yml`)

## Prerequisites

### Install mcp-probe

mcp-probe is a Rust-based CLI tool that can be installed from GitHub releases:

```bash
# Linux x86_64
curl -L https://github.com/conikeec/mcp-probe/releases/latest/download/mcp-probe-x86_64-unknown-linux-gnu.tar.gz | tar xz
sudo mv mcp-probe /usr/local/bin/

# Linux aarch64
curl -L https://github.com/conikeec/mcp-probe/releases/latest/download/mcp-probe-aarch64-unknown-linux-gnu.tar.gz | tar xz
sudo mv mcp-probe /usr/local/bin/

# macOS (if you're on macOS, you likely already have it installed)
# Check the releases page for the appropriate binary:
# https://github.com/conikeec/mcp-probe/releases

# Verify installation
mcp-probe --version
```

### Install Shannot with MCP support

```bash
# Install with MCP dependencies
pip install -e ".[mcp,dev]"

# Verify shannot-mcp is available
which shannot-mcp
shannot-mcp --help
```

## Local Testing

### Quick Test

Run mcp-probe directly against the server:

```bash
# Basic test
mcp-probe test --stdio shannot-mcp

# With timeout and JSON output
mcp-probe test --stdio shannot-mcp --timeout 60 --output json
```

### Using the Python Test Script

The `scripts/test_mcp_server.py` script provides a comprehensive testing workflow:

```bash
# Run all tests
python scripts/test_mcp_server.py

# Run with custom options
python scripts/test_mcp_server.py \
  --report-dir ./my-reports \
  --timeout 120 \
  --fail-fast \
  --verbose

# View help
python scripts/test_mcp_server.py --help
```

The script will:
1. Run the mcp-probe test suite
2. Validate MCP protocol compliance
3. Export server capabilities (JSON and HTML)
4. Generate a test summary report

### Using pytest Integration Tests

Run the pytest integration tests:

```bash
# Run all MCP integration tests
pytest tests/test_mcp_integration.py -v

# Run specific test
pytest tests/test_mcp_integration.py::TestMCPProbeIntegration::test_server_initialization -v

# Skip if mcp-probe not installed (tests will auto-skip)
pytest tests/test_mcp_integration.py -v
```

## Test Coverage

### What's Tested

The test suite covers:

- **Server Initialization**: Verifies the server starts and responds to requests
- **Capabilities**: Checks that tools, resources, and prompts are exposed
- **Protocol Compliance**: Validates against MCP protocol specification
- **Tool Availability**: Verifies sandbox tools are registered correctly
- **Prompt Availability**: Checks all 6 diagnostic prompts are available
- **Executor Targets**: Tests with different executor configurations (local, SSH)

### Test Organization

```
tests/
├── test_mcp_server.py         # Unit tests for MCP server components
└── test_mcp_integration.py    # Integration tests using mcp-probe

scripts/
└── test_mcp_server.py         # CI/CD test script

.github/workflows/
└── test-mcp.yml               # GitHub Actions workflow
```

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/test-mcp.yml` workflow runs automatically on:
- Pushes to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Manual workflow dispatch

The workflow:
1. Tests across Python 3.10, 3.11, 3.12, and 3.13
2. Installs mcp-probe in the CI environment
3. Runs both pytest integration tests and the Python test script
4. Uploads test reports as artifacts
5. Comments test results on pull requests

### Test Artifacts

After each CI run, test reports are available as artifacts:
- `mcp-test-reports-py<version>`: Reports for each Python version
- `mcp-test-reports-with-config`: Reports with executor configuration tests

Artifacts include:
- `test-results.json`: Structured test results from mcp-probe
- `capabilities.json`: Server capabilities in JSON format
- `capabilities.html`: Server capabilities in HTML format (if supported)
- `test-summary.md`: Human-readable test summary

## Interactive Debugging

For interactive debugging with mcp-probe:

```bash
# Start interactive debug session
mcp-probe debug --stdio shannot-mcp

# Available commands in debug mode:
# - list tools      # List all available tools
# - list resources  # List all available resources
# - list prompts    # List all available prompts
# - call <tool>     # Call a specific tool
# - get <resource>  # Get a specific resource
# - prompt <name>   # Get a specific prompt
# - help            # Show available commands
# - exit            # Exit debug session
```

## Testing with Executor Targets

### Create Config File

To test with executor targets, create a config file:

```bash
mkdir -p ~/.config/shannot
cat > ~/.config/shannot/config.toml << 'EOF'
default_executor = "local"

[executor.local]
type = "local"

[executor.remote]
type = "ssh"
host = "example.com"
username = "user"
strict_host_key = false
EOF
```

### Test with Target

```bash
# Test with local executor
mcp-probe test --stdio shannot-mcp --args "--target local"

# Note: Due to mcp-probe limitations with passing flags,
# you may need to create a wrapper script or use the Python test suite
```

## Known Issues

### mcp-probe Argument Passing

mcp-probe has difficulty passing command-line flags as arguments to servers:

```bash
# This doesn't work as expected:
mcp-probe test --stdio shannot-mcp --args "--target local"

# The --target flag is passed as a positional argument instead
```

**Workaround**: Use the pytest integration tests or Python test script, which don't require passing flags through mcp-probe.

### Export Command Support

The `mcp-probe export` command may not be fully supported yet. The test script handles this gracefully by treating export failures as warnings rather than errors.

## Troubleshooting

### Server Won't Start

```bash
# Verify shannot-mcp is installed
which shannot-mcp

# Check for errors
shannot-mcp --help

# Test manually
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}' | shannot-mcp
```

### mcp-probe Timeout

Increase the timeout if tests are timing out:

```bash
# Increase to 120 seconds
python scripts/test_mcp_server.py --timeout 120
```

### Permission Denied

Ensure bubblewrap is installed and the script has execute permissions:

```bash
# Install bubblewrap (Ubuntu/Debian)
sudo apt-get install bubblewrap

# Make script executable
chmod +x scripts/test_mcp_server.py
```

## Best Practices

1. **Run Tests Locally First**: Before pushing, run the test suite locally
2. **Check Reports**: Review test reports for warnings or issues
3. **Update Tests**: When adding new MCP features, add corresponding tests
4. **Monitor CI**: Watch GitHub Actions runs for failures
5. **Use Verbose Mode**: Enable `--verbose` when debugging test failures

## References

- [mcp-probe GitHub Repository](https://github.com/conikeec/mcp-probe)
- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [Shannot MCP Server Documentation](../README.md#mcp-server)
