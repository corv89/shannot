"""Tests for command danger classification."""

import pytest

from shannot.config import (
    DangerLevel,
    ProfileConfig,
    _extract_base_command,
    _matches_deny_pattern,
    _matches_prefix,
    _normalize_command,
    classify_command_danger,
)


class TestNormalizeCommand:
    """Tests for _normalize_command()."""

    def test_simple_command(self):
        assert _normalize_command("ls -la") == "ls -la"

    def test_strip_sudo(self):
        assert _normalize_command("sudo rm -rf /tmp") == "rm -rf /tmp"

    def test_strip_doas(self):
        assert _normalize_command("doas cat /etc/passwd") == "cat /etc/passwd"

    def test_strip_env_var(self):
        assert _normalize_command("FOO=bar cat file") == "cat file"

    def test_strip_multiple_env_vars(self):
        assert _normalize_command("FOO=bar BAZ=qux cat file") == "cat file"

    def test_strip_env_and_sudo(self):
        assert _normalize_command("FOO=bar sudo cat file") == "cat file"

    def test_empty_string(self):
        assert _normalize_command("") == ""

    def test_only_env_vars(self):
        assert _normalize_command("FOO=bar") == ""

    def test_whitespace(self):
        assert _normalize_command("  ls -la  ") == "ls -la"


class TestExtractBaseCommand:
    """Tests for _extract_base_command()."""

    def test_simple_command(self):
        assert _extract_base_command("ls") == "ls"

    def test_with_args(self):
        assert _extract_base_command("ls -la /tmp") == "ls"

    def test_full_path(self):
        assert _extract_base_command("/usr/bin/rm foo") == "rm"

    def test_with_sudo(self):
        assert _extract_base_command("sudo rm -rf /tmp") == "rm"

    def test_with_pipe(self):
        assert _extract_base_command("cat file | grep foo") == "cat"

    def test_empty_string(self):
        assert _extract_base_command("") == ""

    def test_full_path_with_sudo(self):
        assert _extract_base_command("sudo /usr/bin/cat file") == "cat"

    def test_env_and_sudo_and_path(self):
        assert _extract_base_command("FOO=bar sudo /bin/rm -f /tmp/x") == "rm"


class TestMatchesDenyPattern:
    """Tests for _matches_deny_pattern()."""

    def test_exact_match(self):
        assert _matches_deny_pattern("rm -rf /", ["rm -rf /"]) is True

    def test_substring_match(self):
        assert _matches_deny_pattern("echo foo | rm -rf /", ["rm -rf /"]) is True

    def test_no_match(self):
        # rm -f (no recursive) doesn't match rm -rf pattern
        assert _matches_deny_pattern("rm -f /tmp/foo", ["rm -rf /"]) is False

    def test_sudo_stripped(self):
        assert _matches_deny_pattern("sudo rm -rf /", ["rm -rf /"]) is True

    def test_multiple_patterns(self):
        patterns = ["rm -rf /", "dd if=/dev/zero"]
        assert _matches_deny_pattern("dd if=/dev/zero of=/dev/sda", patterns) is True

    def test_empty_patterns(self):
        assert _matches_deny_pattern("rm -rf /", []) is False


class TestMatchesPrefix:
    """Tests for _matches_prefix()."""

    def test_exact_match(self):
        assert _matches_prefix("systemctl status", ["systemctl status"]) is True

    def test_prefix_match(self):
        assert _matches_prefix("systemctl status nginx", ["systemctl status"]) is True

    def test_no_match(self):
        assert _matches_prefix("systemctl restart nginx", ["systemctl status"]) is False

    def test_sudo_stripped(self):
        assert _matches_prefix("sudo systemctl status nginx", ["systemctl status"]) is True

    def test_single_word(self):
        assert _matches_prefix("cat /etc/passwd", ["cat"]) is True


class TestClassifyCommandDanger:
    """Tests for classify_command_danger()."""

    @pytest.fixture
    def default_profile(self):
        """Profile with common auto_approve and always_deny patterns."""
        return ProfileConfig(
            auto_approve=["cat", "ls", "systemctl status", "df", "ps"],
            always_deny=["rm -rf /", "dd if=/dev/zero"],
        )

    @pytest.fixture
    def empty_profile(self):
        """Profile with no patterns."""
        return ProfileConfig(auto_approve=[], always_deny=[])

    def test_always_deny_is_danger(self, default_profile):
        assert classify_command_danger("rm -rf /", default_profile) == DangerLevel.DANGER

    def test_always_deny_with_sudo(self, default_profile):
        assert classify_command_danger("sudo rm -rf /", default_profile) == DangerLevel.DANGER

    def test_destructive_command_is_danger(self, empty_profile):
        assert classify_command_danger("rm foo.txt", empty_profile) == DangerLevel.DANGER

    def test_kill_is_danger(self, empty_profile):
        assert classify_command_danger("kill 1234", empty_profile) == DangerLevel.DANGER

    def test_pkill_is_danger(self, empty_profile):
        assert classify_command_danger("pkill nginx", empty_profile) == DangerLevel.DANGER

    def test_chmod_is_caution(self, empty_profile):
        assert classify_command_danger("chmod 755 script.sh", empty_profile) == DangerLevel.CAUTION

    def test_service_is_caution(self, empty_profile):
        assert (
            classify_command_danger("service nginx restart", empty_profile) == DangerLevel.CAUTION
        )

    def test_reboot_is_caution(self, empty_profile):
        assert classify_command_danger("reboot", empty_profile) == DangerLevel.CAUTION

    def test_auto_approve_is_safe(self, default_profile):
        assert classify_command_danger("cat /etc/hosts", default_profile) == DangerLevel.SAFE

    def test_auto_approve_prefix_match(self, default_profile):
        assert (
            classify_command_danger("systemctl status nginx", default_profile) == DangerLevel.SAFE
        )

    def test_auto_approve_with_sudo(self, default_profile):
        assert classify_command_danger("sudo cat /etc/hosts", default_profile) == DangerLevel.SAFE

    def test_unknown_command(self, default_profile):
        assert classify_command_danger("custom-script.sh", default_profile) == DangerLevel.UNKNOWN

    def test_precedence_deny_over_safe(self):
        """If a command matches both deny and approve, deny wins."""
        profile = ProfileConfig(
            auto_approve=["rm"],  # Someone mistakenly added rm
            always_deny=["rm -rf /"],
        )
        assert classify_command_danger("rm -rf /", profile) == DangerLevel.DANGER

    def test_precedence_destructive_over_safe(self):
        """Hardcoded DESTRUCTIVE overrides auto_approve."""
        profile = ProfileConfig(
            auto_approve=["rm"],  # Someone mistakenly added rm
            always_deny=[],
        )
        # rm is in DESTRUCTIVE_COMMANDS, so still danger
        assert classify_command_danger("rm foo", profile) == DangerLevel.DANGER

    def test_full_path_command(self, default_profile):
        """Full path commands are correctly classified."""
        assert (
            classify_command_danger("/usr/bin/cat /etc/hosts", default_profile) == DangerLevel.SAFE
        )
        assert classify_command_danger("/bin/rm foo", default_profile) == DangerLevel.DANGER
