"""Safe error taxonomy.

Every error carries a stable, non-sensitive ``ErrorCode`` plus a *safe*
message. Details passed to errors must never contain credentials, cookies,
session tokens, or other secrets; use :func:`csip.shared.redaction.redact`
when constructing payloads from untrusted or credential-adjacent data.

Error codes deliberately describe *behavior* (what the system must do),
not HTTP status or transport specifics:

- ``POLICY_DENIED`` / ``APPROVAL_REQUIRED`` -> stop, never retry.
- ``ACCESS_DENIED_STOP`` (403, CAPTCHA, challenge, rate-limit denial) ->
  stop the source run, never retry as transient, never work around.
- ``TRANSIENT`` -> bounded retry with backoff is permitted.
- ``VALIDATION_FAILED`` / ``PARSER_DRIFT`` / ``MODEL_ERROR`` / ``PERSISTENCE``
  -> stage-specific handling per blueprint 4.4.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable, safe error categories. Never encode secrets into these names."""

    POLICY_DENIED = "policy_denied"
    APPROVAL_REQUIRED = "approval_required"
    ACCESS_DENIED_STOP = "access_denied_stop"
    SOURCE_UNAVAILABLE = "source_unavailable"
    RATE_LIMITED = "rate_limited"
    TRANSIENT = "transient"
    VALIDATION_FAILED = "validation_failed"
    PARSER_DRIFT = "parser_drift"
    MODEL_ERROR = "model_error"
    PERSISTENCE = "persistence"
    CONFIGURATION = "configuration"
    UNAUTHORIZED_CALLER = "unauthorized_caller"
    NOT_FOUND = "not_found"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class CSIPError(Exception):
    """Base class for all CSIP errors."""

    code: ErrorCode = ErrorCode.INTERNAL

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details or {})

    def safe_dict(self) -> dict[str, Any]:
        """Serializable representation suitable for logs, events, and API bodies."""
        return {"code": str(self.code), "message": self.message, "details": self.details}

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.code}] {self.message}"


class PolicyDeniedError(CSIPError):
    """Deterministic source-policy denial. Stop; never retried as transient."""

    code = ErrorCode.POLICY_DENIED


class ApprovalRequiredError(CSIPError):
    """Source lacks current approval (unapproved, expired, revoked)."""

    code = ErrorCode.APPROVAL_REQUIRED


class AccessDeniedStopError(CSIPError):
    """403 / challenge / CAPTCHA / rate-limit denial.

    The affected source run MUST stop. Identity rotation, CAPTCHA bypass,
    proxy/fingerprint changes, and re-classifying this as a transient error
    are prohibited (blueprint 3.3, goals G2).
    """

    code = ErrorCode.ACCESS_DENIED_STOP


class SourceUnavailableError(CSIPError):
    """Source temporarily unavailable; bounded retry is permitted."""

    code = ErrorCode.SOURCE_UNAVAILABLE


class TransientError(CSIPError):
    """Transient network/service failure; bounded backoff retry is permitted."""

    code = ErrorCode.TRANSIENT


class ValidationError(CSIPError):
    """Deterministic validation failure in application code."""

    code = ErrorCode.VALIDATION_FAILED


class ParserDriftError(CSIPError):
    """Extraction schema/page-structure drift; quarantine, require review."""

    code = ErrorCode.PARSER_DRIFT


class ModelError(CSIPError):
    """Bounded inference failure (schema violation, provider outage)."""

    code = ErrorCode.MODEL_ERROR


class PersistenceError(CSIPError):
    """Database persistence failure; retry with the same idempotency key."""

    code = ErrorCode.PERSISTENCE


class ConfigurationError(CSIPError):
    """Invalid or unsafe configuration; fail fast at startup."""

    code = ErrorCode.CONFIGURATION


class UnauthorizedCallerError(CSIPError):
    """Caller is not authenticated/authorized for the requested operation."""

    code = ErrorCode.UNAUTHORIZED_CALLER


class NotFoundError(CSIPError):
    """Requested entity does not exist (safe, non-leaking)."""

    code = ErrorCode.NOT_FOUND
