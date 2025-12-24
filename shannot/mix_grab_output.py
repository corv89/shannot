from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from .virtualizedproc import signature

if TYPE_CHECKING:
    from ._protocols import HasSandio


class MixGrabOutput:
    def __init__(self, *args, **kwds):
        self._write_buffer = BytesIO()
        self._write_buffer_limit = kwds.pop("write_buffer_limit", 1000000)
        super().__init__(*args, **kwds)

    @signature("write(ipi)i")
    def s_write(self: HasSandio, fd, p_buf, count):
        """Writes to stdout or stderr are copied to an internal buffer."""

        if fd != 1 and fd != 2:
            return super().s_write(fd, p_buf, count)  # type: ignore[misc]

        data = self.sandio.read_buffer(p_buf, count)
        if self._write_buffer.tell() + len(data) > self._write_buffer_limit:  # type: ignore[attr-defined]
            raise Exception("subprocess is writing too much data on stdout/stderr")
        self._write_buffer.write(data)  # type: ignore[attr-defined]
        return count

    def get_all_output(self):
        return self._write_buffer.getvalue()
