import errno
import os
import platform
import struct
import sys
import time

from . import sandboxio
from .sandboxio import NULL, Ptr, ptr_size
from .structs import (
    SIZEOF_STRUCT_TM,
    MachTimebaseInfo,
    new_struct_tm,
    new_timeval,
    new_utsname,
    pack_gid_t,
    pack_time_t,
    pack_uid_t,
    struct_to_bytes,
)


def signature(sig):
    """Decorator that registers a method as a system call handler.

    The signature string format is: "funcname(argtypes)rettype"
    where argtypes and rettype use single-character codes:
        p = pointer (Ptr)
        i = integer (64-bit)
        f = float (double)
        v = void

    Example: @signature("read(ipi)i") defines a read syscall taking
    (int fd, ptr buf, int count) and returning int.
    """

    def decorator(func):
        func._sandbox_sig_ = sig
        return func

    return decorator


FATAL = object()


def sigerror(sig, error=FATAL, returns=FATAL):
    """Create a stub syscall handler that returns an error.

    Args:
        sig: Signature string (see @signature decorator)
        error: errno value to set, or FATAL to terminate subprocess
        returns: Return value (-1 for int, NULL for pointer, etc.)

    If error is FATAL (default), the stub raises an exception to
    terminate the sandboxed process when called.
    """
    if error is FATAL:
        assert returns is FATAL, "changing 'returns' makes no sense without also setting an 'error'"

        @signature(sig)
        def s_fatal(self, *args):
            raise Exception(f"subprocess tries to call {sig}, terminating it")

        return s_fatal

    retcode = sig[-1]
    if retcode == "i":
        if type(returns) is not int:
            raise Exception(f"{sig}: 'returns' should be an int")
    elif retcode == "p":
        if type(returns) is not Ptr:
            raise Exception(f"{sig}: 'returns' should be a Ptr")
    elif retcode == "d":
        if type(returns) is not float:
            raise Exception(f"{sig}: 'returns' should be a float")
    elif retcode == "v":
        if returns is not None:
            raise Exception(f"{sig}: 'returns' should be None")
    else:
        raise ValueError(f"{sig!r}: invalid return type code")

    # error is known to be an int at this point (not FATAL)
    assert isinstance(error, int)
    error_name = errno.errorcode.get(error, f"Errno {error}")
    stubmsg = f"subprocess: stub: {sig} => {error_name}\n"

    @signature(sig)
    def s_error(self, *args):
        if self.debug_errors:
            sys.stderr.write(stubmsg)
        self.sandio.set_errno(error)
        return returns

    return s_error


