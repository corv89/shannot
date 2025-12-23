# _signal.py
# Stub to let subprocess import in sandbox

SIGINT = 2
SIGTERM = 15
SIGKILL = 9
SIGCHLD = 17
SIGHUP = 1
SIGPIPE = 13
SIGALRM = 14
SIGUSR1 = 10
SIGUSR2 = 12

SIG_DFL = 0
SIG_IGN = 1


def signal(sig, handler):
    return SIG_DFL


def getsignal(sig):
    return SIG_DFL


def default_int_handler(*args):
    raise KeyboardInterrupt


def raise_signal(sig):
    pass


def set_wakeup_fd(fd, warn_on_full_buffer=True):
    return -1


# Python 3.5+
class Signals:
    pass


class Handlers:
    pass


def valid_signals():
    return set()
