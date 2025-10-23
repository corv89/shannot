"""Tests for SSHExecutor host key handling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("asyncssh")

from shannot.executors.ssh import SSHExecutor


class DummyConnection:
    """Minimal asyncssh connection stub."""

    def __init__(self):
        self._closed = False

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True


@pytest.mark.asyncio
async def test_ssh_executor_strict_host_key(monkeypatch):
    """Strict mode should rely on asyncssh defaults (no explicit override)."""
    captured = SimpleNamespace(kwargs=None)

    async def fake_connect(**kwargs):
        captured.kwargs = kwargs
        return DummyConnection()

    monkeypatch.setattr("shannot.executors.ssh.asyncssh.connect", fake_connect)

    executor = SSHExecutor(host="example.com", strict_host_key=True)
    conn = await executor._get_connection()
    assert isinstance(conn, DummyConnection)
    assert captured.kwargs is not None
    assert "known_hosts" not in captured.kwargs


@pytest.mark.asyncio
async def test_ssh_executor_insecure_host_key(monkeypatch):
    """Disabling host key checks should set known_hosts=None."""
    captured = SimpleNamespace(kwargs=None)

    async def fake_connect(**kwargs):
        captured.kwargs = kwargs
        return DummyConnection()

    monkeypatch.setattr("shannot.executors.ssh.asyncssh.connect", fake_connect)

    executor = SSHExecutor(host="example.com", strict_host_key=False)
    await executor._get_connection()
    assert captured.kwargs is not None
    assert captured.kwargs["known_hosts"] is None


@pytest.mark.asyncio
async def test_ssh_executor_custom_known_hosts(monkeypatch, tmp_path):
    """Custom known_hosts path should be respected."""
    captured = SimpleNamespace(kwargs=None)

    async def fake_connect(**kwargs):
        captured.kwargs = kwargs
        return DummyConnection()

    monkeypatch.setattr("shannot.executors.ssh.asyncssh.connect", fake_connect)

    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text("# dummy")

    executor = SSHExecutor(host="example.com", known_hosts=known_hosts)
    await executor._get_connection()
    assert captured.kwargs is not None
    assert captured.kwargs["known_hosts"] == str(known_hosts)
