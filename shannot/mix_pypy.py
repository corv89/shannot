from .virtualizedproc import signature


class MixPyPy(object):

    @signature("_pypy_init_home()p")
    def s__pypy_init_home(self):
        return self.sandio.malloc(b"/pypy\x00")

    @signature("_pypy_init_free(p)v")
    def s__pypy_init_free(self, ptr):
        # could call self.sandio.free(ptr), but not really important
        return None
