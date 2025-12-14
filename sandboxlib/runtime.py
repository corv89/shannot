"""PyPy runtime download and management."""
from __future__ import annotations

import hashlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

from .config import (
    PYPY_DOWNLOAD_URL,
    PYPY_SHA256,
    PYPY_VERSION,
    RUNTIME_DIR,
    RUNTIME_LIB_PYPY,
    RUNTIME_LIB_PYTHON,
)


class SetupError(Exception):
    """Runtime setup failed."""

    pass


def is_runtime_installed() -> bool:
    """Check if runtime is installed and valid."""
    return RUNTIME_LIB_PYTHON.is_dir() and RUNTIME_LIB_PYPY.is_dir()


def get_runtime_path() -> Path | None:
    """Return runtime path if installed, None otherwise."""
    if is_runtime_installed():
        return RUNTIME_DIR
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

    with urllib.request.urlopen(request) as response:
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
    download_url: str = PYPY_DOWNLOAD_URL,
    expected_sha256: str = PYPY_SHA256,
) -> bool:
    """
    Download and install PyPy runtime.

    Args:
        force: Reinstall even if already present
        verbose: Print progress to stdout
        download_url: URL to download from
        expected_sha256: Expected SHA256 checksum

    Returns:
        True if installation succeeded
    """
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
        print(f"Downloading PyPy {PYPY_VERSION} stdlib from pypy.org...")
        print(f"  URL: {download_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / "pypy-src.tar.bz2"

        def download_progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = downloaded * 100 // total
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                sys.stdout.write(
                    f"\r  Downloading: {mb_down:.1f}/{mb_total:.1f} MB ({pct}%)"
                )
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
            raise SetupError(f"Download failed: {e}")

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
            raise SetupError(f"Extraction failed: {e}")

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
