"""PyPy runtime download and management."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import ssl
import sys
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .config import (
    RUNTIME_DIR,
    RUNTIME_LIB_PYPY,
    RUNTIME_LIB_PYTHON,
    SANDBOX_BINARY_NAME,
    SANDBOX_BINARY_PATH,
    SANDBOX_CONFIG,
    SANDBOX_LIB_NAME,
    SANDBOX_LIB_PATH,
    get_pypy_config,
)


class SetupError(Exception):
    """Runtime setup failed."""

    pass


def get_ssl_context() -> ssl.SSLContext:
    """Get SSL context that works on macOS with Nuitka binaries.

    Nuitka-compiled binaries on macOS can't find system SSL certificates.
    This function tries multiple certificate locations.
    """
    # Try default context first (works on most systems)
    ctx = ssl.create_default_context()

    # On macOS, try known certificate locations if default fails verification
    if platform.system() == "Darwin":
        # Common certificate locations on macOS
        cert_paths = [
            "/etc/ssl/cert.pem",  # Homebrew OpenSSL
            "/opt/homebrew/etc/openssl@3/cert.pem",  # Homebrew ARM64
            "/usr/local/etc/openssl@3/cert.pem",  # Homebrew x86_64
            "/opt/homebrew/etc/openssl/cert.pem",
            "/usr/local/etc/openssl/cert.pem",
        ]
        for cert_path in cert_paths:
            if os.path.exists(cert_path):
                try:
                    ctx = ssl.create_default_context(cafile=cert_path)
                    break
                except ssl.SSLError:
                    continue

    return ctx


def is_runtime_installed() -> bool:
    """Check if runtime is installed and valid."""
    return RUNTIME_LIB_PYTHON.is_dir() and RUNTIME_LIB_PYPY.is_dir()


def get_runtime_path() -> Path | None:
    """Return runtime path if installed, None otherwise."""
    if is_runtime_installed():
        return RUNTIME_DIR
    return None


def get_platform_tag() -> str | None:
    """Detect platform tag for sandbox binary download.

    Returns:
        Platform tag (e.g., 'linux-amd64') or None if unsupported.
    """
    system = platform.system().lower()
    machine = platform.machine()

    # Normalize machine names to match release asset naming
    if machine in ("x86_64", "AMD64"):
        arch = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    else:
        return None

    if system == "linux":
        return f"linux-{arch}"
    elif system == "darwin":
        return f"darwin-{arch}"

    return None


def is_sandbox_installed() -> bool:
    """Check if sandbox binary and library are installed at expected location."""
    binary_ok = SANDBOX_BINARY_PATH.exists() and os.access(SANDBOX_BINARY_PATH, os.X_OK)
    lib_ok = SANDBOX_LIB_PATH.exists()
    return binary_ok and lib_ok


def find_pypy_sandbox() -> Path | None:
    """Find pypy3-c (sandbox) binary.

    Checks:
    1. SANDBOX_BINARY_PATH (downloaded or manually placed)
    2. In PATH (via shutil.which)

    Returns:
        Path to sandbox binary if found, None otherwise.
    """
    # Check standard location first
    if SANDBOX_BINARY_PATH.exists() and os.access(SANDBOX_BINARY_PATH, os.X_OK):
        return SANDBOX_BINARY_PATH

    # Check PATH
    which_result = shutil.which("pypy3-c")
    if which_result:
        return Path(which_result)

    return None


def verify_checksum(filepath: Path, expected_sha256: str) -> bool:
    """Verify SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_sha256


