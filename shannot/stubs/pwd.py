# pwd.py
# Stub for pwd module in sandbox
# Provides minimal password database functionality for posixpath.expanduser()

import os
import sys
from collections import namedtuple

struct_passwd = namedtuple(
    "struct_passwd", ["pw_name", "pw_uid", "pw_gid", "pw_gecos", "pw_dir", "pw_shell"]
)

# Platform-specific defaults
_IS_MACOS = sys.platform == "darwin"
_ROOT_HOME = "/var/root" if _IS_MACOS else "/root"


def _get_user_home():
    """Get user home from environment or use platform default."""
    home = os.environ.get("HOME")
    if home:
        return home
    return "/Users/user" if _IS_MACOS else "/home/user"


def _get_username():
    """Get username from environment or default."""
    return os.environ.get("USER", "user")


def getpwuid(uid):
    """Return password database entry for given UID."""
    if uid == os.getuid():
        return struct_passwd(_get_username(), uid, uid, "User", _get_user_home(), "/bin/sh")
    if uid == 0:
        return struct_passwd("root", 0, 0, "System Administrator", _ROOT_HOME, "/bin/sh")
    raise KeyError(f"getpwuid(): uid not found: {uid}")


def getpwnam(name):
    """Return password database entry for given user name."""
    username = _get_username()
    if name == username:
        uid = os.getuid()
        return struct_passwd(username, uid, uid, "User", _get_user_home(), "/bin/sh")
    if name == "root":
        return struct_passwd("root", 0, 0, "System Administrator", _ROOT_HOME, "/bin/sh")
    raise KeyError(f"getpwnam(): name not found: '{name}'")


def getpwall():
    """Return list of all password database entries."""
    uid = os.getuid()
    return [
        struct_passwd("root", 0, 0, "System Administrator", _ROOT_HOME, "/bin/sh"),
        struct_passwd(_get_username(), uid, uid, "User", _get_user_home(), "/bin/sh"),
    ]
