"""Unit tests for the virtual filesystem module."""

import errno
import os
import shutil
import tempfile

import pytest

from shannot.mix_vfs import Dir, File, MixVFS, OverlayDir, RealDir, RealFile


class TestDir:
    """Tests for in-memory Dir class."""

    def test_empty_dir(self):
        d = Dir({})
        assert d.keys() == []
        assert d.is_dir()

    def test_dir_with_entries(self):
        d = Dir({"a": File(b"content"), "b": Dir({})})
        assert d.keys() == ["a", "b"]

    def test_join_existing(self):
        child = File(b"test")
        d = Dir({"child": child})
        assert d.join("child") is child

    def test_join_missing(self):
        d = Dir({})
        with pytest.raises(OSError) as exc:
            d.join("missing")
        assert exc.value.errno == errno.ENOENT


class TestFile:
    """Tests for in-memory File class."""

    def test_file_content(self):
        f = File(b"hello world")
        assert f.getsize() == 11
        assert not f.is_dir()

    def test_file_open(self):
        f = File(b"hello world")
        fobj = f.open()
        assert fobj.read() == b"hello world"


class TestPathTraversal:
    """Tests for path traversal prevention in VFS."""

    def test_basic_path(self):
        """Normal path navigation works."""
        root = Dir({"home": Dir({"user": Dir({"file.txt": File(b"content")})})})

        class TestVFS(MixVFS):
            vfs_root = root

        # Create minimal mock for sandio
        vfs = TestVFS.__new__(TestVFS)
        vfs.vfs_root = root
        vfs.vfs_open_fds = {}
        vfs.vfs_open_dirs = {}
        vfs.vfs_write_buffers = {}

        node = vfs.vfs_getnode("/home/user/file.txt")
        assert isinstance(node, File)

    def test_dotdot_at_root(self):
        """.. at root stays at root."""
        root = Dir({"home": Dir({})})

        class TestVFS(MixVFS):
            vfs_root = root

        vfs = TestVFS.__new__(TestVFS)
        vfs.vfs_root = root
        vfs.vfs_open_fds = {}
        vfs.vfs_open_dirs = {}
        vfs.vfs_write_buffers = {}

        # Multiple .. at root should stay at root
        node = vfs.vfs_getnode("/../../../")
        assert node is root

    def test_dotdot_escape_attempt(self):
        """.. cannot escape the virtual root."""
        root = Dir({"safe": Dir({"file.txt": File(b"safe content")})})

        class TestVFS(MixVFS):
            vfs_root = root

        vfs = TestVFS.__new__(TestVFS)
        vfs.vfs_root = root
        vfs.vfs_open_fds = {}
        vfs.vfs_open_dirs = {}
        vfs.vfs_write_buffers = {}

        # Try to escape with .. - should get ENOENT for 'etc' since we're still at root
        # (.. at root stays at root, so /safe/../../../etc becomes /etc which doesn't exist)
        with pytest.raises(OSError) as exc:
            vfs.vfs_getnode("/safe/../../../etc/passwd")
        assert exc.value.errno == errno.ENOENT

    def test_dot_ignored(self):
        """Single . is ignored in path."""
        child = File(b"content")
        root = Dir({"child": child})

        class TestVFS(MixVFS):
            vfs_root = root

        vfs = TestVFS.__new__(TestVFS)
        vfs.vfs_root = root
        vfs.vfs_open_fds = {}
        vfs.vfs_open_dirs = {}
        vfs.vfs_write_buffers = {}

        node = vfs.vfs_getnode("/./child/.")
        assert node is child

    def test_double_slash(self):
        """Double slashes are handled."""
        child = File(b"content")
        root = Dir({"child": child})

        class TestVFS(MixVFS):
            vfs_root = root

        vfs = TestVFS.__new__(TestVFS)
        vfs.vfs_root = root
        vfs.vfs_open_fds = {}
        vfs.vfs_open_dirs = {}
        vfs.vfs_write_buffers = {}

        node = vfs.vfs_getnode("//child")
        assert node is child


class TestRealDir:
    """Tests for RealDir backed by filesystem."""

    def setup_method(self):
        """Create a temporary directory for tests."""
        self.tmpdir = tempfile.mkdtemp()
        # Create test files
        os.makedirs(os.path.join(self.tmpdir, "subdir"))
        with open(os.path.join(self.tmpdir, "file.txt"), "w") as f:
            f.write("content")
        with open(os.path.join(self.tmpdir, ".hidden"), "w") as f:
            f.write("hidden")
        with open(os.path.join(self.tmpdir, "skip.pyc"), "w") as f:
            f.write("compiled")

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir)

    def test_keys_hides_dotfiles_by_default(self):
        """Dotfiles are hidden by default."""
        d = RealDir(self.tmpdir)
        keys = d.keys()
        assert "file.txt" in keys
        assert ".hidden" not in keys

    def test_keys_shows_dotfiles_when_enabled(self):
        """Dotfiles shown when show_dotfiles=True."""
        d = RealDir(self.tmpdir, show_dotfiles=True)
        keys = d.keys()
        assert ".hidden" in keys

    def test_join_hidden_file_blocked(self):
        """Cannot join to hidden file when dotfiles disabled."""
        d = RealDir(self.tmpdir)
        with pytest.raises(OSError) as exc:
            d.join(".hidden")
        assert exc.value.errno == errno.ENOENT

    def test_exclude_filter(self):
        """Exclude patterns filter files."""
        d = RealDir(self.tmpdir, exclude=[".pyc"])
        keys = d.keys()
        assert "file.txt" in keys
        assert "skip.pyc" not in keys

    def test_join_to_subdir(self):
        """Joining to subdirectory returns RealDir."""
        d = RealDir(self.tmpdir)
        child = d.join("subdir")
        assert isinstance(child, RealDir)

    def test_join_to_file(self):
        """Joining to file returns RealFile."""
        d = RealDir(self.tmpdir)
        child = d.join("file.txt")
        assert isinstance(child, RealFile)


class TestOverlayDir:
    """Tests for OverlayDir with virtual overrides."""

    def setup_method(self):
        """Create a temporary directory for tests."""
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "real.txt"), "w") as f:
            f.write("real content")

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.tmpdir)

    def test_override_takes_precedence(self):
        """Virtual override takes precedence over real file."""
        override = File(b"overridden")
        d = OverlayDir(self.tmpdir, overrides={"real.txt": override})
        assert d.join("real.txt") is override

    def test_keys_includes_both(self):
        """Keys include both real and override files."""
        d = OverlayDir(self.tmpdir, overrides={"virtual.txt": File(b"")})
        keys = d.keys()
        assert "real.txt" in keys
        assert "virtual.txt" in keys


class TestFSObjectAccess:
    """Tests for file access permission checks."""

    def test_read_only_owned_by_root(self):
        """Read-only files appear owned by root."""
        f = File(b"content")
        f.read_only = True
        st = f.stat()
        assert st.st_uid == 0
        assert st.st_gid == 0

    def test_writable_owned_by_user(self):
        """Writable files appear owned by virtual user."""
        f = File(b"content")
        f.read_only = False
        st = f.stat()
        assert st.st_uid == 1000  # UID constant
        assert st.st_gid == 1000  # GID constant
