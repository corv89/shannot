# MCP Server Testing

This document describes how to test the Shannot MCP server for v0.5.0, which uses PyPy sandbox architecture with session-based approval.

## Overview

Shannot v0.5.0 includes comprehensive MCP testing:

1. **Protocol Tests**: JSON-RPC 2.0 message handling (`test/test_mcp_protocol.py`)
2. **Server Tests**: Tool registration, validation, resources (`test/test_mcp_server.py`)
3. **Integration Tests**: End-to-end workflows (`test/test_mcp_script_execution.py`)

**Total Coverage**: 60 tests covering protocol, server infrastructure, and execution workflows.

## Prerequisites

### Install Development Dependencies

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Or using uv
uv pip install -e ".[dev]"
```

### Install PyPy Sandbox Runtime

```bash
# Download PyPy sandbox
shannot setup runtime

# Verify runtime
shannot status
```

## Running Tests

### Quick Test (All MCP Tests)

```bash
# Run all MCP tests
uv run pytest test/test_mcp*.py -v

# Expected output: 60 passed
```

### Individual Test Files

```bash
# Protocol tests (11 tests)
uv run pytest test/test_mcp_protocol.py -v

# Server tests (28 tests)
uv run pytest test/test_mcp_server.py -v

# Integration tests (21 tests)
uv run pytest test/test_mcp_script_execution.py -v
```

### Test with Coverage

```bash
# Run with coverage report
uv run pytest test/test_mcp*.py --cov=shannot.mcp --cov-report=term

# Generate HTML coverage report
uv run pytest test/test_mcp*.py --cov=shannot.mcp --cov-report=html
# Open htmlcov/index.html
```

## Test Coverage

### Protocol Tests (`test_mcp_protocol.py`)

Tests JSON-RPC 2.0 protocol implementation:

- ✅ Read valid JSON messages
- ✅ Handle EOF gracefully
- ✅ Handle invalid JSON
- ✅ Handle keyboard interrupt
- ✅ Write messages with proper formatting
- ✅ Handle broken pipe errors
- ✅ Handle I/O errors
- ✅ Serve loop processes requests
- ✅ Handle notifications
- ✅ Handle handler exceptions

**Coverage**: Pure stdlib implementation (json, sys, io)

### Server Tests (`test_mcp_server.py`)

Tests base MCP server infrastructure:

**Base Server:**
- ✅ Server initialization with metadata
- ✅ Tool registration
- ✅ Resource registration
- ✅ Handle initialize request
- ✅ Handle ping request
- ✅ Handle tools/list
- ✅ Handle tools/call
- ✅ Handle unknown methods

**Shannot Server:**
- ✅ Default profile loading
- ✅ Profile structure validation
- ✅ Tool registration (sandbox_run, session_result)
- ✅ Resource registration (profiles, status)
- ✅ AST-based script analysis
- ✅ Command extraction from AST
- ✅ Invalid script handling
- ✅ Invalid profile handling
- ✅ Denied operation handling
- ✅ Session result polling

**Coverage**: Server infrastructure, validation, AST analysis

### Integration Tests (`test_mcp_script_execution.py`)

Tests complete execution workflows:

**Execution Paths:**
- ✅ Fast path with allowed operations
- ✅ Review path with unapproved operations
- ✅ Blocked path with denied operations

**Session Management:**
- ✅ Session creation from review path
- ✅ Session result polling (pending)
- ✅ Session expiry handling
- ✅ Session cleanup

**AST Analysis:**
- ✅ Detect multiple subprocess calls
- ✅ Handle dynamic commands (limitation)
- ✅ Syntax error handling

**Profile Validation:**
- ✅ Different profiles have different allowlists
- ✅ Custom profile loading
- ✅ Session naming

**Resource Endpoints:**
- ✅ List profiles
- ✅ Get profile configuration
- ✅ Get runtime status

**Tool Schemas:**
- ✅ Python 3.6 syntax warnings
- ✅ Dynamic profile validation
- ✅ Session result schema

**Coverage**: End-to-end workflows, session lifecycle, profile management

## Test Organization

```
test/
├── test_mcp_protocol.py          # 11 tests - JSON-RPC protocol
├── test_mcp_server.py             # 28 tests - Server infrastructure
└── test_mcp_script_execution.py   # 21 tests - Integration workflows
```

## Manual Testing

### Interactive Server Testing

Start the MCP server manually to test JSON-RPC messages:

```bash
# Start server with verbose logging
shannot-mcp --verbose

# In another terminal, send JSON-RPC messages:
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}' | shannot-mcp

