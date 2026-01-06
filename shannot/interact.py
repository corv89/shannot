"""
Sandbox process controller.

Internal module - use 'shannot run' CLI instead.
"""

import subprocess
import sys

from shannot import VirtualizedProc
from shannot.mix_accept_input import MixAcceptInput
from shannot.mix_dump_output import MixDumpOutput
from shannot.mix_pypy import MixPyPy
from shannot.mix_remote import MixRemote
from shannot.mix_subprocess import MixSubprocess
from shannot.mix_vfs import Dir, MixVFS, RealDir
from shannot.vfs_procfs import build_proc, build_sys


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
            "session-id=",
            "script-name=",
            "analysis=",
            "target=",
            "json-output",
            "approved-commands=",
            "code=",
        ],
    )

    def help():
        sys.stderr.write(
            "Usage: shannot run [options] <script.py> [args...]\n"
            "See 'shannot run --help' for details.\n"
        )
        return 2

    if len(arguments) < 1:
        return help()

    class SandboxedProc(
        MixRemote, MixSubprocess, MixPyPy, MixVFS, MixDumpOutput, MixAcceptInput, VirtualizedProc
    ):
        virtual_cwd = "/tmp"
        vfs_root = Dir({"tmp": Dir({})})

    color = True
    raw_stdout = False
    json_output = False
    approved_commands = []
    inline_code = None  # For -c flag
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
        "target": None,
    }

    lib_path_specified = False
    session_id = None

    for option, value in options:
        if option == "--tmp":
            SandboxedProc.vfs_root.entries["tmp"] = RealDir(value)
            sandbox_args["tmp"] = value
        elif option == "--lib-path":
            lib_path_specified = True
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
            SandboxedProc.vfs_track_writes = True  # Track file writes for approval
            SandboxedProc.vfs_track_deletions = True  # Track file deletions for approval
        elif option == "--session-id":
            session_id = value
            # Enable tracking for session execution (writes/deletions committed after)
            SandboxedProc.vfs_track_writes = True
            SandboxedProc.vfs_track_deletions = True
        elif option == "--script-name":
            SandboxedProc.subprocess_script_name = value  # type: ignore[misc]
            sandbox_args["script_name"] = value
        elif option == "--analysis":
            SandboxedProc.subprocess_analysis = value  # type: ignore[misc]
            sandbox_args["analysis"] = value
        elif option == "--target":
            SandboxedProc.remote_target = value
            sandbox_args["target"] = value
        elif option == "--json-output":
            json_output = True
        elif option == "--approved-commands":
            import json as json_module

            approved_commands = json_module.loads(value)
        elif option == "--code":
            inline_code = value
        elif option in ["-h", "--help"]:
            return help()
        else:
            raise ValueError(option)

    # Validate executable argument (basic checks)
    import os

    if not os.path.exists(executable):
        sys.stderr.write(f"Error: PyPy sandbox executable not found: {executable}\n\n")
        sys.stderr.write("Specify a valid path with --pypy-sandbox or ensure it's in PATH.\n")
        return 1

    if not os.access(executable, os.X_OK):
        sys.stderr.write(f"Error: PyPy sandbox executable is not executable: {executable}\n\n")
        sys.stderr.write("Fix permissions with:\n")
        sys.stderr.write(f"  chmod +x {executable}\n")
        return 1

    # Read script content - either from --code or from file
    # Script will be injected into VFS after instance creation
    script_content: bytes | None = None
    script_arg_idx: int | None = None

    if inline_code is not None:
        # -c flag: use inline code directly
        script_content = inline_code.encode("utf-8")
        # Add virtual script path to arguments
        arguments.append("/script.py")
    else:
        # Find script file in arguments and read it
        for i, arg in enumerate(arguments[1:], 1):
            if arg.endswith(".py") and not arg.startswith("-"):
                if os.path.exists(arg):
                    with open(arg, "rb") as f:
                        script_content = f.read()
                    script_arg_idx = i
                break

        # Replace script path with virtual path
        if script_content is not None and script_arg_idx is not None:
            arguments[script_arg_idx] = "/script.py"

    # Prepend bootstrap imports for correct module initialization
    # _bootlocale must be imported early for text I/O encoding to work correctly
    if script_content is not None:
        bootstrap = b"import _bootlocale\n"
        script_content = bootstrap + script_content

    # Auto-detect runtime if --lib-path not specified
    if not lib_path_specified:
        from shannot.runtime import get_runtime_path

        runtime_path = get_runtime_path()
        if runtime_path:
            # Build VFS with stubs overlaid on lib_pypy
            from shannot.mix_vfs import File, OverlayDir
            from shannot.stubs import get_stubs

            stubs = {name: File(content) for name, content in get_stubs().items()}

            SandboxedProc.vfs_root.entries["lib"] = Dir(
                {
                    "pypy": File(b"", mode=0o111),
                    "lib-python": RealDir(str(runtime_path / "lib-python")),
                    "lib_pypy": OverlayDir(str(runtime_path / "lib_pypy"), overrides=stubs),
                }
            )
            arguments[0] = "/lib/pypy"
            sandbox_args["lib_path"] = str(runtime_path)
        else:
            # Runtime stdlib not found
            from shannot.config import RUNTIME_DIR

            sys.stderr.write("Error: PyPy stdlib not found.\n")
            sys.stderr.write(f"Expected location: {RUNTIME_DIR}\n\n")
            sys.stderr.write("The sandbox requires the PyPy stdlib (lib-python, lib_pypy).\n")
            sys.stderr.write("Run the following to install it:\n\n")
            sys.stderr.write("  shannot setup\n\n")
            sys.stderr.write("Or specify a custom path:\n")
            msg = "  shannot run --lib-path /path/to/pypy-stdlib /path/to/pypy-sandbox script.py\n"
            sys.stderr.write(msg)
            return 1

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

    # Mount home directory read-only
    home_path = os.path.expanduser("~")
    home_parts = home_path.strip("/").split("/")
    if len(home_parts) >= 2:
        parent_dir = home_parts[0]  # "Users" or "home"
        user_dir = home_parts[1]
        SandboxedProc.vfs_root.entries[parent_dir] = Dir(
            {user_dir: RealDir(home_path, show_dotfiles=True, follow_links=True)}
        )

    if SandboxedProc.debug_errors:
        popen1 = subprocess.Popen(
            arguments[:1],
            executable=executable,
            env={"RPY_SANDBOX_DUMP": "1"},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        vp = SandboxedProc(popen1.stdin, popen1.stdout)
        assert popen1.stdout is not None
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

    # Inject script into VFS (instance-level, not class)
    if script_content is not None:
        from .mix_vfs import File

        virtualizedproc.vfs_root.entries["script.py"] = File(script_content)

    # Set sandbox args for session re-execution
    virtualizedproc.subprocess_sandbox_args = sandbox_args

    # Capture script path and content for session metadata
    virtualizedproc.subprocess_script_path = "/script.py"  # type: ignore[misc]
    if script_content is not None:
        virtualizedproc.subprocess_script_content = script_content.decode("utf-8", errors="replace")  # type: ignore[misc]

    # Load security profile (populates auto_approve, always_deny)
    virtualizedproc.load_profile()

    # Add pre-approved commands (for recovery when remote session was cleaned up)
    if approved_commands:
        virtualizedproc.subprocess_approved.update(approved_commands)

    # Load session commands if re-executing an approved session
    # (must be after profile so session commands take precedence)
    if session_id:
        from shannot.session import Session

        try:
            session = Session.load(session_id)
            virtualizedproc.load_session_commands(session)
        except FileNotFoundError:
            sys.stderr.write(f"Warning: Session not found: {session_id}\n")

    virtualizedproc.run()

    # Session finalization for dry-run mode
    if SandboxedProc.subprocess_dry_run:
        session = virtualizedproc.finalize_session()

        if json_output:
            # JSON output for remote protocol
            import json as json_module

            from .config import get_version

            output = {
                "version": get_version(),
                "status": "pending",
                "session": {
                    "id": session.id,
                    "commands": session.commands,
                    "pending_writes": session.pending_writes,
                    "script_path": session.script_path,
                }
                if session
                else None,
            }
            print(json_module.dumps(output))
        elif session:
            print(f"\n*** Session created: {session.id} ***")
            print(f"    Commands queued: {len(session.commands)}")
            print(f"    File writes queued: {len(session.pending_writes)}")
            print(f"    Deletions queued: {len(session.pending_deletions)}")
            print("    Run 'shannot approve' to review and execute.")
        else:
            print("\n*** No commands or writes were queued. ***")

    # Wait for natural exit first (script finished, sandbox should exit)
    try:
        popen.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        # Sandbox hung, force terminate
        popen.terminate()
        popen.wait()

    # When executing a session, return execution results
    if session_id:
        return {
            "exit_code": popen.returncode,
            "executed_commands": virtualizedproc.get_execution_results(),
        }

    # Dry-run mode returns just exit code
    if popen.returncode == 0:
        return 0
    else:
        print(f"*** sandboxed subprocess finished with exit code {popen.returncode!r} ***")
        return 1
