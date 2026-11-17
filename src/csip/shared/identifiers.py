"""Typed identifiers used across CSIP.

Identifiers are opaque strings validated at construction so that malformed
IDs cannot cross a trust boundary. They carry no secrets.
"""

from __future__ import annotations

import re
import uuid
from typing import NewType

JobId = NewType("JobId", str)
RunId = NewType("RunId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

_RUN_ID_PATTERN = re.compile(r"^run_[0-9a-f]{32}$")
_JOB_ID_PATTERN = re.compile(r"^job_[0-9a-f]{32}$")
_KEY_PATTERN = re.compile(r"^[\w][\w:.\-]{0,127}$")


def new_run_id() -> RunId:
    """Generate a fresh opaque run identifier."""
    return RunId(f"run_{uuid.uuid4().hex}")


def new_job_id() -> JobId:
    """Generate a fresh opaque job identifier."""
    return JobId(f"job_{uuid.uuid4().hex}")


def new_idempotency_key(namespace: str) -> IdempotencyKey:
    """Generate an idempotency key for a namespace (e.g. ``fixture:``)."""
    return IdempotencyKey(f"{namespace}:{uuid.uuid4().hex}")


def parse_run_id(value: str) -> RunId:
    if not _RUN_ID_PATTERN.match(value):
        raise ValueError(f"invalid run id: {value[:16]!r}")
    return RunId(value)


def parse_job_id(value: str) -> JobId:
    if not _JOB_ID_PATTERN.match(value):
        raise ValueError(f"invalid job id: {value[:16]!r}")
    return JobId(value)


def parse_idempotency_key(value: str) -> IdempotencyKey:
    if not _KEY_PATTERN.match(value):
        raise ValueError(f"invalid idempotency key: {value[:16]!r}")
    return IdempotencyKey(value)
