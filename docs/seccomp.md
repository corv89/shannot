# Seccomp BPF Filters

This guide explains how to add seccomp (Secure Computing Mode) filters to Shannot profiles for additional system call filtering.

## Overview

Seccomp restricts which system calls a process can make. Combined with Shannot's namespace isolation and read-only mounts, it provides defense-in-depth security.

**Note:** Seccomp is optional. Shannot works perfectly without it. Only add seccomp if you need syscall-level restrictions.

## Quick Start

To add seccomp to a profile:

1. Create or obtain a seccomp BPF file
2. Add `"seccomp_profile": "/path/to/filter.bpf"` to your profile
3. Ensure the file exists when the profile is loaded

```json
{
  "name": "with-seccomp",
  "seccomp_profile": "/etc/shannot/readonly.bpf",
  ...
}
```

## Creating Seccomp Profiles

### Using OCI Runtime Spec

The easiest method is to use the OCI (Open Container Initiative) seccomp format and compile it to BPF.

**1. Create OCI JSON seccomp policy:**

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_X86", "SCMP_ARCH_X32"],
  "syscalls": [
    {
      "names": [
        "read", "write", "open", "close", "stat", "fstat",
        "lstat", "poll", "lseek", "mmap", "mprotect", "munmap",
        "brk", "rt_sigaction", "rt_sigprocmask", "ioctl", "pread64",
        "pwrite64", "readv", "writev", "access", "pipe", "select",
        "sched_yield", "mremap", "msync", "mincore", "madvise",
        "shmget", "shmat", "shmctl", "dup", "dup2", "pause",
        "nanosleep", "getitimer", "alarm", "setitimer", "getpid",
        "sendfile", "socket", "connect", "accept", "sendto",
        "recvfrom", "sendmsg", "recvmsg", "shutdown", "bind",
        "listen", "getsockname", "getpeername", "socketpair",
        "setsockopt", "getsockopt", "clone", "fork", "vfork",
        "execve", "exit", "wait4", "kill", "uname", "fcntl",
        "flock", "fsync", "fdatasync", "truncate", "ftruncate",
        "getdents", "getcwd", "chdir", "fchdir", "rename",
        "mkdir", "rmdir", "creat", "link", "unlink", "symlink",
        "readlink", "chmod", "fchmod", "chown", "fchown",
        "lchown", "umask", "gettimeofday", "getrlimit", "getrusage",
        "sysinfo", "times", "ptrace", "getuid", "syslog",
        "getgid", "setuid", "setgid", "geteuid", "getegid",
        "setpgid", "getppid", "getpgrp", "setsid", "setreuid",
        "setregid", "getgroups", "setgroups", "setresuid",
        "getresuid", "setresgid", "getresgid", "getpgid",
        "setfsuid", "setfsgid", "getsid", "capget", "capset",
        "rt_sigpending", "rt_sigtimedwait", "rt_sigqueueinfo",
        "rt_sigsuspend", "sigaltstack", "utime", "mknod",
        "personality", "ustat", "statfs", "fstatfs", "sysfs",
        "getpriority", "setpriority", "sched_setparam",
        "sched_getparam", "sched_setscheduler", "sched_getscheduler",
        "sched_get_priority_max", "sched_get_priority_min",
        "sched_rr_get_interval", "mlock", "munlock", "mlockall",
        "munlockall", "vhangup", "modify_ldt", "pivot_root",
        "_sysctl", "prctl", "arch_prctl", "adjtimex", "setrlimit",
        "chroot", "sync", "acct", "settimeofday", "mount",
        "umount2", "swapon", "swapoff", "reboot", "sethostname",
        "setdomainname", "iopl", "ioperm", "init_module",
        "delete_module", "quotactl", "gettid", "readahead",
        "setxattr", "lsetxattr", "fsetxattr", "getxattr",
        "lgetxattr", "fgetxattr", "listxattr", "llistxattr",
        "flistxattr", "removexattr", "lremovexattr", "fremovexattr",
        "tkill", "time", "futex", "sched_setaffinity",
        "sched_getaffinity", "io_setup", "io_destroy", "io_getevents",
        "io_submit", "io_cancel", "lookup_dcookie",
        "epoll_create", "getdents64", "set_tid_address",
        "restart_syscall", "semtimedop", "fadvise64", "timer_create",
        "timer_settime", "timer_gettime", "timer_getoverrun",
        "timer_delete", "clock_settime", "clock_gettime",
        "clock_getres", "clock_nanosleep", "exit_group",
        "epoll_wait", "epoll_ctl", "tgkill", "utimes", "mbind",
        "set_mempolicy", "get_mempolicy", "mq_open", "mq_unlink",
        "mq_timedsend", "mq_timedreceive", "mq_notify",
        "mq_getsetattr", "waitid", "add_key", "request_key",
        "keyctl", "ioprio_set", "ioprio_get", "inotify_init",
        "inotify_add_watch", "inotify_rm_watch", "openat",
        "mkdirat", "mknodat", "fchownat", "futimesat",
        "newfstatat", "unlinkat", "renameat", "linkat",
        "symlinkat", "readlinkat", "fchmodat", "faccessat",
        "pselect6", "ppoll", "unshare", "set_robust_list",
        "get_robust_list", "splice", "tee", "sync_file_range",
        "vmsplice", "move_pages", "utimensat", "epoll_pwait",
        "signalfd", "timerfd_create", "eventfd", "fallocate",
        "timerfd_settime", "timerfd_gettime", "accept4",
        "signalfd4", "eventfd2", "epoll_create1", "dup3",
        "pipe2", "inotify_init1", "preadv", "pwritev",
        "rt_tgsigqueueinfo", "perf_event_open", "recvmmsg",
        "fanotify_init", "fanotify_mark", "prlimit64",
        "name_to_handle_at", "open_by_handle_at", "clock_adjtime",
        "syncfs", "sendmmsg", "setns", "getcpu", "process_vm_readv",
        "process_vm_writev", "kcmp", "finit_module",
        "sched_setattr", "sched_getattr", "renameat2",
        "seccomp", "getrandom", "memfd_create", "kexec_file_load",
        "bpf", "execveat", "userfaultfd", "membarrier",
        "mlock2", "copy_file_range", "preadv2", "pwritev2",
        "pkey_mprotect", "pkey_alloc", "pkey_free", "statx"
      ],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

Save as `/etc/shannot/readonly-seccomp.json`.

**2. Compile to BPF using Python:**

```python
#!/usr/bin/env python3
"""Compile OCI seccomp JSON to BPF format for bubblewrap."""

import json
import sys
from pathlib import Path

try:
    import seccomp
except ImportError:
    print("Error: libseccomp-python not installed")
    print("Install with: pip install libseccomp")
    sys.exit(1)

def compile_seccomp(input_file, output_file):
    """Compile OCI seccomp JSON to BPF."""
    # Load OCI JSON
    with open(input_file) as f:
        policy = json.load(f)

    # Create seccomp filter
    filter = seccomp.SyscallFilter(
        defaction=seccomp.ERRNO(1)  # Default: return EPERM
    )

    # Add allowed syscalls
    for rule in policy.get("syscalls", []):
        if rule.get("action") == "SCMP_ACT_ALLOW":
            for name in rule.get("names", []):
                try:
                    syscall = seccomp.resolve_syscall(seccomp.Arch.NATIVE, name)
                    filter.add_rule(seccomp.ALLOW, syscall)
                except ValueError:
                    print(f"Warning: Unknown syscall '{name}', skipping")

    # Export to BPF
    filter.export_bpf(open(output_file, 'wb'))
    print(f"Compiled {input_file} -> {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.bpf>")
        sys.exit(1)

    compile_seccomp(sys.argv[1], sys.argv[2])
```

**3. Run the compiler:**

```bash
# Install libseccomp Python bindings
pip install libseccomp

# Compile
python3 compile-seccomp.py readonly-seccomp.json readonly.bpf

# Move to system location
sudo mv readonly.bpf /etc/shannot/
```

### Using libseccomp Directly

For fine-grained control, use libseccomp directly:

```python
#!/usr/bin/env python3
import seccomp

# Create filter with default deny
f = seccomp.SyscallFilter(defaction=seccomp.ERRNO(1))

# Allow specific syscalls
allowed = [
    "read", "write", "open", "close", "stat",
    "fstat", "lstat", "mmap", "munmap", "brk",
    "exit", "exit_group", "rt_sigaction", "rt_sigprocmask"
]

for syscall_name in allowed:
    syscall = seccomp.resolve_syscall(seccomp.Arch.NATIVE, syscall_name)
    f.add_rule(seccomp.ALLOW, syscall)

# Export to BPF
with open("custom.bpf", "wb") as bpf_file:
    f.export_bpf(bpf_file)

print("Seccomp filter created: custom.bpf")
```

## Adding Seccomp to Profiles

### Absolute Path

```json
{
  "name": "readonly",
  "seccomp_profile": "/etc/shannot/readonly.bpf",
  ...
}
```

### Relative Path

Relative to the profile file's directory:

```json
{
  "name": "readonly",
  "seccomp_profile": "./filters/readonly.bpf",
  ...
}
```

## Testing Seccomp Filters

Test that your filter allows necessary syscalls:

```bash
# Should succeed (allowed syscalls)
shannot --profile with-seccomp.json run ls /

# Should fail if write syscalls are blocked
shannot --profile with-seccomp.json run touch /tmp/test
```

## Troubleshooting

### Command Fails Immediately

If commands fail with strange errors, the seccomp filter may be too restrictive.

**Debug:**
1. Temporarily remove `seccomp_profile` from the profile
2. If it works without seccomp, the filter is blocking needed syscalls
3. Use `strace` to see which syscalls are needed:

```bash
strace -c ls / 2>&1 | grep -E "calls|errors"
```

### libseccomp Not Available

```bash
# Fedora/RHEL
sudo dnf install python3-libseccomp

# Debian/Ubuntu
sudo apt install python3-seccomp

# From source
pip install libseccomp
```

### Filter Compilation Errors

```python
# Check seccomp module version
python3 -c "import seccomp; print(seccomp.version())"

# Verify syscall names
python3 -c "import seccomp; print(seccomp.resolve_syscall(seccomp.Arch.NATIVE, 'read'))"
```

## Seccomp Resources

### Preset Profiles

Common seccomp policies:

- **Docker default**: [https://github.com/moby/moby/blob/master/profiles/seccomp/default.json](https://github.com/moby/moby/blob/master/profiles/seccomp/default.json)
- **Podman default**: Similar to Docker
- **Systemd**: `/usr/share/systemd/` on systems with systemd-seccomp

### Reference

- [Seccomp BPF documentation](https://www.kernel.org/doc/Documentation/prctl/seccomp_filter.txt)
- [libseccomp documentation](https://github.com/seccomp/libseccomp/tree/main/doc)
- [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec/blob/main/config-linux.md#seccomp)

## Example: Read-Only Profile

Minimal seccomp for read-only operations:

```python
#!/usr/bin/env python3
"""Create minimal read-only seccomp filter."""
import seccomp

f = seccomp.SyscallFilter(defaction=seccomp.ERRNO(1))

# File reading
for sc in ["open", "openat", "read", "readv", "pread64", "preadv",
           "close", "lseek", "stat", "fstat", "lstat", "newfstatat",
           "getdents", "getdents64", "readlink", "readlinkat"]:
    f.add_rule(seccomp.ALLOW, sc)

# Process/memory management
for sc in ["brk", "mmap", "munmap", "mprotect", "exit", "exit_group",
           "rt_sigaction", "rt_sigprocmask", "rt_sigreturn"]:
    f.add_rule(seccomp.ALLOW, sc)

# Process info
for sc in ["getpid", "gettid", "getuid", "getgid", "geteuid", "getegid"]:
    f.add_rule(seccomp.ALLOW, sc)

# Write to stdout/stderr only
f.add_rule_exactly(seccomp.ALLOW, "write", seccomp.Arg(0, seccomp.EQ, 1))  # stdout
f.add_rule_exactly(seccomp.ALLOW, "write", seccomp.Arg(0, seccomp.EQ, 2))  # stderr

with open("readonly.bpf", "wb") as out:
    f.export_bpf(out)

print("Created readonly.bpf")
```

## See Also

- [profiles.md](profiles.md) - Profile configuration
- [api.md](api.md) - Using profiles from Python\
