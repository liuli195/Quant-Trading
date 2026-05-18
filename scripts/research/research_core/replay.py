"""Standard replay adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ReplayResult:
    """One local replay result."""

    calibrated: bool
    diagnostics: dict[str, Any]
    tables: dict[str, Any]


class ReplayAdapter(Protocol):
    """Protocol for local counterfactual replay adapters."""

    name: str

    def calibrate(self, baseline: dict[str, Any]) -> ReplayResult:
        """Check whether local replay matches the cloud baseline closely enough."""

    def run_variant(self, baseline: dict[str, Any], variant: dict[str, Any]) -> ReplayResult:
        """Run one counterfactual variant after calibration."""
