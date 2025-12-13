import sys
from .virtualizedproc import signature


class MixDumpOutput(object):
    """Sanitize and dump all output, sent to stdout or stderr, to the
    real stdout and stderr.  For now replaces any non-ASCII character with
    '?'.  It may also output ANSI color codes to make it obvious that it's
    coming from the sandboxed process."""

    dump_stdout_fmt = "{0}"
    dump_stderr_fmt = "{0}"
    dump_stdout = None    # means use sys.stdout
    dump_stderr = None    # means use sys.stderr
    raw_stdout = False
    raw_stderr = False

    @staticmethod
    def dump_get_ansi_color_fmt(color_number):
        return '\x1b[%dm{0}\x1b[0m' % (color_number,)

    def dump_sanitize(self, data):
        data = data.decode('latin1')  # string => unicode, on top of python 3
        lst = []
        for c in data:
            if not (' ' <= c < '\x7f' or c == '\n'):
                c = '?'
            lst.append(c)
        return ''.join(lst)


    @signature("write(ipi)i")
    def s_write(self, fd, p_buf, count):
        if fd == 1:
            f = self.dump_stdout or sys.stdout
            fmt = self.dump_stdout_fmt
            raw = self.raw_stdout
        elif fd == 2:
            f = self.dump_stderr or sys.stderr
            fmt = self.dump_stderr_fmt
            raw = self.raw_stderr
        else:
            return super(MixDumpOutput, self).s_write(fd, p_buf, count)

        data = self.sandio.read_buffer(p_buf, count)
        if not raw:
            data = fmt.format(self.dump_sanitize(data))
        f.write(data)
        f.flush()
        return count