# List tools
echo '{"jsonrpc": "2.0", "method": "tools/list", "id": 2}' | shannot-mcp

# Call sandbox_run
echo '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "sandbox_run", "arguments": {"script": "print(\"hello\")", "profile": "minimal"}}, "id": 3}' | shannot-mcp
```

### Test with Claude Code

Install in Claude Code and test interactively:

```bash
# Install for Claude Code
shannot setup mcp install --client claude-code

# Restart Claude Code, then:
# > /mcp
# Should show shannot with 2 tools, 3 resources
```

Ask Claude:
- "Use the sandbox_run tool to check disk space with df -h"
- "List the available approval profiles"
- "What's the status of the PyPy sandbox runtime?"

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Pushes to main
- Pull requests
- Manual workflow dispatch

See `.github/workflows/test.yml` for configuration.

### Pre-commit Hooks

Install pre-commit hooks for local testing:

```bash
# Install pre-commit
uv pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Debugging Test Failures

### Enable Verbose Output

```bash
# Verbose pytest output
uv run pytest test/test_mcp*.py -vv

# Show print statements
uv run pytest test/test_mcp*.py -s

# Stop on first failure
uv run pytest test/test_mcp*.py -x
```

### Debug Specific Test

```bash
# Run specific test
uv run pytest test/test_mcp_server.py::TestShannotMCPServer::test_sandbox_run_tool_registered -vv

# Run with pdb debugger
uv run pytest test/test_mcp_server.py::TestShannotMCPServer::test_sandbox_run_tool_registered --pdb
```

### Check Logs

```bash
# Enable logging in tests
uv run pytest test/test_mcp*.py -v --log-cli-level=DEBUG
```

## Testing with Custom Profiles

Create a custom profile for testing:

```bash
# Create test profile
mkdir -p ~/.config/shannot
cat > ~/.config/shannot/test.json <<'EOF'
{
  "auto_approve": ["echo", "printf"],
  "always_deny": ["eval"]
}
EOF

# Test with custom profile
uv run pytest test/test_mcp_script_execution.py::TestScriptExecutionWorkflow::test_custom_profile -v
```

## Performance Testing

### Measure Test Duration

```bash
# Show slowest tests
uv run pytest test/test_mcp*.py --durations=10

# Run with timing
uv run pytest test/test_mcp*.py -v --tb=short --durations=0
```

### Parallel Testing

```bash
# Install pytest-xdist
uv pip install pytest-xdist

# Run tests in parallel
uv run pytest test/test_mcp*.py -n auto
```

## Known Limitations

### PyPy Sandbox Runtime

Tests that require actual script execution need PyPy sandbox runtime:

```bash
# If runtime not available, tests will gracefully handle errors
# Install runtime for full integration testing
shannot setup
```

### Session Cleanup

Integration tests create sessions. Cleanup is automatic, but you can manually check:

```bash
# List pending sessions
shannot approve list

# Clean up test sessions
shannot approve list | grep "test-session" | cut -d' ' -f1 | xargs -I{} shannot approve cancel {}
```

## Best Practices

1. **Run tests before committing**:
   ```bash
   uv run pytest test/test_mcp*.py -v
   ```

2. **Check coverage**:
   ```bash
   uv run pytest test/test_mcp*.py --cov=shannot.mcp --cov-report=term
   ```

3. **Update tests when adding features**: New MCP tools/resources should have corresponding tests

4. **Use meaningful test names**: Follow pattern `test_<feature>_<scenario>`

5. **Mock external dependencies**: Tests should not require network access or SSH

## Troubleshooting

### "PyPy sandbox runtime not found"

Tests will show warnings but continue. For full integration testing:

```bash
shannot setup
shannot status
```

### "Session directory already exists"

Clean up stale sessions:

```bash
rm -rf ~/.local/share/shannot/sessions/test-*
```

### "Import errors"

Reinstall in development mode:

```bash
uv pip install -e ".[dev]"
```

### "Tests hang"

Check for deadlocks in subprocess execution. Use timeout:

```bash
uv run pytest test/test_mcp*.py -v --timeout=30
```

## Test Checklist

When adding new MCP features, ensure:

- [ ] Protocol tests for new JSON-RPC methods
- [ ] Server tests for tool/resource registration
- [ ] Integration tests for end-to-end workflows
- [ ] Tests pass locally
- [ ] Coverage remains >80%
- [ ] No new warnings or errors
- [ ] Documentation updated

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [Shannot MCP Documentation](mcp.md)
- [pytest Documentation](https://docs.pytest.org)
- [Python unittest Documentation](https://docs.python.org/3/library/unittest.html)
