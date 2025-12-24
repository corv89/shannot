"""SSH connection manager with ControlMaster support."""

from __future__ import annotations

import atexit
import errno
import hashlib
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class SSHConfig:
    """SSH connection configuration."""

    target: str  # user@host
    connect_timeout: int = 10
    command_timeout: int = 30
    control_path: Path | None = field(default=None)
    port: int = 22

    def __post_init__(self):
        if self.control_path is None:
            # Use temp directory for control socket
            # Include target hash to avoid collisions
            target_hash = hashlib.md5(self.target.encode()).hexdigest()[:8]
            control_name = f"shannot-ssh-{os.getpid()}-{target_hash}"
            self.control_path = Path(tempfile.gettempdir()) / control_name


class SSHConnection:
    """
    SSH connection with ControlMaster multiplexing.

    Uses a persistent ControlMaster connection to avoid per-command
    connection overhead. The socket is automatically cleaned up on exit.

    Usage:
        ssh = SSHConnection("user@host")
        ssh.connect()
        result = ssh.run("cat /etc/hostname")
        ssh.disconnect()

    Or as context manager:
        with SSHConnection("user@host") as ssh:
            result = ssh.run("ls -la")
    """

    def __init__(self, config: SSHConfig | str):
        if isinstance(config, str):
            config = SSHConfig(target=config)
        self.config = config
        self._connected = False
        self._registered_cleanup = False

    @property
    def target(self) -> str:
        return self.config.target

    def _base_ssh_args(self) -> list[str]:
        """Base SSH arguments with ControlMaster options."""
        args = [
            "ssh",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={self.config.control_path}",
            "-o",
            "ControlPersist=60",
            "-o",
            f"ConnectTimeout={self.config.connect_timeout}",
            "-o",
            "BatchMode=yes",  # Never prompt for password
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        # Add port if non-default
        if self.config.port != 22:
            args.extend(["-p", str(self.config.port)])
        return args

    def connect(self) -> bool:
        """
        Establish ControlMaster connection.

        Returns True if connection succeeded, False otherwise.
        """
        if self._connected:
            return True

        # Start ControlMaster in background
        args = self._base_ssh_args() + [
            "-M",  # Master mode
            "-N",  # No command
            "-f",  # Background
            self.config.target,
        ]

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                timeout=self.config.connect_timeout + 5,
            )
            if result.returncode == 0:
                self._connected = True
                # Register cleanup on exit
                if not self._registered_cleanup:
                    atexit.register(self.disconnect)
                    self._registered_cleanup = True
                return True
            return False
        except subprocess.TimeoutExpired:
            return False
        except OSError:
            # Connection failures (network unreachable, refused, etc.)
            return False

    def run(
        self,
        command: str,
        input_data: bytes | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Execute command via existing ControlMaster.

        Args:
            command: Shell command to execute on remote host
            input_data: Optional bytes to pipe to stdin
            timeout: Command timeout in seconds (default: config.command_timeout)

        Returns:
            subprocess.CompletedProcess with returncode, stdout, stderr
        """
        if timeout is None:
            timeout = self.config.command_timeout

        args = self._base_ssh_args() + [self.config.target, command]

        try:
            return subprocess.run(
                args,
                input=input_data,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                args=args,
                returncode=124,  # Standard timeout exit code
                stdout=b"",
                stderr=b"Command timed out",
            )
        except Exception as e:
            return subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout=b"",
                stderr=str(e).encode(),
            )

    def read_file(self, path: str) -> bytes:
        """
        Read remote file content.

        Args:
            path: Absolute path on remote host

        Returns:
            File content as bytes

        Raises:
            OSError: If file cannot be read (ENOENT, EACCES, EIO)
        """
        result = self.run(f"cat {shlex.quote(path)}")
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            if "No such file" in stderr or "cannot open" in stderr.lower():
                raise OSError(errno.ENOENT, f"No such file: {path}")
            if "Permission denied" in stderr:
                raise OSError(errno.EACCES, f"Permission denied: {path}")
            raise OSError(errno.EIO, f"Failed to read {path}: {stderr}")
        return result.stdout

    def write_file(self, path: str, content: bytes) -> None:
        """
        Write content to remote file.

        Uses 'tee' to write. For root-owned files, SSH as root or
        configure passwordless sudo in your script.

        Args:
            path: Absolute path on remote host
            content: File content to write

        Raises:
            OSError: If write fails (EACCES, EIO)
        """
        cmd = f"tee {shlex.quote(path)} > /dev/null"

        result = self.run(cmd, input_data=content)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            if "Permission denied" in stderr:
                raise OSError(errno.EACCES, f"Permission denied: {path}")
            raise OSError(errno.EIO, f"Failed to write {path}: {stderr}")

    def stat_file(self, path: str) -> _StatResult:
        """
        Get file stat info via stat command.

        Args:
            path: Absolute path on remote host

        Returns:
            os.stat_result-like object with st_mode, st_size, st_mtime, etc.

        Raises:
            OSError: If stat fails (ENOENT, EACCES)
        """
        # Use stat with format string to get structured output
        # Format: mode size mtime atime uid gid inode nlink
        fmt = "%f %s %Y %X %u %g %i %h"
        result = self.run(f"stat --printf={shlex.quote(fmt)} {shlex.quote(path)}")

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            if "No such file" in stderr or "cannot stat" in stderr.lower():
                raise OSError(errno.ENOENT, f"No such file: {path}")
            if "Permission denied" in stderr:
                raise OSError(errno.EACCES, f"Permission denied: {path}")
            raise OSError(errno.EIO, f"Failed to stat {path}: {stderr}")

        try:
            parts = result.stdout.decode().split()
            st_mode = int(parts[0], 16)  # Mode is in hex
            st_size = int(parts[1])
            st_mtime = int(parts[2])
            st_atime = int(parts[3])
            st_uid = int(parts[4])
            st_gid = int(parts[5])
            st_ino = int(parts[6])
            st_nlink = int(parts[7])

            # Create stat_result-like namedtuple
            return _StatResult(
                st_mode=st_mode,
                st_ino=st_ino,
                st_dev=0,
                st_nlink=st_nlink,
                st_uid=st_uid,
                st_gid=st_gid,
                st_size=st_size,
                st_atime=st_atime,
                st_mtime=st_mtime,
                st_ctime=st_mtime,  # Use mtime for ctime
            )
        except (ValueError, IndexError) as e:
            raise OSError(errno.EIO, f"Failed to parse stat output: {e}") from e

    def list_dir(self, path: str) -> list[str]:
        """
        List directory contents.

        Args:
            path: Absolute path to directory on remote host

        Returns:
            List of filenames (without path prefix)

        Raises:
            OSError: If listing fails (ENOENT, ENOTDIR, EACCES)
        """
        result = self.run(f"ls -1 {shlex.quote(path)}")

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            if "No such file" in stderr:
                raise OSError(errno.ENOENT, f"No such directory: {path}")
            if "Not a directory" in stderr:
                raise OSError(errno.ENOTDIR, f"Not a directory: {path}")
            if "Permission denied" in stderr:
                raise OSError(errno.EACCES, f"Permission denied: {path}")
            raise OSError(errno.EIO, f"Failed to list {path}: {stderr}")

        # Split output into lines, filter empty
        output = result.stdout.decode("utf-8", errors="replace")
        return [name for name in output.splitlines() if name]

    def file_exists(self, path: str) -> bool:
        """Check if file or directory exists."""
        result = self.run(f"test -e {shlex.quote(path)}")
        return result.returncode == 0

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        result = self.run(f"test -d {shlex.quote(path)}")
        return result.returncode == 0

    def disconnect(self) -> None:
        """Close ControlMaster connection and clean up socket."""
        if not self._connected:
            return

        # Send exit command to ControlMaster
        args = [
            "ssh",
            "-o",
            f"ControlPath={self.config.control_path}",
            "-O",
            "exit",
            self.config.target,
        ]

        try:
            subprocess.run(args, capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass  # Best effort cleanup

        # Remove socket file if it exists
        try:
            if self.config.control_path and self.config.control_path.exists():
                self.config.control_path.unlink()
        except OSError:
            pass  # Socket already removed or inaccessible

        self._connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __del__(self):
        # Backup cleanup in case atexit doesn't run
        try:
            self.disconnect()
        except (OSError, subprocess.TimeoutExpired):
            pass  # Best effort cleanup during garbage collection


class _StatResult:
    """
    Minimal stat_result-like object.

    Provides the same attributes as os.stat_result for compatibility.
    """

    def __init__(
        self,
        st_mode: int,
        st_ino: int,
        st_dev: int,
        st_nlink: int,
        st_uid: int,
        st_gid: int,
        st_size: int,
        st_atime: int,
        st_mtime: int,
        st_ctime: int,
    ):
        self.st_mode = st_mode
        self.st_ino = st_ino
        self.st_dev = st_dev
        self.st_nlink = st_nlink
        self.st_uid = st_uid
        self.st_gid = st_gid
        self.st_size = st_size
        self.st_atime = st_atime
        self.st_mtime = st_mtime
        self.st_ctime = st_ctime

    def __repr__(self):
        return (
            f"_StatResult(st_mode={self.st_mode:#o}, st_size={self.st_size}, "
            f"st_uid={self.st_uid}, st_gid={self.st_gid})"
        )
