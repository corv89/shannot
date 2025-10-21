"""
Foundational utilities for constructing and executing read-only sandbox sessions.

This module intentionally focuses on declarative configuration and pure data
structures so higher-level entrypoints (e.g. ``sandbox.py``) can
remain small and testable. The initial implementation is designed around the
Bubblewrap (`bwrap`) tool because it offers fine-grained control over Linux
namespaces, bind mounts, and seccomp integration without depending on a daemon.

Key abstractions
----------------
* ``SandboxProfile`` — Immutable description of the sandbox. Profiles are kept
  independent from execution details so they can be serialized, linted, and
  unit-tested in isolation.
* ``BubblewrapCommandBuilder`` — Translates a ``SandboxProfile`` plus the
  caller's requested command into a deterministic ``bwrap`` argument vector.
* ``SandboxManager`` — Coordinates validation and invocation; exact runtime
  mechanics will be implemented in a future revision once profile parsing,
  command building, and testing scaffolding are in place.

The goal of this scaffolding is to provide well-documented, type-checked hooks
that subsequent work can extend without refactoring prior code.
"""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Mapping, MutableSequence, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .process import ProcessResult, run_process

if TYPE_CHECKING:
    from shannot.execution import SandboxExecutor

__all__ = [
    "SandboxError",
    "SandboxBind",
    "SandboxProfile",
    "BubblewrapCommandBuilder",
    "SandboxManager",
    "load_profile_from_mapping",
    "load_profile_from_path",
]


class SandboxError(RuntimeError):
    """Raised when sandbox configuration or execution fails."""


@dataclass(frozen=True)
class SandboxBind:
    """
    Describe a bind mount that should be applied inside the sandbox.

    Parameters
    ----------
    source:
        Path on the host that will be mounted into the sandbox.
    target:
        Path inside the sandbox where the source will be exposed.
    read_only:
        Whether the bind should be read-only. Defaults to ``True``.
    create_target:
        Whether the target path should be created inside the sandbox prior to
        the bind. When ``True``, the Bubblewrap command builder will insert the
        necessary ``--dir`` or ``--file`` directives.
    """

    source: Path
    target: Path
    read_only: bool = True
    create_target: bool = True

    def validate(self) -> None:
        """Ensure the bind definition is structurally sound."""
        if not self.source.is_absolute():
            raise SandboxError(f"Bind source must be absolute: {self.source}")
        if not self.target.is_absolute():
            raise SandboxError(f"Bind target must be absolute: {self.target}")


def _normalize_base_path(base_path: Path | str | None) -> Path | None:
    """Return an absolute Path for ``base_path`` when provided."""
    if base_path is None:
        return None
    candidate = Path(base_path)
    if not candidate.is_absolute():
        candidate = candidate.resolve()
    return candidate


def _require_string(value: object, *, field_name: str) -> str:
    """Ensure ``value`` is a non-empty string."""
    if not isinstance(value, str) or not value:
        raise SandboxError(f"{field_name} must be a non-empty string.")
    return value


def _coerce_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    """Convert ``value`` into a tuple of non-empty strings."""
    if value is None:
        return tuple()
    if isinstance(value, str | bytes):
        raise SandboxError(f"{field_name} must be a sequence of strings.")
    if not isinstance(value, Sequence):
        raise SandboxError(f"{field_name} must be a sequence of strings.")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise SandboxError(f"{field_name}[{index}] must be a non-empty string.")
        result.append(item)
    return tuple(result)


