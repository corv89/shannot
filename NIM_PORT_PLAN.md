# Shannot Python to Nim Port Plan

## Executive Summary

This document outlines a comprehensive plan to port Shannot from Python to Nim, enabling compilation to a single static binary for easier deployment. The port will maintain full feature parity while leveraging Nim's strengths: static compilation, zero dependencies, excellent performance, and small binary size.

## Current Codebase Analysis

### Code Statistics
- **Total Python LOC**: ~3,700 lines
- **Core modules**: ~2,600 lines (excluding tests)
- **Test suite**: ~3,500 lines
- **Configuration files**: 3 JSON profiles

### Module Breakdown
```
shannot/
├── sandbox.py          (809 LOC) - Core sandbox/bubblewrap logic
├── cli.py              (1,053 LOC) - Command-line interface
├── mcp_server.py       (299 LOC) - MCP server for Claude integration
├── tools.py            (315 LOC) - MCP tool implementations
├── executors/
│   ├── ssh.py          (284 LOC) - Remote SSH executor
│   └── local.py        (151 LOC) - Local executor
├── config.py           (251 LOC) - Configuration management
├── process.py          (132 LOC) - Process execution utilities
├── execution.py        (138 LOC) - Executor abstraction
├── mcp_main.py         (160 LOC) - MCP entrypoint
└── __init__.py         (74 LOC) - Package exports
```

### Key Dependencies
**Core (required)**:
- pydantic >= 2.0.0 - Data validation/serialization
- Python stdlib: subprocess, argparse, json, pathlib, logging

**Optional**:
- mcp >= 1.0.0 - MCP protocol support
- asyncssh >= 2.14.0 - SSH remote execution
- tomli/tomllib - TOML config parsing

## Why Nim?

### Advantages
1. **Static binary compilation** - Single executable, no Python runtime needed
2. **Zero dependencies** - Fully self-contained binary
3. **Excellent C interop** - Easy integration with bubblewrap
4. **Memory safety** - Compile-time checks similar to Rust but simpler
5. **Python-like syntax** - Easier learning curve for team
6. **Small binary size** - Typical range: 100KB-500KB (vs Python + deps: 50MB+)
7. **Fast execution** - Near C-level performance
8. **Good standard library** - JSON, async, process, networking built-in

### Challenges
1. **Async/await ecosystem** - Less mature than Python's asyncio
2. **SSH library availability** - May need to use C bindings or implement subset
3. **MCP protocol** - No native Nim library (need to implement or use JSON-RPC)
4. **Testing framework** - Different from pytest (but unittest-style available)
5. **Learning curve** - Team needs to learn Nim

## Port Strategy

### Phase 1: Core Foundation (Week 1-2)
**Goal**: Port core sandbox functionality to working Nim binary

#### 1.1 Process Execution Module
**File**: `process.nim`
**Python source**: `process.py` (132 LOC)
**Estimated Nim LOC**: ~150

```nim
# Key types to implement
type
  ProcessResult* = object
    command*: seq[string]
    returncode*: int
    stdout*: string
    stderr*: string
    duration*: float

# Key functions
proc runProcess*(args: seq[string], ...): ProcessResult
proc ensureToolAvailable*(executable: string): string
```

**Nim packages needed**:
- `std/osproc` - Process execution
- `std/times` - Timing measurements
- `std/strutils` - String operations

**Considerations**:
- Nim's `osproc` module is robust and handles most use cases
- Timeout handling via `std/asyncdispatch` or threads
- UTF-8 handling with `std/unicode` if needed

#### 1.2 Sandbox Profile & Core Logic
**File**: `sandbox.nim`
**Python source**: `sandbox.py` (809 LOC)
**Estimated Nim LOC**: ~700

```nim
# Key types
type
  SandboxBind* = object
    source*: string
    target*: string
    readOnly*: bool
    createTarget*: bool

  SandboxProfile* = object
    name*: string
    allowedCommands*: seq[string]
    binds*: seq[SandboxBind]
    tmpfsPaths*: seq[string]
    environment*: Table[string, string]
    networkIsolation*: bool
    seccompProfile*: Option[string]
    additionalArgs*: seq[string]

  BubblewrapCommandBuilder* = object
    profile*: SandboxProfile
    bwrapPath*: string

  SandboxManager* = object
    profile*: SandboxProfile
    bwrapPath*: string
```

