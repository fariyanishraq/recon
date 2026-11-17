"""Source-governance value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AccessBasis(StrEnum):
    """Recorded access basis. A permissive robots.txt is NOT an access basis."""

    LOCAL_FIXTURE = "local_fixture"
    OFFICIAL_API = "official_api"
    PARTNER_INTEGRATION = "partner_integration"
    SUPPLIER_EXPORT = "supplier_export"
    WRITTEN_PERMISSION = "written_permission"
    PERMITTED_PUBLIC_PAGES = "permitted_public_pages"


class AcquisitionMethod(StrEnum):
    """Acquisition methods, ordered by increasing complexity.

    The acquisition router MUST select the lowest-complexity approved method
    (blueprint 2.3). FIXTURE is the local-mode, no-network adapter.
    """

    FIXTURE = "fixture"
    DOCUMENTED_API = "documented_api"
    PARTNER_FEED = "partner_feed"
    SUPPLIER_EXPORT = "supplier_export"
    AUTHORIZED_PORTAL = "authorized_portal"
    BROWSER_PAGES = "browser_pages"


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class PageFamily(StrEnum):
    """Versioned page families for extraction profiles."""

    SEARCH_RESULTS = "search_results"
    CATEGORY_LISTING = "category_listing"
    SUPPLIER_PROFILE = "supplier_profile"
    PRODUCT_DETAIL = "product_detail"
    VARIANT_TABLE = "variant_table"
    PAGINATION_STATE = "pagination_state"


class StopCondition(StrEnum):
    """Conditions that require stopping the affected source run."""

    HTTP_403 = "http_403"
    CAPTCHA_OR_CHALLENGE = "captcha_or_challenge"
    LOGIN_RESTRICTION = "login_restriction"
    RATE_LIMIT_DENIAL = "rate_limit_denial"
    ROBOTS_DISALLOWED_PATH = "robots_disallowed_path"
    SCOPE_MISMATCH = "scope_mismatch"
    EXPIRED_APPROVAL = "expired_approval"


@dataclass(frozen=True, slots=True)
class RateLimits:
    """Explicit ceilings. Defaults are conservative."""

    max_requests_per_minute: int = 10
    max_concurrency: int = 1
    max_pages_per_run: int = 10

    def __post_init__(self) -> None:
        if self.max_requests_per_minute < 1:
            raise ValueError("max_requests_per_minute must be >= 1")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if self.max_pages_per_run < 1:
            raise ValueError("max_pages_per_run must be >= 1")


@dataclass(frozen=True, slots=True)
class AllowedScope:
    """Approved collection scope for a source."""

    allowed_hosts: tuple[str, ...]
    allowed_page_families: tuple[PageFamily, ...]
    allowed_url_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.allowed_page_families:
            raise ValueError("scope must allow at least one page family")
        hosts = tuple(h.lower().strip() for h in self.allowed_hosts)
        object.__setattr__(self, "allowed_hosts", hosts)


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Retention/reuse constraints for observed content."""

    retain_raw_days: int = 90
    retain_artifacts: bool = False
    redistribution_permitted: bool = False

    def __post_init__(self) -> None:
        if self.retain_raw_days < 0:
            raise ValueError("retain_raw_days must be >= 0")


@dataclass(frozen=True, slots=True)
class ApprovalEvidence:
    """Recorded review evidence for a source approval decision."""

    reviewer: str
    reviewed_at: datetime
    reference: str  # e.g. "contract CSIP-2026-014", "terms review 2026-11-10"

    def __post_init__(self) -> None:
        if not self.reviewer or not self.reference:
            raise ValueError("approval evidence requires reviewer and reference")


def host_matches(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    """Exact-or-subdomain match against the allowlist (no wildcard tricks)."""
    host = host.lower().strip().rstrip(".")
    if not host:
        return False
    return any(
        host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts
    )