def download_with_progress(
    url: str,
    dest: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Download URL to dest with optional progress reporting."""
    request = urllib.request.Request(url, headers={"User-Agent": "shannot/1.0"})
    ssl_context = get_ssl_context()

    with urllib.request.urlopen(request, context=ssl_context) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size)


def extract_runtime(
    archive_path: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Extract lib-python and lib_pypy from PyPy source archive.

    Archive structure:
        pypy3.6-v7.3.3-src/
        ├── lib-python/3/    → runtime/lib-python/3/
        └── lib_pypy/        → runtime/lib_pypy/
    """
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:bz2") as tar:
        # Find the root directory name (e.g., "pypy3.6-v7.3.3-src")
        root_name = None
        for member in tar.getmembers():
            if "/" in member.name:
                root_name = member.name.split("/")[0]
                break

        if not root_name:
            raise SetupError("Invalid archive structure")

        # Prefixes to extract (with trailing slash)
        lib_python_prefix = f"{root_name}/lib-python/"
        lib_pypy_prefix = f"{root_name}/lib_pypy/"

        for member in tar.getmembers():
            if member.name.startswith(lib_python_prefix):
                # Remap: pypy3.6-v7.3.3-src/lib-python/X -> lib-python/X
                rel_path = member.name[len(f"{root_name}/") :]
                if rel_path and rel_path != "lib-python/":
                    member.name = rel_path
                    if progress_callback:
                        progress_callback(member.name)
                    tar.extract(member, RUNTIME_DIR)

            elif member.name.startswith(lib_pypy_prefix):
                # Remap: pypy3.6-v7.3.3-src/lib_pypy/X -> lib_pypy/X
                rel_path = member.name[len(f"{root_name}/") :]
                if rel_path and rel_path != "lib_pypy/":
                    member.name = rel_path
                    if progress_callback:
                        progress_callback(member.name)
                    tar.extract(member, RUNTIME_DIR)


def setup_runtime(
    force: bool = False,
    verbose: bool = True,
    download_url: str | None = None,
    expected_sha256: str | None = None,
) -> bool:
    """
    Download and install PyPy runtime.

    Args:
        force: Reinstall even if already present
        verbose: Print progress to stdout
        download_url: URL to download from (uses platform-specific default)
        expected_sha256: Expected SHA256 checksum (uses platform-specific default)

    Returns:
        True if installation succeeded
    """
    # Get platform-specific config
    pypy_config = get_pypy_config()
    if download_url is None:
        download_url = pypy_config["url"]
    if expected_sha256 is None:
        expected_sha256 = pypy_config["sha256"]

    # Check if already installed
    if is_runtime_installed() and not force:
        if verbose:
            print(f"Runtime already installed at {RUNTIME_DIR}")
            print("Use --force to reinstall.")
        return True

    # Clean up if force reinstall
    if force and RUNTIME_DIR.exists():
        if verbose:
            print(f"Removing existing runtime at {RUNTIME_DIR}...")
        shutil.rmtree(RUNTIME_DIR)

    # Download
    if verbose:
        print(f"Downloading PyPy {pypy_config['version']} stdlib from pypy.org...")
        print(f"  URL: {download_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "pypy-src.tar.bz2"

        def download_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = downloaded * 100 // total
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                sys.stdout.write(f"\r  Downloading: {mb_down:.1f}/{mb_total:.1f} MB ({pct}%)")
                sys.stdout.flush()

        try:
            download_with_progress(
                download_url,
                archive_path,
                progress_callback=download_progress if verbose else None,
            )
            if verbose:
                print()  # Newline after progress
        except Exception as e:
            raise SetupError(f"Download failed: {e}") from e

        # Verify checksum
        if verbose:
            print(f"  SHA256: {expected_sha256}")
            sys.stdout.write("  Verifying checksum... ")
            sys.stdout.flush()

        if not verify_checksum(archive_path, expected_sha256):
            if verbose:
                print("FAILED")
            raise SetupError("Checksum verification failed!")

        if verbose:
            print("\u2713")  # checkmark

        # Extract
        if verbose:
            print("\nExtracting lib-python and lib_pypy...")

        file_count = 0

        def extract_progress(filename: str) -> None:
            nonlocal file_count
            file_count += 1
            if file_count % 100 == 0:
                sys.stdout.write(f"\r  Extracted {file_count} files...")
                sys.stdout.flush()

        try:
            extract_runtime(
                archive_path,
                progress_callback=extract_progress if verbose else None,
            )
            if verbose:
                print(f"\r  Extracted {file_count} files.    ")
        except Exception as e:
            raise SetupError(f"Extraction failed: {e}") from e

    if verbose:
        print(f"  {RUNTIME_LIB_PYTHON}/")
        print(f"  {RUNTIME_LIB_PYPY}/")
        print("\nSetup complete.")

    return True


def remove_runtime(verbose: bool = True) -> bool:
    """Remove installed runtime."""
    if not RUNTIME_DIR.exists():
        if verbose:
            print("No runtime installed.")
        return True

    shutil.rmtree(RUNTIME_DIR)
    if verbose:
        print(f"Runtime removed from {RUNTIME_DIR}")
    return True


def download_sandbox(
    force: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Download pre-built PyPy sandbox binary from GitHub releases.

    Args:
        force: Reinstall even if already present
        verbose: Print progress to stdout

    Returns:
        True if installation succeeded

    Raises:
        SetupError: If download or verification fails
    """
    # Check if already installed
    if is_sandbox_installed() and not force:
        if verbose:
            print(f"Sandbox binary already installed at {SANDBOX_BINARY_PATH}")
            print("Use --force to reinstall.")
        return True

    # Detect platform
    platform_tag = get_platform_tag()
    if not platform_tag:
        raise SetupError(
            f"Unsupported platform: {platform.system()} {platform.machine()}\n"
            "Supported: Linux x86_64, Linux aarch64, macOS x86_64, macOS arm64\n"
            "You can build from source: https://github.com/corv89/pypy"
        )

    # Get platform-specific config
    sandbox_config = SANDBOX_CONFIG.get(platform_tag)
    if not sandbox_config or not sandbox_config.get("sha256"):
        raise SetupError(
            f"No pre-built binary available for {platform_tag}\n"
            "You can build from source: https://github.com/corv89/pypy"
        )

    version = sandbox_config["version"]
    download_url = sandbox_config["url"]
    expected_sha256 = sandbox_config["sha256"]
    archive_name = download_url.rsplit("/", 1)[-1]  # Extract filename from URL

    if verbose:
        print(f"Downloading PyPy sandbox ({version}) for {platform_tag}...")
        print(f"  URL: {download_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / archive_name

        # Download with progress
        def download_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = downloaded * 100 // total
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                sys.stdout.write(f"\r  Downloading: {mb_down:.1f}/{mb_total:.1f} MB ({pct}%)")
                sys.stdout.flush()

        try:
            download_with_progress(
                download_url,
                archive_path,
                progress_callback=download_progress if verbose else None,
            )
            if verbose:
                print()
        except Exception as e:
            raise SetupError(f"Download failed: {e}") from e

        # Verify checksum
        if verbose:
            sys.stdout.write("  Verifying checksum... ")
            sys.stdout.flush()

        if not verify_checksum(archive_path, expected_sha256):
            if verbose:
                print("FAILED")
            raise SetupError("Checksum verification failed!")

        if verbose:
            print("\u2713")  # checkmark

        # Extract binary and shared library
        if verbose:
            print("  Extracting...")

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

        with tarfile.open(archive_path, "r:gz") as tar:
            # Find and extract pypy3-c binary
            binary_member = None
            lib_member = None
            for member in tar.getmembers():
                basename = Path(member.name).name
                if basename == SANDBOX_BINARY_NAME:
                    binary_member = member
                elif basename == SANDBOX_LIB_NAME:
                    lib_member = member

            if not binary_member:
                raise SetupError(f"Binary '{SANDBOX_BINARY_NAME}' not found in archive")

            # Extract binary
            binary_member.name = SANDBOX_BINARY_NAME  # Flatten path
            tar.extract(binary_member, RUNTIME_DIR)
            SANDBOX_BINARY_PATH.chmod(0o755)

            # Extract shared library if present
            if lib_member:
                lib_member.name = SANDBOX_LIB_NAME  # Flatten path
                tar.extract(lib_member, RUNTIME_DIR)
                SANDBOX_LIB_PATH.chmod(0o644)

    if verbose:
        print("\nInstalled:")
        print(f"  {SANDBOX_BINARY_PATH}")
        if SANDBOX_LIB_PATH.exists():
            print(f"  {SANDBOX_LIB_PATH}")

    return True
