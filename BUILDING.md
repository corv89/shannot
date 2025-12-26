# Building Shannot Binaries with Nuitka

This document describes how to build standalone binaries for shannot using Nuitka.

## Overview

We provide a `build_binary.py` script that compiles the `shannot` CLI into a standalone binary. This is useful for:

- Deploying to systems without Python
- Distributing to end users (simpler installation)
- Embedded/minimal systems
- When you want "download and run" simplicity

## Important Notes

### Version Management

**Version is managed through pyproject.toml and importlib.metadata:**
- `pyproject.toml` - Source of truth for version
- `shannot/config.py` - Reads version via `importlib.metadata.version("shannot")`
- Fallback to `"dev"` if metadata unavailable

⚠️ **When releasing a new version, update pyproject.toml!**

**Note**: Nuitka's pkg-resources plugin resolves `importlib.metadata.version()` at compile time, so the version is correctly embedded in the binary.

### Platform Requirements

**⚠️ Important: Functional binaries should be built on Linux**

While the build script works on macOS for development/testing, **functional binaries should be created on Linux** because:

1. **Shannot uses PyPy sandbox**, which is platform-specific
2. **The binary will only run on Linux anyway** (PyPy sandbox requirement)
3. **Nuitka onefile mode has stdout/stderr issues on macOS** (known limitation)

**For production use:**
- Build on the same platform you'll deploy to (Linux x86_64, ARM64, etc.)
- Use GitHub Actions or CI/CD for cross-platform builds
- Test on actual target systems

## Quick Start

### Prerequisites

```bash
# Install build dependencies
pip install nuitka ordered-set zstandard

# Ensure you have a C compiler (gcc or clang)
which gcc || which clang
```

### Build the Binary

```bash
# Basic build (output to dist/)
python build_binary.py

# Debug build with verbose output
python build_binary.py --debug

# Custom output directory
python build_binary.py --output-dir build/

# Skip smoke tests
python build_binary.py --skip-tests
```

### Build Output

```
dist/shannot-linux-x86_64    # On Linux x86_64
dist/shannot-linux-arm64     # On Linux ARM64
dist/shannot-darwin-arm64    # On macOS ARM (dev/testing only)
```

Binary size: ~8-15MB (includes Python interpreter + stdlib + shannot code)

## Build Script Details

### What It Does

1. **Checks requirements**: Nuitka, C compiler, source files
2. **Compiles** `shannot` package directory → `shannot` binary
3. **Includes**:
   - Entire `shannot` package
   - Stub files (`stubs/_signal.py`, `stubs/subprocess.py`)
   - Package metadata (for version detection)
4. **Excludes**:
   - Unused stdlib modules (tkinter, turtle, test, distutils)
5. **Runs smoke tests**: `--version`, `--help`, `status`
6. **Produces**: Platform-specific binary in `dist/`

### Key Files

- `build_binary.py` - Main build script
- `shannot/__main__.py` - Package entry point (used by Nuitka)
- `shannot/stubs/*.py` - Bundled as data files for runtime reading

### Nuitka Flags Used

```python
--standalone                          # Include dependencies
--onefile                             # Single executable
--include-package-data=shannot        # Include package data
--include-data-files=...              # Include stub files explicitly
--python-flag=no_site                 # Don't include site-packages
--python-flag=-O                      # Optimize bytecode
--python-flag=-u                      # Unbuffered I/O
--python-flag=-m                      # Run as module
--nofollow-import-to=tkinter          # Exclude GUI modules
--nofollow-import-to=turtle           # Exclude turtle graphics
--nofollow-import-to=test             # Exclude test modules
--nofollow-import-to=distutils        # Exclude distutils
```

## Testing the Binary

```bash
# Basic functionality
./dist/shannot-linux-x86_64 --version
./dist/shannot-linux-x86_64 --help
./dist/shannot-linux-x86_64 status

# Setup and run (requires PyPy sandbox)
./dist/shannot-linux-x86_64 setup
./dist/shannot-linux-x86_64 run script.py

# Check remote targets
./dist/shannot-linux-x86_64 remote list
```

## Distribution

### Manual Distribution

