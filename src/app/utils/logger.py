import json
import logging
import sys

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


logger = logging.getLogger("pdfkatana")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(settings.LOG_LEVEL.upper())
logger.propagate = False
