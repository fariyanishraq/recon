"""Tests: structured logging, run/correlation IDs, and secret redaction."""

from __future__ import annotations

import io
import json
import logging

import pytest

from csip.infrastructure.observability.logging import (
    configure_logging,
    get_run_id,
    set_run_id,
)
from csip.shared.redaction import redact


@pytest.fixture()
def log_stream() -> io.StringIO:
    stream = io.StringIO()
    configure_logging("DEBUG", stream=stream)
    logger = logging.getLogger("csip")
    yield stream
    logger.handlers.clear()


class TestRedaction:
    def test_secret_keys_redacted(self) -> None:
        payload = {"password": "hunter2", "api-key": "abcd", "name": "widget"}
        cleaned = redact(payload)
        assert cleaned["password"] == "[REDACTED]"
        assert cleaned["api-key"] == "[REDACTED]"
        assert cleaned["name"] == "widget"

    def test_nested_and_bearer_like_values_redacted(self) -> None:
        payload = {"config": {"Authorization": "Bearer abc.def.ghi", "host": "x"}, "note": "ok"}
        cleaned = redact(payload)
        assert cleaned["config"]["Authorization"] == "[REDACTED]"
        assert cleaned["config"]["host"] == "x"

    def test_token_like_scalar_redacted(self) -> None:
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        assert redact({"value": token})["value"] == "[REDACTED]"

    def test_normal_text_untouched(self) -> None:
        assert redact({"value": "US $0.85 / piece"}) == {"value": "US $0.85 / piece"}


class TestStructuredLogging:
    def test_json_output_with_run_id(self, log_stream: io.StringIO) -> None:
        set_run_id("run_abc")
        logging.getLogger("csip.test").info("hello", extra={"source_id": "s1"})
        line = json.loads(log_stream.getvalue().strip().splitlines()[-1])
        assert line["message"] == "hello"
        assert line["run_id"] == "run_abc"
        assert line["source_id"] == "s1"

    def test_secret_values_never_reach_handlers(self, log_stream: io.StringIO) -> None:
        logging.getLogger("csip.test").info(
            "submit", extra={"cookie": "session=abc123", "token": "Bearer " + "x" * 40}
        )
        text = log_stream.getvalue()
        assert "abc123" not in text
        assert "x" * 40 not in text
        assert "[REDACTED]" in text

    def test_default_run_id_placeholder(self, log_stream: io.StringIO) -> None:
        set_run_id("")
        logging.getLogger("csip.test").info("no run")
        line = json.loads(log_stream.getvalue().strip().splitlines()[-1])
        assert line["run_id"] == "-"

    def test_get_run_id_roundtrip(self) -> None:
        set_run_id("run_123")
        assert get_run_id() == "run_123"
        set_run_id("")
