"""Security and policy regression tests (Phase 0 subset of SK-12).

Focus: safe error taxonomy behavior and API error shaping. Full SSRF /
prompt-injection / recovery suites land with their phases.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from csip.api.app import create_app
from csip.shared.errors import (
    AccessDeniedStopError,
    ErrorCode,
    PolicyDeniedError,
    ValidationError,
)


class TestSafeErrorTaxonomy:
    def test_access_denied_stops_is_its_own_code(self) -> None:
        err = AccessDeniedStopError("403 from source")
        assert err.code is ErrorCode.ACCESS_DENIED_STOP
        # The safe payload exposes no stack details.
        assert set(err.safe_dict()) == {"code", "message", "details"}

    def test_policy_denied_never_a_transient_code(self) -> None:
        assert PolicyDeniedError("denied").code is not ErrorCode.TRANSIENT

    def test_validation_error_keeps_safe_details(self) -> None:
        err = ValidationError("bad field", details={"field": "price"})
        assert err.safe_dict()["details"] == {"field": "price"}


class TestApiSurface:
    def test_healthz_is_public_and_secret_free(self) -> None:
        client = TestClient(create_app())
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "csip"}
        assert "database" not in response.text.lower()

    def test_csip_errors_render_safe_json(self) -> None:
        app = create_app()
        client = TestClient(app)

        @app.get("/boom")
        async def boom() -> None:
            raise AccessDeniedStopError("challenge page encountered")

        response = client.get("/boom")
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == "access_denied_stop"
        assert "traceback" not in body

    def test_policy_denied_maps_to_403(self) -> None:
        app = create_app()
        client = TestClient(app)

        @app.get("/denied")
        async def denied() -> None:
            raise PolicyDeniedError("source not approved")

        assert client.get("/denied").status_code == 403

    def test_validation_error_maps_to_422(self) -> None:
        app = create_app()
        client = TestClient(app)

        @app.get("/bad")
        async def bad() -> None:
            raise ValidationError("bad input")

        assert client.get("/bad").status_code == 422


@pytest.mark.parametrize(
    ("error_cls", "code"),
    [
        (PolicyDeniedError, "policy_denied"),
        (AccessDeniedStopError, "access_denied_stop"),
    ],
)
def test_error_codes_stable(error_cls: type, code: str) -> None:
    assert error_cls("m").code.value == code
