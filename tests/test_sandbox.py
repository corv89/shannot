"""
Unit tests for the sandbox configuration and command builder utilities.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from shannot import (
    BubblewrapCommandBuilder,
    SandboxBind,
    SandboxError,
    SandboxProfile,
    load_profile_from_path,
)


class SandboxProfileTests(unittest.TestCase):
    """Validation and construction behaviour for SandboxProfile."""

    def _make_profile(self, **overrides: object) -> SandboxProfile:
        from typing import Any, cast

        kwargs: dict[str, Any] = {
            "name": "readonly",
            "allowed_commands": ("ls",),
            "binds": tuple(),
            "tmpfs_paths": tuple(),
            "environment": {"PATH": "/usr/bin"},
            "seccomp_profile": None,
            "network_isolation": True,
            "additional_args": tuple(),
        }
        kwargs.update(overrides)
        profile = SandboxProfile(
            name=cast(str, kwargs["name"]),
            allowed_commands=cast(tuple[str, ...], kwargs["allowed_commands"]),
            binds=cast(tuple[SandboxBind, ...], kwargs["binds"]),
            tmpfs_paths=cast(tuple[Path, ...], kwargs["tmpfs_paths"]),
            environment=cast(dict[str, str], kwargs["environment"]),
            seccomp_profile=cast(Path | None, kwargs["seccomp_profile"]),
            network_isolation=cast(bool, kwargs["network_isolation"]),
            additional_args=cast(tuple[str, ...], kwargs["additional_args"]),
        )
        return profile

    def test_validate_requires_non_empty_name(self) -> None:
        """Profiles must define a non-empty name."""
        profile = self._make_profile(name="")
        with self.assertRaises(SandboxError):
            profile.validate()

    def test_validate_rejects_relative_tmpfs_paths(self) -> None:
        """Relative tmpfs paths should be rejected."""
        profile = self._make_profile(tmpfs_paths=(Path("tmp"),))
        with self.assertRaises(SandboxError):
            profile.validate()

    def test_from_mapping_resolves_relative_paths(self) -> None:
        """Relative binds and seccomp profiles honour the provided base path."""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            base_dir = Path(tmpdir_str)
            mapping: dict[str, object] = {
                "name": "readonly",
                "allowed_commands": ["ls"],
                "binds": [
                    {
                        "source": "source",
                        "target": "/target",
                        "read_only": True,
                    }
                ],
                "tmpfs_paths": ["/tmp"],
                "seccomp_profile": "seccomp.bpf",
            }
            (base_dir / "source").mkdir()
            (base_dir / "seccomp.bpf").touch()

            profile = SandboxProfile.from_mapping(mapping, base_path=base_dir)

            self.assertTrue(profile.binds[0].source.is_absolute())
            # Resolve both paths to handle macOS /var -> /private/var symlink
            self.assertEqual(profile.binds[0].source.resolve(), (base_dir / "source").resolve())
            self.assertIsNotNone(profile.seccomp_profile)
            assert profile.seccomp_profile is not None  # Type narrowing for basedpyright
            self.assertTrue(profile.seccomp_profile.is_absolute())
            self.assertEqual(
                profile.seccomp_profile.resolve(), (base_dir / "seccomp.bpf").resolve()
            )

    def test_load_profile_from_path(self) -> None:
        """Loading a profile from a JSON file works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            profile_path = tmpdir / "profile.json"

            profile_data = {
                "name": "test-profile",
                "allowed_commands": ["ls", "cat"],
                "binds": [{"source": "/usr", "target": "/usr", "read_only": True}],
                "tmpfs_paths": ["/tmp"],
                "environment": {"PATH": "/usr/bin"},
                "network_isolation": True,
            }

            _ = profile_path.write_text(json.dumps(profile_data))

            profile = load_profile_from_path(profile_path)

            self.assertEqual(profile.name, "test-profile")
            self.assertEqual(list(profile.allowed_commands), ["ls", "cat"])
            self.assertTrue(profile.network_isolation)


class BubblewrapCommandBuilderTests(unittest.TestCase):
    """Tests for BubblewrapCommandBuilder argument generation."""

    def test_basic_command_building(self) -> None:
        """Builder generates expected bwrap arguments."""
        profile = SandboxProfile(
            name="test",
            allowed_commands=[],
            binds=[
                SandboxBind(
                    source=Path("/usr"),
                    target=Path("/usr"),
                    read_only=True,
                    create_target=False,
                )
            ],
            tmpfs_paths=[Path("/tmp")],
            environment={"PATH": "/usr/bin"},
            network_isolation=True,
        )

        builder = BubblewrapCommandBuilder(profile, ["ls", "/"])
        args = builder.build()

        # Check essential arguments are present
        self.assertIn("--die-with-parent", args)
        # Check granular namespace isolation flags
        self.assertIn("--unshare-net", args)  # network_isolation=True
        self.assertIn("--unshare-user", args)  # user_namespace_isolation=True (default)
        self.assertIn("--unshare-ipc", args)
        self.assertIn("--unshare-pid", args)
        self.assertIn("--unshare-uts", args)
        self.assertIn("--unshare-cgroup", args)
        self.assertIn("--proc", args)
        self.assertIn("/proc", args)
        self.assertIn("--tmpfs", args)
        self.assertIn("/tmp", args)
        self.assertIn("--ro-bind", args)
        self.assertIn("/usr", args)
        self.assertIn("--setenv", args)
        self.assertIn("PATH", args)
        self.assertIn("/usr/bin", args)

        # Command comes after --
        dash_idx = args.index("--")
        self.assertEqual(args[dash_idx + 1], "ls")
        self.assertEqual(args[dash_idx + 2], "/")

    def test_network_isolation_optional(self) -> None:
        """Network isolation can be disabled while other namespaces remain isolated."""
        profile = SandboxProfile(
            name="test",
            network_isolation=False,
        )

        builder = BubblewrapCommandBuilder(profile, ["ls"])
        args = builder.build()

        # When network_isolation=False, --unshare-net should NOT be present
        self.assertNotIn("--unshare-net", args)
        # But other namespace isolation should still be present
        self.assertIn("--unshare-user", args)
        self.assertIn("--unshare-ipc", args)
        self.assertIn("--unshare-pid", args)
        self.assertIn("--unshare-uts", args)
        self.assertIn("--unshare-cgroup", args)

    def test_user_namespace_isolation_optional(self) -> None:
        """User namespace isolation can be disabled for restricted environments."""
        profile = SandboxProfile(
            name="test",
            user_namespace_isolation=False,
        )

        builder = BubblewrapCommandBuilder(profile, ["ls"])
        args = builder.build()

        # When user_namespace_isolation=False, --unshare-user should NOT be present
        self.assertNotIn("--unshare-user", args)
        # But other namespace isolation should still be present
        self.assertIn("--unshare-ipc", args)
        self.assertIn("--unshare-pid", args)
        self.assertIn("--unshare-uts", args)
        self.assertIn("--unshare-cgroup", args)


class SandboxBindTests(unittest.TestCase):
    """Tests for SandboxBind validation."""

    def test_validate_requires_absolute_paths(self) -> None:
        """Both source and target must be absolute."""
        bind_relative_source = SandboxBind(
            source=Path("relative"),
            target=Path("/target"),
        )
        with self.assertRaises(SandboxError):
            bind_relative_source.validate()

        bind_relative_target = SandboxBind(
            source=Path("/source"),
            target=Path("relative"),
        )
        with self.assertRaises(SandboxError):
            bind_relative_target.validate()


if __name__ == "__main__":
    _ = unittest.main()
