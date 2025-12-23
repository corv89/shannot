"""Tests for ctypes struct definitions."""

from shannot.structs import (
    ARCH,
    DT_DIR,
    DT_REG,
    IS_LINUX,
    SIZEOF_DIRENT,
    SIZEOF_STAT,
    SIZEOF_TIMEVAL,
    new_dirent,
    new_stat,
    new_timeval,
    pack_gid_t,
    pack_time_t,
    pack_uid_t,
    struct_to_bytes,
)


def test_stat_size():
    """Verify struct stat has expected size for platform."""
    if IS_LINUX and ARCH == "aarch64":
        assert SIZEOF_STAT == 128, f"Expected 128, got {SIZEOF_STAT}"
    elif IS_LINUX and ARCH == "x86_64":
        assert SIZEOF_STAT == 144, f"Expected 144, got {SIZEOF_STAT}"


def test_dirent_size():
    """Verify struct dirent has expected size."""
    if IS_LINUX:
        assert SIZEOF_DIRENT == 280, f"Expected 280, got {SIZEOF_DIRENT}"


def test_timeval_size():
    """Verify struct timeval has expected size."""
    assert SIZEOF_TIMEVAL == 16, f"Expected 16, got {SIZEOF_TIMEVAL}"


def test_stat_roundtrip():
    """Test creating and converting stat struct."""
    s = new_stat(
        st_ino=12345,
        st_dev=1,
        st_nlink=1,
        st_size=4096,
        st_mode=0o644,
        st_uid=1000,
        st_gid=1000,
    )
    assert s.st_ino == 12345
    assert s.st_size == 4096
    assert s.st_uid == 1000

    data = struct_to_bytes(s)
    assert len(data) == SIZEOF_STAT


def test_dirent_roundtrip():
    """Test creating and converting dirent struct."""
    d = new_dirent()
    d.d_ino = 12345
    d.d_type = DT_REG
    d.d_reclen = SIZEOF_DIRENT

    data = struct_to_bytes(d)
    assert len(data) == SIZEOF_DIRENT


def test_timeval_pack():
    """Test timeval struct packing."""
    tv = new_timeval(1234567890, 123456)
    assert tv.tv_sec == 1234567890
    assert tv.tv_usec == 123456

    data = struct_to_bytes(tv)
    assert len(data) == 16


def test_pack_time_t():
    """Test time_t packing."""
    data = pack_time_t(1234567890)
    assert len(data) == 8


def test_pack_uid_t():
    """Test uid_t packing."""
    data = pack_uid_t(1000)
    assert len(data) == 4


def test_pack_gid_t():
    """Test gid_t packing."""
    data = pack_gid_t(1000)
    assert len(data) == 4


def test_constants():
    """Test dirent type constants."""
    assert DT_REG == 8
    assert DT_DIR == 4
