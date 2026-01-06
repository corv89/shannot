from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .virtualizedproc import signature

if TYPE_CHECKING:
    from ._protocols import HasSandio


class MixDumpOutput:
    """Sanitize and dump all output, sent to stdout or stderr, to the
    real stdout and stderr.  Replaces control characters (except newline,
    tab, carriage return) with '?'.  Unicode characters are preserved.
    May output ANSI color codes to distinguish sandbox output."""

    dump_stdout_fmt = "{0}"
    dump_stderr_fmt = "{0}"
    dump_stdout = None  # means use sys.stdout
    dump_stderr = None  # means use sys.stderr
    raw_stdout = False
    raw_stderr = False

    @staticmethod
    def dump_get_ansi_color_fmt(color_number):
        return f"\x1b[{color_number}m{{0}}\x1b[0m"

    def dump_sanitize(self, data):
        # Decode as UTF-8, replacing invalid sequences
        data = data.decode("utf-8", errors="replace")
        # Filter out control characters except newline, tab, carriage return
        lst = []
        for c in data:
            if c >= " " or c in "\n\t\r":
                lst.append(c)
            else:
                lst.append("?")
        return "".join(lst)

    @signature("write(ipi)i")
    def s_write(self: HasSandio, fd, p_buf, count):
        if fd == 1:
            f = self.dump_stdout or sys.stdout  # type: ignore[attr-defined]
            fmt = self.dump_stdout_fmt  # type: ignore[attr-defined]
            raw = self.raw_stdout  # type: ignore[attr-defined]
        elif fd == 2:
            f = self.dump_stderr or sys.stderr  # type: ignore[attr-defined]
            fmt = self.dump_stderr_fmt  # type: ignore[attr-defined]
            raw = self.raw_stderr  # type: ignore[attr-defined]
        else:
            return super().s_write(fd, p_buf, count)  # type: ignore[misc]

        data = self.sandio.read_buffer(p_buf, count)
        if not raw:
            data = fmt.format(self.dump_sanitize(data))  # type: ignore[attr-defined]
        f.write(data)
        f.flush()
        return count