**Nim packages needed**:
- `std/json` - JSON parsing for profiles
- `std/tables` - Environment variable mappings
- `std/options` - Optional values
- `std/os` - Path operations

**Validation approach**:
- Replace Pydantic with compile-time or runtime validation
- Consider `jsony` package for cleaner JSON handling
- Manual validation functions (Nim has no decorator system)

**Example validation**:
```nim
proc validate*(self: SandboxBind) =
  if not isAbsolute(self.source):
    raise newException(SandboxError, "Bind source must be absolute")
  if not isAbsolute(self.target):
    raise newException(SandboxError, "Bind target must be absolute")
```

#### 1.3 Profile Loading
**Nim packages**:
- `std/json` - Built-in JSON parser
- Consider `jsony` for better error messages

**Implementation notes**:
- Nim's JSON module is simpler than Python's
- Need explicit type conversion from `JsonNode` to types
- Use `to()` macro or manual field extraction

```nim
proc loadProfileFromPath*(path: string): SandboxProfile =
  let jsonData = parseFile(path)
  result.name = jsonData["name"].getStr()
  result.allowedCommands = jsonData["allowed_commands"].elems.mapIt(it.getStr())
  # ... etc
```

### Phase 2: CLI & Configuration (Week 2-3)
**Goal**: Working CLI with all commands (run, verify, export, remote, mcp)

#### 2.1 Configuration Management
**File**: `config.nim`
**Python source**: `config.py` (251 LOC)
**Estimated Nim LOC**: ~200

**Nim packages needed**:
- `std/parsecfg` or `parsetoml` - TOML parsing
- `std/json` - JSON support
- `std/os` - File system operations

**Package recommendation**:
- Use `parsetoml` (Nim package) for TOML support
- Or consider switching config format to JSON/YAML for simplicity

```nim
type
  ExecutorType* = enum
    etLocal, etSSH

  ExecutorConfig* = object
    case kind*: ExecutorType
    of etLocal:
      bwrapPath*: Option[string]
    of etSSH:
      host*: string
      username*: Option[string]
      keyFile*: Option[string]
      port*: int

  ShannotConfig* = object
    defaultExecutor*: string
    executors*: Table[string, ExecutorConfig]
```

#### 2.2 CLI Implementation
**File**: `cli.nim`
**Python source**: `cli.py` (1,053 LOC)
**Estimated Nim LOC**: ~900

**Nim packages needed**:
- `std/parseopt` - Basic CLI parsing
- OR `cligen` - Advanced CLI library (HIGHLY RECOMMENDED)
- `std/logging` - Logging support
- `std/terminal` - Color output

**Recommendation**: Use `cligen` package
- Automatically generates CLI from proc signatures
- Type-safe argument parsing
- Help text generation
- Much cleaner than manual parseopt

**Example with cligen**:
```nim
proc run(command: seq[string],
         profile: string = "",
         target: string = "",
         verbose: bool = false) =
  ## Run a command in the sandbox
  configureLogging(verbose)
  let profile = loadProfile(profile)
  let result = runSandboxCommand(profile, command)
  echo result.stdout

when isMainModule:
  import cligen
  dispatchMulti([run], [verify], [export], ...)
```

### Phase 3: Executor Abstraction (Week 3-4)
**Goal**: Local and SSH remote execution working

#### 3.1 Executor Base
**File**: `execution.nim`
**Python source**: `execution.py` (138 LOC)
**Estimated Nim LOC**: ~100

```nim
type
  SandboxExecutor* = ref object of RootObj

method runCommand*(self: SandboxExecutor,
                   profile: SandboxProfile,
                   command: seq[string],
                   timeout: int = 30): Future[ProcessResult] {.base, async.} =
  raise newException(Exception, "Not implemented")

method cleanup*(self: SandboxExecutor): Future[void] {.base, async.} =
  discard
```

