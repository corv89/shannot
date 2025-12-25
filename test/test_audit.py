"""Tests for audit logging module."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from shannot.audit import (
    AUDIT_LOG_DIR,
    AuditEvent,
    AuditLogger,
    get_today_event_count,
    log_approval_decision,
    log_command_decision,
)
from shannot.config import AuditConfig


class TestAuditConfig:
    """Tests for audit configuration."""

    def test_default_config(self):
        """Default config has expected values."""
        config = AuditConfig()
        assert config.enabled is True  # Opt-out default
        assert config.rotation == "daily"
        assert config.max_files == 30
        assert config.log_dir is None

    def test_effective_log_dir_default(self):
        """effective_log_dir returns AUDIT_LOG_DIR when log_dir is None."""
        config = AuditConfig()
        assert config.effective_log_dir == AUDIT_LOG_DIR

    def test_effective_log_dir_custom(self):
        """effective_log_dir returns custom log_dir when set."""
        custom_dir = Path("/tmp/custom-audit")
        config = AuditConfig(log_dir=custom_dir)
        assert config.effective_log_dir == custom_dir

    def test_is_event_enabled_default(self):
        """All event types enabled by default."""
        config = AuditConfig()
        assert config.is_event_enabled("session_created") is True
        assert config.is_event_enabled("command_decision") is True
        assert config.is_event_enabled("file_write_queued") is True
        assert config.is_event_enabled("approval_decision") is True
        assert config.is_event_enabled("execution_started") is True
        assert config.is_event_enabled("remote_connection") is True

    def test_is_event_enabled_disabled_category(self):
        """Event types disabled when category is disabled."""
        config = AuditConfig()
        config.events["session"] = False

        assert config.is_event_enabled("session_created") is False
        assert config.is_event_enabled("session_loaded") is False
        assert config.is_event_enabled("session_status_changed") is False
        # Other categories still enabled
        assert config.is_event_enabled("command_decision") is True


class TestAuditEvent:
    """Tests for audit event model."""

    def test_to_json_compact(self):
        """to_json returns compact JSON without spaces."""
        event = AuditEvent(
            seq=1,
            timestamp="2024-01-15T14:30:45.123456Z",
            event_type="session_created",
            session_id="test-session",
            host="localhost",
            target=None,
            user="testuser",
            pid=12345,
            payload={"name": "test"},
        )
        json_str = event.to_json()

        # Should be compact (no spaces after separators)
        assert ": " not in json_str
        assert ", " not in json_str

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["seq"] == 1
        assert parsed["event_type"] == "session_created"


class TestAuditLogger:
    """Tests for audit logger."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = AuditConfig(enabled=True, log_dir=self.tmpdir)
        # Reset singleton
        AuditLogger.reset_instance()

    def teardown_method(self):
        """Clean up test fixtures."""
        AuditLogger.reset_instance()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_creates_file(self):
        """Logging creates log file in log directory."""
        logger = AuditLogger(self.config)
        logger.log("session_created", "test-session", {"name": "test"})

        log_files = list(self.tmpdir.glob("audit-*.jsonl"))
        assert len(log_files) == 1

    def test_log_appends_jsonl(self):
        """Multiple logs append to same file."""
        logger = AuditLogger(self.config)
        logger.log("session_created", "s1", {"name": "test1"})
        logger.log("session_created", "s2", {"name": "test2"})

        log_files = list(self.tmpdir.glob("audit-*.jsonl"))
        content = log_files[0].read_text()
        lines = [line for line in content.strip().split("\n") if line]

        assert len(lines) == 2

        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])
        assert event1["session_id"] == "s1"
        assert event2["session_id"] == "s2"

    def test_sequence_numbers_increment(self):
        """Sequence numbers increment with each event."""
        logger = AuditLogger(self.config)
        logger.log("session_created", "s1", {"name": "test1"})
        logger.log("session_created", "s2", {"name": "test2"})
        logger.log("session_created", "s3", {"name": "test3"})

        log_files = list(self.tmpdir.glob("audit-*.jsonl"))
        lines = log_files[0].read_text().strip().split("\n")

        seqs = [json.loads(line)["seq"] for line in lines]
        assert seqs == [1, 2, 3]

    def test_disabled_does_not_log(self):
        """Logging disabled does not create files."""
        self.config.enabled = False
        logger = AuditLogger(self.config)
        logger.log("session_created", "test", {"name": "test"})

        log_files = list(self.tmpdir.glob("*.jsonl"))
        assert len(log_files) == 0

    def test_event_type_filtering(self):
        """Disabled event categories are not logged."""
        self.config.events["session"] = False
        logger = AuditLogger(self.config)
        logger.log("session_created", "test", {"name": "test"})

        log_files = list(self.tmpdir.glob("*.jsonl"))
        assert len(log_files) == 0

    def test_includes_host_user_pid(self):
        """Events include host, user, and pid fields."""
        logger = AuditLogger(self.config)
        logger.log("session_created", "test", {"name": "test"})

        log_files = list(self.tmpdir.glob("audit-*.jsonl"))
        content = log_files[0].read_text().strip()
        event = json.loads(content)

        assert "host" in event
        assert "user" in event
        assert "pid" in event
        assert isinstance(event["pid"], int)

    def test_singleton_pattern(self):
        """get_instance returns same logger instance."""
        logger1 = AuditLogger.get_instance(self.config)
        logger2 = AuditLogger.get_instance()

        assert logger1 is logger2

    def test_reset_instance(self):
        """reset_instance clears singleton."""
        logger1 = AuditLogger.get_instance(self.config)
        AuditLogger.reset_instance()
        logger2 = AuditLogger.get_instance(self.config)

        assert logger1 is not logger2


