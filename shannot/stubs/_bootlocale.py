# _bootlocale.py
# Stub for _bootlocale module in sandbox
# Always returns UTF-8 encoding (safe default for sandbox environment)


def getpreferredencoding(do_setlocale=True):
    """Return preferred encoding - always UTF-8 in sandbox."""
    return "UTF-8"
