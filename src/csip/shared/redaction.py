"""Secret redaction helper.

A single, narrow, dependency-free scrubber applied at trust boundaries:
logging, job-event payloads, and API error responses. It removes values
whose *keys* look credential-bearing and drops values that look like
bearer tokens or long opaque session material.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_REDACTED = "[REDACTED]"

_SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "session",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "service_role",
    "bearer",
)

# Heuristic: JWT-shaped strings, Bearer tokens, and long opaque session
# material are treated as secrets even when the key name is innocent.
_JWT_LIKE = re.compile(r"^[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{8,}$")
_BEARER_LIKE = re.compile(r"^(?:Bearer\s+)?[A-Za-z0-9_.\-]{32,}$")


def is_secret_key(key: str) -> bool:
    """True when a mapping/attribute name looks credential-bearing."""
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def redact(value: Any) -> Any:
    """Return a copy of ``value`` with credential-bearing content removed.

    Mapping keys are matched case-insensitively. Nested mappings/lists are
    walked recursively; scalar values are inspected for token-like shapes.
    """
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if is_secret_key(str(key)):
                cleaned[str(key)] = _REDACTED
            else:
                cleaned[str(key)] = redact(item)
        return cleaned
    if isinstance(value, (list, tuple, set)):
        cleaned_list = [redact(item) for item in value]
        return type(value)(cleaned_list) if isinstance(value, tuple) else cleaned_list
    if isinstance(value, str) and (_JWT_LIKE.match(value) or _BEARER_LIKE.match(value)):
        return _REDACTED
    return value
