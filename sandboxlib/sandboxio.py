import struct

VERSION = 20001


class SandboxError(Exception):
    """The sandboxed process misbehaved"""


class Ptr(object):
    def __init__(self, addr):
        self.addr = addr

    def __repr__(self):
        return 'Ptr(%s)' % (hex(self.addr),)


ptr_size = struct.calcsize("P")
NULL = Ptr(0)

_ptr_code = 'q' if ptr_size == 8 else 'i'
_pack_one_ptr = struct.Struct("=" + _ptr_code).pack
_pack_one_longlong = struct.Struct("=q").pack
_pack_one_double = struct.Struct("=d").pack
_pack_one_int = struct.Struct("=i").pack
_pack_two_ptrs = struct.Struct("=" + _ptr_code + _ptr_code).pack
_unpack_one_ptr = struct.Struct("=" + _ptr_code).unpack


class SandboxedIO(object):
    _message_decoders = {}


    def __init__(self, child_stdin, child_stdout):
        self.child_stdin = child_stdin
        self.child_stdout = child_stdout

    def _read(self, count):
        result = self.child_stdout.read(count)
        if len(result) != count:
            raise SandboxError(
                "connection interrupted with the sandboxed process")
        return result

    @staticmethod
    def _make_message_decoder(data):
        i1 = data.find(b'(')
        i2 = data.find(b')')
        if not (i1 > 0 and i1 < i2 and i2 == len(data) - 2):
            raise SandboxError(
                "badly formatted data received from the sandboxed process")
        pack_args = ['=']
        codes = []
        for c in data[i1+1:i2]:
            if isinstance(c, int):
                c = chr(c)   # Python 3
            if c == 'p':
                pack_args.append(_ptr_code)
            elif c == 'i':
                pack_args.append('q')
            elif c == 'f':
                pack_args.append('d')
            elif c == 'v':
                pass
            else:
                raise SandboxError(
                    "unsupported format string in parentheses: %r" % (data,))
            codes.append(c)
        unpacker = struct.Struct(''.join(pack_args))
        decoder = unpacker, ''.join(codes)

        SandboxedIO._message_decoders[data] = decoder
        return decoder

    def read_message(self):
        """Wait for the next message and returns it.  Raises EOFError if the
        subprocess finished.  Raises SandboxError if there is another kind
        of detected misbehaviour.
        """
        ch = self.child_stdout.read(1)
        if len(ch) == 0:
            raise EOFError
        n = ord(ch)
        msg = self._read(n)
        decoder = self._message_decoders.get(msg)
        if decoder is None:
            decoder = self._make_message_decoder(msg)

        unpacker, codes = decoder
        raw_args = iter(unpacker.unpack(self._read(unpacker.size)))
        args = []
        for c in codes:
            if c == 'p':
                args.append(Ptr(next(raw_args)))
            elif c == 'v':
                args.append(None)
            else:
                args.append(next(raw_args))
        return msg, args

    def read_buffer(self, ptr, length):
        if length < 0:
            raise Exception("read_buffer: negative length")
        g = self.child_stdin
        g.write(b"R" + _pack_two_ptrs(ptr.addr, length))
        g.flush()
        return self._read(length)

    def read_charp(self, ptr, maxlen):
        g = self.child_stdin
        g.write(b"Z" + _pack_two_ptrs(ptr.addr, maxlen))
        g.flush()
        length = _unpack_one_ptr(self._read(ptr_size))[0]
        return self._read(length)

    def write_buffer(self, ptr, bytes_data):
        assert isinstance(bytes_data, bytes)
        g = self.child_stdin
        g.write(b"W" + _pack_two_ptrs(ptr.addr, len(bytes_data)))
        g.write(bytes_data)
        # g.flush() not necessary here

    def write_result(self, result):
        g = self.child_stdin
        if result is None:
            g.write(b'v')
        elif isinstance(result, Ptr):
            g.write(b'p' + _pack_one_ptr(result.addr))
        elif isinstance(result, float):
            g.write(b'f' + _pack_one_double(result))
        else:
            g.write(b'i' + _pack_one_longlong(result))
        g.flush()

    def set_errno(self, err):
        g = self.child_stdin
        g.write(b"E" + _pack_one_int(err))
        # g.flush() not necessary here

    def malloc(self, bytes_data):
        assert isinstance(bytes_data, bytes)
        g = self.child_stdin
        g.write(b"M" + _pack_one_ptr(len(bytes_data)))
        g.write(bytes_data)
        g.flush()
        addr = _unpack_one_ptr(self._read(ptr_size))[0]
        return Ptr(addr)

    def free(self, ptr):
        g = self.child_stdin
        g.write(b"F" + _pack_one_ptr(ptr.addr))
        # g.flush() not necessary here
