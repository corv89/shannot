"""Unit tests for MCP remote execution functionality."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shannot.mcp.server_impl import ShannotMCPServer
from shannot.mcp.types import TextContent


@dataclass
class MockRemote:
    """Mock Remote object for testing."""

    host: str
    user: str
    port: int = 22

    @property
    def target_string(self) -> str:
        return f"{self.user}@{self.host}"


class MockSSHResult:
    """Mock SSH command result."""

    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class MockSSHConnection:
    """Mock SSH connection for testing."""

    def __init__(self, config: Any = None):
        self.config = config
        self.target = config.target if config else "mock@localhost"
        self.commands_run: list[str] = []

    def __enter__(self) -> MockSSHConnection:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def run(self, cmd: str, timeout: int = 30, input_data: bytes | None = None) -> MockSSHResult:
        self.commands_run.append(cmd)
        return MockSSHResult(returncode=0, stdout=b"", stderr=b"")

    def write_file(self, path: str, content: bytes) -> None:
        pass


class TestMCPRemoteTargetParameter:
    """Tests for sandbox_run target parameter."""

    def test_sandbox_run_schema_includes_target(self) -> None:
        """Test that sandbox_run tool schema includes target parameter."""
        with patch.object(ShannotMCPServer, "_load_profiles", return_value={}):
            server = ShannotMCPServer()

        # Find sandbox_run tool
        assert "sandbox_run" in server.tools
        tool = server.tools["sandbox_run"]

        # Check target is in properties
        props = tool.inputSchema.get("properties", {})
        assert "target" in props
        assert "Named remote target" in props["target"].get("description", "")


class TestMCPRemoteTargetResolution:
    """Tests for remote target resolution."""

    @pytest.fixture
    def mock_profiles(self) -> dict[str, dict[str, list[str]]]:
        """Default profiles for testing."""
        return {
            "minimal": {"auto_approve": ["ls"], "always_deny": []},
        }

    def test_unknown_remote_returns_error(self, mock_profiles: dict) -> None:
        """Test that unknown remote target returns helpful error."""
        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value={}):
                server = ShannotMCPServer()

                result = server._handle_sandbox_run(
                    {
                        "script": "print('hello')",
                        "target": "nonexistent",
                    }
                )

                data = json.loads(result.text)
                assert data["status"] == "error"
                assert "Unknown remote target 'nonexistent'" in data["error"]
                assert "shannot remote add" in data["error"]

    def test_arbitrary_user_at_host_rejected(self, mock_profiles: dict) -> None:
        """Test that arbitrary user@host format is rejected."""
        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value={}):
                server = ShannotMCPServer()

                result = server._handle_sandbox_run(
                    {
                        "script": "print('hello')",
                        "target": "attacker@evil.com",
                    }
                )

                data = json.loads(result.text)
                assert data["status"] == "error"
                assert "Arbitrary SSH targets are not allowed" in data["error"]

    def test_arbitrary_user_at_host_port_rejected(self, mock_profiles: dict) -> None:
        """Test that user@host:port format is rejected."""
        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value={}):
                server = ShannotMCPServer()

                result = server._handle_sandbox_run(
                    {
                        "script": "print('hello')",
                        "target": "user@host.com:2222",
                    }
                )

                data = json.loads(result.text)
                assert data["status"] == "error"
                assert "Arbitrary SSH targets are not allowed" in data["error"]

    def test_named_remote_is_resolved(self, mock_profiles: dict) -> None:
        """Test that named remotes are properly resolved."""
        mock_remotes = {
            "prod": MockRemote(host="prod.example.com", user="deploy", port=22),
        }

        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value=mock_remotes):
                with patch("shannot.mcp.server_impl.SSHConnection") as mock_ssh:
                    with patch("shannot.mcp.server_impl.ensure_deployed", return_value=True):
                        # Mock the SSH context manager
                        mock_ssh_instance = MockSSHConnection()
                        mock_ssh.return_value.__enter__ = lambda x: mock_ssh_instance
                        mock_ssh.return_value.__exit__ = lambda x, *args: None

                        server = ShannotMCPServer()

                        # This will fail at deployment but proves target resolution worked
                        with patch.object(
                            server, "_create_remote_approval_session"
                        ) as mock_session:
                            mock_session.return_value = TextContent(
                                text=json.dumps({"status": "pending_approval"})
                            )

                            server._handle_sandbox_run(
                                {
                                    "script": "print('hello')",
                                    "target": "prod",
                                }
                            )

                            # If we got here without error, target was resolved
                            assert mock_session.called


class TestMCPRemoteDeployment:
    """Tests for remote deployment behavior."""

    @pytest.fixture
    def mock_profiles(self) -> dict[str, dict[str, list[str]]]:
        """Default profiles for testing."""
        return {
            "minimal": {"auto_approve": ["ls"], "always_deny": []},
        }

    def test_deployment_called_for_remote_target(self, mock_profiles: dict) -> None:
        """Test that ensure_deployed is called for remote targets."""
        mock_remotes = {
            "staging": MockRemote(host="staging.local", user="admin", port=22),
        }

        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value=mock_remotes):
                with patch("shannot.mcp.server_impl.SSHConnection") as mock_ssh:
                    with patch(
                        "shannot.mcp.server_impl.ensure_deployed", return_value=False
                    ) as mock_deploy:
                        mock_ssh_instance = MockSSHConnection()
                        mock_ssh.return_value.__enter__ = lambda x: mock_ssh_instance
                        mock_ssh.return_value.__exit__ = lambda x, *args: None

                        server = ShannotMCPServer()
                        result = server._handle_sandbox_run(
                            {
                                "script": "print('hello')",
                                "target": "staging",
                            }
                        )

                        # ensure_deployed should have been called
                        assert mock_deploy.called
                        data = json.loads(result.text)
                        # Deployment failed (returned False)
                        assert data["status"] == "error"
                        assert "Failed to deploy" in data["error"]


class TestMCPRemoteFastPath:
    """Tests for remote fast path execution."""

    def test_fast_path_with_allowed_ops(self) -> None:
        """Test fast path executes when all ops are auto-approved."""
        mock_remotes = {
            "prod": MockRemote(host="prod.example.com", user="deploy", port=22),
        }
        mock_profiles = {
            "diagnostics": {
                "auto_approve": ["ls", "cat", "df"],
                "always_deny": [],
            }
        }

        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value=mock_remotes):
                with patch("shannot.mcp.server_impl.SSHConnection") as mock_ssh:
                    with patch("shannot.mcp.server_impl.ensure_deployed", return_value=True):
                        mock_ssh_instance = MockSSHConnection()
                        mock_ssh.return_value.__enter__ = lambda x: mock_ssh_instance
                        mock_ssh.return_value.__exit__ = lambda x, *args: None

                        server = ShannotMCPServer()

                        # Mock the fast path execution
                        with patch.object(server, "_execute_remote_fast_path") as mock_fast:
                            mock_fast.return_value = TextContent(
                                text=json.dumps(
                                    {
                                        "status": "success",
                                        "exit_code": 0,
                                        "stdout": "output",
                                        "target": "prod",
                                    }
                                )
                            )

                            server._handle_sandbox_run(
                                {
                                    "script": "import subprocess; subprocess.run(['ls'])",
                                    "target": "prod",
                                    "profile": "diagnostics",
                                }
                            )

                            # Fast path should have been called
                            assert mock_fast.called


class TestMCPRemoteReviewPath:
    """Tests for remote review path (session creation)."""

    def test_review_path_creates_session(self) -> None:
        """Test review path creates session for unapproved ops."""
        mock_remotes = {
            "prod": MockRemote(host="prod.example.com", user="deploy", port=22),
        }
        mock_profiles = {
            "minimal": {
                "auto_approve": ["ls"],
                "always_deny": [],
            }
        }

        with patch.object(ShannotMCPServer, "_load_profiles", return_value=mock_profiles):
            with patch("shannot.mcp.server_impl.load_remotes", return_value=mock_remotes):
                with patch("shannot.mcp.server_impl.SSHConnection") as mock_ssh:
                    with patch("shannot.mcp.server_impl.ensure_deployed", return_value=True):
                        mock_ssh_instance = MockSSHConnection()
                        mock_ssh.return_value.__enter__ = lambda x: mock_ssh_instance
                        mock_ssh.return_value.__exit__ = lambda x, *args: None

                        server = ShannotMCPServer()

                        # Mock the review path
                        with patch.object(
                            server, "_create_remote_approval_session"
                        ) as mock_session:
                            mock_session.return_value = TextContent(
                                text=json.dumps(
                                    {
                                        "status": "pending_approval",
                                        "session_id": "test-session",
                                        "target": "prod",
                                    }
                                )
                            )

                            # Use 'rm' which is not in auto_approve
                            server._handle_sandbox_run(
                                {
                                    "script": "import subprocess; subprocess.run(['rm', 'file'])",
                                    "target": "prod",
                                    "profile": "minimal",
                                }
                            )

                            # Review path should have been called
                            assert mock_session.called


class TestMCPRemoteSessionResult:
    """Tests for session_result with remote sessions."""

    def test_session_result_includes_target(self) -> None:
        """Test session_result includes target for remote sessions."""
        from shannot.session import Session

        mock_session = MagicMock(spec=Session)
        mock_session.id = "test-session"
        mock_session.status = "pending"
        mock_session.created_at = "2024-01-15T10:00:00"
        mock_session.target = "prod"
        mock_session.is_expired.return_value = False
        mock_session.expires_at = "2024-01-15T11:00:00"

        with patch.object(ShannotMCPServer, "_load_profiles", return_value={}):
            with patch("shannot.mcp.server_impl.Session.load", return_value=mock_session):
                server = ShannotMCPServer()

                result = server._handle_session_result({"session_id": "test-session"})

                data = json.loads(result.text)
                assert data["target"] == "prod"
                assert "Target: prod" in data.get("instructions", [])[0]


class TestMCPRemotesResource:
    """Tests for sandbox://remotes resource."""

    def test_remotes_resource_lists_configured_remotes(self) -> None:
        """Test remotes resource returns configured remotes."""
        mock_remotes = {
            "prod": MockRemote(host="prod.example.com", user="deploy", port=22),
            "staging": MockRemote(host="staging.local", user="admin", port=2222),
        }

        with patch.object(ShannotMCPServer, "_load_profiles", return_value={}):
            with patch("shannot.mcp.server_impl.load_remotes", return_value=mock_remotes):
                server = ShannotMCPServer()

                result = server._handle_list_remotes()
                data = json.loads(result)

                assert "remotes" in data
                assert "prod" in data["remotes"]
                assert data["remotes"]["prod"]["host"] == "prod.example.com"
                assert data["remotes"]["prod"]["user"] == "deploy"
                assert data["remotes"]["prod"]["port"] == 22
                assert "staging" in data["remotes"]
                assert data["remotes"]["staging"]["port"] == 2222

    def test_remotes_resource_empty_when_none_configured(self) -> None:
        """Test remotes resource returns empty dict when no remotes configured."""
        with patch.object(ShannotMCPServer, "_load_profiles", return_value={}):
            with patch("shannot.mcp.server_impl.load_remotes", return_value={}):
                server = ShannotMCPServer()

                result = server._handle_list_remotes()
                data = json.loads(result)

                assert data["remotes"] == {}

    def test_remotes_resource_registered(self) -> None:
        """Test sandbox://remotes resource is properly registered."""
        with patch.object(ShannotMCPServer, "_load_profiles", return_value={}):
            server = ShannotMCPServer()

            assert "sandbox://remotes" in server.resources
            resource = server.resources["sandbox://remotes"]
            assert resource.name == "SSH Remotes"
