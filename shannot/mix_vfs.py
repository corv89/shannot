from __future__ import annotations

import errno
import hashlib
import os
import stat
import sys
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from .sandboxio import NULL
from .structs import DT_DIR, DT_REG, SIZEOF_DIRENT, new_dirent, new_stat, struct_to_bytes
from .virtualizedproc import sigerror, signature

MAX_PATH = 256
MAX_WRITE_CHUNK = 256 * 1024  # 256KB maximum single write/read size
MAX_WRITE_SIZE = 50 * 1024 * 1024  # 50MB maximum file write size
UID = 1000
GID = 1000
INO_COUNTER = 0


class FSObject:
    """Base class for virtual filesystem objects.

    Subclasses implement specific node types (files, directories).
    The read_only flag controls virtual ownership: read-only files
    appear owned by root, read-write files by the virtual user.
    """

    read_only = True
    kind: int = 0  # Subclasses must override with stat.S_IFDIR or stat.S_IFREG

    def stat(self):
        try:
            st_ino = self._st_ino
        except AttributeError:
            global INO_COUNTER
            INO_COUNTER += 1
            st_ino = self._st_ino = INO_COUNTER
        st_mode = self.kind
        st_mode |= stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
        if self.is_dir():
            st_mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        if self.read_only:
            st_uid = 0  # read-only files are virtually owned by root
            st_gid = 0
        else:
            st_uid = UID  # read-write files are owned by this virtual user
            st_gid = GID
        return new_stat(
            st_ino=st_ino,
            st_dev=1,
            st_nlink=1,
            st_size=self.getsize(),
            st_mode=st_mode,
            st_uid=st_uid,
            st_gid=st_gid,
        )

    def access(self, mode):
        s = self.stat()
        e_mode = s.st_mode & stat.S_IRWXO
        if UID == s.st_uid:
            e_mode |= (s.st_mode & stat.S_IRWXU) >> 6
        if GID == s.st_gid:
            e_mode |= (s.st_mode & stat.S_IRWXG) >> 3
        return (e_mode & mode) == mode

    def keys(self) -> list[str]:
        """Return list of child names. Raises OSError for non-directories."""
        raise OSError(errno.ENOTDIR, self)

    def join(self, name: str) -> FSObject:
        """Return child node by name. Raises OSError for non-directories."""
        raise OSError(errno.ENOTDIR, self)

    def open(self) -> BinaryIO:
        """Open and return file-like object. Raises OSError for directories."""
        raise OSError(errno.EACCES, self)

    def getsize(self) -> int:
        """Return size in bytes."""
        return 0

    def is_dir(self) -> bool:
        """Return True if this is a directory."""
        return stat.S_ISDIR(self.kind)


class Dir(FSObject):
    """Virtual directory with in-memory entries.

    Entries is a dict mapping names to FSObject instances.
    """

    kind = stat.S_IFDIR

    def __init__(self, entries: dict[str, FSObject] | None = None):
        self.entries: dict[str, FSObject] = entries if entries is not None else {}

    def keys(self) -> list[str]:
        return sorted(self.entries.keys())

    def join(self, name: str) -> FSObject:
        try:
            return self.entries[name]
        except KeyError:
            raise OSError(errno.ENOENT, name) from None


class RealDir(Dir):
    """Directory backed by a real filesystem path.

    Provides controlled access to real directories with filtering options.
    """

    # If show_dotfiles=False, we pretend that all files whose name starts
    # with '.' simply don't exist.  If follow_links=True, then symlinks are
    # transparently followed (they look like a regular file or directory to
    # the sandboxed process).  If follow_links=False, the subprocess is
    # not allowed to access them at all.  Finally, exclude is a list of
    # file endings that we filter out (note that we also filter out files
    # with the same ending but a different case, to be safe).
    def __init__(self, path, show_dotfiles=False, follow_links=False, exclude=None):
        self.path = path
        self.show_dotfiles = show_dotfiles
        self.follow_links = follow_links
        self.exclude = [excl.lower() for excl in (exclude or [])]

    def __repr__(self):
        return f"<RealDir {self.path}>"

    def keys(self) -> list[str]:
        names = os.listdir(self.path)
        if not self.show_dotfiles:
            names = [name for name in names if not name.startswith(".")]
        for excl in self.exclude:
            names = [name for name in names if not name.lower().endswith(excl)]
        return sorted(names)

    def join(self, name: str) -> FSObject:
        if name.startswith(".") and not self.show_dotfiles:
            raise OSError(errno.ENOENT, name)
        for excl in self.exclude:
            if name.lower().endswith(excl):
                raise OSError(errno.ENOENT, name)
        path = os.path.join(self.path, name)
        if self.follow_links:
            st = os.stat(path)
        else:
            st = os.lstat(path)
        if stat.S_ISDIR(st.st_mode):
            return RealDir(
                path,
                show_dotfiles=self.show_dotfiles,
                follow_links=self.follow_links,
                exclude=self.exclude,
            )
        elif stat.S_ISREG(st.st_mode):
            return RealFile(path)
        else:
            # don't allow access to symlinks and other special files
            raise OSError(errno.EACCES, path)


