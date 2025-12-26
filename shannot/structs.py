"""C struct definitions using ctypes (stdlib only).

Platform and architecture-specific struct layouts for IPC with the
PyPy sandbox subprocess.
"""

from __future__ import annotations

import platform
import sys
from ctypes import (
    Structure,
    c_char,
    c_int,
    c_long,
    c_longlong,
    c_ubyte,
    c_uint,
    c_ulong,
    c_ushort,
    sizeof,
)
from typing import TYPE_CHECKING

ARCH = platform.machine()
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# Constants (from dirent.h)
DT_REG = 8  # Regular file
DT_DIR = 4  # Directory


# struct timespec (used in stat on Linux)
class Timespec(Structure):
    _fields_ = [
        ("tv_sec", c_long),
        ("tv_nsec", c_long),
    ]


# Platform-specific struct dirent and stat
# Use TYPE_CHECKING to provide a single definition for type checkers
# while keeping runtime platform-specific definitions
if TYPE_CHECKING:
    from typing import ClassVar

    # Type-checking definition (using Linux x86_64 layout as canonical)
    class Dirent(Structure):
        _fields_: ClassVar[list[tuple[str, type]]]  # type: ignore[misc]
        d_ino: int
        d_off: int
        d_reclen: int
        d_type: int
        d_name: bytes

    class Stat(Structure):
        _fields_: ClassVar[list[tuple[str, type]]]  # type: ignore[misc]
        st_dev: int
        st_ino: int
        st_nlink: int
        st_mode: int
        st_uid: int
        st_gid: int
        st_rdev: int
        st_size: int
        st_blksize: int
        st_blocks: int

elif IS_MACOS:

    class Dirent(Structure):
        _fields_ = [
            ("d_ino", c_ulong),  # 8 bytes
            ("d_reclen", c_ushort),  # 2 bytes
            ("d_type", c_ubyte),  # 1 byte
            ("d_namlen", c_ubyte),  # 1 byte
            ("d_name", c_char * 256),  # 256 bytes
        ]

    # macOS stat64 structure
    class Stat(Structure):
        _fields_ = [
            ("st_dev", c_int),
            ("st_mode", c_ushort),
            ("st_nlink", c_ushort),
            ("st_ino", c_ulong),
            ("st_uid", c_uint),
            ("st_gid", c_uint),
            ("st_rdev", c_int),
            ("st_atimespec", Timespec),
            ("st_mtimespec", Timespec),
            ("st_ctimespec", Timespec),
            ("st_birthtimespec", Timespec),
            ("st_size", c_longlong),
            ("st_blocks", c_longlong),
            ("st_blksize", c_int),
            ("st_flags", c_uint),
            ("st_gen", c_uint),
            ("st_lspare", c_int),
            ("st_qspare", c_longlong * 2),
        ]

elif IS_LINUX and ARCH == "aarch64":

    class Dirent(Structure):
        _fields_ = [
            ("d_ino", c_ulong),  # 8 bytes
            ("d_off", c_ulong),  # 8 bytes
            ("d_reclen", c_ushort),  # 2 bytes
            ("d_type", c_ubyte),  # 1 byte
            ("d_name", c_char * 256),  # 256 bytes (+ 5 bytes padding)
        ]

    # Linux aarch64 - verified on Ubuntu 20.04 arm64 (128 bytes)
    class Stat(Structure):
        _fields_ = [
            ("st_dev", c_ulong),  # 8
            ("st_ino", c_ulong),  # 8
            ("st_mode", c_uint),  # 4
            ("st_nlink", c_uint),  # 4
            ("st_uid", c_uint),  # 4
            ("st_gid", c_uint),  # 4
            ("st_rdev", c_ulong),  # 8
            ("__pad1", c_ulong),  # 8
            ("st_size", c_long),  # 8
            ("st_blksize", c_int),  # 4
            ("__pad2", c_int),  # 4
            ("st_blocks", c_long),  # 8
            ("st_atime", c_long),  # 8
            ("st_atime_nsec", c_long),  # 8
            ("st_mtime", c_long),  # 8
            ("st_mtime_nsec", c_long),  # 8
            ("st_ctime", c_long),  # 8
            ("st_ctime_nsec", c_long),  # 8
            ("__unused", c_uint * 2),  # 8
        ]  # Total: 128 bytes

