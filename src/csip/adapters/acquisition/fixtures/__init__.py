"""Fixture adapter implementation.

Implements the acquisition port for local mode: reads a fixture file from
the fixture directory, computes a content fingerprint, and returns an
``AcquisitionArtifact`` with retrieval metadata. No network access occurs.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from csip.domain.acquisition.entities import AcquisitionArtifact, AcquisitionPlan, ArtifactType
from csip.domain.sources.value_objects import AcquisitionMethod
from csip.shared.errors import PolicyDeniedError, ValidationError

logger = logging.getLogger("csip.adapters.acquisition.fixture")


class FixtureAcquisitionAdapter:
    """Acquisition adapter for ``fixture`` method (local mode only)."""

    def __init__(self, fixture_dir: Path) -> None:
        self._fixture_dir = fixture_dir

    @property
    def method(self) -> str:
        return AcquisitionMethod.FIXTURE.value

    def acquire(self, plan: AcquisitionPlan) -> AcquisitionArtifact:
        # Defense-in-depth: refuse any plan not issued for the fixture method.
        if plan.method is not AcquisitionMethod.FIXTURE:
            raise PolicyDeniedError(
                "fixture adapter refuses non-fixture acquisition plans",
                details={"requested_method": plan.method.value},
            )

        reference = _safe_fixture_reference(plan)
        path = self._fixture_dir / f"{reference}"
        if not path.is_file():
            raise ValidationError(
                "fixture file not found", details={"fixture_reference": reference}
            )

        content = path.read_bytes()
        fingerprint = hashlib.sha256(content).hexdigest()
        artifact = AcquisitionArtifact(
            artifact_id=f"art_{fingerprint[:32]}",
            source_id=plan.source_id,
            run_id=plan.run_id,
            artifact_type=ArtifactType.FIXTURE,
            reference=reference,
            captured_at=plan.approved_at,
            content_fingerprint=fingerprint,
            byte_size=len(content),
            storage_ref=str(path),
            retrieval_metadata={"adapter": "fixture", "fingerprint": fingerprint},
        )
        logger.info(
            "fixture artifact acquired",
            extra={"run_id": plan.run_id, "source_id": plan.source_id,
                   "fingerprint": fingerprint, "bytes": len(content)},
        )
        return artifact


def _safe_fixture_reference(plan: AcquisitionPlan) -> str:
    """Derive a fixture filename from the plan without path traversal.

    Fixture references carry no secrets; the approved page family is the
    natural key for the fixture directory.
    """
    name = f"{plan.page_family.value}.html"
    if "/" in name or "\\" in name or ".." in name:
        raise ValidationError("unsafe fixture reference", details={"fixture_reference": name})
    return name
