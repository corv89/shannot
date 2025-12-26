"""Deploy shannot to remote targets."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config import RELEASE_PATH_ENV, VERSION, get_remote_deploy_dir
from .ssh import SSHConnection

if TYPE_CHECKING:
    pass


def detect_arch(ssh: SSHConnection) -> str:
    """
    Detect remote architecture.

    Returns: "x86_64" or "aarch64"

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
        return "aarch64"
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


def get_release_tarball(arch: str) -> Path:
    """
    Get path to release tarball for architecture.

    Looks for:
    1. $SHANNOT_RELEASE_PATH environment variable
    2. ./releases/shannot-{version}-linux-{arch}.tar.gz

    Raises:
        FileNotFoundError: If tarball not found
    """
    # Check environment variable first
    env_path = os.environ.get(RELEASE_PATH_ENV)
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # Look in releases directory (relative to package)
    releases_dir = Path(__file__).parent.parent / "releases"
    tarball = releases_dir / f"shannot-{VERSION}-linux-{arch}.tar.gz"
    if tarball.exists():
        return tarball

    raise FileNotFoundError(
        f"Release tarball not found for {arch}.\n"
        f"For development, build first: make build-binary\n"
        f"Or set {RELEASE_PATH_ENV}=/path/to/tarball"
    )


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

    # Get tarball
    try:
        tarball = get_release_tarball(arch)
    except FileNotFoundError as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        return False

    sys.stderr.write(f"[DEPLOY] Deploying shannot v{VERSION} to {ssh.target}...\n")

    # Create deploy directory
    result = ssh.run(f"mkdir -p {deploy_dir}")
    if result.returncode != 0:
        sys.stderr.write(f"[ERROR] Failed to create deploy directory: {result.stderr.decode()}\n")
        return False

    # Read tarball content
    with open(tarball, "rb") as f:
        tarball_content = f.read()

    # Upload and extract tarball
    # Use cat to write tarball, then extract
    result = ssh.run(
        f"cat > /tmp/shannot-deploy.tar.gz && "
        f"tar -xzf /tmp/shannot-deploy.tar.gz -C {deploy_dir} && "
        f"rm /tmp/shannot-deploy.tar.gz",
        input_data=tarball_content,
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
