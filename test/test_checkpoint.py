"""Tests for checkpoint and rollback functionality."""

from __future__ import annotations

import base64
import hashlib

import pytest


@pytest.fixture
def temp_session_dir(tmp_path):
    """Create a temporary session directory structure."""
    session_dir = tmp_path / "sessions" / "test-session-1234"
    session_dir.mkdir(parents=True)
    return session_dir


@pytest.fixture
def mock_session(temp_session_dir, monkeypatch):
    """Create a mock session for testing."""
    from shannot.session import Session

    # Patch SESSIONS_DIR to use temp directory
    sessions_dir = temp_session_dir.parent
    monkeypatch.setattr("shannot.config.SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr("shannot.session.SESSIONS_DIR", sessions_dir)

    session = Session(
        id="test-session-1234",
        name="Test Session",
        script_path="/tmp/test.py",
        pending_writes=[],
        pending_deletions=[],
    )
    return session


class TestCreateCheckpoint:
    """Tests for create_checkpoint function."""

    def test_checkpoint_modified_file(self, mock_session, tmp_path):
        """Test checkpointing a modified file."""
        from shannot.checkpoint import create_checkpoint

        # Set up: file that will be modified
        original_content = b"original content"
        new_content = b"new content"
        original_hash = hashlib.sha256(original_content).hexdigest()

        mock_session.pending_writes = [
            {
                "path": "/tmp/test.txt",
                "content_b64": base64.b64encode(new_content).decode(),
                "original_b64": base64.b64encode(original_content).decode(),
                "original_hash": original_hash,
            }
        ]

        # Create checkpoint
        checkpoint = create_checkpoint(mock_session)

        # Verify checkpoint was created
        assert "/tmp/test.txt" in checkpoint
        entry = checkpoint["/tmp/test.txt"]
        assert entry["blob"] is not None
        assert entry["size"] == len(original_content)
        assert entry["was_created"] is False

        # Verify blob file exists
        blob_path = mock_session.checkpoint_dir / entry["blob"]
        assert blob_path.exists()
        assert blob_path.read_bytes() == original_content

    def test_checkpoint_new_file(self, mock_session):
        """Test checkpointing a newly created file."""
        from shannot.checkpoint import create_checkpoint

        new_content = b"new file content"

        mock_session.pending_writes = [
            {
                "path": "/tmp/newfile.txt",
                "content_b64": base64.b64encode(new_content).decode(),
                "original_b64": None,
                "original_hash": None,
            }
        ]

        checkpoint = create_checkpoint(mock_session)

        assert "/tmp/newfile.txt" in checkpoint
        entry = checkpoint["/tmp/newfile.txt"]
        assert entry["blob"] is None
        assert entry["was_created"] is True

    def test_checkpoint_deleted_file(self, mock_session, tmp_path):
        """Test checkpointing a file marked for deletion."""
        from shannot.checkpoint import create_checkpoint

        # Create real file to be deleted
        test_file = tmp_path / "to_delete.txt"
        test_file.write_bytes(b"content to backup")

        mock_session.pending_deletions = [
            {
                "path": str(test_file),
                "target_type": "file",
                "size": 17,
            }
        ]

        checkpoint = create_checkpoint(mock_session)

        assert str(test_file) in checkpoint
        entry = checkpoint[str(test_file)]
        assert entry["blob"] is not None
        assert entry["was_deleted"] is True

        # Verify blob contains original content
        blob_path = mock_session.checkpoint_dir / entry["blob"]
        assert blob_path.read_bytes() == b"content to backup"

    def test_checkpoint_sets_timestamps(self, mock_session):
        """Test that checkpoint creation sets timestamps."""
        from shannot.checkpoint import create_checkpoint

        mock_session.pending_writes = []
        mock_session.pending_deletions = []

        create_checkpoint(mock_session)

        assert mock_session.checkpoint_created_at is not None
        assert mock_session.checkpoint is not None


class TestUpdatePostExecHashes:
    """Tests for update_post_exec_hashes function."""

    def test_update_hashes_for_modified_files(self, mock_session, tmp_path):
        """Test post-exec hash is recorded for modified files."""
        from shannot.checkpoint import update_post_exec_hashes

        # Create file that was "written" during execution
        test_file = tmp_path / "modified.txt"
        test_file.write_bytes(b"new content after execution")

        mock_session.checkpoint = {
            str(test_file): {
                "blob": "abc12345.blob",
                "size": 10,
                "was_created": False,
            }
        }

        update_post_exec_hashes(mock_session)

        entry = mock_session.checkpoint[str(test_file)]
        assert "post_exec_hash" in entry
        expected_hash = hashlib.sha256(b"new content after execution").hexdigest()
        assert entry["post_exec_hash"] == expected_hash


class TestRollbackLocal:
    """Tests for rollback_local function."""

    def test_rollback_modified_file(self, mock_session, tmp_path):
        """Test rolling back a modified file to original content."""
        from shannot.checkpoint import rollback_local

        # Set up: file exists with "new" content
        test_file = tmp_path / "modified.txt"
        test_file.write_bytes(b"new content")

        # Create checkpoint with original content
        checkpoint_dir = mock_session.checkpoint_dir
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        blob_name = "abc12345.blob"
        (checkpoint_dir / blob_name).write_bytes(b"original content")

        mock_session.checkpoint = {
            str(test_file): {
                "blob": blob_name,
                "size": 16,
                "was_created": False,
                "post_exec_hash": hashlib.sha256(b"new content").hexdigest(),
            }
        }

        results = rollback_local(mock_session)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["action"] == "restored"
        assert test_file.read_bytes() == b"original content"

    def test_rollback_created_file(self, mock_session, tmp_path):
        """Test rolling back a created file by deleting it."""
        from shannot.checkpoint import rollback_local

        # Set up: file was created during execution
        test_file = tmp_path / "created.txt"
        test_file.write_bytes(b"created content")

        mock_session.checkpoint = {
            str(test_file): {
                "blob": None,
                "size": 0,
                "was_created": True,
                "post_exec_hash": hashlib.sha256(b"created content").hexdigest(),
            }
        }

        results = rollback_local(mock_session)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["action"] == "deleted"
        assert not test_file.exists()

    def test_rollback_deleted_file(self, mock_session, tmp_path):
        """Test rolling back a deleted file by recreating it."""
        from shannot.checkpoint import rollback_local

        # Set up: file doesn't exist (was deleted)
        test_file = tmp_path / "deleted.txt"
        assert not test_file.exists()

        # Create checkpoint with original content
        checkpoint_dir = mock_session.checkpoint_dir
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        blob_name = "def67890.blob"
        (checkpoint_dir / blob_name).write_bytes(b"deleted file content")

        mock_session.checkpoint = {
            str(test_file): {
                "blob": blob_name,
                "size": 20,
                "was_deleted": True,
            }
        }

        results = rollback_local(mock_session)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["action"] == "recreated"
        assert test_file.exists()
        assert test_file.read_bytes() == b"deleted file content"

    def test_rollback_detects_conflict(self, mock_session, tmp_path):
        """Test that rollback detects file modifications since execution."""
        from shannot.checkpoint import rollback_local

        # Set up: file was modified again after execution
        test_file = tmp_path / "conflict.txt"
        test_file.write_bytes(b"modified again after execution")

        checkpoint_dir = mock_session.checkpoint_dir
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        blob_name = "conflict.blob"
        (checkpoint_dir / blob_name).write_bytes(b"original content")

        mock_session.checkpoint = {
            str(test_file): {
                "blob": blob_name,
                "size": 16,
                "was_created": False,
                "post_exec_hash": hashlib.sha256(b"content at execution time").hexdigest(),
            }
        }

        results = rollback_local(mock_session)

        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["action"] == "conflict"
        # File should NOT be modified
        assert test_file.read_bytes() == b"modified again after execution"

    def test_rollback_force_ignores_conflict(self, mock_session, tmp_path):
        """Test that --force bypasses conflict detection."""
        from shannot.checkpoint import rollback_local

        test_file = tmp_path / "conflict.txt"
        test_file.write_bytes(b"modified again after execution")

        checkpoint_dir = mock_session.checkpoint_dir
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        blob_name = "conflict.blob"
        (checkpoint_dir / blob_name).write_bytes(b"original content")

        mock_session.checkpoint = {
            str(test_file): {
                "blob": blob_name,
                "size": 16,
                "was_created": False,
                "post_exec_hash": hashlib.sha256(b"content at execution time").hexdigest(),
            }
        }

        results = rollback_local(mock_session, force=True)

        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["action"] == "restored"
        assert test_file.read_bytes() == b"original content"

    def test_rollback_partial_checkpoint_skipped(self, mock_session, tmp_path):
        """Test that partial checkpoints are skipped with warning."""
        from shannot.checkpoint import rollback_local

        mock_session.checkpoint = {
            "/tmp/large_dir": {
                "blob": None,
                "size": 0,
                "was_deleted": True,
                "partial": True,
                "file_count": 1000,
                "total_size": 100_000_000,
            }
        }

        results = rollback_local(mock_session)

        assert len(results) == 1
        assert results[0]["success"] is False
        assert results[0]["action"] == "skipped"
        assert "partial" in results[0]["error"].lower()


class TestListCheckpoints:
    """Tests for list_checkpoints function."""

    def test_list_empty(self, monkeypatch):
        """Test listing when no checkpoints exist."""
        from shannot.checkpoint import list_checkpoints
        from shannot.session import Session

        monkeypatch.setattr(Session, "list_all", lambda: [])

        result = list_checkpoints()
        assert result == []

    def test_list_with_checkpoints(self, mock_session, monkeypatch):
        """Test listing sessions with checkpoints."""
        from shannot.checkpoint import list_checkpoints
        from shannot.session import Session

        mock_session.checkpoint_created_at = "2026-01-11T10:00:00"
        mock_session.checkpoint = {
            "/tmp/file1.txt": {"blob": "abc.blob", "size": 100},
            "/tmp/file2.txt": {"blob": "def.blob", "size": 200},
        }

        monkeypatch.setattr(Session, "list_all", lambda: [mock_session])

        result = list_checkpoints()

        assert len(result) == 1
        session, info = result[0]
        assert session.id == "test-session-1234"
        assert info["file_count"] == 2
        assert info["total_size"] == 300
        assert info["created_at"] == "2026-01-11T10:00:00"


class TestCheckpointDirectory:
    """Tests for directory checkpoint with size limits."""

    def test_large_directory_creates_partial_checkpoint(self, mock_session, tmp_path):
        """Test that large directories create partial checkpoints."""
        from shannot.checkpoint import CHECKPOINT_MAX_FILES, create_checkpoint

        # Create directory with more than CHECKPOINT_MAX_FILES files
        large_dir = tmp_path / "large_dir"
        large_dir.mkdir()
        for i in range(CHECKPOINT_MAX_FILES + 10):
            (large_dir / f"file_{i}.txt").write_bytes(b"x")

        mock_session.pending_deletions = [
            {
                "path": str(large_dir),
                "target_type": "directory",
                "size": 0,
            }
        ]

        checkpoint = create_checkpoint(mock_session)

        # Should have partial checkpoint entry
        entry = checkpoint[str(large_dir)]
        assert entry["partial"] is True
        assert entry["file_count"] > CHECKPOINT_MAX_FILES


class TestSessionIntegration:
    """Integration tests with actual session execution flow."""

    def test_checkpoint_survives_session_save_load(self, mock_session):
        """Test that checkpoint data survives session save/load cycle."""
        from shannot.checkpoint import create_checkpoint

        mock_session.pending_writes = [
            {
                "path": "/tmp/test.txt",
                "content_b64": base64.b64encode(b"new").decode(),
                "original_b64": base64.b64encode(b"old").decode(),
                "original_hash": hashlib.sha256(b"old").hexdigest(),
            }
        ]

        create_checkpoint(mock_session)
        mock_session.save()

        # Load session
        from shannot.session import Session

        loaded = Session.load("test-session-1234", audit=False)

        assert loaded.checkpoint_created_at is not None
        assert loaded.checkpoint is not None
        assert "/tmp/test.txt" in loaded.checkpoint

    def test_rolled_back_status(self, mock_session):
        """Test that rolled_back status is valid."""
        mock_session.status = "rolled_back"
        mock_session.save()

        from shannot.session import Session

        loaded = Session.load("test-session-1234", audit=False)
        assert loaded.status == "rolled_back"
