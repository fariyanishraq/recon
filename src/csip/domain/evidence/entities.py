"""Evidence and provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceType(StrEnum):
    CSS_SELECTOR = "css_selector"
    XPATH = "xpath"
    JSON_PATH = "json_path"
    TABLE_CELL = "table_cell"
    TEXT_SNIPPET = "text_snippet"


@dataclass(frozen=True, slots=True)
class EvidenceLocator:
    """A usable locator for one observed field value (goals G4).

    Populated critical fields MUST carry evidence; absent or ambiguous
    values remain null or go to review instead of being guessed.
    """

    field_key: str
    evidence_type: EvidenceType
    locator: str
    snippet: str
    page_family: str

    def __post_init__(self) -> None:
        if not self.field_key:
            raise ValueError("evidence requires a field key")
        if not self.locator or not self.snippet:
            raise ValueError("evidence requires both a locator and a supporting snippet")
