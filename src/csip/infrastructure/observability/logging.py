"""Structured logging with run/correlation IDs and secret redaction.

Every log line renders as JSON with a ``run_id`` taken from a contextvar
(set by the workflow/API layers), so a run can be traced from API
submission through workflow, browser, extraction, model, and persistence
(blueprint 8.4). A logging filter applies ``csip.shared.redaction`` to
message and extra payloads.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from typing import Any

from csip.shared.redaction import is_secret_key, redact

_run_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("csip_run_id", default="")


def set_run_id(run_id: str) -> None:
    """Bind the current execution context to a run/correlation ID."""
    _run_id_var.set(run_id)


def get_run_id() -> str:
    return _run_id_var.get()


class RunIdFilter(logging.Filter):
    """Attach the contextual run ID to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = get_run_id() or "-"
        return True


# Keys that must never be redacted (control fields, not secrets).
_KEEP_KEYS = frozenset(
    {"msg", "args", "message", "run_id", "levelname", "levelno", "name",
     "filename", "module", "lineno", "funcName", "created", "msecs",
     "relativeCreated", "thread", "threadName", "processName", "process",
     "taskName", "stack_info", "exc_info", "exc_text"}
)


class RedactionFilter(logging.Filter):
    """Scrub credential-bearing content before any handler sees it.

    Applies to the rendered message AND all ``extra`` payload attributes;
    without the latter, values like cookies/tokens passed via ``extra=``
    would bypass redaction.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        for key in list(record.__dict__):
            if key in _KEEP_KEYS or key.startswith("_"):
                continue
            try:
                if is_secret_key(key):
                    record.__dict__[key] = "[REDACTED]"
                else:
                    record.__dict__[key] = redact(record.__dict__[key])
            except Exception:  # pragma: no cover - redaction must never raise
                record.__dict__[key] = "[REDACTED]"
        return True


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter; keys are stable for log ingestion."""

    def __init__(self) -> None:
        super().__init__()
        self._reserved = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "taskName", "message", "run_id",
        }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": getattr(record, "run_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in self._reserved and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "unknown"
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", *, stream: Any = None) -> None:
    """Idempotent root configuration for the csip.* logger tree.

    Filters are attached to the *handler*, not the logger: logger filters do
    not apply to records from child loggers, while handler filters run for
    every record they emit.
    """
    logger = logging.getLogger("csip")
    if any(
        isinstance(f, RedactionFilter) for h in logger.handlers for f in h.filters
    ):
        logger.setLevel(level.upper())
        return
    logger.setLevel(level.upper())
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    # Order matters: bind the run ID first, then redact content.
    handler.addFilter(RunIdFilter())
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    logger.propagate = False
