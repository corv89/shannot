"""Virtual /proc and /sys filesystem builders.

This module provides factory functions that return Dir structures for
virtual /proc and /sys filesystems. These are static snapshots set at
sandbox startup time.

Usage:
    from sandboxlib.vfs_procfs import build_proc, build_sys

    vfs_root = Dir({
        'proc': build_proc(cmdline=['python', 'script.py'], exe_path='/lib/pypy', cwd='/tmp'),
        'sys': build_sys(),
        ...
    })
"""

from .mix_vfs import Dir, File


def _format_cmdline(args):
    """Format command line as null-separated bytes."""
    if not args:
        return b''
    return b'\x00'.join(arg.encode('utf-8') if isinstance(arg, str) else arg for arg in args) + b'\x00'


def _format_environ(env):
    """Format environment as null-separated KEY=VALUE pairs."""
    if not env:
        return b''
    pairs = []
    for key, value in env.items():
        pair = '%s=%s' % (key, value)
        pairs.append(pair.encode('utf-8') if isinstance(pair, str) else pair)
    return b'\x00'.join(pairs) + b'\x00'


def _format_status(pid, ppid, uid, gid, process_name):
    """Format /proc/self/status content."""
    return (
        'Name:\t%s\n'
        'Umask:\t0022\n'
        'State:\tR (running)\n'
        'Tgid:\t%d\n'
        'Ngid:\t0\n'
        'Pid:\t%d\n'
        'PPid:\t%d\n'
        'TracerPid:\t0\n'
        'Uid:\t%d\t%d\t%d\t%d\n'
        'Gid:\t%d\t%d\t%d\t%d\n'
        'FDSize:\t256\n'
        'Groups:\t\n'
        'VmPeak:\t    0 kB\n'
        'VmSize:\t    0 kB\n'
        'VmRSS:\t    0 kB\n'
        'VmData:\t    0 kB\n'
        'VmStk:\t    0 kB\n'
        'VmExe:\t    0 kB\n'
        'VmLib:\t    0 kB\n'
        'Threads:\t1\n'
    ) % (process_name, pid, pid, ppid, uid, uid, uid, uid, gid, gid, gid, gid)


def _format_stat(pid, ppid, process_name):
    """Format /proc/self/stat content (single line)."""
    # Fields: pid, comm, state, ppid, pgrp, session, tty_nr, tpgid, flags,
    # minflt, cminflt, majflt, cmajflt, utime, stime, cutime, cstime, priority,
    # nice, num_threads, itrealvalue, starttime, vsize, rss, ...
    return (
        '%d (%s) R %d %d %d 0 -1 4194304 0 0 0 0 0 0 0 0 20 0 1 0 0 0 0 '
        '18446744073709551615 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n'
    ) % (pid, process_name, ppid, pid, pid)


def _format_meminfo(total_kb, free_kb):
    """Format /proc/meminfo content."""
    available_kb = free_kb
    return (
        'MemTotal:       %8d kB\n'
        'MemFree:        %8d kB\n'
        'MemAvailable:   %8d kB\n'
        'Buffers:               0 kB\n'
        'Cached:                0 kB\n'
        'SwapCached:            0 kB\n'
        'Active:                0 kB\n'
        'Inactive:              0 kB\n'
        'SwapTotal:             0 kB\n'
        'SwapFree:              0 kB\n'
        'Dirty:                 0 kB\n'
        'Writeback:             0 kB\n'
        'AnonPages:             0 kB\n'
        'Mapped:                0 kB\n'
        'Shmem:                 0 kB\n'
    ) % (total_kb, free_kb, available_kb)


def _format_cpuinfo(num_cpus):
    """Format /proc/cpuinfo content."""
    lines = []
    for i in range(num_cpus):
        entry = (
            'processor\t: %d\n'
            'vendor_id\t: GenuineIntel\n'
            'cpu family\t: 6\n'
            'model\t\t: 142\n'
            'model name\t: Virtual CPU\n'
            'stepping\t: 10\n'
            'cpu MHz\t\t: 2400.000\n'
            'cache size\t: 8192 KB\n'
            'physical id\t: 0\n'
            'siblings\t: %d\n'
            'core id\t\t: %d\n'
            'cpu cores\t: %d\n'
            'apicid\t\t: %d\n'
            'fpu\t\t: yes\n'
            'fpu_exception\t: yes\n'
            'cpuid level\t: 22\n'
            'wp\t\t: yes\n'
            'flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2\n'
            'bogomips\t: 4800.00\n'
            'clflush size\t: 64\n'
            'cache_alignment\t: 64\n'
            'address sizes\t: 39 bits physical, 48 bits virtual\n'
            '\n'
        ) % (i, num_cpus, i, num_cpus, i)
        lines.append(entry)
    return ''.join(lines)


