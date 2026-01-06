# subprocess.py
# Minimal subprocess implementation for sandbox
# Routes through os.system() which controller intercepts

import os

PIPE = -1
STDOUT = -2
DEVNULL = -3


class CompletedProcess:
    def __init__(self, args, returncode, stdout=None, stderr=None):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run(
    args,
    capture_output=False,
    text=False,
    shell=False,
    cwd=None,
    env=None,
    timeout=None,
    check=False,
    stdin=None,
    stdout=None,
    stderr=None,
    **kwargs,
):
    if isinstance(args, str):
        cmd = args
    else:
        cmd = " ".join(str(a) for a in args)

    stdout_data = None
    stderr_data = None

    if capture_output or stdout == PIPE:
        stdout_file = "/tmp/_shannot_stdout.tmp"
        stderr_file = "/tmp/_shannot_stderr.tmp"
        cmd = f"{cmd} > {stdout_file} 2> {stderr_file}"

        returncode = os.system(cmd)
        returncode = returncode >> 8  # Extract actual exit code

        try:
            with open(stdout_file, "rb") as f:
                stdout_data = f.read()
            with open(stderr_file, "rb") as f:
                stderr_data = f.read()
        except OSError:
            stdout_data = b""
            stderr_data = b""

        if text:
            stdout_data = stdout_data.decode("utf-8", errors="replace")
            stderr_data = stderr_data.decode("utf-8", errors="replace")
    else:
        returncode = os.system(cmd) >> 8

    result = CompletedProcess(args, returncode, stdout_data, stderr_data)

    if check and returncode != 0:
        raise CalledProcessError(returncode, args, stdout_data, stderr_data)

    return result


def check_output(args, *, stdin=None, stderr=None, shell=False, cwd=None, timeout=None, **kwargs):
    """Run command and return output, raising CalledProcessError on failure."""
    result = run(args, capture_output=True, shell=shell, cwd=cwd, timeout=timeout, check=True)
    return result.stdout


class CalledProcessError(Exception):
    def __init__(self, returncode, cmd, stdout=None, stderr=None):
        self.returncode = returncode
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        return f"Command '{self.cmd}' returned non-zero exit status {self.returncode}"


# Popen - minimal implementation
class Popen:
    def __init__(self, args, **kwargs):
        self.args = args
        self.returncode = None
        self._stdout = None
        self._stderr = None

    def communicate(self, input=None, timeout=None):
        result = run(self.args, capture_output=True)
        self.returncode = result.returncode
        return result.stdout, result.stderr

    def wait(self, timeout=None):
        if self.returncode is None:
            result = run(self.args)
            self.returncode = result.returncode
        return self.returncode

    def poll(self):
        return self.returncode