**Note**: Nim's method dispatch enables polymorphism similar to Python

#### 3.2 Local Executor
**File**: `executors/local.nim`
**Python source**: `executors/local.py` (151 LOC)
**Estimated Nim LOC**: ~120

```nim
type
  LocalExecutor* = ref object of SandboxExecutor
    bwrapPath*: string

method runCommand*(self: LocalExecutor,
                   profile: SandboxProfile,
                   command: seq[string],
                   timeout: int = 30): Future[ProcessResult] {.async.} =
  let builder = newBubblewrapCommandBuilder(profile, self.bwrapPath)
  let bwrapCmd = builder.build(command)
  result = await runProcessAsync(bwrapCmd, timeout = timeout)
```

#### 3.3 SSH Executor (CHALLENGING)
**File**: `executors/ssh.nim`
**Python source**: `executors/ssh.py` (284 LOC)
**Estimated Nim LOC**: ~350-400

**Options for SSH support**:

1. **Option A: Use libssh2 via C bindings** (RECOMMENDED)
   - Package: `nim-ssh2` or create wrapper
   - Pros: Native, fast, no external process
   - Cons: C binding complexity

2. **Option B: Shell out to `ssh` command**
   - Use `osproc.execCmd("ssh user@host 'command'")`
   - Pros: Simple, no dependencies
   - Cons: Less control, harder to manage connections

3. **Option C: Pure Nim SSH implementation**
   - Package: Look for existing Nim SSH packages
   - Pros: Pure Nim, good control
   - Cons: May not exist or be incomplete

**Recommendation**: Start with Option B (shell out), migrate to Option A if needed

```nim
type
  SSHExecutor* = ref object of SandboxExecutor
    host*: string
    username*: string
    port*: int
    keyFile*: string

method runCommand*(self: SSHExecutor, ...): Future[ProcessResult] {.async.} =
  let sshCmd = @[
    "ssh",
    "-p", $self.port,
    "-i", self.keyFile,
    self.username & "@" & self.host,
    # ... command
  ]
  result = await runProcessAsync(sshCmd, timeout = timeout)
```

### Phase 4: MCP Server (Week 4-5)
**Goal**: MCP protocol support for Claude Desktop integration

#### 4.1 MCP Protocol Implementation
**Files**: `mcp_server.nim`, `mcp_main.nim`, `tools.nim`
**Python source**: ~774 LOC combined
**Estimated Nim LOC**: ~600-700

**Challenge**: No Nim MCP library exists

**Approach**: Implement JSON-RPC based MCP protocol manually
- MCP is based on JSON-RPC 2.0 over stdio
- Need to implement:
  - Tool registration and discovery
  - Request/response handling
  - Stdio transport

```nim
type
  MCPTool* = object
    name*: string
    description*: string
    inputSchema*: JsonNode

  MCPServer* = object
    tools*: Table[string, MCPTool]
    sandboxDeps*: Table[string, SandboxDeps]

proc handleRequest*(server: var MCPServer, request: JsonNode): JsonNode =
  # Parse JSON-RPC request
  # Route to appropriate handler
  # Return JSON-RPC response
  discard
```

**Nim packages needed**:
- `std/json` - JSON parsing
- `std/jsonutils` - JSON utilities
- `std/streams` - Stdio handling

**Simplification opportunity**:
- Could initially skip MCP and focus on CLI-only version
- Add MCP in later phase if needed

### Phase 5: Testing & Quality (Week 5-6)
**Goal**: Comprehensive test coverage

#### 5.1 Test Framework
**Python**: pytest (~3,500 LOC of tests)
**Nim**: Use `std/unittest`

```nim
import unittest
import sandbox

suite "sandbox profile loading":
  test "loads minimal profile":
    let profile = loadProfileFromPath("profiles/minimal.json")
    check profile.name == "minimal"
    check "ls" in profile.allowedCommands

  test "validates bind mounts":
    let bind = SandboxBind(
      source: "relative/path",  # Invalid!
      target: "/target"
    )
    expect SandboxError:
      bind.validate()
```

