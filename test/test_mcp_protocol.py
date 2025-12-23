"""Unit tests for MCP protocol implementation (JSON-RPC over stdio)."""

from __future__ import annotations

import io
import json
from unittest import mock

import pytest

from shannot.mcp import protocol


class TestReadMessage:
    """Tests for read_message function."""

    def test_read_valid_message(self):
        """Test reading a valid JSON message from stdin."""
        test_input = '{"jsonrpc": "2.0", "method": "ping", "id": 1}\n'

        with mock.patch("sys.stdin", io.StringIO(test_input)):
            msg = protocol.read_message()

        assert msg == {"jsonrpc": "2.0", "method": "ping", "id": 1}

    def test_read_empty_returns_none(self):
        """Test that EOF returns None."""
        with mock.patch("sys.stdin", io.StringIO("")):
            msg = protocol.read_message()

        assert msg is None

    def test_read_invalid_json_returns_none(self):
        """Test that invalid JSON returns None and logs warning."""
        test_input = "{invalid json\n"

        with mock.patch("sys.stdin", io.StringIO(test_input)):
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                msg = protocol.read_message()

        assert msg is None
        assert "Invalid JSON" in mock_stderr.getvalue()

    def test_read_keyboard_interrupt_returns_none(self):
        """Test that KeyboardInterrupt returns None."""

        def readline_interrupt():
            raise KeyboardInterrupt

        mock_stdin = mock.MagicMock()
        mock_stdin.readline = readline_interrupt

        with mock.patch("sys.stdin", mock_stdin):
            msg = protocol.read_message()

        assert msg is None


class TestWriteMessage:
    """Tests for write_message function."""

    def test_write_valid_message(self):
        """Test writing a valid JSON message to stdout."""
        msg = {"jsonrpc": "2.0", "result": "pong", "id": 1}

        mock_stdout = io.StringIO()
        with mock.patch("sys.stdout", mock_stdout):
            protocol.write_message(msg)

        output = mock_stdout.getvalue()
        assert output.endswith("\n")
        assert json.loads(output.strip()) == msg

    def test_write_handles_broken_pipe(self):
        """Test that broken pipe exits gracefully."""

        def write_broken_pipe(data):
            raise BrokenPipeError

        mock_stdout = mock.MagicMock()
        mock_stdout.write = write_broken_pipe

        with mock.patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as exc_info:
                protocol.write_message({"test": "data"})

        assert exc_info.value.code == 0

    def test_write_handles_io_error(self):
        """Test that IOError exits gracefully."""

        def write_io_error(data):
            raise OSError("Connection reset")

        mock_stdout = mock.MagicMock()
        mock_stdout.write = write_io_error

        with mock.patch("sys.stdout", mock_stdout):
            with pytest.raises(SystemExit) as exc_info:
                protocol.write_message({"test": "data"})

        assert exc_info.value.code == 0


class TestServe:
    """Tests for serve function (main serving loop)."""

    def test_serve_processes_requests(self):
        """Test that serve calls handler for each message."""
        messages = [
            '{"jsonrpc": "2.0", "method": "ping", "id": 1}\n',
            '{"jsonrpc": "2.0", "method": "ping", "id": 2}\n',
            "",  # EOF
        ]

        mock_stdin = io.StringIO("".join(messages))
        mock_stdout = io.StringIO()

        handler_calls = []

        def test_handler(msg):
            handler_calls.append(msg)
            return {"jsonrpc": "2.0", "result": "pong", "id": msg["id"]}

        with mock.patch("sys.stdin", mock_stdin):
            with mock.patch("sys.stdout", mock_stdout):
                protocol.serve(test_handler)

        assert len(handler_calls) == 2
        assert handler_calls[0]["id"] == 1
        assert handler_calls[1]["id"] == 2

        # Check responses were written
        output = mock_stdout.getvalue()
        lines = [line for line in output.strip().split("\n") if line]
        assert len(lines) == 2

    def test_serve_handles_notification(self):
        """Test that serve doesn't write response for notifications (no id)."""
        messages = [
            '{"jsonrpc": "2.0", "method": "notify"}\n',
            "",  # EOF
        ]

        mock_stdin = io.StringIO("".join(messages))
        mock_stdout = io.StringIO()

        def test_handler(msg):
            # Return None for notifications
            return None

        with mock.patch("sys.stdin", mock_stdin):
            with mock.patch("sys.stdout", mock_stdout):
                protocol.serve(test_handler)

        # No output should be written
        output = mock_stdout.getvalue()
        assert output == ""

    def test_serve_handles_handler_exception(self):
        """Test that serve sends error response when handler raises."""
        messages = [
            '{"jsonrpc": "2.0", "method": "fail", "id": 1}\n',
            "",  # EOF
        ]

        mock_stdin = io.StringIO("".join(messages))
        mock_stdout = io.StringIO()

        def failing_handler(msg):
            raise ValueError("Handler failed")

        with mock.patch("sys.stdin", mock_stdin):
            with mock.patch("sys.stdout", mock_stdout):
                protocol.serve(failing_handler)

        # Error response should be written
        output = mock_stdout.getvalue()
        response = json.loads(output.strip())

        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32603
        assert "Handler failed" in response["error"]["message"]
        assert response["id"] == 1

    def test_serve_no_error_for_notification_exception(self):
        """Test that no error response for notification (no id) exceptions."""
        messages = [
            '{"jsonrpc": "2.0", "method": "fail"}\n',  # No id
            "",  # EOF
        ]

        mock_stdin = io.StringIO("".join(messages))
        mock_stdout = io.StringIO()

        def failing_handler(msg):
            raise ValueError("Handler failed")

        with mock.patch("sys.stdin", mock_stdin):
            with mock.patch("sys.stdout", mock_stdout):
                protocol.serve(failing_handler)

        # No output for notification error
        output = mock_stdout.getvalue()
        assert output == ""
