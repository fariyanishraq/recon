"""Shared kernel: identifiers, safe error taxonomy, result type, primitives.

This package must stay dependency-light: standard library plus internal
primitives only, so it can be imported by every layer including ``domain``.
"""

from csip.shared.errors import (
    AccessDeniedStopError,
    ApprovalRequiredError,
    ConfigurationError,
    CSIPError,
    ErrorCode,
    ModelError,
    ParserDriftError,
    PersistenceError,
    PolicyDeniedError,
    TransientError,
    ValidationError,
)
from csip.shared.identifiers import (
    IdempotencyKey,
    JobId,
    RunId,
    new_idempotency_key,
    new_job_id,
    new_run_id,
)
from csip.shared.redaction import redact
from csip.shared.result import Failure, Result, Success

__all__ = [
    "AccessDeniedStopError",
    "ApprovalRequiredError",
    "CSIPError",
    "ConfigurationError",
    "ErrorCode",
    "Failure",
    "IdempotencyKey",
    "JobId",
    "ModelError",
    "ParserDriftError",
    "PersistenceError",
    "PolicyDeniedError",
    "Result",
    "RunId",
    "Success",
    "TransientError",
    "ValidationError",
    "new_idempotency_key",
    "new_job_id",
    "new_run_id",
    "redact",
]