def _coerce_bool(value: object, *, field_name: str, default: bool) -> bool:
    """Return a boolean value or fall back to ``default`` when ``value`` is ``None``."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise SandboxError(f"{field_name} must be a boolean value.")


def _coerce_path(value: object, *, field_name: str) -> Path:
    """Coerce ``value`` into a ``Path`` instance."""
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    raise SandboxError(f"{field_name} must be a non-empty string or Path.")


def _absolutize_path(path: Path, *, field_name: str, base_path: Path | None) -> Path:
    """Return an absolute path, using ``base_path`` when ``path`` is relative."""
    if path.is_absolute():
        return path
    if base_path is None:
        raise SandboxError(f"{field_name} must be absolute: {path}")
    return (base_path / path).resolve()


def _coerce_optional_path(
    value: object,
    *,
    field_name: str,
    base_path: Path | None,
) -> Path | None:
    """Coerce optional path fields to absolute ``Path`` instances."""
    if value is None:
        return None
    path = _coerce_path(value, field_name=field_name)
    return _absolutize_path(path, field_name=field_name, base_path=base_path)


def _coerce_path_sequence(
    value: object,
    *,
    field_name: str,
    base_path: Path | None,
) -> tuple[Path, ...]:
    """Convert ``value`` into a tuple of absolute paths."""
    if value is None:
        return tuple()
    if isinstance(value, str | bytes):
        raise SandboxError(f"{field_name} must be a sequence of paths.")
    if not isinstance(value, Sequence):
        raise SandboxError(f"{field_name} must be a sequence of paths.")
    paths: list[Path] = []
    for index, item in enumerate(value):
        member = _coerce_path(item, field_name=f"{field_name}[{index}]")
        paths.append(
            _absolutize_path(member, field_name=f"{field_name}[{index}]", base_path=base_path)
        )
    return tuple(paths)


def _coerce_environment_mapping(value: object, *, field_name: str) -> Mapping[str, str]:
    """Coerce ``value`` into a mapping of string keys and values."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise SandboxError(f"{field_name} must be a mapping of strings.")
    environment: dict[str, str] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str) or not key:
            raise SandboxError(f"{field_name} keys must be non-empty strings.")
        if not isinstance(raw_value, str):
            raise SandboxError(f"{field_name}[{key}] must be a string.")
        environment[key] = raw_value
    return environment


def _coerce_binds(value: object, *, base_path: Path | None) -> tuple[SandboxBind, ...]:
    """Convert ``value`` into a tuple of ``SandboxBind`` entries."""
    if value is None:
        return tuple()
    if isinstance(value, str | bytes):
        raise SandboxError("binds must be a sequence of mappings.")
    if not isinstance(value, Sequence):
        raise SandboxError("binds must be a sequence of mappings.")
    binds: list[SandboxBind] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, Mapping):
            raise SandboxError(f"binds[{index}] must be a mapping.")
        if "source" not in entry:
            raise SandboxError(f"binds[{index}] must define 'source'.")
        if "target" not in entry:
            raise SandboxError(f"binds[{index}] must define 'target'.")
        source = _absolutize_path(
            _coerce_path(entry["source"], field_name=f"binds[{index}].source"),
            field_name=f"binds[{index}].source",
            base_path=base_path,
        )
        target = _absolutize_path(
            _coerce_path(entry["target"], field_name=f"binds[{index}].target"),
            field_name=f"binds[{index}].target",
            base_path=base_path,
        )
        read_only = _coerce_bool(
            entry.get("read_only"), field_name=f"binds[{index}].read_only", default=True
        )
        create_target = _coerce_bool(
            entry.get("create_target"),
            field_name=f"binds[{index}].create_target",
            default=True,
        )
        binds.append(
            SandboxBind(
                source=source,
                target=target,
                read_only=read_only,
                create_target=create_target,
            )
        )
    return tuple(binds)


