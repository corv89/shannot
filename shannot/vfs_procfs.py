"""Virtual /proc and /sys filesystem builders.

This module provides factory functions that return Dir structures for
virtual /proc and /sys filesystems. These are static snapshots set at
sandbox startup time.

Usage:
    from shannot.vfs_procfs import build_proc, build_sys

    vfs_root = Dir({
        'proc': build_proc(cmdline=['python', 'script.py'], exe_path='/lib/pypy', cwd='/tmp'),
        'sys': build_sys(),
        ...
    })
"""

from .mix_vfs import Dir, File, FSObject


def _format_cmdline(args):
    """Format command line as null-separated bytes."""
    if not args:
        return b""
    encoded = [arg.encode("utf-8") if isinstance(arg, str) else arg for arg in args]
    return b"\x00".join(encoded) + b"\x00"


def _format_environ(env):
    """Format environment as null-separated KEY=VALUE pairs."""
    if not env:
        return b""
    pairs = []
    for key, value in env.items():
        pair = f"{key}={value}"
        pairs.append(pair.encode("utf-8") if isinstance(pair, str) else pair)
    return b"\x00".join(pairs) + b"\x00"


def _format_status(pid, ppid, uid, gid, process_name):
    """Format /proc/self/status content."""
    return (
        f"Name:\t{process_name}\n"
        f"Umask:\t0022\n"
        f"State:\tR (running)\n"
        f"Tgid:\t{pid}\n"
        f"Ngid:\t0\n"
        f"Pid:\t{pid}\n"
        f"PPid:\t{ppid}\n"
        f"TracerPid:\t0\n"
        f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        f"Gid:\t{gid}\t{gid}\t{gid}\t{gid}\n"
        f"FDSize:\t256\n"
        f"Groups:\t\n"
        f"VmPeak:\t    0 kB\n"
        f"VmSize:\t    0 kB\n"
        f"VmRSS:\t    0 kB\n"
        f"VmData:\t    0 kB\n"
        f"VmStk:\t    0 kB\n"
        f"VmExe:\t    0 kB\n"
        f"VmLib:\t    0 kB\n"
        f"Threads:\t1\n"
    )


def _format_stat(pid, ppid, process_name):
    """Format /proc/self/stat content (single line)."""
    # Fields: pid, comm, state, ppid, pgrp, session, tty_nr, tpgid, flags,
    # minflt, cminflt, majflt, cmajflt, utime, stime, cutime, cstime, priority,
    # nice, num_threads, itrealvalue, starttime, vsize, rss, ...
    return (
        f"{pid} ({process_name}) R {ppid} {pid} {pid} 0 -1 4194304 0 0 0 0 0 0 0 0 20 0 1 0 0 0 0 "
        f"18446744073709551615 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
    )


def _format_meminfo(total_kb, free_kb):
    """Format /proc/meminfo content."""
    available_kb = free_kb
    return (
        f"MemTotal:       {total_kb:8d} kB\n"
        f"MemFree:        {free_kb:8d} kB\n"
        f"MemAvailable:   {available_kb:8d} kB\n"
        f"Buffers:               0 kB\n"
        f"Cached:                0 kB\n"
        f"SwapCached:            0 kB\n"
        f"Active:                0 kB\n"
        f"Inactive:              0 kB\n"
        f"SwapTotal:             0 kB\n"
        f"SwapFree:              0 kB\n"
        f"Dirty:                 0 kB\n"
        f"Writeback:             0 kB\n"
        f"AnonPages:             0 kB\n"
        f"Mapped:                0 kB\n"
        f"Shmem:                 0 kB\n"
    )


