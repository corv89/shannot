from io import BytesIO
from .virtualizedproc import signature


class MixGrabOutput(object):

    def __init__(self, *args, **kwds):
        self._write_buffer = BytesIO()
        self._write_buffer_limit = kwds.pop('write_buffer_limit', 1000000)
        super(MixGrabOutput, self).__init__(*args, **kwds)

    @signature("write(ipi)i")
    def s_write(self, fd, p_buf, count):
        """Writes to stdout or stderr are copied to an internal buffer."""

        if fd != 1 and fd != 2:
            return super(MixGrabOutput, self).s_write(fd, p_buf, count)

        data = self.sandio.read_buffer(p_buf, count)
        if self._write_buffer.tell() + len(data) > self._write_buffer_limit:
            raise Exception("subprocess is writing too much data on "
                            "stdout/stderr")
        self._write_buffer.write(data)
        return count

    def get_all_output(self):
        return self._write_buffer.getvalue()