@dataclass(frozen=True)
class SandboxProfile:
    """
    Declarative description of the sandboxing policy.

    Only simple, serializable datatypes are used so that profiles can be loaded
    from YAML or JSON documents without custom hooks. Future iterations may add
    convenience constructors (e.g. ``from_mapping``) once the serialization
    format is finalized.

    Parameters
    ----------
    name:
        Human-readable identifier for logging and auditing.
    allowed_commands:
        Shell globs or absolute paths that the caller is permitted to execute.
        Allowlist enforcement is performed by higher-level orchestrators.
    binds:
        Collection of ``SandboxBind`` entries describing mount topology.
    tmpfs_paths:
        Directories that should be backed by tmpfs for ephemeral storage.
    environment:
        Environment variables to expose inside the sandbox.
    seccomp_profile:
        Optional path to a seccomp JSON profile consumed by ``bwrap``.
    network_isolation:
        When ``True``, the sandbox is expected to execute within an isolated
        network namespace (e.g. ``--unshare-net``).
    user_namespace_isolation:
        When ``True``, use user namespace isolation (``--unshare-user``).
        May need to be disabled in some environments (e.g., restrictive kernels).
    additional_args:
        Extra ``bwrap`` arguments to append verbatim. Useful for experimental
        tuning while the profile format is still evolving.
    """

    name: str
    allowed_commands: Sequence[str] = field(default_factory=tuple)
    binds: Sequence[SandboxBind] = field(default_factory=tuple)
    tmpfs_paths: Sequence[Path] = field(default_factory=tuple)
    environment: Mapping[str, str] = field(default_factory=dict)
    seccomp_profile: Path | None = None
    network_isolation: bool = True
    user_namespace_isolation: bool = True
    additional_args: Sequence[str] = field(default_factory=tuple)

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, object],
        *,
        base_path: Path | str | None = None,
    ) -> SandboxProfile:
        """Construct a ``SandboxProfile`` from a plain mapping."""
        # Note: data is already typed as Mapping[str, object], so isinstance check is redundant
        normalized_base = _normalize_base_path(base_path)
        name = _require_string(data.get("name"), field_name="name")
        allowed_commands = _coerce_string_sequence(
            data.get("allowed_commands"),
            field_name="allowed_commands",
        )
        binds = _coerce_binds(
            data.get("binds"),
            base_path=normalized_base,
        )
        tmpfs_paths = _coerce_path_sequence(
            data.get("tmpfs_paths"),
            field_name="tmpfs_paths",
            base_path=normalized_base,
        )
        environment = dict(
            _coerce_environment_mapping(
                data.get("environment"),
                field_name="environment",
            )
        )
        seccomp_profile = _coerce_optional_path(
            data.get("seccomp_profile"),
            field_name="seccomp_profile",
            base_path=normalized_base,
        )
        network_isolation = _coerce_bool(
            data.get("network_isolation"),
            field_name="network_isolation",
            default=True,
        )
        user_namespace_isolation = _coerce_bool(
            data.get("user_namespace_isolation"),
            field_name="user_namespace_isolation",
            default=True,
        )
        additional_args = _coerce_string_sequence(
            data.get("additional_args"),
            field_name="additional_args",
        )
        profile = cls(
            name=name,
            allowed_commands=allowed_commands,
            binds=binds,
            tmpfs_paths=tmpfs_paths,
            environment=environment,
            seccomp_profile=seccomp_profile,
            network_isolation=network_isolation,
            user_namespace_isolation=user_namespace_isolation,
            additional_args=additional_args,
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        """Raise ``SandboxError`` if the profile contains invalid entries."""
        if not self.name:
            raise SandboxError("Sandbox profile must have a non-empty name.")

        for pattern in self.allowed_commands:
            if not pattern:
                raise SandboxError("Allowed command patterns may not be empty.")

        for bind in self.binds:
            bind.validate()

        for tmpfs_path in self.tmpfs_paths:
            if not tmpfs_path.is_absolute():
                raise SandboxError(f"tmpfs mount must target absolute path: {tmpfs_path}")

        if self.seccomp_profile is not None and not self.seccomp_profile.is_absolute():
            raise SandboxError(f"Seccomp profile path must be absolute: {self.seccomp_profile}")

        for arg in self.additional_args:
            if not arg:
                raise SandboxError("Additional Bubblewrap arguments cannot be empty.")


def load_profile_from_mapping(
    data: Mapping[str, object],
    *,
    base_path: Path | str | None = None,
) -> SandboxProfile:
    """Create a ``SandboxProfile`` from an in-memory mapping."""
    # TODO: Provide a YAML loader that reuses this helper for parity with JSON profiles.
    return SandboxProfile.from_mapping(data, base_path=base_path)


def load_profile_from_path(path: Path | str) -> SandboxProfile:
    """Load a ``SandboxProfile`` from a JSON configuration file."""
    candidate = Path(path).expanduser()
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        raise SandboxError(f"Unable to read sandbox profile file: {candidate}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SandboxError(f"Sandbox profile file {candidate} is not valid JSON.") from exc
    if not isinstance(raw, Mapping):
        raise SandboxError("Sandbox profile file must contain a JSON object.")
    base_path = _normalize_base_path(candidate.parent)
    return SandboxProfile.from_mapping(raw, base_path=base_path)


class BubblewrapCommandBuilder:
    """
    Convert a ``SandboxProfile`` into a Bubblewrap command invocation.

    The builder performs deterministic argument ordering so unit tests can make
    stable assertions. At this stage the builder does not consider runtime
    details (e.g. existence of certain directories); those checks belong in the
    eventual executor.

    Parameters
    ----------
    profile:
        ``SandboxProfile`` describing the desired sandbox configuration.
    command:
        Sequence representing the command to run inside the sandbox. This is
        appended after ``--`` in the resulting Bubblewrap invocation.
    validate_paths:
        Whether to validate that bind source paths exist locally. Set to False
        for remote execution where paths exist on the remote system only.
        Defaults to True for backward compatibility.
    """

    def __init__(
        self,
        profile: SandboxProfile,
        command: Sequence[str],
        validate_paths: bool = True,
    ) -> None:
        profile.validate()
        if not command:
            raise SandboxError("Sandbox command must not be empty.")

        self._profile: SandboxProfile = profile
        self._command: tuple[str, ...] = tuple(command)
        self._validate_paths: bool = validate_paths

    def build(self) -> list[str]:
        """
        Return the complete ``bwrap`` argument list without the executable name.

        The caller is responsible for prepending the path to the Bubblewrap
        binary (commonly ``/usr/bin/bwrap``) prior to execution.
        """
        args: MutableSequence[str] = []

        # Namespace isolation
        args.append("--die-with-parent")

        # Use granular unsharing instead of --unshare-all to handle isolation flags
        if self._profile.network_isolation:
            args.append("--unshare-net")
        if self._profile.user_namespace_isolation:
            args.append("--unshare-user")
        args.append("--unshare-ipc")
        args.append("--unshare-pid")
        args.append("--unshare-uts")
        args.append("--unshare-cgroup")

        # Standard mounts.
        args.extend(("--proc", "/proc"))
        args.extend(("--dev", "/dev"))

        # tmpfs mounts.
        for tmpfs_path in sorted(self._profile.tmpfs_paths):
            args.extend(("--tmpfs", str(tmpfs_path)))

        # Bind mounts.
        for bind in sorted(self._profile.binds, key=lambda b: str(b.target)):
            # Skip binds where the source doesn't exist (only when validating paths)
            if self._validate_paths and not bind.source.exists():
                continue
            if bind.create_target:
                args.extend(("--dir", str(bind.target)))
            flag = "--ro-bind" if bind.read_only else "--bind"
            args.extend((flag, str(bind.source), str(bind.target)))

        # Environment variables.
        for key in sorted(self._profile.environment):
            args.extend(("--setenv", key, self._profile.environment[key]))

        # Seccomp profile.
        if self._profile.seccomp_profile is not None:
            args.extend(("--seccomp", str(self._profile.seccomp_profile)))

        # Additional arguments supplied verbatim.
        args.extend(self._profile.additional_args)

        # Command separator.
        args.append("--")
        args.extend(self._command)
        return list(args)


class SandboxManager:
    """
    Orchestrate sandbox validation and execution.

    The SandboxManager can now use different execution strategies via the
    executor parameter. This allows for local execution (LocalExecutor) or
    remote execution (SSHExecutor) while maintaining backward compatibility.

    Parameters
    ----------
    profile:
        The profile to use when launching sandboxed commands.
    bubblewrap_path:
        Filesystem location of the Bubblewrap executable.
        Used for backward compatibility when executor is not provided.
    executor:
        Optional executor instance (LocalExecutor or SSHExecutor).
        If not provided, uses legacy direct execution with bubblewrap_path.

    Examples
    --------
    Legacy usage (backward compatible):
        >>> manager = SandboxManager(profile, Path("/usr/bin/bwrap"))
        >>> result = manager.run(["ls", "/"])

    New usage with LocalExecutor:
        >>> from shannot.executors import LocalExecutor
        >>> executor = LocalExecutor()
        >>> manager = SandboxManager(profile, executor=executor)
        >>> result = manager.run(["ls", "/"])

    New usage with SSHExecutor:
        >>> from shannot.executors import SSHExecutor
        >>> executor = SSHExecutor(host="prod.example.com")
        >>> manager = SandboxManager(profile, executor=executor)
        >>> result = manager.run(["ls", "/"])
    """

    def __init__(
        self,
        profile: SandboxProfile,
        bubblewrap_path: Path | None = None,
        executor: SandboxExecutor | None = None,
    ) -> None:
        profile.validate()
        self._profile: SandboxProfile = profile
        self._executor: SandboxExecutor | None = executor

        # Legacy mode: use bubblewrap_path directly
        if executor is None:
            if bubblewrap_path is None:
                raise SandboxError("Either bubblewrap_path or executor must be provided")
            if not bubblewrap_path.is_absolute():
                raise SandboxError("Bubblewrap path must be absolute.")
            resolved = bubblewrap_path.resolve()
            if not resolved.exists():
                raise SandboxError(f"Bubblewrap executable not found at {resolved}")
            self._bubblewrap_path: Path | None = resolved
        else:
            # New mode: use executor
            self._bubblewrap_path = bubblewrap_path

    @property
    def profile(self) -> SandboxProfile:
        """Return the active sandbox profile."""
        return self._profile

    @property
    def bubblewrap_path(self) -> Path | None:
        """Return the resolved Bubblewrap executable path.

        Returns None when using an executor instead of direct bubblewrap_path.
        """
        return self._bubblewrap_path

    @property
    def executor(self) -> SandboxExecutor | None:
        """Return the executor if one is configured."""
        return self._executor

    def build_command(self, command: Sequence[str]) -> list[str]:
        """
        Construct the full Bubblewrap invocation for the requested command.

        The returned list includes the Bubblewrap executable at index 0 followed
        by the arguments produced by ``BubblewrapCommandBuilder``.

        Note: Only used in legacy mode (when executor is None).
        """
        if self._bubblewrap_path is None:
            raise SandboxError("bubblewrap_path not available when using executor")
        builder = BubblewrapCommandBuilder(self._profile, command)
        return [str(self._bubblewrap_path), *builder.build()]

    def _is_command_allowed(self, candidate: str) -> bool:
        """Return True when ``candidate`` matches an allowed command pattern."""
        if not self._profile.allowed_commands:
            return True
        return any(
            fnmatch.fnmatch(candidate, pattern) for pattern in self._profile.allowed_commands
        )

    def run(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        """
        Execute ``command`` inside the sandbox and return a ``ProcessResult``.

        Parameters
        ----------
        command:
            Command and arguments to execute within the sandbox.
        check:
            When ``True`` (default), raise ``SandboxError`` if the command exits
            with a non-zero status.
        env:
            Optional environment overrides passed to the Bubblewrap launcher.

        Raises
        ------
        SandboxError
            Raised when the command is not permitted or exits with a non-zero
            status while ``check`` is enabled.
        """
        import subprocess

        if not command:
            raise SandboxError("Sandbox command must not be empty.")
        executable = command[0]
        if not self._is_command_allowed(executable):
            raise SandboxError(
                f"Command '{executable}' is not permitted by sandbox profile "
                f"'{self._profile.name}'."
            )

        # Build the base command
        invocation = self.build_command(command)

        # Handle seccomp file descriptor if profile specifies one
        if self._profile.seccomp_profile is not None:
            # Open the seccomp file and pass its FD to bwrap
            with open(self._profile.seccomp_profile, "rb") as seccomp_file:
                fd_num = seccomp_file.fileno()
                # Replace the path in invocation with actual FD number
                try:
                    idx = invocation.index("--seccomp")
                    if idx + 1 < len(invocation):
                        invocation[idx + 1] = str(fd_num)
                except ValueError:
                    pass  # --seccomp not in args

                # Run with the file descriptor passed to subprocess
                import time

                process_env = dict(env) if env else {}
                start_time = time.monotonic()
                result_proc = subprocess.run(
                    invocation,
                    env=process_env if process_env else None,
                    capture_output=True,
                    check=False,
                    pass_fds=(fd_num,),
                )
                duration = time.monotonic() - start_time
                result = ProcessResult(
                    command=tuple(invocation),
                    returncode=result_proc.returncode,
                    stdout=result_proc.stdout.decode("utf-8", errors="replace")
                    if result_proc.stdout
                    else "",
                    stderr=result_proc.stderr.decode("utf-8", errors="replace")
                    if result_proc.stderr
                    else "",
                    duration=duration,
                )
        else:
            # No seccomp, run normally
            result = run_process(invocation, env=env, capture_output=True, check=False)

        if check and not result.succeeded():
            error_msg = f"Sandbox command failed with exit code {result.returncode}: {executable}"
            if result.stderr:
                error_msg += f"\nStderr: {result.stderr.strip()}"

                # Detect common environment issues
                if (
                    "setting up uid map: Permission denied" in result.stderr
                    or "Failed RTM_NEWADDR: Operation not permitted" in result.stderr
                ):
                    error_msg += (
                        "\n\nUSER NAMESPACE ISSUE: Unprivileged user namespace creation is blocked"
                        "\n"
                        "\nCommon causes:"
                        "\n  1. Ubuntu 24.04+ has AppArmor restricting unprivileged user namespaces"
                        "\n  2. Kernel user namespace support is disabled"
                        "\n  3. Running in a restricted container/VM environment"
                        "\n"
                        "\nSolutions (in order of preference):"
                        "\n"
                        "\n  Ubuntu 24.04+ (AppArmor restriction):"
                        "\n    sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
                        "\n    echo 'kernel.apparmor_restrict_unprivileged_userns=0' | "
                        "sudo tee -a /etc/sysctl.conf"
                        "\n"
                        "\n  Other distros (check if enabled):"
                        "\n    cat /proc/sys/kernel/unprivileged_userns_clone  # should be 1"
                        "\n    cat /proc/sys/user/max_user_namespaces          # should be > 0"
                        "\n"
                        "\n  Enable if needed:"
                        "\n    sudo sysctl -w kernel.unprivileged_userns_clone=1"
                        "\n    echo 'kernel.unprivileged_userns_clone=1' | "
                        "sudo tee -a /etc/sysctl.conf"
                        "\n"
                        "\nFor more details, see:"
                        "\n  https://github.com/corv89/shannot/blob/main/docs/troubleshooting.md"
                    )
                elif "pivot_root: Operation not permitted" in result.stderr:
                    error_msg += (
                        "\n\nENVIRONMENT ISSUE: pivot_root is not permitted"
                        "\nThis usually means you're running in a restricted container environment"
                        "\n(e.g., GitHub Codespaces, Docker, or Kubernetes)."
                        "\n"
                        "\nBubblewrap requires CAP_SYS_ADMIN capability to create namespaces."
                        "\nThis is typically not available in container environments for security."
                        "\n"
                        "\nSolutions:"
                        "\n  1. Use a real Linux VM instead of a container"
                        "\n  2. Use WSL2 on Windows (supports user namespaces)"
                        "\n  3. Run on native Linux (Ubuntu, Fedora, etc.)"
                        "\n  4. Enable privileged containers (not recommended)"
                    )
                elif "Operation not permitted" in result.stderr:
                    error_msg += (
                        "\n\nHint: This may be a permissions or capability issue."
                        "\nCheck if user namespaces are enabled:"
                        "\n  cat /proc/sys/kernel/unprivileged_userns_clone"
                        "\n  cat /proc/sys/user/max_user_namespaces"
                    )
            if not result.stderr and not result.stdout:
                error_msg += "\n(No output captured - command may require stdin or file not found)"
            raise SandboxError(error_msg)
        return result

    async def run_async(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
        timeout: int = 30,
    ) -> ProcessResult:
        """
        Execute ``command`` inside the sandbox asynchronously using an executor.

        This method requires an executor to be configured. It delegates execution
        to the executor, which can be LocalExecutor (for local execution) or
        SSHExecutor (for remote execution).

        Parameters
        ----------
        command:
            Command and arguments to execute within the sandbox.
        check:
            When ``True`` (default), raise ``SandboxError`` if the command exits
            with a non-zero status.
        timeout:
            Command timeout in seconds (default: 30).

        Raises
        ------
        SandboxError
            Raised when the command is not permitted, no executor is configured,
            or the command exits with a non-zero status while ``check`` is enabled.

        Examples
        --------
        With LocalExecutor:
            >>> from shannot.executors import LocalExecutor
            >>> executor = LocalExecutor()
            >>> manager = SandboxManager(profile, executor=executor)
            >>> result = await manager.run_async(["ls", "/"])

        With SSHExecutor:
            >>> from shannot.executors import SSHExecutor
            >>> executor = SSHExecutor(host="prod.example.com")
            >>> manager = SandboxManager(profile, executor=executor)
            >>> result = await manager.run_async(["ls", "/"])
        """
        if self._executor is None:
            raise SandboxError(
                "run_async() requires an executor. Either provide an executor "
                "during initialization or use the synchronous run() method."
            )

        if not command:
            raise SandboxError("Sandbox command must not be empty.")

        executable = command[0]
        if not self._is_command_allowed(executable):
            raise SandboxError(
                f"Command '{executable}' is not permitted by sandbox profile "
                f"'{self._profile.name}'."
            )

        # Use executor to run command
        result = await self._executor.run_command(self._profile, list(command), timeout=timeout)

        if check and not result.succeeded():
            raise SandboxError(
                f"Sandbox command failed with exit code {result.returncode}: {executable}"
            )
        return result