class TestConvenienceFunctions:
    """Tests for logging convenience functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = AuditConfig(enabled=True, log_dir=self.tmpdir)
        AuditLogger.reset_instance()

    def teardown_method(self):
        """Clean up test fixtures."""
        AuditLogger.reset_instance()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_command_decision(self):
        """log_command_decision creates correct event."""
        # Patch the singleton to use our config
        AuditLogger._instance = AuditLogger(self.config)

        log_command_decision(
            session_id="test-session",
            command="ls -la",
            decision="allow",
            reason="auto_approve",
            base_command="ls",
            target=None,
        )

        log_files = list(self.tmpdir.glob("*.jsonl"))
        assert len(log_files) == 1

        event = json.loads(log_files[0].read_text().strip())
        assert event["event_type"] == "command_decision"
        assert event["payload"]["decision"] == "allow"
        assert event["payload"]["base_command"] == "ls"

    def test_log_approval_decision(self):
        """log_approval_decision creates correct event."""
        AuditLogger._instance = AuditLogger(self.config)

        # Create mock sessions
        @dataclass
        class MockSession:
            id: str
            target: str | None = None

        sessions = [MockSession(id="s1"), MockSession(id="s2")]

        log_approval_decision(sessions, "approved", "tui")  # type: ignore[arg-type]

        log_files = list(self.tmpdir.glob("*.jsonl"))
        event = json.loads(log_files[0].read_text().strip())

        assert event["event_type"] == "approval_decision"
        assert event["payload"]["action"] == "approved"
        assert event["payload"]["sessions"] == ["s1", "s2"]
        assert event["payload"]["source"] == "tui"

    def test_get_today_event_count(self):
        """get_today_event_count returns count of today's events."""
        AuditLogger._instance = AuditLogger(self.config)

        # Log some events
        AuditLogger._instance.log("session_created", "s1", {"name": "test1"})
        AuditLogger._instance.log("session_created", "s2", {"name": "test2"})
        AuditLogger._instance.log("command_decision", "s1", {"command": "ls"})

        with mock.patch("shannot.audit.load_audit_config", return_value=self.config):
            count = get_today_event_count()

        assert count == 3

    def test_list_all_does_not_audit(self):
        """Session.list_all() should not generate audit events."""
        from shannot.session import SESSIONS_DIR, Session

        AuditLogger._instance = AuditLogger(self.config)

        # Create a fake session directory
        session_id = "test-session-no-audit"
        session_dir = SESSIONS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "session.json").write_text(
            json.dumps(
                {
                    "id": session_id,
                    "name": "test",
                    "script_path": "/tmp/test.py",
                    "status": "pending",
                    "created_at": "2024-01-01T00:00:00Z",
                    "commands": [],
                    "pending_writes": [],
                }
            )
        )

        try:
            # List sessions - should NOT create audit events
            Session.list_all()

            log_files = list(self.tmpdir.glob("*.jsonl"))
            assert len(log_files) == 0, "Session.list_all() should not audit"
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)
