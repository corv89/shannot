import os
import sys

from .virtualizedproc import signature


class MixAcceptInput:
    input_stdin = None  # means use sys.stdin

    @signature("read(ipi)i")
    def s_read(self, fd, p_buf, count):
        if fd != 0:
            return super().s_read(fd, p_buf, count)

        if count < 0:
            raise ValueError("count must be non-negative")
        f = self.input_stdin or sys.stdin
        fileno = f.fileno()  # for now, must be a real file
        data = os.read(fileno, count)
        if len(data) > count:
            raise RuntimeError("os.read returned more data than requested")
        self.sandio.write_buffer(p_buf, data)
        return len(data)