def _format_proc_stat(num_cpus, boot_time):
    """Format /proc/stat content."""
    lines = ['cpu  0 0 0 0 0 0 0 0 0 0\n']
    for i in range(num_cpus):
        lines.append('cpu%d 0 0 0 0 0 0 0 0 0 0\n' % i)
    lines.append('intr 0\n')
    lines.append('ctxt 0\n')
    lines.append('btime %d\n' % boot_time)
    lines.append('processes 1\n')
    lines.append('procs_running 1\n')
    lines.append('procs_blocked 0\n')
    lines.append('softirq 0 0 0 0 0 0 0 0 0 0 0\n')
    return ''.join(lines)


def _format_cpu_range(num_cpus):
    """Format CPU range string (e.g., '0' for 1 CPU, '0-3' for 4 CPUs)."""
    if num_cpus <= 1:
        return '0\n'
    return '0-%d\n' % (num_cpus - 1)


def build_proc_self(cmdline, exe_path, cwd, environ=None, pid=4200, ppid=1,
                    uid=1000, gid=1000, process_name='python'):
    """Build a /proc/self directory structure.

    Args:
        cmdline: List of command line arguments [arg0, arg1, ...]
        exe_path: Virtual path to the executable (e.g., '/lib/pypy')
        cwd: Current working directory (e.g., '/tmp')
        environ: Environment variables dict, or None for empty
        pid: Virtual PID (default 4200)
        ppid: Virtual parent PID (default 1)
        uid: Virtual UID (default 1000)
        gid: Virtual GID (default 1000)
        process_name: Name shown in status/stat (default 'python')

    Returns:
        Dir object representing /proc/self
    """
    cwd_bytes = cwd.encode('utf-8') if isinstance(cwd, str) else cwd
    exe_bytes = exe_path.encode('utf-8') if isinstance(exe_path, str) else exe_path

    return Dir({
        'cmdline': File(_format_cmdline(cmdline)),
        'cwd': File(cwd_bytes),
        'exe': File(exe_bytes),
        'environ': File(_format_environ(environ)),
        'status': File(_format_status(pid, ppid, uid, gid, process_name).encode('utf-8')),
        'stat': File(_format_stat(pid, ppid, process_name).encode('utf-8')),
        'maps': File(b''),
        'fd': Dir({}),
        'root': File(b'/'),
    })


def build_proc(cmdline, exe_path, cwd, environ=None, pid=4200, ppid=1,
               uid=1000, gid=1000, process_name='python',
               num_cpus=1, mem_total_kb=8192000, mem_free_kb=4096000,
               boot_time=None):
    """Build a complete /proc directory structure.

    Args:
        cmdline: List of command line arguments
        exe_path: Virtual path to the executable
        cwd: Current working directory
        environ: Environment variables dict, or None for empty
        pid: Virtual PID (default 4200)
        ppid: Virtual parent PID (default 1)
        uid: Virtual UID (default 1000)
        gid: Virtual GID (default 1000)
        process_name: Name shown in status/stat (default 'python')
        num_cpus: Number of virtual CPUs (default 1)
        mem_total_kb: Total memory in KB (default 8192000 = 8GB)
        mem_free_kb: Free memory in KB (default 4096000 = 4GB)
        boot_time: Unix timestamp for boot time (default: 0)

    Returns:
        Dir object representing /proc
    """
    if boot_time is None:
        boot_time = 0

    return Dir({
        'self': build_proc_self(cmdline, exe_path, cwd, environ,
                                pid, ppid, uid, gid, process_name),
        'meminfo': File(_format_meminfo(mem_total_kb, mem_free_kb).encode('utf-8')),
        'cpuinfo': File(_format_cpuinfo(num_cpus).encode('utf-8')),
        'stat': File(_format_proc_stat(num_cpus, boot_time).encode('utf-8')),
    })


def build_sys(num_cpus=1):
    """Build a /sys directory structure with CPU topology.

    Args:
        num_cpus: Number of virtual CPUs (default 1)

    Returns:
        Dir object representing /sys
    """
    cpu_range = _format_cpu_range(num_cpus).encode('utf-8')

    # Build cpu entries: cpu0, cpu1, ...
    cpu_entries = {
        'online': File(cpu_range),
        'present': File(cpu_range),
        'possible': File(cpu_range),
    }
    for i in range(num_cpus):
        cpu_entries['cpu%d' % i] = Dir({
            'online': File(b'1\n'),
        })

    return Dir({
        'devices': Dir({
            'system': Dir({
                'cpu': Dir(cpu_entries),
            }),
        }),
    })
