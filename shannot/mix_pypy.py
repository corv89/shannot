from __future__ import annotations

from typing import TYPE_CHECKING

from .virtualizedproc import signature

if TYPE_CHECKING:
    from ._protocols import HasSandio


class MixPyPy:
    @signature("_pypy_init_home()p")
    def s__pypy_init_home(self: HasSandio):
        return self.sandio.malloc(b"/lib\x00")  # was "/pypy"

    @signature("_pypy_init_free(p)v")
    def s__pypy_init_free(self: HasSandio, ptr):
        # could call self.sandio.free(ptr), but not really important
        return None