class OverlayDir(RealDir):
    """RealDir with virtual file overrides.

    Files in the overrides dict take precedence over real files.
    Useful for injecting stubs into real directories.
    """

    def __init__(self, path, overrides=None, **kwargs):
        super().__init__(path, **kwargs)
        self.overrides = overrides or {}

    def __repr__(self):
        return f"<OverlayDir {self.path} (+{len(self.overrides)} overrides)>"

    def keys(self) -> list[str]:
        real_keys = set(super().keys())
        return sorted(real_keys | set(self.overrides.keys()))

    def join(self, name: str) -> FSObject:
        if name in self.overrides:
            return self.overrides[name]
        return super().join(name)


class File(FSObject):
    """Virtual file with in-memory content."""

    kind = stat.S_IFREG

    def __init__(self, data: bytes, mode: int = 0):
        self.data = data
        self.kind |= mode

    def getsize(self) -> int:
        return len(self.data)

    def open(self) -> BinaryIO:
        return BytesIO(self.data)


class RealFile(File):
    """File backed by a real filesystem path (read-only access)."""

    def __init__(self, path: str, mode: int = 0):
        self.path = path
        self.kind = stat.S_IFREG | mode

    def __repr__(self) -> str:
        return f"<RealFile {self.path}>"

    def getsize(self) -> int:
        return os.stat(self.path).st_size

    def open(self) -> BinaryIO:
        try:
            return open(self.path, "rb")
        except OSError as e:
            raise OSError(e.errno, "open failed") from e


class OpenDir:
    """Iterator state for an open directory (used by opendir/readdir)."""

    def __init__(self, node):
        self.node = node
        self.iter_names = iter(node.keys())

    def readdir(self):
        return next(self.iter_names)


def vfs_signature(sig, filearg=None):
    def decorate(func):
        @signature(sig)
        def wrapper(self, *args):
            try:
                return func(self, *args) or 0
            except OSError as e:
                err_code = e.errno if e.errno is not None else 0
                if self.debug_errors:
                    filename = ""
                    if filearg is not None:
                        filename = repr(self.vfs_fetch_path(args[filearg]))
                    err_name = errno.errorcode.get(err_code, f"Errno {err_code}")
                    msg = f"subprocess: vfs: {sig.split('(')[0]}({filename}) => {err_name}\n"
                    sys.stderr.write(msg)
                self.sandio.set_errno(err_code)
                if sig.endswith("i"):
                    return -1
                if sig.endswith("p"):
                    return NULL
                raise AssertionError(f"vfs_signature({sig!r}): should end in 'i' or 'p'") from e

        return wrapper

    return decorate


