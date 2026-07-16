import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.request_context import get_request_id

# Call sites use extra={"extra_foo": ...} (never a bare "foo") so a log call
# can never collide with LogRecord's own reserved attribute names (message,
# args, levelname, ...) -- the formatter strips the prefix on the way out.
_EXTRA_PREFIX = "extra_"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key.startswith(_EXTRA_PREFIX):
                payload[key.removeprefix(_EXTRA_PREFIX)] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # uvicorn's own access log is plaintext and would interleave with our
    # JSON lines; RequestContextMiddleware logs every request as JSON instead.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
