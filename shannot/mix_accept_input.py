from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from .virtualizedproc import signature

if TYPE_CHECKING:
    from ._protocols import HasSandio


class MixAcceptInput:
    input_stdin = None  # means use sys.stdin

    @signature("read(ipi)i")
    def s_read(self: HasSandio, fd, p_buf, count):
        if fd != 0:
            return super().s_read(fd, p_buf, count)  # type: ignore[misc]

        if count < 0:
            raise ValueError("count must be non-negative")
        f = self.input_stdin or sys.stdin  # type: ignore[attr-defined]
        fileno = f.fileno()  # for now, must be a real file
        data = os.read(fileno, count)
        if len(data) > count:
            raise RuntimeError("os.read returned more data than requested")
        self.sandio.write_buffer(p_buf, data)
        return len(data)
