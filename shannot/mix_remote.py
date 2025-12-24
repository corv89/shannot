"""Mixin for remote file system access via SSH."""

from __future__ import annotations

import errno
import stat
from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

from .mix_vfs import GID, INO_COUNTER, UID, Dir, FSObject
from .structs import new_stat

if TYPE_CHECKING:
    from .ssh import SSHConnection


class RemoteFile(FSObject):
    """
    File backed by remote SSH access.

    Lazily fetches file content and stat info via SSH.
    """

    kind = stat.S_IFREG

    def __init__(self, ssh: SSHConnection, remote_path: str, read_only: bool = True):
        self.ssh = ssh
        self.remote_path = remote_path
        self.read_only = read_only
        self._cached_stat = None
        self._cached_content = None

    def __repr__(self):
        return f"<RemoteFile {self.remote_path}>"

    def stat(self):
        """Get file stat from remote, with caching."""
        if self._cached_stat is None:
            self._cached_stat = self._fetch_stat()
        return self._cached_stat

    def _fetch_stat(self):
        """Fetch stat info via SSH and convert to ffi struct."""
        global INO_COUNTER

        try:
            remote_stat = self.ssh.stat_file(self.remote_path)
        except OSError:
            # Return a default stat on error
            INO_COUNTER += 1
            return new_stat(
                st_ino=INO_COUNTER,
                st_dev=1,
                st_nlink=1,
                st_size=0,
                st_mode=self.kind | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
                st_uid=0,
                st_gid=0,
            )

        # Convert remote stat to Stat struct
        st_mode = remote_stat.st_mode
        if self.read_only:
            st_uid = 0
            st_gid = 0
        else:
            st_uid = UID
            st_gid = GID

        return new_stat(
            st_ino=remote_stat.st_ino,
            st_dev=1,
            st_nlink=remote_stat.st_nlink,
            st_size=remote_stat.st_size,
            st_mode=st_mode,
            st_uid=st_uid,
            st_gid=st_gid,
        )

    def getsize(self) -> int:
        """Return file size."""
        try:
            return self.stat().st_size
        except OSError:
            return 0

    def open(self) -> BinaryIO:
        """Return file-like object with remote content."""
        if self._cached_content is None:
            try:
                self._cached_content = self.ssh.read_file(self.remote_path)
            except OSError as e:
                raise OSError(e.errno, f"Failed to read {self.remote_path}") from e
        return BytesIO(self._cached_content)

    def invalidate_cache(self):
        """Clear cached content and stat."""
        self._cached_stat = None
        self._cached_content = None


class RemoteDir(FSObject):
    """
    Directory backed by remote SSH access.

    Lazily lists directory contents via SSH.
    """

    kind = stat.S_IFDIR

    def __init__(self, ssh: SSHConnection, remote_path: str, read_only: bool = True):
        self.ssh = ssh
        self.remote_path = remote_path
        self.read_only = read_only
        self._cached_keys = None

    def __repr__(self):
        return f"<RemoteDir {self.remote_path}>"

    def stat(self):
        """Get directory stat."""
        global INO_COUNTER

        try:
            remote_stat = self.ssh.stat_file(self.remote_path)
            st_mode = remote_stat.st_mode
            st_ino = remote_stat.st_ino
        except OSError:
            INO_COUNTER += 1
            st_ino = INO_COUNTER
            st_mode = (
                self.kind | stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
            )

        if self.read_only:
            st_uid = 0
            st_gid = 0
        else:
            st_uid = UID
            st_gid = GID

        return new_stat(
            st_ino=st_ino,
            st_dev=1,
            st_nlink=1,
            st_size=4096,
            st_mode=st_mode,
            st_uid=st_uid,
            st_gid=st_gid,
        )

    def keys(self) -> list[str]:
        """List directory contents."""
        if self._cached_keys is None:
            try:
                self._cached_keys = sorted(self.ssh.list_dir(self.remote_path))
            except OSError:
                self._cached_keys = []
        return self._cached_keys

    def join(self, name: str) -> RemoteDir | RemoteFile:
        """
        Traverse to child node.

        Returns RemoteFile or RemoteDir based on remote file type.
        """
        child_path = f"{self.remote_path.rstrip('/')}/{name}"

        try:
            remote_stat = self.ssh.stat_file(child_path)
        except OSError:
            raise OSError(errno.ENOENT, name) from None

        if stat.S_ISDIR(remote_stat.st_mode):
            return RemoteDir(self.ssh, child_path, self.read_only)
        else:
            return RemoteFile(self.ssh, child_path, self.read_only)

    def invalidate_cache(self):
        """Clear cached keys."""
        self._cached_keys = None


