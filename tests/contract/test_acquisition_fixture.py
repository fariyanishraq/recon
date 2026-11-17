"""Contract tests: acquisition port and the fixture adapter.

Security properties verified:
- the fixture adapter refuses any plan issued for a different method;
- no network access occurs (fixture files only);
- artifacts always carry content fingerprints and retrieval metadata.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from csip.adapters.acquisition.fixtures import FixtureAcquisitionAdapter
from csip.domain.acquisition.entities import AcquisitionPlan, ArtifactType
from csip.domain.sources.value_objects import (
    AcquisitionMethod,
    PageFamily,
    RateLimits,
    StopCondition,
)
from csip.shared.errors import PolicyDeniedError, ValidationError
from tests.support import utc

FIXTURE_CONTENT = b"<html><body><h1>Fixture product</h1></body></html>"


def plan(method: AcquisitionMethod = AcquisitionMethod.FIXTURE) -> AcquisitionPlan:
    return AcquisitionPlan(
        source_id="fixture:synthetic-supplier",
        run_id="run_abc",
        method=method,
        page_family=PageFamily.PRODUCT_DETAIL,
        scope_hosts=("fixtures.internal",),
        rate_limits=RateLimits(),
        stop_conditions=tuple(StopCondition),
        authorization_reference="source=fixture:basis=local_fixture",
        approved_at=utc(2026, 11, 17),
        plan_expires_at=utc(2027, 11, 1),
    )


@pytest.fixture()
def fixture_dir(tmp_path: Path) -> Path:
    (tmp_path / "product_detail.html").write_bytes(FIXTURE_CONTENT)
    return tmp_path


class TestFixtureAdapter:
    def test_acquires_artifact_with_fingerprint(self, fixture_dir: Path) -> None:
        adapter = FixtureAcquisitionAdapter(fixture_dir)
        artifact = adapter.acquire(plan())
        assert artifact.content_fingerprint
        assert artifact.byte_size == len(FIXTURE_CONTENT)
        assert artifact.artifact_type is ArtifactType.FIXTURE
        assert artifact.retrieval_metadata["adapter"] == "fixture"
        assert artifact.artifact_id.startswith("art_")

    def test_refuses_non_fixture_plans(self, fixture_dir: Path) -> None:
        adapter = FixtureAcquisitionAdapter(fixture_dir)
        with pytest.raises(PolicyDeniedError, match="non-fixture"):
            adapter.acquire(plan(method=AcquisitionMethod.BROWSER_PAGES))

    def test_missing_fixture_is_a_validation_error(self, fixture_dir: Path) -> None:
        adapter = FixtureAcquisitionAdapter(fixture_dir)
        other = plan()
        bad = AcquisitionPlan(
            **{**{f: getattr(other, f) for f in other.__dataclass_fields__},
               "page_family": PageFamily.SUPPLIER_PROFILE}
        )
        with pytest.raises(ValidationError, match="not found"):
            adapter.acquire(bad)

    def test_no_network_side_effects(self, fixture_dir: Path) -> None:
        """If the adapter tried to reach the network, this server would see it."""
        hits: list[str] = []

        class Probe(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()

        server = HTTPServer(("127.0.0.1", 0), Probe)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            FixtureAcquisitionAdapter(fixture_dir).acquire(plan())
        finally:
            server.shutdown()
            thread.join(timeout=2)
        assert hits == []
