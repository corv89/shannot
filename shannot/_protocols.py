"""Type protocols for mixin patterns.

These protocols define the interface that mixins expect from the composed class.
They are used only for type checking and have no runtime effect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .mix_vfs import Dir
    from .sandboxio import Ptr, SandboxedIO


class HasSandio(Protocol):
    """Protocol for classes that provide sandio attribute."""

    sandio: SandboxedIO
    debug_errors: bool


class HasVFSRoot(Protocol):
    """Protocol for classes that provide vfs_root attribute."""

    vfs_root: Dir


class HasSyscallRead(Protocol):
    """Protocol for classes that provide s_read syscall handler."""

    def s_read(self, fd: int, p_buf: Ptr, count: int) -> int:
        raise NotImplementedError


class HasSyscallWrite(Protocol):
    """Protocol for classes that provide s_write syscall handler."""

    def s_write(self, fd: int, p_buf: Ptr, count: int) -> int:
        raise NotImplementedError


class HasSyscallFstat(Protocol):
    """Protocol for classes that provide s_fstat64 syscall handler."""

    def s_fstat64(self, fd: int, p_statbuf: Ptr) -> int:
        raise NotImplementedError
