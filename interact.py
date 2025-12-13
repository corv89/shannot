#! /usr/bin/env python

"""Interacts with a subprocess translated with --sandbox.

Usage:
    interact.py [options] <executable> <args...>

Options:
    --lib-path=DIR  the real directory that contains lib-python and lib_pypy
                    directories (only needed if executable is a pypy sandbox)

    --tmp=DIR       the real directory that corresponds to the virtual /tmp,
                    which is the virtual current dir (always read-only for now)

    --nocolor       turn off coloring of the sandboxed-produced output

    --raw-stdout    turn off all sanitization (and coloring) of stdout
                    (only if you need binary output---don't let it go to
                    a terminal!)

    --debug         check if all "system calls" of the subprocess are handled
                    and dump all errors reported to the subprocess

    --dry-run       log system() calls but don't execute them

    --allow-cmd=CMD add CMD to immediate allowlist (can repeat)

    --approve-cmd=CMD
                    add CMD to requires-approval list (can repeat)

    --deny-cmd=CMD  add CMD to denylist (can repeat)

    --default-allow allow unknown commands (default is deny)

    --script-name=NAME
                    human-readable name for the session (used in dry-run)

    --analysis=TEXT description of what the script does (used in dry-run)

Note that you can get readline-like behavior with a tool like 'ledit',
provided you use enough -u options:

    ledit python -u interact.py --lib-path=/path/lib /path/pypy-c-sandbox -u -i
"""

import subprocess
import sys

from sandboxlib import VirtualizedProc
from sandboxlib.mix_accept_input import MixAcceptInput
from sandboxlib.mix_dump_output import MixDumpOutput
from sandboxlib.mix_pypy import MixPyPy
from sandboxlib.mix_subprocess import MixSubprocess
from sandboxlib.mix_vfs import Dir, MixVFS, RealDir
from sandboxlib.vfs_procfs import build_proc, build_sys


def main(argv):
    from getopt import getopt  # and not gnu_getopt!

    options, arguments = getopt(
        argv,
        "h",
        [
            "tmp=",
            "lib-path=",
            "nocolor",
            "raw-stdout",
            "debug",
            "help",
            "dry-run",
            "allow-cmd=",
            "approve-cmd=",
            "deny-cmd=",
            "default-allow",
            "script-name=",
            "analysis=",
        ],
    )

    def help():
        sys.stderr.write(__doc__)
        return 2

    if len(arguments) < 1:
        return help()

    class SandboxedProc(
        MixSubprocess, MixPyPy, MixVFS, MixDumpOutput, MixAcceptInput, VirtualizedProc
    ):
        virtual_cwd = "/tmp"
        vfs_root = Dir({"tmp": Dir({})})

    color = True
    raw_stdout = False
    executable = arguments[0]

    # Capture sandbox args as structured dict for session re-execution
    sandbox_args = {
        "lib_path": None,
        "tmp": None,
        "pypy_exe": executable,
        "nocolor": False,
        "raw_stdout": False,
        "script_name": None,
        "analysis": None,
    }

    for option, value in options:
        if option == "--tmp":
            SandboxedProc.vfs_root.entries["tmp"] = RealDir(value)
            sandbox_args["tmp"] = value
        elif option == "--lib-path":
            SandboxedProc.vfs_root.entries["lib"] = MixVFS.vfs_pypy_lib_directory(value)
            arguments[0] = "/lib/pypy"
            sandbox_args["lib_path"] = value
        elif option == "--nocolor":
            color = False
            sandbox_args["nocolor"] = True
        elif option == "--raw-stdout":
            raw_stdout = True
            sandbox_args["raw_stdout"] = True
        elif option == "--debug":
            SandboxedProc.debug_errors = True
        elif option == "--dry-run":
            SandboxedProc.subprocess_dry_run = True
        elif option == "--allow-cmd":
            SandboxedProc.subprocess_allowlist.add(value)
        elif option == "--approve-cmd":
            SandboxedProc.subprocess_requires_approval.add(value)
        elif option == "--deny-cmd":
            SandboxedProc.subprocess_denylist.add(value)
        elif option == "--default-allow":
            SandboxedProc.subprocess_default_deny = False
        elif option == "--script-name":
            SandboxedProc.subprocess_script_name = value
            sandbox_args["script_name"] = value
        elif option == "--analysis":
            SandboxedProc.subprocess_analysis = value
            sandbox_args["analysis"] = value
        elif option in ["-h", "--help"]:
            return help()
        else:
            raise ValueError(option)

    if color:
        SandboxedProc.dump_stdout_fmt = SandboxedProc.dump_get_ansi_color_fmt(32)
        SandboxedProc.dump_stderr_fmt = SandboxedProc.dump_get_ansi_color_fmt(31)
    if raw_stdout:
        SandboxedProc.raw_stdout = True

    # Add virtual /proc and /sys filesystems
    SandboxedProc.vfs_root.entries["proc"] = build_proc(
        cmdline=arguments,
        exe_path=arguments[0],
        cwd=SandboxedProc.virtual_cwd,
        pid=SandboxedProc.virtual_pid,
        uid=SandboxedProc.virtual_uid,
        gid=SandboxedProc.virtual_gid,
    )
    SandboxedProc.vfs_root.entries["sys"] = build_sys()

    if SandboxedProc.debug_errors:
        popen1 = subprocess.Popen(
            arguments[:1],
            executable=executable,
            env={"RPY_SANDBOX_DUMP": "1"},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        vp = SandboxedProc(popen1.stdin, popen1.stdout)
        errors = vp.check_dump(popen1.stdout.read())
        if errors:
            for error in errors:
                sys.stderr.write("*** " + error + "\n")
        popen1.wait()
        if errors:
            return 1

    popen = subprocess.Popen(
        arguments,
        executable=executable,
        env={},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    virtualizedproc = SandboxedProc(popen.stdin, popen.stdout)

    # Set sandbox args for session re-execution
    virtualizedproc.subprocess_sandbox_args = sandbox_args

    # Capture script path from arguments (look for .py files after the executable)
    script_args = [a for a in arguments[1:] if a.endswith(".py")]
    if script_args:
        virtualizedproc.subprocess_script_path = script_args[0]
        # Try to read script content from VFS if tmp is mapped
        if sandbox_args.get("tmp"):
            import os

            real_script_path = os.path.join(sandbox_args["tmp"], os.path.basename(script_args[0]))
            if os.path.exists(real_script_path):
                try:
                    with open(real_script_path, "r") as f:
                        virtualizedproc.subprocess_script_content = f.read()
                except Exception:
                    pass

    virtualizedproc.run()

    # Session finalization for dry-run mode
    if SandboxedProc.subprocess_dry_run:
        session = virtualizedproc.finalize_session()
        if session:
            print(f"\n*** Session created: {session.id} ***")
            print(f"    Commands queued: {len(session.commands)}")
            print(f"    Run 'shannot-approve' to review and execute.")
        else:
            print("\n*** No commands were queued. ***")

    popen.terminate()
    popen.wait()
    if popen.returncode == 0:
        return 0
    else:
        print(
            "*** sandboxed subprocess finished with exit code %r ***"
            % (popen.returncode,)
        )
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
