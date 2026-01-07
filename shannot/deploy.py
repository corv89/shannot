"""Deploy shannot CLI and runtime to remote targets."""

from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from .config import (
    DATA_DIR,
    PYPY_CONFIG,
    RELEASE_PATH_ENV,
    SANDBOX_CONFIG,
    SHANNOT_RELEASES_URL,
    get_remote_deploy_dir,
    get_version,
)
from .runtime import get_ssl_context
from .ssh import SSHConnection

if TYPE_CHECKING:
    pass

# Cache directory for downloaded artifacts
CACHE_DIR = DATA_DIR / "cache"


# =============================================================================
# Architecture Detection
# =============================================================================


def detect_arch(ssh: SSHConnection) -> str:
    """
    Detect remote architecture.

    Returns: "x86_64" or "arm64"

    Raises:
        RuntimeError: If architecture detection fails or unsupported
    """
    result = ssh.run("uname -m")
    if result.returncode != 0:
        raise RuntimeError("Failed to detect remote architecture")

    arch = result.stdout.decode().strip()
    # Normalize architecture names
    if arch in ("x86_64", "amd64"):
        return "x86_64"
    elif arch in ("aarch64", "arm64"):
        return "arm64"
    raise RuntimeError(f"Unsupported architecture: {arch}")


def _arch_to_platform_tag(arch: str) -> str:
    """Convert architecture to platform tag used in releases."""
    if arch == "x86_64":
        return "linux-amd64"
    elif arch == "arm64":
        return "linux-arm64"
    raise ValueError(f"Unknown architecture: {arch}")


# =============================================================================
# Download Utilities
# =============================================================================


def _download_file(url: str, dest: Path, desc: str = "Downloading") -> None:
    """Download a file with progress reporting."""
    sys.stderr.write(f"[DEPLOY] {desc}...\n")
    sys.stderr.write(f"[DEPLOY]   URL: {url}\n")

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "shannot/1.0"})
        ssl_context = get_ssl_context()
        with urllib.request.urlopen(request, context=ssl_context) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0

            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = downloaded * 100 // total_size
                        mb_down = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        sys.stderr.write(
                            f"\r[DEPLOY]   Progress: {mb_down:.1f}/{mb_total:.1f} MB ({pct}%)"
                        )
                        sys.stderr.flush()

            sys.stderr.write("\n")

    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(f"Not found: {url}") from e
        raise


def _verify_checksum(path: Path, expected: str) -> bool:
    """Verify SHA256 checksum of a file."""
    import hashlib

    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected


# =============================================================================
# CLI Binary
# =============================================================================


def _get_cli_binary(arch: str) -> Path:
    """
    Get shannot CLI binary for architecture, downloading if needed.

    Looks for (in order):
    1. $SHANNOT_RELEASE_PATH environment variable
    2. ./releases/shannot-linux-{arch} (local development)
    3. Cache at ~/.local/share/shannot/cache/shannot/v{VERSION}/
    4. Downloads from GitHub releases
    """
    binary_name = f"shannot-linux-{arch}"

    # 1. Check environment variable
    env_path = os.environ.get(RELEASE_PATH_ENV)
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # 2. Check local releases directory (development)
    releases_dir = Path(__file__).parent.parent / "releases"
    local_binary = releases_dir / binary_name
    if local_binary.exists():
        return local_binary

    # 3. Check cache
    version = get_version()
    cached = CACHE_DIR / "shannot" / f"v{version}" / binary_name
    if cached.exists():
        return cached

    # 4. Download from GitHub releases
    url = f"{SHANNOT_RELEASES_URL}/v{version}/{binary_name}"
    _download_file(url, cached, f"Downloading shannot v{version} for linux-{arch}")
    cached.chmod(0o755)
    sys.stderr.write(f"[DEPLOY]   Cached: {cached}\n")
    return cached


# =============================================================================
# Sandbox Binary
# =============================================================================


def _get_sandbox_binary(arch: str) -> Path:
    """
    Get PyPy sandbox binary for architecture, downloading if needed.

    Downloads from corv89/pypy releases.
    """
    platform_tag = _arch_to_platform_tag(arch)

    # Get platform-specific config
    sandbox_config = SANDBOX_CONFIG.get(platform_tag)
    if not sandbox_config or not sandbox_config.get("sha256"):
        raise FileNotFoundError(f"No pre-built sandbox for {platform_tag}")

    version = sandbox_config["version"]
    url = sandbox_config["url"]
    expected_sha256 = sandbox_config["sha256"]
    archive_name = url.rsplit("/", 1)[-1]

    # Check cache
    cached_binary = CACHE_DIR / "pypy" / version / f"pypy3-c-{arch}"
    if cached_binary.exists():
        return cached_binary
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / archive_name
        _download_file(url, archive_path, f"Downloading pypy3-sandbox for {platform_tag}")

        # Verify checksum
        sys.stderr.write("[DEPLOY]   Verifying checksum... ")
        sys.stderr.flush()
        if not _verify_checksum(archive_path, expected_sha256):
            sys.stderr.write("FAILED\n")
            raise RuntimeError("Checksum verification failed")
        sys.stderr.write("OK\n")

        # Extract binary
        cached_binary.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if Path(member.name).name == "pypy3-c":
                    # Extract to cache
                    src = tar.extractfile(member)
                    if src:
                        with open(cached_binary, "wb") as dst:
                            dst.write(src.read())
                        src.close()
                    cached_binary.chmod(0o755)
                    break
            else:
                raise RuntimeError("pypy3-c not found in archive")

    sys.stderr.write(f"[DEPLOY]   Cached: {cached_binary}\n")
    return cached_binary


