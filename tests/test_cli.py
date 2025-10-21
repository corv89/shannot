"""
Tests for the CLI interface.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shannot.cli import (  # type: ignore[reportPrivateUsage]
    _build_parser,
    _get_default_profile,
    main,
)


class CLIParserTests(unittest.TestCase):
    """Tests for command-line argument parsing."""

    def test_parser_allows_direct_commands(self) -> None:
        """Parser should allow commands without 'run' keyword."""
        parser = _build_parser()
        # Empty args should not raise - they get smart-parsed to run subcommand
        _ = parser.parse_args([])
        # The smart parsing in main() handles converting this to a run command

    def test_run_subcommand(self) -> None:
        """Run subcommand should parse correctly."""
        parser = _build_parser()
        args = parser.parse_args(["run", "ls", "/"])

        self.assertEqual(args.command_name, "run")
        self.assertEqual(args.command, ["ls", "/"])
        self.assertTrue(args.check)
        self.assertTrue(args.print_stdout)

    def test_verify_subcommand(self) -> None:
        """Verify subcommand should parse correctly."""
        parser = _build_parser()
        args = parser.parse_args(["verify"])

        self.assertEqual(args.command_name, "verify")

    def test_export_subcommand(self) -> None:
        """Export subcommand should parse correctly."""
        parser = _build_parser()
        args = parser.parse_args(["export"])

        self.assertEqual(args.command_name, "export")

    def test_profile_option(self) -> None:
        """Profile option should be parsed."""
        parser = _build_parser()
        args = parser.parse_args(["--profile", "/custom/profile.json", "run", "ls"])

        self.assertEqual(args.profile, "/custom/profile.json")


class DefaultProfileTests(unittest.TestCase):
    """Tests for default profile detection."""

    def test_env_var_takes_precedence(self) -> None:
        """SANDBOX_PROFILE environment variable should take precedence."""
        with patch.dict("os.environ", {"SANDBOX_PROFILE": "/env/profile.json"}):
            profile_path = _get_default_profile()
            self.assertEqual(profile_path, Path("/env/profile.json"))

    def test_raises_when_no_profile_found(self) -> None:
        """Should raise error when no profile is found."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                from shannot import SandboxError

                with self.assertRaises(SandboxError):
                    _get_default_profile()


class MainFunctionTests(unittest.TestCase):
    """Tests for the main CLI entry point."""

    def test_export_command(self) -> None:
        """Export command should output JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile.json"
            profile_data = {
                "name": "test-profile",
                "allowed_commands": ["ls"],
                "binds": [],
                "tmpfs_paths": [],
                "environment": {},
                "network_isolation": True,
            }
            _ = profile_path.write_text(json.dumps(profile_data))

            # Capture output
            import io

            captured_output = io.StringIO()

            with patch("sys.stdout", captured_output):
                exit_code = main(["--profile", str(profile_path), "export"])

            self.assertEqual(exit_code, 0)
            output = captured_output.getvalue()
            self.assertIn('"name": "test-profile"', output)


if __name__ == "__main__":
    _ = unittest.main()