class MixVFS:
    """A virtual file system with optional write tracking.

    Call with 'vfs_root = root directory' in the constructor or by
    adding an attribute 'vfs_root' on the subclass directory.
    This should be a hierarchy built using the classes above.

    Write tracking:
        When vfs_track_writes is True, file writes are captured and
        queued in file_writes_pending for later approval instead of
        being executed immediately.
    """

    # The allowed 'fd' to return.  You might increase the range if your
    # subprocess needs more fd's.
    virtual_fd_range = range(3, 50)

    # This is the number of simultaneous open directories.  The value of 0
    # prevents opendir() from working at all, which is fine in some situations
    # (notably with pypy2-sandbox, but not with pypy3-sandbox).
    virtual_fd_directories = 20

    # Write tracking
    vfs_track_writes = False  # When True, queue writes for approval
    file_writes_pending = []  # List of PendingWrite objects

    def __init__(self, *args, **kwds):
        try:
            self.vfs_root = kwds.pop("vfs_root")
        except KeyError:
            if not hasattr(self, "vfs_root"):
                raise ValueError(
                    "must pass a vfs_root argument to the constructor, or assign "
                    "a vfs_root class attribute directory in the subclass"
                ) from None
        self.vfs_open_fds = {}
        self.vfs_open_dirs = {}
        self.vfs_write_buffers = {}  # fd -> (path, BytesIO, node) for write mode files
        super().__init__(*args, **kwds)

    s_mkdir = sigerror("mkdir(pi)i", errno.EPERM, -1)
    s_fcntl = sigerror("fcntl(iii)i", errno.ENOSYS, -1)
    s_unlink = sigerror("unlink(p)i", errno.EPERM, -1)

    @staticmethod
    def vfs_pypy_lib_directory(library_path, exclude=None):
        """Returns a Dir() instance that emulates the settings of a binary
        executable '.../pypy' and the standard library '.../lib-python' and
        '.../lib_pypy'.  This Dir() should be put inside the vfs_root
        somewhere, like under '/lib' for example, and then when you actually
        start the subprocess you give it args[0]=="/lib/pypy".
        (E.g. with subprocess.Popen you make sure args[0]=="/lib/pypy" but
        you specify a different executable="/real/path/to/pypy-sandbox".)

        'library_path' must be the real directory that contains the
        'lib-python' and 'lib_pypy' directories to use.

        Stubs from shannot.stubs are automatically injected into lib_pypy,
        overriding any real files with the same names.
        """
        if exclude is None:
            exclude = ["*.pyc", "*.pyo"]
        from shannot.stubs import get_stubs

        lib_python = os.path.join(library_path, "lib-python")
        lib_pypy = os.path.join(library_path, "lib_pypy")
        if not os.path.isdir(lib_python):
            raise OSError(f"directory not found: {lib_python!r}")
        if not os.path.isdir(lib_pypy):
            raise OSError(f"directory not found: {lib_pypy!r}")

        # Build stub overrides for lib_pypy
        stubs = {name: File(content) for name, content in get_stubs().items()}

        return Dir(
            {
                "pypy": File(b"", mode=0o111),
                "lib-python": RealDir(lib_python, exclude=exclude),
                "lib_pypy": OverlayDir(lib_pypy, overrides=stubs, exclude=exclude),
            }
        )

    def vfs_fetch_path(self, p_pathname):
        if isinstance(p_pathname, str):
            return p_pathname
        return self.sandio.read_charp(p_pathname, MAX_PATH).decode("utf-8")  # type: ignore[attr-defined]

    def vfs_getnode(self, p_pathname):
        path = self.vfs_fetch_path(p_pathname)
        all_components = [self.vfs_root]
        for name in path.split("/"):
            if name == "..":
                if len(all_components) > 1:
                    del all_components[-1]
            elif name and name != ".":
                all_components.append(all_components[-1].join(name))
        return all_components[-1]

    def vfs_write_stat(self, p_statbuf, node):
        stat_struct = node.stat()
        bytes_data = struct_to_bytes(stat_struct)
        self.sandio.write_buffer(p_statbuf, bytes_data)  # type: ignore[attr-defined]

    def vfs_allocate_fd(self, f, node):
        if node.is_dir():
            raise ValueError("cannot allocate fd for directory")
        for fd in self.virtual_fd_range:
            if fd not in self.vfs_open_fds:
                self.vfs_open_fds[fd] = (f, node)
                return fd
        else:
            raise OSError(errno.EMFILE, "trying to open too many files")

    def vfs_get_file(self, fd):
        """Return the open file for file descriptor `fd`."""
        try:
            return self.vfs_open_fds[fd][0]
        except KeyError:
            raise OSError(errno.EBADF, "bad file descriptor") from None

    def vfs_stat_for_pipe(self, p_statbuf):
        stat_struct = new_stat(
            st_ino=120,
            st_dev=12,
            st_nlink=1,
            st_mode=stat.S_IFIFO | stat.S_IRUSR | stat.S_IWUSR,
            st_uid=UID,
            st_gid=GID,
        )
        bytes_data = struct_to_bytes(stat_struct)
        self.sandio.write_buffer(p_statbuf, bytes_data)  # type: ignore[attr-defined]

    @vfs_signature("stat64(pp)i", filearg=0)
    def s_stat64(self, p_pathname, p_statbuf):
        node = self.vfs_getnode(p_pathname)
        self.vfs_write_stat(p_statbuf, node)

    @vfs_signature("lstat64(pp)i", filearg=0)
    def s_lstat64(self, p_pathname, p_statbuf):
        node = self.vfs_getnode(p_pathname)
        self.vfs_write_stat(p_statbuf, node)

    def vfs_stat_for_new_file(self, p_statbuf, size=0):
        """Write stat for a newly created file (node is None)."""
        stat_struct = new_stat(
            st_ino=200,
            st_dev=12,
            st_nlink=1,
            st_mode=stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR,
            st_uid=UID,
            st_gid=GID,
            st_size=size,
        )
        bytes_data = struct_to_bytes(stat_struct)
        self.sandio.write_buffer(p_statbuf, bytes_data)  # type: ignore[attr-defined]

    @vfs_signature("fstat64(ip)i")
    def s_fstat64(self, fd, p_statbuf):
        try:
            f, node = self.vfs_open_fds[fd]
        except KeyError:
            # Check write buffers for write-mode files
            if fd in self.vfs_write_buffers:
                path, write_buf, original, node = self.vfs_write_buffers[fd]
                if node is None:
                    # New file being created - use synthetic stat
                    self.vfs_stat_for_new_file(p_statbuf, write_buf.tell())
                else:
                    self.vfs_write_stat(p_statbuf, node)
                return
            if fd in (0, 1, 2):
                self.vfs_stat_for_pipe(p_statbuf)
                return
            raise OSError(errno.EBADF, "bad file descriptor") from None
        self.vfs_write_stat(p_statbuf, node)

    @vfs_signature("access(pi)i", filearg=0)
    def s_access(self, p_pathname, mode):
        node = self.vfs_getnode(p_pathname)
        if not node.access(mode):
            raise OSError(errno.EACCES, node)

    @vfs_signature("open(pii)i", filearg=0)
    def s_open(self, p_pathname, flags, mode):
        path = self.vfs_fetch_path(p_pathname)
        write_mode = flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR) != os.O_RDONLY
        create_mode = flags & os.O_CREAT

        # Handle write mode with tracking
        if write_mode:
            if not self.vfs_track_writes:
                raise OSError(errno.EPERM, "write mode not enabled")

            # Get original content if file exists
            original = None
            try:
                node = self.vfs_getnode(p_pathname)
                if not node.is_dir():
                    try:
                        f = node.open()
                        original = f.read()
                        f.close()
                    except OSError:
                        pass
            except OSError:
                if not create_mode:
                    raise
                node = None

            # Create write buffer
            write_buf = BytesIO()
            fd = self._vfs_allocate_write_fd(path, write_buf, original, node)
            return fd

        # Read-only mode
        node = self.vfs_getnode(p_pathname)
        if not node.access(os.R_OK):
            raise OSError(errno.EACCES, node)
        f = node.open()
        return self.vfs_allocate_fd(f, node)

    def _vfs_allocate_write_fd(self, path, write_buf, original, node):
        """Allocate fd for write mode file."""
        for fd in self.virtual_fd_range:
            if fd not in self.vfs_open_fds and fd not in self.vfs_write_buffers:
                self.vfs_write_buffers[fd] = (path, write_buf, original, node)
                return fd
        raise OSError(errno.EMFILE, "trying to open too many files")

    @vfs_signature("close(i)i")
    def s_close(self, fd):
        # Check if this is a write buffer
        if fd in self.vfs_write_buffers:
            path, write_buf, original, node = self.vfs_write_buffers[fd]
            del self.vfs_write_buffers[fd]

            # Create PendingWrite and queue it
            content = write_buf.getvalue()
            if content or original:  # Only queue if there's actual content
                # Enforce size limit
                if len(content) > MAX_WRITE_SIZE:
                    sys.stderr.write(
                        f"[BLOCKED] Write exceeds 50MB limit: {path} ({len(content)} bytes)\n"
                    )
                    return

                from .pending_write import PendingWrite

                # Check if it's a remote file
                is_remote = hasattr(node, "remote_path") if node else False

                # Compute hash of original content for conflict detection
                # First check VFS original, then fall back to real filesystem
                original_hash = None
                if original is not None:
                    original_hash = hashlib.sha256(original).hexdigest()
                elif not is_remote:
                    # VFS didn't have file, check if real file exists
                    # This handles case where /tmp is virtual but real file exists
                    try:
                        real_path = Path(path)
                        if real_path.exists():
                            original_hash = hashlib.sha256(real_path.read_bytes()).hexdigest()
                    except (OSError, PermissionError):
                        pass  # Can't read real file, no conflict detection

                pending = PendingWrite(
                    path=path,
                    content=content,
                    original=original,
                    remote=is_remote,
                    original_hash=original_hash,
                )
                self.file_writes_pending.append(pending)
                # Only show message during dry-run (execution summary shows writes)
                if getattr(self, "subprocess_dry_run", False):
                    sys.stderr.write(f"[DRY-RUN] {path} ({len(content)} bytes)\n")

                # Audit log file write queueing
                from .audit import log_file_write_queued

                remote_target = getattr(self, "remote_target", None)
                log_file_write_queued(
                    session_id=None,  # Session not yet created
                    path=path,
                    size_bytes=len(content),
                    is_new_file=(original is None),
                    remote=is_remote,
                    target=remote_target,
                )
            return

        # Regular file close
        f = self.vfs_get_file(fd)
        del self.vfs_open_fds[fd]
        f.close()

    @vfs_signature("write(ipi)i")
    def s_write(self, fd, p_buf, count):
        # Check if this is a write buffer
        if fd in self.vfs_write_buffers:
            path, write_buf, original, node = self.vfs_write_buffers[fd]
            if count < 0:
                count = 0
            data = self.sandio.read_buffer(p_buf, min(count, MAX_WRITE_CHUNK))  # type: ignore[attr-defined]
            write_buf.write(data)
            return len(data)

        # Delegate stdout/stderr to parent
        return super().s_write(fd, p_buf, count)  # type: ignore[misc]

    @vfs_signature("read(ipi)i")
    def s_read(self, fd, p_buf, count):
        # Check if this is a write buffer (for read/write mode)
        if fd in self.vfs_write_buffers:
            path, write_buf, original, node = self.vfs_write_buffers[fd]
            if count < 0:
                count = 0
            data = write_buf.read(min(count, MAX_WRITE_CHUNK))
            self.sandio.write_buffer(p_buf, data)  # type: ignore[attr-defined]
            return len(data)

        try:
            f = self.vfs_get_file(fd)
        except OSError:
            return super().s_read(fd, p_buf, count)  # type: ignore[misc]
        if count < 0:
            count = 0
        # don't try to read more than MAX_WRITE_CHUNK at once here
        data = f.read(min(count, MAX_WRITE_CHUNK))
        self.sandio.write_buffer(p_buf, data)  # type: ignore[attr-defined]
        return len(data)

    @vfs_signature("lseek(iii)i")
    def s_lseek(self, fd, offset, whence):
        if whence not in (0, 1, 2):
            raise OSError(errno.EINVAL, "bad value for lseek(whence)")
        if fd in (0, 1, 2):
            raise OSError(errno.ESPIPE, "seeking on stdin/stdout/stderr")

        # Check if this is a write buffer
        if fd in self.vfs_write_buffers:
            path, write_buf, original, node = self.vfs_write_buffers[fd]
            write_buf.seek(offset, whence)
            return write_buf.tell()

        f = self.vfs_get_file(fd)
        f.seek(offset, whence)
        return f.tell()

    @vfs_signature("opendir(p)p", filearg=0)
    def s_opendir(self, p_name):
        # we pretend that "DIR *" pointers are actually implemented as
        # "struct dirent *", where we store the result of each readdir()
        if len(self.vfs_open_dirs) >= self.virtual_fd_directories:
            if self.virtual_fd_directories == 0:
                raise OSError(errno.EPERM, "opendir() not allowed")
            raise OSError(errno.EMFILE, "trying to open too many directories")
        node = self.vfs_getnode(p_name)
        fdir = OpenDir(node)
        p = self.sandio.malloc(b"\x00" * SIZEOF_DIRENT)  # type: ignore[attr-defined]
        self.vfs_open_dirs[p.addr] = fdir
        return p

    @vfs_signature("readdir(p)p")
    def s_readdir(self, p_dir):
        fdir = self.vfs_open_dirs[p_dir.addr]
        while True:
            try:
                name = fdir.readdir()
            except StopIteration:
                return NULL
            try:
                subnode = fdir.node.join(name)
                st = subnode.stat()
            except OSError:
                continue
            break
        dirent = new_dirent()
        dirent.d_ino = st.st_ino
        dirent.d_reclen = SIZEOF_DIRENT
        dirent.d_type = DT_DIR if subnode.is_dir() else DT_REG
        name = name.encode("utf-8")
        if len(name) > 255:  # d_name is 256 bytes including null terminator
            raise OSError(errno.EOVERFLOW, subnode)
        dirent.d_name = name
        bytes_data = struct_to_bytes(dirent)
        self.sandio.write_buffer(p_dir, bytes_data)  # type: ignore[attr-defined]
        return p_dir

    @vfs_signature("closedir(p)i")
    def s_closedir(self, p_dir):
        del self.vfs_open_dirs[p_dir.addr]
        self.sandio.free(p_dir)  # type: ignore[attr-defined]