```bash
# Copy to /usr/local/bin
sudo cp dist/shannot-linux-x86_64 /usr/local/bin/shannot
sudo chmod +x /usr/local/bin/shannot

# Or create symlink
sudo ln -s /path/to/dist/shannot-linux-x86_64 /usr/local/bin/shannot
```

### GitHub Releases

Attach binaries to releases:

```bash
# Tag a release
git tag -a v0.4.0 -m "Release v0.4.0"
git push origin v0.4.0

# Build binaries on Linux (via CI or manually)
python build_binary.py

# Upload to GitHub release
gh release create v0.4.0 dist/shannot-linux-x86_64 \
  --title "v0.4.0" \
  --notes "Release notes here"
```

### Download URLs

```bash
# Users can download directly
curl -L https://github.com/corv89/shannot/releases/download/v0.4.0/shannot-linux-x86_64 \
  -o shannot
chmod +x shannot
```

## Known Issues

### macOS Build Issues

**Problem**: Binary compiles on macOS but produces no stdout/stderr output
**Cause**: Known Nuitka limitation with onefile mode on macOS
**Workaround**: Build on Linux for production use
**Status**: macOS binaries are for development/testing of build process only

### Version Detection

The version is correctly embedded via Nuitka's pkg-resources plugin, which resolves `importlib.metadata.version()` at compile time. No special handling needed.

### Binary Size

If binary size is too large:

1. Check what's included:
   ```bash
   # On Linux
   strings dist/shannot-linux-x86_64 | grep -i "site-packages"
   ```

2. Add more exclusions in `build_binary.py`:
   ```python
   "--nofollow-import-to=module_name",
   ```

3. Use UPX compression (optional):
   ```bash
   upx --best dist/shannot-linux-x86_64
   ```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build Binaries

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    strategy:
      matrix:
        platform:
          - os: ubuntu-latest
            arch: x86_64
          - os: ubuntu-latest
            arch: aarch64  # Use QEMU or native ARM runner

    runs-on: ${{ matrix.platform.os }}

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install nuitka ordered-set zstandard
          pip install -e .

      - name: Build binary
        run: python build_binary.py

      - name: Upload to release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/shannot-*
```

## Troubleshooting

### Build fails with "C compiler not found"

```bash
# Install gcc/clang
sudo apt install build-essential  # Debian/Ubuntu
sudo dnf install gcc              # Fedora/RHEL
```

### Build fails with "Nuitka not found"

```bash
# Make sure Nuitka is installed in current environment
pip install nuitka
python -m nuitka --version
```

### Binary won't run

```bash
# Check if it's executable
chmod +x dist/shannot-linux-x86_64

# Check architecture matches
file dist/shannot-linux-x86_64
uname -m

# Check library dependencies
ldd dist/shannot-linux-x86_64  # Should be mostly self-contained
```

### Smoke tests fail

```bash
# Run with verbose output to see what's failing
python build_binary.py --debug

# Test manually
./dist/shannot-linux-x86_64 --version
echo "Exit code: $?"
```

## Development

### Testing Build Changes

```bash
# Quick iteration
rm -rf dist/
python build_binary.py --skip-tests

# Full test
python build_binary.py
```

### Adding New Exclusions

To reduce binary size, add exclusions for modules not used by core CLI:

```python
# In build_binary.py
"--nofollow-import-to=module_name",
```

Common candidates:
- `unittest`, `doctest` - Testing frameworks
- `pydoc`, `inspect` - Documentation tools
- `xml`, `html` - Parsers (if not used)
- `sqlite3` - Database (if not used)

### Verifying Inclusions

Check what's actually in the binary:

```bash
# Extract and inspect (Linux)
./dist/shannot-linux-x86_64 --help  # Extracts to temp dir
ls -la /tmp/onefile_*/

# Check for specific files
strings dist/shannot-linux-x86_64 | grep "stubs/_signal.py"
```

## Further Reading

- [Nuitka Documentation](https://nuitka.net/doc/user-manual.html)
- [Nuitka Onefile Mode](https://nuitka.net/doc/user-manual.html#onefile-mode)
- [Nuitka Performance](https://nuitka.net/pages/performance.html)

## Support

If you encounter issues:

1. Check this document's troubleshooting section
2. Verify you're building on Linux for production
3. Open an issue: https://github.com/corv89/shannot/issues
