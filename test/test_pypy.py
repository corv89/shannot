import os

import pytest

from shannot import VirtualizedProc
from shannot.mix_grab_output import MixGrabOutput
from shannot.mix_pypy import MixPyPy
from shannot.mix_vfs import Dir, MixVFS

from . import support


class TestVirtualizedProc(support.BaseTest):
    @classmethod
    def setup_class(cls):
        cls.pypy_c_sandbox = os.path.join(os.path.dirname(__file__), "pypy-sandbox")
        if not os.path.exists(cls.pypy_c_sandbox):
            pytest.skip("make a symlink 'pypy-sandbox'")

        searchdir = os.path.realpath(cls.pypy_c_sandbox)
        while True:
            search1 = os.path.dirname(searchdir)
            assert len(search1) < len(searchdir)
            searchdir = search1
            lib_python = os.path.join(searchdir, "lib-python")
            lib_pypy = os.path.join(searchdir, "lib_pypy")
            if os.path.isdir(lib_python) and os.path.isdir(lib_pypy):
                break

        class PyPyProc(MixPyPy, MixVFS, MixGrabOutput, VirtualizedProc):
            debug_errors = True

            virtual_cwd = "/tmp"

            vfs_root = Dir(
                {
                    "bin": MixVFS.vfs_pypy_lib_directory(searchdir),
                    "tmp": Dir({}),
                }
            )

        cls.vproccls = PyPyProc

    def test_check_dump(self):
        vp = self.execute(["/tmp/pypy"], env={"RPY_SANDBOX_DUMP": "1"})
        assert self.popen.stdout is not None
        errors = vp.check_dump(self.popen.stdout.read())
        for error in errors:
            print(error)
        assert not errors

    def test_starts(self):
        vp = self.execute(["/bin/pypy", "-S", "-c", "pass"])
        vp.run()
        self.close()

    def test_prints_42(self):
        vp = self.execute(["/bin/pypy", "-S", "-c", "print(6*7)"])
        vp.run()
        out = self.close()
        assert out is not None and out.endswith("42\n")

    def test_listdir_forbidden(self):
        vp = self.execute(["/bin/pypy", "-S", "-c", 'import os; os.listdir("/")'])
        self.virtualizedproc.virtual_fd_directories = 0  # type: ignore[misc]
        vp.run()
        out = self.close(expected_exitcode=1)
        assert out is not None
        assert (
            "Operation not permitted:" in out  # pypy2
            or "No module named 'encodings'" in out
        )  # pypy3

    def test_listdir(self):
        vp = self.execute(["/bin/pypy", "-S", "-c", 'import os; print(os.listdir("/"))'])
        self.virtualizedproc.virtual_fd_directories = 20  # type: ignore[misc]
        vp.run()
        out = self.close()
        assert out is not None and out.endswith("['bin', 'tmp']\n")

    def test_regexp(self):
        vp = self.execute(
            [
                "/bin/pypy",
                "-S",
                "-c",
                'import re; print(re.search(r"a(.+)b", "caadsjsatfbsss").group(1))',
            ]
        )
        vp.run()
        out = self.close()
        assert out is not None and out.endswith("adsjsatf\n")