#### 5.2 Integration Tests
- Requires Linux + bubblewrap for full testing
- Use Docker for CI/CD testing
- Mark Linux-only tests similar to pytest markers

```nim
when defined(linux):
  test "runs command in sandbox":
    # Full integration test
    discard
```

### Phase 6: Documentation & Deployment (Week 6)

#### 6.1 Build Configuration
**File**: `shannot.nimble`

```nimble
# Package
version       = "0.3.0"
author        = "corv89"
description   = "Bubblewrap-based sandboxing (Nim port)"
license       = "Apache-2.0"

# Dependencies
requires "nim >= 2.0.0"
requires "cligen >= 1.5.0"     # CLI framework
requires "parsetoml >= 0.7.0"  # TOML parsing

# Optional
requires "ssh2 >= 0.1.0"       # SSH support (if available)

# Tasks
task release, "Build optimized release binary":
  exec "nim c -d:release --opt:size --threads:on -o:bin/shannot src/shannot.nim"

task static, "Build static binary":
  exec "nim c -d:release --opt:size --passL:-static -o:bin/shannot src/shannot.nim"
```

#### 6.2 Static Binary Build
```bash
# Full static binary (no libc dependency)
nim c -d:release --opt:size \
      --passL:-static \
      --threads:on \
      -o:shannot \
      src/shannot.nim

# Result: ~200-500KB binary with ZERO dependencies
```

#### 6.3 Cross-compilation
Nim excels at cross-compilation:

```bash
# From Linux, build for different targets
nim c -d:release --os:linux --cpu:amd64 src/shannot.nim
nim c -d:release --os:linux --cpu:arm64 src/shannot.nim

# Can even cross-compile from macOS to Linux (with setup)
```

## Directory Structure (Nim Port)

```
shannot-nim/
├── shannot.nimble              # Nimble package file
├── README.md                   # Updated documentation
├── CHANGELOG.md                # Version history
├── LICENSE                     # Apache 2.0
├── Makefile                    # Build shortcuts
├── profiles/                   # JSON profiles (unchanged)
│   ├── minimal.json
│   ├── readonly.json
│   └── diagnostics.json
├── src/
│   ├── shannot.nim             # Main entry point
│   ├── sandbox.nim             # Core sandbox logic
│   ├── process.nim             # Process execution
│   ├── config.nim              # Configuration management
│   ├── cli.nim                 # CLI commands (or split with cligen)
│   ├── execution.nim           # Executor base
│   ├── executors/
│   │   ├── local.nim           # Local executor
│   │   └── ssh.nim             # SSH executor
│   ├── mcp/
│   │   ├── server.nim          # MCP server
│   │   ├── protocol.nim        # JSON-RPC protocol
│   │   └── tools.nim           # MCP tool handlers
│   └── private/
│       └── utils.nim           # Internal utilities
├── tests/
│   ├── test_sandbox.nim
│   ├── test_process.nim
│   ├── test_config.nim
│   ├── test_local_executor.nim
│   └── test_integration.nim
└── bin/
    └── shannot                 # Compiled binary
```

## Implementation Priorities

### Must Have (MVP)
1. ✅ Core sandbox profile loading
2. ✅ Bubblewrap command building
3. ✅ Local command execution
4. ✅ Basic CLI (run, verify, export)
5. ✅ JSON profile support
6. ✅ Process execution & timeout handling

### Should Have (v1.0)
7. ✅ Full CLI with all subcommands
8. ✅ Configuration file support (TOML or JSON)
9. ✅ SSH remote executor (even if basic)
10. ✅ Comprehensive test suite
11. ✅ Error handling & logging

### Nice to Have (v1.1+)
12. 🔄 MCP server support
13. 🔄 Connection pooling for SSH
14. 🔄 Seccomp profile support
15. 🔄 Advanced SSH features (SFTP, etc.)

## Migration Strategy

### Approach A: Big Bang (NOT RECOMMENDED)
- Port everything at once
- Switch repo to Nim
- High risk, long feedback loop