def _get_sandbox_lib(arch: str) -> Path | None:
    """
    Get PyPy sandbox shared library for architecture, downloading if needed.

    Returns None if not present in archive (statically linked).
    """
    platform_tag = _arch_to_platform_tag(arch)

    # Get platform-specific config
    sandbox_config = SANDBOX_CONFIG.get(platform_tag)
    if not sandbox_config or not sandbox_config.get("sha256"):
        return None

    version = sandbox_config["version"]
    url = sandbox_config["url"]
    archive_name = url.rsplit("/", 1)[-1]

    # Check cache
    cached_lib = CACHE_DIR / "pypy" / version / f"libpypy3-c-{arch}.so"
    if cached_lib.exists():
        return cached_lib
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = Path(tmpdir) / archive_name
        _download_file(url, archive_path, f"Downloading sandbox lib for {platform_tag}")

        # Extract library
        cached_lib.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if Path(member.name).name == "libpypy3-c.so":
                    src = tar.extractfile(member)
                    if src:
                        with open(cached_lib, "wb") as dst:
                            dst.write(src.read())
                        src.close()
                    cached_lib.chmod(0o644)
                    return cached_lib

    return None


# =============================================================================
# Stdlib
# =============================================================================


def _get_stdlib_archive() -> Path:
    """
    Get PyPy stdlib archive, downloading if needed.

    Downloads from official PyPy downloads (python.org).
    For remote deployment, always use Linux config.
    """
    # Get Linux PyPy config (remote deployment is always Linux)
    pypy_config = PYPY_CONFIG["linux"]
    url = pypy_config["url"]
    expected_sha256 = pypy_config["sha256"]
    archive_name = url.rsplit("/", 1)[-1]

    # Cache the source archive
    cached = CACHE_DIR / "pypy" / archive_name
    if cached.exists():
        return cached

    _download_file(url, cached, "Downloading PyPy stdlib")

    # Verify checksum
    sys.stderr.write("[DEPLOY]   Verifying checksum... ")
    sys.stderr.flush()
    if not _verify_checksum(cached, expected_sha256):
        sys.stderr.write("FAILED\n")
        cached.unlink()
        raise RuntimeError("Checksum verification failed")
    sys.stderr.write("OK\n")
    sys.stderr.write(f"[DEPLOY]   Cached: {cached}\n")

    return cached


# =============================================================================
# Deployment Status Checks
# =============================================================================


def is_cli_deployed(ssh: SSHConnection) -> bool:
    """Check if shannot CLI is deployed on remote."""
    deploy_dir = get_remote_deploy_dir()
    result = ssh.run(f"test -x {deploy_dir}/shannot")
    return result.returncode == 0


def is_runtime_deployed(ssh: SSHConnection) -> bool:
    """Check if PyPy runtime (sandbox + stdlib) is deployed on remote."""
    deploy_dir = get_remote_deploy_dir()
    result = ssh.run(f"test -x {deploy_dir}/pypy3-c && test -d {deploy_dir}/lib-python")
    return result.returncode == 0


def get_deployed_version(ssh: SSHConnection) -> str | None:
    """Get deployed shannot version on remote, or None if not deployed."""
    deploy_dir = get_remote_deploy_dir()
    result = ssh.run(f"{deploy_dir}/shannot --version 2>/dev/null || echo ''")
    if result.returncode == 0:
        output = result.stdout.decode().strip()
        if output:
            # Output format is "shannot X.Y.Z" - extract version number
            parts = output.split()
            if len(parts) >= 2:
                return parts[1]  # Return just the version number
            return output  # Fallback to full output
    return None


# =============================================================================
# Deployment Functions
# =============================================================================


