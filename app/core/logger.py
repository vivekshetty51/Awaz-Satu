"""
Structured JSON Logger for Awaaz Setu.

Architectural Context:
- Strict zero-cost constraint: Built exclusively using Python's standard `logging`, `json`, and `sys` libraries.
- Emits single-line structured JSON logs directly to STDOUT for cloud-native ingestion
  (e.g., Vector, Fluentd, Promtail/Loki, GCP Cloud Logging, or standard container runtimes).
- Non-blocking, thread-safe, and asynchronous-friendly design.
"""

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Custom logging formatter that serializes log records into structured JSON.
    Standardizes schema across all backend components and asynchronous tasks.
    """

    # Standard attributes of logging.LogRecord to avoid collision with custom extra fields
    _RESERVED_ATTRS = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Formats a standard LogRecord as a single-line JSON payload.
        """
        # Format the log message string
        message = record.getMessage()

        # Generate standard ISO 8601 UTC timestamp
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        log_payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "module": record.module,
            "logger_name": record.name,
            "message": message,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Include traceback details if an exception is attached
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_payload["exception"] = record.exc_text

        # Include stack info if present
        if record.stack_info:
            log_payload["stack_info"] = self.formatStack(record.stack_info)

        # Merge any custom fields passed via logger.info("...", extra={"user_id": ...})
        for key, value in record.__dict__.items():
            if key not in self._RESERVED_ATTRS and not key.startswith("_"):
                try:
                    # Test JSON serializability; fallback to str() if complex object
                    json.dumps(value)
                    log_payload[key] = value
                except (TypeError, OverflowError):
                    log_payload[key] = str(value)

        return json.dumps(log_payload, default=str, ensure_ascii=False)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Initializes and configures the root logger with a structured JSON StreamHandler on STDOUT.

    Args:
        log_level: Logging threshold ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').

    Returns:
        The configured root logger instance.
    """
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout for h in root_logger.handlers):
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(JSONFormatter())
        stdout_handler.setLevel(numeric_level)
        root_logger.addHandler(stdout_handler)

    # Disable noisy third-party propagation where desired
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = True

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Factory function to obtain a configured named logger.

    Args:
        name: Name of the logger, typically __name__.

    Returns:
        logging.Logger configured to emit structured JSON output.
    """
    return logging.getLogger(name)


# Initialize default root logging on import to guarantee immediate structured logging
setup_logging()
logger = get_logger("awaaz_setu")
