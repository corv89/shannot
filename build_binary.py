#!/usr/bin/env python3
"""
Build script for compiling shannot CLI to standalone binary using Nuitka.

This script compiles shannot CLI to a single
executable binary.

Usage:
    python build_binary.py [--debug] [--output-dir DIR]

Requirements:
    pip install nuitka ordered-set zstandard

Output:
    Binary will be created in dist/ directory by default.
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_platform_suffix() -> str:
    """Get platform-specific suffix for binary name."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize machine architecture
    if machine in ("x86_64", "amd64"):
        machine = "x86_64"
    elif machine in ("aarch64", "arm64"):
        machine = "arm64"

    return f"{system}-{machine}"


def check_requirements() -> None:
    """Verify all build requirements are met."""
    print("Checking build requirements...")

    # Check for Nuitka
    try:
        result = subprocess.run(
            ["python3", "-m", "nuitka", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"✓ Nuitka: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ Nuitka not found. Install with: pip install nuitka")
        sys.exit(1)

    # Check for C compiler
    compilers = ["gcc", "clang", "cc"]
    compiler_found = False
    for compiler in compilers:
        if shutil.which(compiler):
            print(f"✓ C compiler: {compiler}")
            compiler_found = True
            break

    if not compiler_found:
        print("✗ No C compiler found. Install gcc or clang.")
        sys.exit(1)

    # Check for source files
    source_dir = Path(__file__).parent / "shannot"
    if not source_dir.exists():
        print(f"✗ Source directory not found: {source_dir}")
        sys.exit(1)

    cli_file = source_dir / "cli.py"
    if not cli_file.exists():
        print(f"✗ CLI source not found: {cli_file}")
        sys.exit(1)

    print(f"✓ Source files found in {source_dir}")


def build_binary(output_dir: Path, debug: bool = False) -> Path:
    """Build the shannot binary using Nuitka."""
    project_root = Path(__file__).parent
    source_dir = project_root / "shannot"
    # Compile the shannot package directory (contains __main__.py)
    entrypoint = source_dir

    # Determine output name with platform suffix
    platform_suffix = get_platform_suffix()
    binary_name = f"shannot-{platform_suffix}"

    print(f"\nBuilding shannot binary for {platform_suffix}...")
    print(f"Output directory: {output_dir}")

    # Nuitka build arguments
    # Compile the shannot package directory (contains __main__.py)
    nuitka_args = [
        sys.executable,
        "-m",
        "nuitka",
        # Input - shannot package directory
        str(entrypoint),
        # Output configuration
        "--standalone",
        "--onefile",
        # Custom tempdir for onefile extraction
        "--onefile-tempdir-spec={CACHE_DIR}/shannot",
        f"--output-dir={output_dir}",
        f"--output-filename={binary_name}",
        # Include package data files (Nuitka auto-includes modules when compiling package dir)
        "--include-package-data=shannot",
        # Include stub .py files as data (not code) - needed for runtime reading
        f"--include-data-files={source_dir / 'stubs' / '_signal.py'}=shannot/stubs/_signal.py",
        f"--include-data-files="
        f"{source_dir / 'stubs' / 'subprocess.py'}=shannot/stubs/subprocess.py",
        # Note: importlib.metadata.version() is resolved at compile time by Nuitka's
        # pkg-resources plugin, so we don't need to bundle importlib.metadata
        # Python flags
        "--python-flag=no_site",  # Don't include site-packages
        "--python-flag=-O",  # Optimize bytecode
        "--python-flag=-u",  # Unbuffered stdout/stderr
        "--python-flag=-m",  # Run as module (for __main__.py)
        # Optional stdlib exclusions for smaller binary
        # These are not used by core shannot CLI
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=turtle",
        "--nofollow-import-to=test",
        "--nofollow-import-to=distutils",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=pydoc",
        "--nofollow-import-to=doctest",
        # Build options
        "--lto=yes",  # Link Time Optimization
        "--assume-yes-for-downloads",
        "--remove-output",  # Clean build artifacts after success
        # Warning settings
        "--warn-implicit-exceptions",
        "--warn-unusual-code",
    ]

    # Add debug options if requested
    if debug:
        nuitka_args.extend(
            [
                "--debug",
                "--verbose",
            ]
        )
    else:
        nuitka_args.append("--quiet")

    # Platform-specific optimizations
    # Note: No Linux-specific options needed for CLI tools

    print("\nRunning Nuitka (this may take several minutes)...")
    print(f"Command: {' '.join(nuitka_args[:5])} ...")

    try:
        subprocess.run(nuitka_args, check=True, cwd=project_root)
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed with exit code {e.returncode}")
        sys.exit(1)

    binary_path = output_dir / binary_name

    if not binary_path.exists():
        print(f"✗ Binary not found at expected location: {binary_path}")
        sys.exit(1)

    # Make executable
    binary_path.chmod(0o755)

    # Get binary size before compression
    size_before = binary_path.stat().st_size / (1024 * 1024)

    # Compress with UPX if available
    upx_path = shutil.which("upx")
    if upx_path:
        print("\nCompressing with UPX...")
        try:
            subprocess.run([upx_path, "--best", str(binary_path)], check=True)
            size_after = binary_path.stat().st_size / (1024 * 1024)
            reduction = (1 - size_after / size_before) * 100
            print(f"  Compressed: {size_before:.1f} MB → {size_after:.1f} MB (-{reduction:.0f}%)")
        except subprocess.CalledProcessError:
            print("  UPX compression failed, using uncompressed binary")
            size_after = size_before
    else:
        print("\n⚠ UPX not found, skipping compression (install with: apt install upx-ucl)")
        size_after = size_before

    print("\n✓ Build successful!")
    print(f"  Binary: {binary_path}")
    print(f"  Size: {size_after:.1f} MB")

    return binary_path


def test_binary(binary_path: Path) -> bool:
    """Run basic smoke tests on the compiled binary."""
    print("\nRunning smoke tests...")

    tests = [
        (["--version"], "version check", False),  # (args, description, expect_output)
        (["--help"], "help output", True),
        (["status"], "status command", True),  # Simple command that works without setup
    ]

    for args, description, expect_output in tests:
        print(f"  Testing {description}...", end=" ")
        try:
            result = subprocess.run(
                [str(binary_path)] + args,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            # Check if we got expected output
            if expect_output:
                total_output = len(result.stdout) + len(result.stderr)
                if total_output == 0:
                    print("✗ (no output)")
                    print("    Expected output but got none")
                    return False

            print("✓")
        except subprocess.CalledProcessError as e:
            print(f"✗ (exit code {e.returncode})")
            print(f"    stderr: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            print("✗ (timeout)")
            return False

    print("\n✓ All smoke tests passed!")
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build shannot CLI binary with Nuitka",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="Output directory for binary (default: dist/)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output from Nuitka",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip smoke tests after building",
    )

    args = parser.parse_args()

    # Verify build requirements
    check_requirements()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Build the binary
    binary_path = build_binary(args.output_dir, debug=args.debug)

    # Test the binary
    if not args.skip_tests:
        if not test_binary(binary_path):
            print("\n⚠ Warning: Some smoke tests failed")
            return 1

    print("\n" + "=" * 60)
    print("Build complete!")
    print("=" * 60)
    print(f"\nBinary location: {binary_path}")
    print("\nUsage:")
    print(f"  {binary_path} --help")
    print(f"  {binary_path} setup")
    print(f"  {binary_path} status")
    print("\nTo install system-wide:")
    print(f"  sudo cp {binary_path} /usr/local/bin/shannot")

    return 0


if __name__ == "__main__":
    sys.exit(main())
