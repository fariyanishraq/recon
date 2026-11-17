"""Acquisition port.

Adapters implement this to acquire approved artifacts. The contract is
deliberately narrow: an adapter receives a *policy-approved plan* and
nothing else. There is no method to acquire without a plan, which keeps
the "no route into acquisition bypasses the policy check" invariant
structural rather than procedural.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from csip.domain.acquisition.entities import AcquisitionArtifact, AcquisitionPlan


@runtime_checkable
class AcquisitionAdapterPort(Protocol):
    """Contract for all acquisition adapters (fixture, API, export, browser)."""

    @property
    def method(self) -> str:
        """The AcquisitionMethod value this adapter serves, e.g. ``fixture``."""
        ...

    def acquire(self, plan: AcquisitionPlan) -> AcquisitionArtifact:
        """Acquire one artifact strictly within the plan's approved scope.

        Implementations MUST:
        - act only inside ``plan.scope_hosts`` / approved page family,
        - respect ``plan.rate_limits`` and bounded timeouts,
        - honor ``plan.stop_conditions`` (stop, never work around),
        - return an artifact with a content fingerprint and retrieval metadata.
        """
        ...