def _format_cpuinfo(num_cpus):
    """Format /proc/cpuinfo content."""
    lines = []
    cpu_flags = (
        "fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov "
        "pat pse36 clflush mmx fxsr sse sse2"
    )
    for i in range(num_cpus):
        entry = (
            f"processor\t: {i}\n"
            f"vendor_id\t: GenuineIntel\n"
            f"cpu family\t: 6\n"
            f"model\t\t: 142\n"
            f"model name\t: Virtual CPU\n"
            f"stepping\t: 10\n"
            f"cpu MHz\t\t: 2400.000\n"
            f"cache size\t: 8192 KB\n"
            f"physical id\t: 0\n"
            f"siblings\t: {num_cpus}\n"
            f"core id\t\t: {i}\n"
            f"cpu cores\t: {num_cpus}\n"
            f"apicid\t\t: {i}\n"
            f"fpu\t\t: yes\n"
            f"fpu_exception\t: yes\n"
            f"cpuid level\t: 22\n"
            f"wp\t\t: yes\n"
            f"flags\t\t: {cpu_flags}\n"
            f"bogomips\t: 4800.00\n"
            f"clflush size\t: 64\n"
            f"cache_alignment\t: 64\n"
            f"address sizes\t: 39 bits physical, 48 bits virtual\n"
            f"\n"
        )
        lines.append(entry)
    return "".join(lines)


def _format_proc_stat(num_cpus, boot_time):
    """Format /proc/stat content."""
    lines = ["cpu  0 0 0 0 0 0 0 0 0 0\n"]
    for i in range(num_cpus):
        lines.append(f"cpu{i} 0 0 0 0 0 0 0 0 0 0\n")
    lines.append("intr 0\n")
    lines.append("ctxt 0\n")
    lines.append(f"btime {boot_time}\n")
    lines.append("processes 1\n")
    lines.append("procs_running 1\n")
    lines.append("procs_blocked 0\n")
    lines.append("softirq 0 0 0 0 0 0 0 0 0 0 0\n")
    return "".join(lines)


def _format_cpu_range(num_cpus):
    """Format CPU range string (e.g., '0' for 1 CPU, '0-3' for 4 CPUs)."""
    if num_cpus <= 1:
        return "0\n"
    return f"0-{num_cpus - 1}\n"


def build_proc_self(
    cmdline,
    exe_path,
    cwd,
    environ=None,
    pid=4200,
    ppid=1,
    uid=1000,
    gid=1000,
    process_name="python",
):
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
    cwd_bytes = cwd.encode("utf-8") if isinstance(cwd, str) else cwd
    exe_bytes = exe_path.encode("utf-8") if isinstance(exe_path, str) else exe_path

    return Dir(
        {
            "cmdline": File(_format_cmdline(cmdline)),
            "cwd": File(cwd_bytes),
            "exe": File(exe_bytes),
            "environ": File(_format_environ(environ)),
            "status": File(_format_status(pid, ppid, uid, gid, process_name).encode("utf-8")),
            "stat": File(_format_stat(pid, ppid, process_name).encode("utf-8")),
            "maps": File(b""),
            "fd": Dir({}),
            "root": File(b"/"),
        }
    )


def build_proc(
    cmdline,
    exe_path,
    cwd,
    environ=None,
    pid=4200,
    ppid=1,
    uid=1000,
    gid=1000,
    process_name="python",
    num_cpus=1,
    mem_total_kb=8192000,
    mem_free_kb=4096000,
    boot_time=None,
):
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

    return Dir(
        {
            "self": build_proc_self(
                cmdline, exe_path, cwd, environ, pid, ppid, uid, gid, process_name
            ),
            "meminfo": File(_format_meminfo(mem_total_kb, mem_free_kb).encode("utf-8")),
            "cpuinfo": File(_format_cpuinfo(num_cpus).encode("utf-8")),
            "stat": File(_format_proc_stat(num_cpus, boot_time).encode("utf-8")),
        }
    )


def build_sys(num_cpus=1):
    """Build a /sys directory structure with CPU topology.

    Args:
        num_cpus: Number of virtual CPUs (default 1)

    Returns:
        Dir object representing /sys
    """
    cpu_range = _format_cpu_range(num_cpus).encode("utf-8")

    # Build cpu entries: cpu0, cpu1, ...
    cpu_entries: dict[str, FSObject] = {
        "online": File(cpu_range),
        "present": File(cpu_range),
        "possible": File(cpu_range),
    }
    for i in range(num_cpus):
        cpu_entries[f"cpu{i}"] = Dir(
            {
                "online": File(b"1\n"),
            }
        )

    return Dir(
        {
            "devices": Dir(
                {
                    "system": Dir(
                        {
                            "cpu": Dir(cpu_entries),
                        }
                    ),
                }
            ),
        }
    )