### Approach B: Gradual Migration (RECOMMENDED)
1. **Phase 1**: Create `shannot-nim` as separate repo/branch
2. **Phase 2**: Implement core MVP in Nim
3. **Phase 3**: Run both versions in parallel, compare outputs
4. **Phase 4**: Add integration tests comparing Python vs Nim
5. **Phase 5**: Once feature parity reached, switch default to Nim
6. **Phase 6**: Keep Python version for 1-2 releases, then archive

### Version Strategy
- Current Python version: `0.2.1`
- Nim port initial release: `0.3.0-nim.beta1`
- Feature parity: `0.3.0`
- Stable Nim release: `1.0.0`

## Testing Strategy

### Compatibility Testing
Create test suite that runs identical commands in both Python and Nim versions:

```python
# tests/test_compatibility.py
def test_minimal_profile():
    py_result = subprocess.run(["shannot", "ls", "/"], capture_output=True)
    nim_result = subprocess.run(["shannot-nim", "ls", "/"], capture_output=True)
    assert py_result.stdout == nim_result.stdout
    assert py_result.returncode == nim_result.returncode
```

### Performance Testing
Benchmark to validate performance improvements:
- Binary size (Python: ~50MB, Target Nim: <1MB)
- Startup time (Python: ~100ms, Target Nim: <10ms)
- Memory usage (Python: ~30MB, Target Nim: <5MB)

## Risk Analysis

### High Risk
1. **SSH Implementation** - No mature Nim SSH library
   - Mitigation: Start with shelling out to `ssh` command
   - Future: Wrap libssh2 via C bindings

2. **MCP Protocol** - No Nim MCP library
   - Mitigation: Implement minimal JSON-RPC subset
   - Alternative: Consider skipping MCP initially

3. **Team Learning Curve** - Team needs to learn Nim
   - Mitigation: Start small, pair programming
   - Resource: Nim documentation is excellent

### Medium Risk
1. **Async/Await Differences** - Nim's async is different from Python
   - Mitigation: Keep async usage minimal initially
   - Note: Nim's async macro is powerful but different

2. **Testing Framework** - Different from pytest
   - Mitigation: unittest module is adequate
   - Consider: nimble package `testutils` for better output

3. **Dependency Management** - Nimble ecosystem smaller than PyPI
   - Mitigation: Nim stdlib is comprehensive
   - Most features possible with stdlib alone

### Low Risk
1. **JSON Parsing** - Well supported in Nim stdlib
2. **Process Execution** - `osproc` is mature and robust
3. **CLI Parsing** - `cligen` is production-ready
4. **Cross-platform** - Nim handles this well

## Performance Expectations

### Binary Size
- Python + dependencies: ~50-100MB
- Nim static binary: ~200-800KB
- **Improvement: 50-100x smaller**

### Startup Time
- Python: ~50-150ms (interpreter + imports)
- Nim: ~1-5ms (native binary)
- **Improvement: 10-50x faster**

### Memory Usage
- Python: ~20-40MB baseline
- Nim: ~1-5MB baseline
- **Improvement: 4-20x less memory**

### Execution Speed
- For this use case (mostly subprocess execution), similar
- Nim overhead: negligible
- Bottleneck: bubblewrap itself

## Recommended Packages

### Essential
- `cligen` - CLI argument parsing (better than manual)
- `parsetoml` - TOML configuration files

### Optional
- `nimSsh2` - SSH support via libssh2 (if available/mature)
- `jsony` - Better JSON parsing with good errors
- `chronicles` - Advanced logging (alternative to std/logging)

### For Development
- `testament` - Advanced testing framework
- `fusion` - Additional stdlib utilities
- `nimpretty` - Code formatting

## Documentation Plan

### Update Existing Docs
1. README.md - Add "Building from Source (Nim)" section
2. INSTALLATION.md - Add binary download instructions
3. CONTRIBUTING.md - Add Nim development setup

### New Documentation
1. `docs/nim-port.md` - This document
2. `docs/building.md` - Building Nim version
3. `docs/contributing-nim.md` - Nim contribution guide

## Timeline Estimate

