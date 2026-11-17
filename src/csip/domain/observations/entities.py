"""Observation and normalization contracts.

Layering (blueprint 6.1): raw observations are append-only and must never be
overwritten by normalized values; normalized candidates always reference the
raw observations they were derived from.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from csip.domain.evidence.entities import EvidenceLocator


@dataclass(frozen=True, slots=True)
class RawObservation:
    """One raw field value captured from one source at one point in time.

    Frozen: raw observations are append-only; corrections are new
    observations, never mutations (goals FR-06).
    """

    observation_id: str
    run_id: str
    source_id: str
    artifact_id: str
    field_key: str
    raw_value: str
    language: str
    captured_at: datetime
    evidence: EvidenceLocator
    parser_version: str
    schema_version: str

    def __post_init__(self) -> None:
        if not self.observation_id or not self.field_key:
            raise ValueError("observations require observation_id and field_key")
        if not self.parser_version or not self.schema_version:
            raise ValueError("observations must record parser and schema versions")


@dataclass(frozen=True, slots=True)
class NormalizedCandidate:
    """A proposed canonical record derived from raw observations.

    The model produces these; deterministic application code validates them
    before persistence. Model confidence is advisory metadata, not proof.
    """

    candidate_id: str
    run_id: str
    observation_ids: tuple[str, ...]
    raw_values: Mapping[str, str]  # original source-language values
    normalized_values: Mapping[str, str | None]  # canonical values; None = absent
    original_language: str
    evidence: Mapping[str, EvidenceLocator]  # per critical field
    uncertainty_labels: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    model_id: str = ""
    prompt_version: str = ""
    schema_version: str = ""

    def __post_init__(self) -> None:
        if not self.observation_ids:
            raise ValueError("candidates must reference at least one raw observation")
        if not self.normalized_values:
            raise ValueError("candidates must carry normalized values (possibly all null)")
        for key, value in self.raw_values.items():
            if not key:
                raise ValueError("raw value keys must be non-empty")
            if value == "":
                raise ValueError("raw values must not be silently blanked")
        if self.normalized_values and not self.model_id:
            # Populated critical fields require model provenance; fully-null
            # abstention candidates may omit model metadata.
            populated = [v for v in self.normalized_values.values() if v is not None]
            if populated:
                raise ValueError("populated candidates require model_id")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Deterministic validation outcome for a candidate (goals G5)."""

    candidate_id: str
    rule_set_version: str
    passed: bool
    warnings: tuple[str, ...] = ()
    hard_failures: tuple[str, ...] = ()
    review_required: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.rule_set_version:
            raise ValueError("validation reports must record the rule-set version")
        if self.hard_failures and self.passed:
            raise ValueError("a report with hard failures cannot pass")