class MixRemote:
    """
    Mixin to proxy certain paths to a remote host via SSH.

    When remote_target is None, this mixin is a no-op.
    When remote_target is set (e.g., "user@host"), paths matching
    remote_paths will be served via SSH.

    Configuration (class attributes):
        remote_target: str | None - SSH target (user@host), None = disabled
        remote_paths: list[str] - Virtual paths to proxy to remote

    Usage:
        class MyProc(MixRemote, MixVFS, VirtualizedProc):
            remote_target = "user@host"
            remote_paths = ["/proc", "/sys", "/etc"]
    """

    remote_target: str | None = None
    remote_paths: list = ["/proc", "/sys", "/var/log", "/etc", "/run"]

    # Internal state
    _ssh_connection: SSHConnection | None = None

    def __init__(self, *args, **kwargs):
        # Extract remote args from kwargs if provided
        target = kwargs.pop("remote_target", None)
        if target is not None:
            self.remote_target = target

        super().__init__(*args, **kwargs)

        # Initialize SSH and mount remote paths if target is set
        if self._is_remote():
            self._init_remote_vfs()

    def _is_remote(self) -> bool:
        """Check if remote mode is enabled."""
        return self.remote_target is not None

    def _init_remote_vfs(self):
        """Initialize SSH connection and mount remote paths into VFS."""
        from .ssh import SSHConnection

        # remote_target is guaranteed non-None here (called only when _is_remote() is True)
        assert self.remote_target is not None
        self._ssh_connection = SSHConnection(self.remote_target)

        if not self._ssh_connection.connect():
            import sys

            sys.stderr.write(f"[WARN] Failed to connect to {self.remote_target}\n")
            self._ssh_connection = None
            return

        # Mount remote directories into VFS root
        for path in self.remote_paths:
            self._mount_remote_path(path)

    def _mount_remote_path(self, virtual_path: str):
        """
        Mount a remote path into the VFS tree.

        Creates necessary parent directories in the VFS and mounts
        a RemoteDir at the target path.
        """
        if self._ssh_connection is None:
            return

        path_parts = virtual_path.strip("/").split("/")
        if not path_parts or not path_parts[0]:
            return

        # Navigate to parent and create directories as needed
        current = self.vfs_root  # type: ignore[attr-defined]

        # Create parent directories as virtual Dir objects
        for _i, part in enumerate(path_parts[:-1]):
            if hasattr(current, "entries"):
                if part not in current.entries:
                    current.entries[part] = Dir({})
                current = current.entries[part]
            else:
                # Can't navigate further
                return

        # Mount RemoteDir at final location
        final_name = path_parts[-1]
        if hasattr(current, "entries"):
            # Check if the remote path exists before mounting
            if self._ssh_connection.file_exists(virtual_path):
                if self._ssh_connection.is_dir(virtual_path):
                    current.entries[final_name] = RemoteDir(
                        self._ssh_connection,
                        virtual_path,
                        read_only=True,
                    )
                else:
                    current.entries[final_name] = RemoteFile(
                        self._ssh_connection,
                        virtual_path,
                        read_only=True,
                    )

    def cleanup(self):
        """Disconnect SSH on cleanup."""
        if self._ssh_connection:
            self._ssh_connection.disconnect()
            self._ssh_connection = None

    def get_ssh_connection(self) -> SSHConnection | None:
        """Get the SSH connection for use by other mixins."""
        return self._ssh_connection
