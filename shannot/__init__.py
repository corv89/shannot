# Lazy imports to avoid ~30ms startup overhead from virtualizedproc/platform/ctypes
# These are only loaded when actually accessed

__all__ = ["VirtualizedProc", "sigerror", "signature"]


def __getattr__(name: str):
    if name in ("VirtualizedProc", "sigerror", "signature"):
        from . import virtualizedproc

        return getattr(virtualizedproc, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