elif IS_LINUX and ARCH == "x86_64":

    class Dirent(Structure):
        _fields_ = [
            ("d_ino", c_ulong),  # 8 bytes
            ("d_off", c_ulong),  # 8 bytes
            ("d_reclen", c_ushort),  # 2 bytes
            ("d_type", c_ubyte),  # 1 byte
            ("d_name", c_char * 256),  # 256 bytes (+ 5 bytes padding)
        ]

    # Linux x86_64 (144 bytes)
    class Stat(Structure):
        _fields_ = [
            ("st_dev", c_ulong),  # 8 bytes
            ("st_ino", c_ulong),  # 8 bytes
            ("st_nlink", c_ulong),  # 8 bytes
            ("st_mode", c_uint),  # 4 bytes
            ("st_uid", c_uint),  # 4 bytes
            ("st_gid", c_uint),  # 4 bytes
            ("_pad0", c_int),  # 4 bytes padding
            ("st_rdev", c_ulong),  # 8 bytes
            ("st_size", c_long),  # 8 bytes
            ("st_blksize", c_long),  # 8 bytes
            ("st_blocks", c_long),  # 8 bytes
            ("st_atim", Timespec),  # 16 bytes
            ("st_mtim", Timespec),  # 16 bytes
            ("st_ctim", Timespec),  # 16 bytes
            ("_reserved", c_long * 3),  # 24 bytes
        ]  # Total: 144 bytes

else:
    raise NotImplementedError(f"Unsupported platform: {sys.platform}/{ARCH}")


# struct timeval
class Timeval(Structure):
    _fields_ = [
        ("tv_sec", c_long),
        ("tv_usec", c_long),
    ]


# Size constants
SIZEOF_DIRENT = sizeof(Dirent)
SIZEOF_STAT = sizeof(Stat)
SIZEOF_TIMEVAL = sizeof(Timeval)


def new_stat(**kwargs) -> Stat:
    """Create and return a Stat struct with given fields."""
    s = Stat()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def new_dirent() -> Dirent:
    """Create an empty Dirent struct."""
    return Dirent()


def new_timeval(sec: int, usec: int) -> Timeval:
    """Create a Timeval struct."""
    return Timeval(tv_sec=sec, tv_usec=usec)


# struct utsname (from sys/utsname.h)
# Linux uses 65-byte fields (including null terminator)
class Utsname(Structure):
    _fields_ = [
        ("sysname", c_char * 65),  # e.g., "Linux"
        ("nodename", c_char * 65),  # hostname
        ("release", c_char * 65),  # e.g., "5.10.0"
        ("version", c_char * 65),  # e.g., "#1 SMP"
        ("machine", c_char * 65),  # e.g., "x86_64"
        ("domainname", c_char * 65),  # GNU extension
    ]


SIZEOF_UTSNAME = sizeof(Utsname)


def new_utsname(
    sysname: bytes = b"Linux",
    nodename: bytes = b"sandbox",
    release: bytes = b"5.10.0",
    version: bytes = b"#1 SMP",
    machine: bytes = b"x86_64",
    domainname: bytes = b"",
) -> Utsname:
    """Create a Utsname struct with given fields."""
    return Utsname(
        sysname=sysname,
        nodename=nodename,
        release=release,
        version=version,
        machine=machine,
        domainname=domainname,
    )


def struct_to_bytes(s: Structure) -> bytes:
    """Convert any ctypes Structure to bytes."""
    return bytes(s)


def pack_time_t(t: int) -> bytes:
    """Pack a time_t value (8 bytes)."""
    return c_long(t).value.to_bytes(8, sys.byteorder, signed=True)


def pack_uid_t(uid: int) -> bytes:
    """Pack a uid_t value (4 bytes)."""
    return c_uint(uid).value.to_bytes(4, sys.byteorder, signed=False)


def pack_gid_t(gid: int) -> bytes:
    """Pack a gid_t value (4 bytes)."""
    return c_uint(gid).value.to_bytes(4, sys.byteorder, signed=False)


# Runtime validation of struct sizes
_EXPECTED_SIZES = {
    ("linux", "aarch64"): {"stat": 128, "dirent": 280, "timeval": 16},
    ("linux", "x86_64"): {"stat": 144, "dirent": 280, "timeval": 16},
    # macOS sizes TBD
}


def _validate():
    import warnings

    key = ("linux" if IS_LINUX else sys.platform, ARCH)
    if key not in _EXPECTED_SIZES:
        warnings.warn(
            f"Struct sizes unverified for {sys.platform}/{ARCH}. "
            "Local sandbox may behave incorrectly. "
            "Use --target for verified remote execution.",
            RuntimeWarning,
            stacklevel=2,
        )
        return
    expected = _EXPECTED_SIZES[key]
    actual_stat = sizeof(Stat)
    actual_dirent = sizeof(Dirent)
    assert actual_stat == expected["stat"], (
        f"stat: got {actual_stat}, expected {expected['stat']} on {key}"
    )
    assert actual_dirent == expected["dirent"], (
        f"dirent: got {actual_dirent}, expected {expected['dirent']} on {key}"
    )


_validate()
