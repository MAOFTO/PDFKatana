import os
import time

from app.core.config import settings
from app.utils.logger import logger

# Use the same temp directory as the split endpoint
TEMP_DIR = "/app/src/tmp"
RETENTION_MIN = settings.TEMP_RETENTION_MIN


def cleanup_temp_files():
    """Clean up temporary files older than TEMP_RETENTION_MIN minutes"""
    try:
        # Check if temp directory exists
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR, exist_ok=True)
            logger.debug(f"Created temp directory: {TEMP_DIR}")
            return

        # Calculate cutoff time
        now = time.time()
        cutoff = now - (RETENTION_MIN * 60)

        # Scan for old files
        deleted_count = 0
        for fname in os.listdir(TEMP_DIR):
            fpath = os.path.join(TEMP_DIR, fname)

            try:
                # Check if it's a file and get its modification time
                if os.path.isfile(fpath):
                    file_mtime = os.path.getmtime(fpath)

                    # Delete if older than retention period
                    if file_mtime < cutoff:
                        os.remove(fpath)
                        deleted_count += 1
                        logger.info(
                            f"Deleted old temp file: {fname} (age: {int((now - file_mtime) / 60)} minutes)"
                        )

            except OSError as e:
                # File might have been deleted by another process
                logger.debug(f"File {fname} no longer accessible: {e}")
            except Exception as e:
                logger.error(f"Error processing temp file {fname}: {e}")

        # Log cleanup summary if files were deleted
        if deleted_count > 0:
            logger.info(f"Cleanup: deleted {deleted_count} old temp files")

    except Exception as e:
        logger.error(f"Cleanup error: {e}")


async def sweeper_task():
    """Background task that runs cleanup on every call"""
    cleanup_temp_files()