### Conservative Estimate (Solo Developer)
- **Week 1-2**: Core (sandbox, process) - 40-60 hours
- **Week 2-3**: CLI & config - 30-40 hours
- **Week 3-4**: Executors - 40-50 hours
- **Week 4-5**: MCP (optional) - 40-50 hours
- **Week 5-6**: Testing & polish - 30-40 hours
- **Total**: 180-240 hours (~6 weeks full-time or 12 weeks part-time)

### Aggressive Estimate (Experienced Nim Developer)
- **Week 1**: Core + CLI - 30-40 hours
- **Week 2**: Executors + Config - 30-40 hours
- **Week 3**: Testing + MCP basics - 30-40 hours
- **Week 4**: Polish + Documentation - 20-30 hours
- **Total**: 110-150 hours (~4 weeks full-time)

### Phased Release Timeline
- **v0.3.0-beta1** (MVP): Week 2-3 - Core CLI working
- **v0.3.0-beta2**: Week 4 - SSH support added
- **v0.3.0-rc1**: Week 5 - Feature complete, testing
- **v0.3.0**: Week 6 - Production ready
- **v1.0.0**: 2-4 weeks after 0.3.0 - Stable after real-world usage

## Success Criteria

### Technical
- ✅ All existing Python tests pass with Nim version
- ✅ Binary size < 1MB (without MCP) or < 2MB (with MCP)
- ✅ Startup time < 10ms
- ✅ Zero external dependencies (fully static binary)
- ✅ Cross-compilation working (x86_64, ARM64)

### Functional
- ✅ All CLI commands work identically to Python version
- ✅ All profiles load and execute correctly
- ✅ SSH remote execution works
- ✅ Error messages are helpful and clear

### Quality
- ✅ Test coverage > 80%
- ✅ Documentation complete and accurate
- ✅ CI/CD pipeline building binaries for releases
- ✅ No security regressions

## Next Steps

### Immediate (Before Starting)
1. ✅ Get team buy-in on Nim port plan
2. ✅ Set up Nim development environment
3. ✅ Create `nim-port` branch or new repo
4. ✅ Install required Nim packages
5. ✅ Familiarize team with Nim basics

### Week 1 Tasks
1. Implement `process.nim` module
2. Implement basic `sandbox.nim` types
3. Implement JSON profile loading
4. Create first test suite
5. Get basic "hello world" running with bubblewrap

### Quick Wins to Prove Concept
- Day 1: Nim binary that can parse a JSON profile
- Day 3: Nim binary that can execute `ls /` via bubblewrap
- Day 5: Basic CLI that matches `shannot run ls /`
- Week 2: Full feature parity with Python CLI

## Open Questions

1. **Should we maintain both versions?**
   - Recommendation: Yes, for 2-3 releases, then deprecate Python

2. **Should we skip MCP initially?**
   - Recommendation: Yes, focus on core CLI first
   - MCP can be added in v0.4.0 or v1.1.0

3. **What about Windows support?**
   - Current Python version doesn't support Windows (requires bubblewrap)
   - Nim version same limitation
   - Could add WSL2 detection in future

4. **Should we use C bindings for SSH?**
   - Recommendation: Start with shelling out to `ssh`
   - Migrate to libssh2 bindings if performance critical

5. **Static binary dependencies?**
   - Recommendation: Use musl libc for true static linking
   - Or accept glibc dependency (99% of Linux systems)

## Conclusion

Porting Shannot to Nim is **feasible and recommended** for the stated goal of creating a single static binary. The Nim language is well-suited for this type of system utility, offering:

- ✅ Python-like syntax (easier learning curve)
- ✅ Static compilation (single binary goal)
- ✅ Excellent C interop (bubblewrap integration)
- ✅ Strong standard library (most features built-in)
- ✅ Great performance (negligible overhead)

**Estimated effort**: 4-6 weeks full-time for experienced developer, or 8-12 weeks part-time.

**Risk level**: Low-Medium. Main risks are SSH library maturity and MCP implementation, both of which have viable workarounds.

**Recommended approach**:
1. Start with MVP (core + CLI)
2. Run parallel versions
3. Gradually migrate users
4. Deprecate Python version after stability proven

This approach minimizes risk while achieving the static binary deployment goal.
