"""Deploy shannot to remote targets."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from .config import (
    DATA_DIR,
    RELEASE_PATH_ENV,
    SHANNOT_RELEASES_URL,
    VERSION,
    get_remote_deploy_dir,
)
from .ssh import SSHConnection

if TYPE_CHECKING:
    pass

# Cache directory for downloaded binaries
BINARY_CACHE_DIR = DATA_DIR / "binaries"


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


def is_deployed(ssh: SSHConnection) -> bool:
    """Check if shannot is deployed on remote."""
    deploy_dir = get_remote_deploy_dir()
    result = ssh.run(f"test -x {deploy_dir}/shannot")
    return result.returncode == 0


def get_deployed_version(ssh: SSHConnection) -> str | None:
    """Get deployed shannot version on remote, or None if not deployed."""
    deploy_dir = get_remote_deploy_dir()
    result = ssh.run(f"{deploy_dir}/shannot --version 2>/dev/null || echo ''")
    if result.returncode == 0:
        version = result.stdout.decode().strip()
        if version:
            return version
    return None


def _download_binary(arch: str, dest: Path) -> None:
    """Download shannot binary from GitHub releases."""
    # Format: https://github.com/corv89/shannot/releases/download/v0.8.6/shannot-linux-arm64
    binary_name = f"shannot-linux-{arch}"
    download_url = f"{SHANNOT_RELEASES_URL}/v{VERSION}/{binary_name}"

    sys.stderr.write(f"[DEPLOY] Downloading shannot v{VERSION} for linux-{arch}...\n")
    sys.stderr.write(f"[DEPLOY]   URL: {download_url}\n")

    try:
        request = urllib.request.Request(download_url, headers={"User-Agent": "shannot/1.0"})
        with urllib.request.urlopen(request) as response:
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
                            f"\r[DEPLOY]   Downloading: {mb_down:.1f}/{mb_total:.1f} MB ({pct}%)"
                        )
                        sys.stderr.flush()

            sys.stderr.write("\n")
            dest.chmod(0o755)
            sys.stderr.write(f"[DEPLOY]   Cached to {dest}\n")

    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(
                f"Binary not found at {download_url}\n"
                f"Make sure v{VERSION} release exists with linux-{arch} binary"
            ) from e
        raise


def get_release_binary(arch: str) -> Path:
    """
    Get path to release binary for architecture.

    Looks for (in order):
    1. $SHANNOT_RELEASE_PATH environment variable
    2. ./releases/shannot-linux-{arch} (local development)
    3. ~/.local/share/shannot/binaries/v{VERSION}/shannot-linux-{arch} (cached)
    4. Downloads from GitHub releases and caches

    Raises:
        FileNotFoundError: If binary not found and download fails
    """
    binary_name = f"shannot-linux-{arch}"

    # 1. Check environment variable first
    env_path = os.environ.get(RELEASE_PATH_ENV)
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # 2. Look in releases directory (relative to package, for development)
    releases_dir = Path(__file__).parent.parent / "releases"
    local_binary = releases_dir / binary_name
    if local_binary.exists():
        return local_binary

    # 3. Check cache
    cached_binary = BINARY_CACHE_DIR / f"v{VERSION}" / binary_name
    if cached_binary.exists():
        return cached_binary

    # 4. Download from GitHub releases
    _download_binary(arch, cached_binary)
    return cached_binary


def deploy(ssh: SSHConnection, force: bool = False) -> bool:
    """
    Deploy shannot to remote target.

    Args:
        ssh: Connected SSH session
        force: Redeploy even if already present

    Returns:
        True if deployment succeeded
    """
    deploy_dir = get_remote_deploy_dir()

    if not force and is_deployed(ssh):
        return True

    # Detect architecture
    try:
        arch = detect_arch(ssh)
    except RuntimeError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    # Get binary (downloads if needed)
    try:
        binary = get_release_binary(arch)
    except FileNotFoundError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    sys.stderr.write(f"[DEPLOY] Deploying shannot v{VERSION} to {ssh.target}...\n")

    # Create deploy directory
    result = ssh.run(f"mkdir -p {deploy_dir}")
    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Failed to create deploy directory: {result.stderr.decode()}\n")
        return False

    # Read binary content
    with open(binary, "rb") as f:
        binary_content = f.read()

    # Upload binary directly
    result = ssh.run(
        f"cat > {deploy_dir}/shannot && chmod +x {deploy_dir}/shannot",
        input_data=binary_content,
        timeout=120,
    )

    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Deploy failed: {result.stderr.decode()}\n")
        return False

    # Verify deployment
    if is_deployed(ssh):
        sys.stderr.write(f"[DEPLOY] Successfully deployed to {deploy_dir}\n")
        return True

    sys.stderr.write("[ERROR] Deployment verification failed\n")
    return False


def ensure_deployed(ssh: SSHConnection) -> bool:
    """Deploy if needed, return True if ready."""
    if is_deployed(ssh):
        return True
    return deploy(ssh)
