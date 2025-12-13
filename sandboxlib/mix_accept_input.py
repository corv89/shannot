import sys
import os
from .virtualizedproc import signature


class MixAcceptInput(object):
    input_stdin = None    # means use sys.stdin

    @signature("read(ipi)i")
    def s_read(self, fd, p_buf, count):
        if fd != 0:
            return super(MixAcceptInput, self).s_read(fd, p_buf, count)

        assert count >= 0
        f = self.input_stdin or sys.stdin
        fileno = f.fileno()     # for now, must be a real file
        data = os.read(fileno, count)
        assert len(data) <= count
        self.sandio.write_buffer(p_buf, data)
        return len(data)
