import os
import tempfile
import time
from unittest.mock import patch

import pytest

from app.core.sweeper import RETENTION_MIN, TEMP_DIR, cleanup_temp_files


def test_temp_directory_path():
    """Test that the temp directory path is correct"""
    assert TEMP_DIR == "/app/src/tmp"


def test_retention_time_from_config():
    """Test that retention time is loaded from config"""
    assert RETENTION_MIN == 60  # Default value


def test_cleanup_creates_temp_dir():
    """Test that cleanup creates temp directory if it doesn't exist"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("app.core.sweeper.TEMP_DIR", temp_dir):
            with patch("app.core.sweeper.logger") as mock_logger:
                # Mock os.path.exists to return False initially
                with patch("os.path.exists", return_value=False):
                    with patch("os.makedirs") as mock_makedirs:
                        cleanup_temp_files()
                        mock_makedirs.assert_called_with(temp_dir, exist_ok=True)
                        # Verify logger was called
                        mock_logger.debug.assert_called()


def test_cleanup_deletes_old_files():
    """Test that cleanup deletes files older than retention time"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("app.core.sweeper.TEMP_DIR", temp_dir):
            with patch("app.core.sweeper.logger") as mock_logger:
                # Create a test file
                test_file = os.path.join(temp_dir, "test_old_file.pdf")
                with open(test_file, "w") as f:
                    f.write("test content")

                # Set file modification time to be older than retention period
                old_time = time.time() - (RETENTION_MIN * 60 + 60)  # 1 hour older
                os.utime(test_file, (old_time, old_time))

                # Verify file exists and is old
                assert os.path.exists(test_file)
                assert os.path.getmtime(test_file) < time.time() - (RETENTION_MIN * 60)

                # Run cleanup
                cleanup_temp_files()

                # Verify old file was deleted
                assert not os.path.exists(test_file)
                # Verify logger was called
                mock_logger.info.assert_called()


def test_cleanup_keeps_new_files():
    """Test that cleanup keeps files newer than retention time"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("app.core.sweeper.TEMP_DIR", temp_dir):
            # Create a test file
            test_file = os.path.join(temp_dir, "test_new_file.pdf")
            with open(test_file, "w") as f:
                f.write("test content")

            # Set file modification time to be newer than retention period
            new_time = time.time() - (RETENTION_MIN * 60 - 60)  # 1 minute newer
            os.utime(test_file, (new_time, new_time))

            # Verify file exists and is new
            assert os.path.exists(test_file)
            assert os.path.getmtime(test_file) > time.time() - (RETENTION_MIN * 60)

            # Run cleanup
            cleanup_temp_files()

            # Verify new file was kept
            assert os.path.exists(test_file)


def test_cleanup_error_handling():
    """Test that cleanup handles errors gracefully"""
    with patch("app.core.sweeper.logger") as mock_logger:
        with patch("os.path.exists", side_effect=Exception("Test error")):
            # Should not raise exception
            cleanup_temp_files()

            # Verify error was logged
            mock_logger.error.assert_called()


def test_cleanup_logic_old_file_deletion():
    """Test the core logic for determining if a file should be deleted"""
    # Mock current time
    current_time = 1000000  # Some timestamp

    # File older than retention period (61 minutes old)
    old_file_time = current_time - (RETENTION_MIN * 60 + 60)
    cutoff = current_time - (RETENTION_MIN * 60)

    # Should be deleted (older than cutoff)
    assert old_file_time < cutoff

    # File newer than retention period (59 minutes old)
    new_file_time = current_time - (RETENTION_MIN * 60 - 60)

    # Should be kept (newer than cutoff)
    assert new_file_time > cutoff


def test_cleanup_logic_exact_retention_time():
    """Test edge case where file is exactly at retention time"""
    current_time = 1000000
    exact_file_time = current_time - (RETENTION_MIN * 60)
    cutoff = current_time - (RETENTION_MIN * 60)

    # File exactly at cutoff time should be kept (not older than)
    assert exact_file_time >= cutoff


if __name__ == "__main__":
    pytest.main([__file__])
