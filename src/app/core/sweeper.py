import asyncio
import os
import time

from app.core.config import settings
from app.utils.logger import logger

TEMP_DIR = os.path.join(os.getcwd(), "tmp")
RETENTION_MIN = settings.TEMP_RETENTION_MIN


async def sweeper_task():
    while True:
        now = time.time()
        cutoff = now - (RETENTION_MIN * 60)
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR, exist_ok=True)
        for fname in os.listdir(TEMP_DIR):
            fpath = os.path.join(TEMP_DIR, fname)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    logger.info(f"Deleted temp file: {fpath}")
            except Exception as e:
                logger.error(f"Error deleting {fpath}: {e}")
        await asyncio.sleep(60)