class VirtualizedProc:
    """Controls a virtualized sandboxed process, which is given a custom
    view on the filesystem and a custom environment.
    """

    debug_errors = False
    virtual_uid = 1000
    virtual_gid = 1000
    virtual_pid = 4200
    virtual_cwd = "/"
    virtual_time = time.mktime((2019, 8, 1, 0, 0, 0, 0, 0, 0))
    # ^^^ Aug 1st, 2019.  Subclasses can overwrite with a property
    # to get the current time dynamically, too
    virtual_hostname = "sandbox"
    virtual_machine = platform.machine()  # "x86_64" or "aarch64"
    virtual_home = os.path.expanduser("~")  # Real user's home directory
    virtual_user = os.environ.get("USER", "user")  # Real username

    def __init__(self, child_stdin, child_stdout):
        self.sandio = sandboxio.SandboxedIO(child_stdin, child_stdout)

    @classmethod
    def collect_signatures(cls):
        funcs = {}
        for cls1 in cls.__mro__:
            for value in cls1.__dict__.values():
                # Check if it has the signature attribute
                # Don't check type - Nuitka compiles methods differently
                if hasattr(value, "_sandbox_sig_"):
                    sig = value._sandbox_sig_.encode("ascii")
                    funcs.setdefault(sig, value)
        return funcs

    @classmethod
    def check_dump(cls, dump, missing_ok=None):
        if missing_ok is None:
            missing_ok = set()
        errors = []
        cls_signatures = cls.collect_signatures()
        dump = dump.decode("ascii")
        for line in dump.splitlines(False):
            key, value = line.split(": ", 1)
            if key == "Version":
                if value != str(sandboxio.VERSION):
                    errors.append(f"Bad version number: expected {sandboxio.VERSION}, got {value}")
            elif key == "Platform":
                expected = sys.platform
                if expected in ["linux2", "linux3"]:
                    expected = "linux"
                got = value
                if got in ["linux2", "linux3"]:
                    got = "linux"
                if got != expected:
                    errors.append(f"Bad platform: expected {expected!r}, got {value!r}")
            elif key == "Funcs":
                for fnname in value.split(" "):
                    if fnname.encode("ascii") not in cls_signatures and fnname not in missing_ok:
                        errors.append(f"Sandboxed function signature not implemented: {fnname}")
        return errors

    def run(self):
        """Main execution loop for the sandboxed process.

        Reads syscall requests from the subprocess via IPC, dispatches
        them to the appropriate @signature-decorated handler methods,
        and writes results back. Continues until the subprocess exits
        (EOFError) or a fatal error occurs.
        """
        cls_signatures = self.collect_signatures()
        sandio = self.sandio
        while True:
            try:
                msg, args = sandio.read_message()
            except EOFError:
                break
            try:
                sigfunc = cls_signatures[msg]
            except KeyError:
                self.handle_missing_signature(msg, args)
            else:
                result = sigfunc(self, *args)
                sandio.write_result(result)

    def handle_missing_signature(self, msg, args):
        raise Exception(f"subprocess tries to call {msg!r}, terminating it")

    s_access = sigerror("access(pi)i")
    s_chdir = sigerror("chdir(p)i")
    s_chmod = sigerror("chmod(pi)i")
    s_chown = sigerror("chown(pii)i")
    s_chroot = sigerror("chroot(p)i")
    s_clock_getres = sigerror("clock_getres(ip)i")
    s_clock_gettime = sigerror("clock_gettime(ip)i", errno.ENOSYS, -1)
    s_close = sigerror("close(i)i")
    s_closedir = sigerror("closedir(p)i")
    s_confstr = sigerror("confstr(ipi)i", errno.EINVAL, 0)
    s_dup = sigerror("dup(i)i")
    s_dup2 = sigerror("dup2(ii)i")
    s_execv = sigerror("execv(pp)i")
    s_execve = sigerror("execve(ppp)i")
    s_fchdir = sigerror("fchdir(i)i")
    s_fchmod = sigerror("fchmod(ii)i")
    s_fchown = sigerror("fchown(iii)i")
    s_fcntl = sigerror("fcntl(iii)i")
    s_fdatasync = sigerror("fdatasync(i)i")
    s_fork = sigerror("fork()i")
    s_forkpty = sigerror("forkpty(pppp)i")
    s_fpathconf = sigerror("fpathconf(ii)i")
    s_fstat64 = sigerror("fstat64(ip)i")
    s_fstatvfs = sigerror("fstatvfs(ip)i")
    s_fsync = sigerror("fsync(i)i")
    s_ftruncate = sigerror("ftruncate(ii)i")
    s_getloadavg = sigerror("getloadavg(pi)i")
    s_getlogin = sigerror("getlogin()p")
    s_getpgid = sigerror("getpgid(i)i")
    s_getpgrp = sigerror("getpgrp()i")
    s_getrusage = sigerror("getrusage(ip)i")
    s_getsid = sigerror("getsid(i)i")
    s_initgroups = sigerror("initgroups(pi)i")
    s_kill = sigerror("kill(ii)i")
    s_killpg = sigerror("killpg(ii)i")
    s_lchown = sigerror("lchown(pii)i")
    s_link = sigerror("link(pp)i")
    s_lseek = sigerror("lseek(iii)i")
    s_lstat64 = sigerror("lstat64(pp)i")
    s_mkdir = sigerror("mkdir(pi)i")
    s_mkfifo = sigerror("mkfifo(pi)i")
    s_mknod = sigerror("mknod(pii)i")
    s_nice = sigerror("nice(i)i")
    s_open = sigerror("open(pii)i")
    s_opendir = sigerror("opendir(p)p")
    s_openpty = sigerror("openpty(ppppp)i")
    s_pathconf = sigerror("pathconf(pi)i")
    s_pipe = sigerror("pipe(p)i")
    s_pipe2 = sigerror("pipe2(pi)i")
    s_putenv = sigerror("putenv(p)i")
    s_read = sigerror("read(ipi)i")
    s_readdir = sigerror("readdir(p)p")
    s_readlink = sigerror("readlink(ppi)i")
    s_rename = sigerror("rename(pp)i")
    s_rmdir = sigerror("rmdir(p)i")
    s_select = sigerror("select(ipppp)i")
    s_setegid = sigerror("setegid(i)i")
    s_seteuid = sigerror("seteuid(i)i")
    s_setgid = sigerror("setgid(i)i")
    s_setgroups = sigerror("setgroups(ip)i")
    s_setpgid = sigerror("setpgid(ii)i")
    s_setpgrp = sigerror("setpgrp()i")
    s_setregid = sigerror("setregid(ii)i")
    s_setresgid = sigerror("setresgid(iii)i")
    s_setresuid = sigerror("setresuid(iii)i")
    s_setreuid = sigerror("setreuid(ii)i")
    s_setsid = sigerror("setsid()i")
    s_setuid = sigerror("setuid(i)i")
    s_stat64 = sigerror("stat64(pp)i")
    s_statvfs = sigerror("statvfs(pp)i")
    s_symlink = sigerror("symlink(pp)i")
    s_sysconf = sigerror("sysconf(i)i")
    s_system = sigerror("system(p)i")
    s_tcgetpgrp = sigerror("tcgetpgrp(i)i", errno.ENOTTY, -1)
    s_tcsetpgrp = sigerror("tcsetpgrp(ii)i", errno.ENOTTY, -1)
    s_times = sigerror("times(p)i")
    s_ttyname = sigerror("ttyname(i)p", errno.ENOTTY, NULL)
    s_umask = sigerror("umask(i)i")

    @signature("uname(p)i")
    def s_uname(self, p_utsname):
        """Fill the utsname structure with virtualized values."""
        if p_utsname.addr == 0:
            self.sandio.set_errno(errno.EFAULT)
            return -1

        hostname = self.virtual_hostname
        if isinstance(hostname, str):
            hostname = hostname.encode()
        machine = self.virtual_machine
        if isinstance(machine, str):
            machine = machine.encode()

        utsname = new_utsname(
            sysname=b"Linux",
            nodename=hostname,
            release=b"5.10.0",
            version=b"#1 SMP",
            machine=machine,
        )
        self.sandio.write_buffer(p_utsname, struct_to_bytes(utsname))
        return 0

    s_unlink = sigerror("unlink(p)i")
    s_unsetenv = sigerror("unsetenv(p)i")
    s_utime = sigerror("utime(pp)i")
    s_utimes = sigerror("utimes(pp)i")
    s_waitpid = sigerror("waitpid(ipi)i")
    s_write = sigerror("write(ipi)i")

    # extra functions needed for pypy3
    s_clock = sigerror("clock()i")
    s_clock_settime = sigerror("clock_settime(ip)i")
    s_dirfd = sigerror("dirfd(p)i")
    s_faccessat = sigerror("faccessat(ipii)i")
    s_fchmodat = sigerror("fchmodat(ipii)i")
    s_fchownat = sigerror("fchownat(ipiii)i")
    s_fdopendir = sigerror("fdopendir(i)p")
    s_fexecve = sigerror("fexecve(ipp)i")
    s_fgetxattr = sigerror("fgetxattr(ippi)i")
    s_fileno = sigerror("fileno(p)i", errno.EBADF, -1)
    s_flistxattr = sigerror("flistxattr(ipi)i")
    s_fremovexattr = sigerror("fremovexattr(ip)i")
    s_fsetxattr = sigerror("fsetxattr(ippii)i")
    s_fstatat64 = sigerror("fstatat64(ippi)i")
    s_futimens = sigerror("futimens(ip)i")
    s_getpriority = sigerror("getpriority(ii)i")
    s_getxattr = sigerror("getxattr(pppi)i")
    s_ioctl = sigerror("ioctl(iip)i")
    s_lgetxattr = sigerror("lgetxattr(pppi)i")
    s_linkat = sigerror("linkat(ipipi)i")
    s_listxattr = sigerror("listxattr(ppi)i")
    s_llistxattr = sigerror("llistxattr(ppi)i")
    s_lockf = sigerror("lockf(iii)i")
    s_lremovexattr = sigerror("lremovexattr(pp)i")
    s_lsetxattr = sigerror("lsetxattr(pppii)i")
    s_mkdirat = sigerror("mkdirat(ipi)i")
    s_mkfifoat = sigerror("mkfifoat(ipi)i")
    s_mknodat = sigerror("mknodat(ipii)i")
    s_openat = sigerror("openat(ipii)i")
    s_posix_fadvise = sigerror("posix_fadvise(iiii)i")
    s_posix_fallocate = sigerror("posix_fallocate(iii)i")
    s_pread = sigerror("pread(ipii)i")
    s_pwrite = sigerror("pwrite(ipii)i")
    s_readlinkat = sigerror("readlinkat(ippi)i")
    s_removexattr = sigerror("removexattr(pp)i")
    s_renameat = sigerror("renameat(ipip)i")
    s_rpy_dup2_noninheritable = sigerror("rpy_dup2_noninheritable(ii)i")
    s_rpy_dup_noninheritable = sigerror("rpy_dup_noninheritable(i)i")
    s_rpy_get_status_flags = sigerror("rpy_get_status_flags(i)i")
    s_rpy_set_status_flags = sigerror("rpy_set_status_flags(ii)i")
    s_sched_get_priority_max = sigerror("sched_get_priority_max(i)i")
    s_sched_get_priority_min = sigerror("sched_get_priority_min(i)i")
    s_sendfile = sigerror("sendfile(iiippi)i")
    s_setpriority = sigerror("setpriority(iii)i")
    s_setxattr = sigerror("setxattr(pppii)i")
    s_symlinkat = sigerror("symlinkat(pip)i")
    s_unlinkat = sigerror("unlinkat(ipi)i")
    s_utimensat = sigerror("utimensat(ippi)i")

    @signature("time(p)i")
    def s_time(self, p_tloc):
        t = int(self.virtual_time)
        if p_tloc.addr != 0:
            bytes_data = pack_time_t(t)
            self.sandio.write_buffer(p_tloc, bytes_data)
        return t

    @signature("gettimeofday(pp)i")
    def s_gettimeofday(self, p_tv, p_tz):
        if p_tv.addr != 0:
            t = self.virtual_time
            assert t >= 0.0
            sec = int(t)
            usec = int((t - sec) * 1000000.0)
            bytes_data = struct_to_bytes(new_timeval(sec, usec))
            self.sandio.write_buffer(p_tv, bytes_data)
        if p_tz.addr != 0:
            raise Exception("subprocess called gettimeofday() with a non-null second argument (tz)")
        return 0

    @signature("tzset()v")
    def s_tzset(self):
        """Initialize timezone - no-op in sandbox."""
        return None

    @signature("localtime(p)p")
    def s_localtime(self, p_time):
        """Convert time_t to struct tm (local time)."""
        if p_time.addr != 0:
            time_bytes = self.sandio.read_buffer(p_time, 8)
            t = int.from_bytes(time_bytes, sys.byteorder, signed=True)
        else:
            t = int(self.virtual_time)

        try:
            tm = time.localtime(t)
        except (OSError, OverflowError):
            self.sandio.set_errno(errno.EINVAL)
            return NULL

        # Allocate timezone string (tm_zone must point to valid string, not NULL)
        if not hasattr(self, "_tz_local_str"):
            self._tz_local_str = self.sandio.malloc(b"UTC\x00")

        result = new_struct_tm(
            tm_sec=tm.tm_sec,
            tm_min=tm.tm_min,
            tm_hour=tm.tm_hour,
            tm_mday=tm.tm_mday,
            tm_mon=tm.tm_mon - 1,  # C is 0-11, Python is 1-12
            tm_year=tm.tm_year - 1900,  # C is years since 1900
            tm_wday=(tm.tm_wday + 1) % 7,  # Python: Mon=0, C: Sun=0
            tm_yday=tm.tm_yday - 1,  # C is 0-365, Python is 1-366
            tm_isdst=tm.tm_isdst,
            tm_gmtoff=0,
            tm_zone=self._tz_local_str.addr,
        )

        if not hasattr(self, "_localtime_buf"):
            self._localtime_buf = self.sandio.malloc(b"\x00" * SIZEOF_STRUCT_TM)
        self.sandio.write_buffer(self._localtime_buf, struct_to_bytes(result))
        return self._localtime_buf

    @signature("gmtime(p)p")
    def s_gmtime(self, p_time):
        """Convert time_t to struct tm (UTC)."""
        if p_time.addr != 0:
            time_bytes = self.sandio.read_buffer(p_time, 8)
            t = int.from_bytes(time_bytes, sys.byteorder, signed=True)
        else:
            t = int(self.virtual_time)

        try:
            tm = time.gmtime(t)
        except (OSError, OverflowError):
            self.sandio.set_errno(errno.EINVAL)
            return NULL

        # Allocate timezone string (tm_zone must point to valid string, not NULL)
        if not hasattr(self, "_tz_utc_str"):
            self._tz_utc_str = self.sandio.malloc(b"UTC\x00")

        result = new_struct_tm(
            tm_sec=tm.tm_sec,
            tm_min=tm.tm_min,
            tm_hour=tm.tm_hour,
            tm_mday=tm.tm_mday,
            tm_mon=tm.tm_mon - 1,  # C is 0-11, Python is 1-12
            tm_year=tm.tm_year - 1900,  # C is years since 1900
            tm_wday=(tm.tm_wday + 1) % 7,  # Python: Mon=0, C: Sun=0
            tm_yday=tm.tm_yday - 1,  # C is 0-365, Python is 1-366
            tm_isdst=tm.tm_isdst,
            tm_gmtoff=0,  # UTC has no offset
            tm_zone=self._tz_utc_str.addr,
        )

        if not hasattr(self, "_gmtime_buf"):
            self._gmtime_buf = self.sandio.malloc(b"\x00" * SIZEOF_STRUCT_TM)
        self.sandio.write_buffer(self._gmtime_buf, struct_to_bytes(result))
        return self._gmtime_buf

    @signature("mktime(p)i")
    def s_mktime(self, p_tm):
        """Convert struct tm to time_t."""
        import calendar

        tm_bytes = self.sandio.read_buffer(p_tm, SIZEOF_STRUCT_TM)
        # Unpack: 9 ints (36 bytes)
        ints = struct.unpack("9i", tm_bytes[:36])

        try:
            t = calendar.timegm(
                (
                    ints[5] + 1900,  # tm_year -> year
                    ints[4] + 1,  # tm_mon -> month (C 0-11 to Python 1-12)
                    ints[3],  # tm_mday
                    ints[2],  # tm_hour
                    ints[1],  # tm_min
                    ints[0],  # tm_sec
                    0,
                    0,
                    ints[8],  # tm_isdst
                )
            )
        except (ValueError, OverflowError):
            self.sandio.set_errno(errno.EOVERFLOW)
            return -1
        return t

    @signature("strftime(pipp)i")
    def s_strftime(self, p_buf, maxsize, p_format, p_tm):
        """Format time to string."""
        fmt = self.sandio.read_charp(p_format, 256).decode("utf-8", errors="replace")
        tm_bytes = self.sandio.read_buffer(p_tm, SIZEOF_STRUCT_TM)
        # Unpack: 9 ints (36 bytes)
        ints = struct.unpack("9i", tm_bytes[:36])

        tm_tuple = time.struct_time(
            (
                ints[5] + 1900,  # tm_year -> year
                ints[4] + 1,  # tm_mon -> month (C 0-11 to Python 1-12)
                ints[3],  # tm_mday
                ints[2],  # tm_hour
                ints[1],  # tm_min
                ints[0],  # tm_sec
                (ints[6] - 1) % 7,  # tm_wday: C Sun=0 to Python Mon=0
                ints[7] + 1,  # tm_yday: C 0-365 to Python 1-366
                ints[8],  # tm_isdst
            )
        )

        try:
            result = time.strftime(fmt, tm_tuple)
        except (ValueError, OverflowError):
            return 0

        result_bytes = result.encode("utf-8")
        if len(result_bytes) >= maxsize:
            return 0
        self.sandio.write_buffer(p_buf, result_bytes + b"\x00")
        return len(result_bytes)

    @signature("mach_absolute_time()i")
    def s_mach_absolute_time(self):
        """Return high-resolution time (nanoseconds as 64-bit int)."""
        return int(self.virtual_time * 1_000_000_000) & 0x7FFFFFFFFFFFFFFF

    @signature("mach_timebase_info(p)v")
    def s_mach_timebase_info(self, p_info):
        """Fill mach_timebase_info: numer=1, denom=1 (nanoseconds)."""
        info = MachTimebaseInfo(numer=1, denom=1)
        self.sandio.write_buffer(p_info, struct_to_bytes(info))
        return None

    @signature("strerror(i)p")
    def s_strerror(self, errnum):
        """Return error string for errno."""
        import os

        if not hasattr(self, "_strerror_cache"):
            self._strerror_cache = {}
        if errnum not in self._strerror_cache:
            msg = os.strerror(errnum).encode("utf-8") + b"\x00"
            self._strerror_cache[errnum] = self.sandio.malloc(msg)
        return self._strerror_cache[errnum]

    @signature("major(i)i")
    def s_major(self, dev):
        """Extract major device number (macOS format)."""
        return (dev >> 24) & 0xFF

    @signature("minor(i)i")
    def s_minor(self, dev):
        """Extract minor device number (macOS format)."""
        return dev & 0xFFFFFF

    @signature("makedev(ii)i")
    def s_makedev(self, major, minor):
        """Create device number from major/minor (macOS format)."""
        return ((major & 0xFF) << 24) | (minor & 0xFFFFFF)

    s_getgrouplist = sigerror("getgrouplist(pipp)i", errno.EPERM, -1)
    s_ftime = sigerror("ftime(p)v", errno.ENOSYS, None)

    # Wait status inspection macros (used by shutil, os.wait*, etc.)
    # Return 0 since sandbox doesn't spawn real child processes
    s_WCOREDUMP = sigerror("WCOREDUMP(i)i", 0, 0)
    s_WEXITSTATUS = sigerror("WEXITSTATUS(i)i", 0, 0)
    s_WIFCONTINUED = sigerror("WIFCONTINUED(i)i", 0, 0)
    s_WIFEXITED = sigerror("WIFEXITED(i)i", 0, 0)
    s_WIFSIGNALED = sigerror("WIFSIGNALED(i)i", 0, 0)
    s_WIFSTOPPED = sigerror("WIFSTOPPED(i)i", 0, 0)
    s_WSTOPSIG = sigerror("WSTOPSIG(i)i", 0, 0)
    s_WTERMSIG = sigerror("WTERMSIG(i)i", 0, 0)

    @signature("pypy_debug_catch_fatal_exception()v")
    def s_pypy_debug_catch_fatal_exception(self):
        """PyPy internal - no-op."""
        return None

    @signature("get_environ()p")
    def s_get_environ(self):
        """Return environ array (char **) with HOME and USER variables."""
        if not hasattr(self, "_alloc_environ_array"):
            # Build environ array: array of pointers to "KEY=VALUE\0" strings
            env_vars = [
                f"HOME={self.virtual_home}",
                f"USER={self.virtual_user}",
                "SHANNOT_SANDBOX=1",
            ]
            # Allocate each string and collect pointers
            ptrs = []
            for var in env_vars:
                ptr = self.sandio.malloc(var.encode("utf-8") + b"\x00")
                ptrs.append(ptr)
            # Build array of pointers, NULL-terminated
            array_data = b"".join(p.addr.to_bytes(ptr_size, sys.byteorder) for p in ptrs) + (
                b"\x00" * ptr_size
            )
            self._alloc_environ_array = self.sandio.malloc(array_data)
        return self._alloc_environ_array

    @signature("_NSGetEnviron()p")
    def s__NSGetEnviron(self):  # noqa: N802 - matches syscall name
        """macOS-specific: return pointer to pointer to environ array (char ***).

        _NSGetEnviron returns &environ, so we need another level of indirection.
        """
        if not hasattr(self, "_alloc_environ_ptr"):
            environ_array = self.s_get_environ()
            # Allocate a pointer to the environ array
            ptr_data = environ_array.addr.to_bytes(ptr_size, sys.byteorder)
            self._alloc_environ_ptr = self.sandio.malloc(ptr_data)
        return self._alloc_environ_ptr

    @signature("getenv(p)p")
    def s_getenv(self, p_name):
        """Return environment variable value, or NULL if not set."""
        name = self.sandio.read_charp(p_name, 256).decode("utf-8", errors="replace")
        env_vars = {
            "HOME": self.virtual_home,
            "USER": self.virtual_user,
            "SHANNOT_SANDBOX": "1",
        }
        value = env_vars.get(name)
        if value is None:
            return NULL
        # Allocate string in sandbox memory
        value_bytes = value.encode("utf-8") + b"\x00"
        return self.sandio.malloc(value_bytes)

    @signature("getcwd(pi)p")
    def s_getcwd(self, p_buf, size):
        cwd = self.virtual_cwd.encode("utf-8")
        if len(cwd) >= size:
            self.sandio.set_errno(errno.ERANGE)
            return NULL
        self.sandio.write_buffer(p_buf, cwd + b"\x00")
        return p_buf

    @signature("_exit(i)v")
    def s__exit(self, exitcode):
        raise Exception(f"subprocess called _exit({exitcode})")

    @signature("isatty(i)i")
    def s_isatty(self, fd):
        self.sandio.set_errno(errno.ENOTTY)
        return 0

    @signature("getuid()i")
    def s_getuid(self):
        return self.virtual_uid

    @signature("getgid()i")
    def s_getgid(self):
        return self.virtual_gid

    @signature("geteuid()i")
    def s_geteuid(self):
        return self.virtual_uid

    @signature("getegid()i")
    def s_getegid(self):
        return self.virtual_gid

    @signature("getresuid(ppp)i")
    def s_getresuid(self, p_ruid, p_euid, p_suid):
        bytes_data = pack_uid_t(self.virtual_uid)
        self.sandio.write_buffer(p_ruid, bytes_data)
        self.sandio.write_buffer(p_euid, bytes_data)
        self.sandio.write_buffer(p_suid, bytes_data)
        return 0

    @signature("getresgid(ppp)i")
    def s_getresgid(self, p_rgid, p_egid, p_sgid):
        bytes_data = pack_gid_t(self.virtual_gid)
        self.sandio.write_buffer(p_rgid, bytes_data)
        self.sandio.write_buffer(p_egid, bytes_data)
        self.sandio.write_buffer(p_sgid, bytes_data)
        return 0

    @signature("getgroups(ip)i")
    def s_getgroups(self, size, p_list):
        return 0

    @signature("getpid()i")
    def s_getpid(self):
        return self.virtual_pid

    @signature("getppid()i")
    def s_getppid(self):
        return 1  # emulates reparented to 'init'

    @signature("pypy__allow_attach()v")
    def s_pypy__allow_attach(self):
        return None

    @signature("ctermid(p)p")
    def s_ctermid(self, s_p):
        if s_p.addr != 0:
            raise Exception("subprocess tried to call ctermid(non-NULL) which is not implemented")
        if not hasattr(self, "_alloc_dev_tty"):
            self._alloc_dev_tty = self.sandio.malloc(b"/dev/tty\x00")
        return self._alloc_dev_tty

    @signature("get_stdout()p")
    def s_get_stdout(self, *args):
        raise Exception("subprocess calls the unsupported RPython get_stdout() helper")

    @signature("rewinddir(p)v")
    def s_rewinddir(self, p_dir: Ptr) -> None:
        raise Exception("subprocess calls the unsupported rewinddir() function")

    @signature("rpy_cpu_count()i")
    def s_rpy_cpu_count(self, *args):
        return 1

    @signature("rpy_get_inheritable(i)i")
    def s_rpy_get_inheritable(self, fd):
        return 0  # ignored

    @signature("rpy_set_inheritable(ii)i")
    def s_rpy_set_inheritable(self, fd, inheritable):
        return 0  # ignored

    @signature("sched_yield()i")
    def s_sched_yield(self):
        return 0  # always succeeds

    @signature("sync()v")
    def s_sync(self):
        if self.debug_errors:
            sys.stderr.write("subprocess: sync ignored\n")
