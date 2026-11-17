"""FastAPI application factory.

Phase 0 scope: one application lifecycle, one API surface. A public
liveness endpoint is deliberately separate from privileged operational
telemetry (blueprint section 9). The AgentOS-backed runtime becomes the
lifecycle owner in Phase 1 (SK-11); this factory already returns a plain
FastAPI app that can later host mounted AgentOS routes, preserving a
single lifecycle owner.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from csip.infrastructure.config.settings import Settings
from csip.shared.errors import CSIPError

health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
async def liveness() -> dict[str, Any]:
    """Public liveness only: no privileged telemetry, no secrets."""
    return {"status": "ok", "service": "csip"}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the CSIP FastAPI application in safe local mode by default."""
    app = FastAPI(
        title="China Sourcing Intelligence Pipeline",
        version="0.1.0",
        # Docs only for non-production environments.
        docs_url=None if settings and settings.app_env == "production" else "/docs",
    )
    app.include_router(health_router)

    @app.exception_handler(CSIPError)
    async def csip_error_handler(_: Any, exc: CSIPError) -> JSONResponse:
        # Safe error taxonomy: stable codes, redacted payloads, no stack traces.
        return JSONResponse(status_code=_status_for(exc), content=exc.safe_dict())

    app.state.settings = settings
    return app


def _status_for(exc: CSIPError) -> int:
    from csip.shared.errors import ErrorCode

    return {
        ErrorCode.POLICY_DENIED: 403,
        ErrorCode.APPROVAL_REQUIRED: 403,
        ErrorCode.ACCESS_DENIED_STOP: 403,
        ErrorCode.UNAUTHORIZED_CALLER: 401,
        ErrorCode.NOT_FOUND: 404,
        ErrorCode.VALIDATION_FAILED: 422,
        ErrorCode.CONFIGURATION: 500,
    }.get(exc.code, 500)
