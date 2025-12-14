# Shannot v2

A sandbox tool for safely executing Python 3.6 compatible code. Shannot intercepts system calls from a sandboxed PyPy subprocess and virtualizes the filesystem, providing secure isolation for untrusted code.

## Features

- **Virtual filesystem isolation** - Map specific directories to virtual paths, preventing access to the real filesystem
- **Subprocess execution control** - Tiered security with approval workflow for system commands
- **SSH remote execution** - Run sandboxed scripts with files fetched from remote hosts
- **Dry-run mode** - Test scripts without executing system calls
- **Session-based approval** - Review and approve pending operations via interactive TUI
- **ANSI-colored output** - Distinguish sandbox output from host output

## Requirements

**Host system:**
- Python 3.6+ (CPython or PyPy)
- cffi

**Sandboxed code:**
- Must use Python 3.6 compatible syntax
- Requires a PyPy sandbox executable

## Installation

```bash
pip install -e .
```

The cffi extension module is built automatically during installation.

## Quick Start

### 1. Install the runtime

```bash
shannot setup
```

This downloads and installs the PyPy 3.6 stdlib to `~/.local/share/shannot/runtime/`.

### 2. Run a script in the sandbox

```bash
shannot run /path/to/pypy-c-sandbox -S /tmp/script.py --tmp=/path/to/tmp
```

The `--tmp` option maps a real directory to the virtual `/tmp` inside the sandbox.

### 3. Review pending sessions

```bash
shannot approve
```

Opens an interactive TUI for reviewing and approving queued operations from dry-run sessions.

## CLI Reference

### `shannot setup`

Install PyPy stdlib for sandboxing.

```
Options:
  -f, --force    Force reinstall even if already installed
  -q, --quiet    Suppress progress output
  -s, --status   Check if runtime is installed
  --remove       Remove installed runtime
```

### `shannot run`

Run a script in the sandbox.

```
Usage: shannot run [options] <executable> [script_args...]

Options:
  --lib-path PATH    Path to lib-python and lib_pypy (auto-detected if not specified)
  --tmp DIR          Real directory mapped to virtual /tmp
  --nocolor          Disable ANSI coloring
  --raw-stdout       Disable output sanitization
  --debug            Enable debug mode
  --dry-run          Log commands without executing
  --script-name NAME Human-readable session name
  --analysis DESC    Description of script purpose
  --target USER@HOST SSH target for remote execution
```

### `shannot approve`

Launch interactive TUI for reviewing and approving pending sessions.

## License

See LICENSE file for details.