def deploy_cli(ssh: SSHConnection, force: bool = False) -> bool:
    """Deploy shannot CLI binary to remote."""
    deploy_dir = get_remote_deploy_dir()
    version = get_version()

    if not force and is_cli_deployed(ssh):
        # Check version
        deployed_ver = get_deployed_version(ssh)
        if deployed_ver == version:
            sys.stderr.write(f"[DEPLOY] CLI v{version} already deployed\n")
            return True
        sys.stderr.write(f"[DEPLOY] Upgrading CLI: {deployed_ver} → {version}\n")

    try:
        arch = detect_arch(ssh)
        binary = _get_cli_binary(arch)
    except (RuntimeError, FileNotFoundError) as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    sys.stderr.write(f"[DEPLOY] Uploading shannot CLI to {ssh.target}...\n")

    # Create deploy directory
    result = ssh.run(f"mkdir -p {deploy_dir}")
    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Failed to create directory: {result.stderr.decode()}\n")
        return False

    # Upload binary
    with open(binary, "rb") as f:
        binary_content = f.read()

    result = ssh.run(
        f"cat > {deploy_dir}/shannot && chmod +x {deploy_dir}/shannot",
        input_data=binary_content,
        timeout=120,
    )

    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Upload failed: {result.stderr.decode()}\n")
        return False

    sys.stderr.write(f"[DEPLOY] CLI deployed to {deploy_dir}/shannot\n")
    return True


def deploy_runtime(ssh: SSHConnection, force: bool = False) -> bool:
    """Deploy PyPy sandbox and stdlib to remote."""
    deploy_dir = get_remote_deploy_dir()

    if not force and is_runtime_deployed(ssh):
        sys.stderr.write("[DEPLOY] Runtime already deployed\n")
        return True

    try:
        arch = detect_arch(ssh)
    except RuntimeError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    # Create deploy directory
    result = ssh.run(f"mkdir -p {deploy_dir}")
    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Failed to create directory: {result.stderr.decode()}\n")
        return False

    # 1. Deploy sandbox binary
    try:
        sandbox_binary = _get_sandbox_binary(arch)
    except (FileNotFoundError, RuntimeError) as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    sys.stderr.write(f"[DEPLOY] Uploading sandbox binary to {ssh.target}...\n")
    with open(sandbox_binary, "rb") as f:
        content = f.read()

    result = ssh.run(
        f"cat > {deploy_dir}/pypy3-c && chmod +x {deploy_dir}/pypy3-c",
        input_data=content,
        timeout=120,
    )
    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Sandbox upload failed: {result.stderr.decode()}\n")
        return False

    # 2. Deploy sandbox shared library (if exists)
    sandbox_lib = _get_sandbox_lib(arch)
    if sandbox_lib and sandbox_lib.exists():
        sys.stderr.write("[DEPLOY] Uploading sandbox library...\n")
        with open(sandbox_lib, "rb") as f:
            content = f.read()
        result = ssh.run(
            f"cat > {deploy_dir}/libpypy3-c.so",
            input_data=content,
            timeout=60,
        )
        if result.returncode != 0:
            sys.stderr.write(f"[WARN] Library upload failed: {result.stderr.decode()}\n")

    # 3. Deploy stdlib
    try:
        stdlib_archive = _get_stdlib_archive()
    except (FileNotFoundError, RuntimeError) as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    sys.stderr.write(f"[DEPLOY] Uploading stdlib to {ssh.target}...\n")
    with open(stdlib_archive, "rb") as f:
        archive_content = f.read()

    # Upload and extract on remote
    # The archive has structure: pypy3.6-v7.3.3-src/{lib-python,lib_pypy}/...
    # We extract lib-python and lib_pypy to deploy_dir
    # Note: GNU tar requires --wildcards for glob patterns (BSD tar doesn't need it)
    extract_cmd = f"""
cd {deploy_dir} && \\
cat > stdlib.tar.bz2 && \\
tar -xjf stdlib.tar.bz2 --wildcards --strip-components=1 '*/lib-python' '*/lib_pypy' && \\
rm stdlib.tar.bz2
"""
    result = ssh.run(
        extract_cmd,
        input_data=archive_content,
        timeout=300,  # Large file, slow connection
    )
    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Stdlib extraction failed: {result.stderr.decode()}\n")
        return False

    sys.stderr.write(f"[DEPLOY] Runtime deployed to {deploy_dir}\n")
    return True


def deploy(ssh: SSHConnection, force: bool = False) -> bool:
    """
    Deploy shannot CLI and runtime to remote target.

    Args:
        ssh: Connected SSH session
        force: Redeploy even if already present

    Returns:
        True if deployment succeeded
    """
    # Deploy CLI
    if not deploy_cli(ssh, force):
        return False

    # Deploy runtime
    if not deploy_runtime(ssh, force):
        return False

    return True


def is_deployed(ssh: SSHConnection) -> bool:
    """Check if both CLI and runtime are deployed on remote."""
    return is_cli_deployed(ssh) and is_runtime_deployed(ssh)


def ensure_deployed(ssh: SSHConnection) -> bool:
    """Deploy if needed, return True if ready."""
    if is_deployed(ssh):
        return True
    return deploy(ssh)
