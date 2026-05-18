"""Shared contracts for local-first research plugins."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from scripts.research.research_core.layout import ResearchRunLayout


class FidelityLevel(StrEnum):
    """How much trust the platform can place in one local study."""

    LOCAL_EXACT = "local_exact"
    LOCAL_REPLAYABLE = "local_replayable"
    CLOUD_ONLY = "cloud_only"


BASELINE_REQUIRED_EXPORTS = (
    "daily_returns",
    "signals",
    "gates",
    "scores",
    "penalties",
    "target_weights",
    "actual_weights",
    "params",
    "audit_events",
)


@dataclass(frozen=True)
class PluginCapabilities:
    """Declarative description of what one plugin can decide locally."""

    local_capabilities: tuple[str, ...]
    replayable_params: tuple[str, ...]
    required_exports: tuple[str, ...]
    unsupported_changes: tuple[str, ...]
    fidelity_level: FidelityLevel


@dataclass(frozen=True)
class ResearchRunContext:
    """Runtime inputs shared with one plugin execution."""

    project_dir: Path
    project: dict[str, Any]
    run: ResearchRunLayout
    mode: str
    top_k: int
    cloud_top_k: int
    source_run_id: str | None = None
    feature_cache_hit: bool | None = None
    feature_cold_build_seconds: float | None = None


class ResearchPlugin(Protocol):
    """Minimal plugin surface required by the local-first engine."""

    name: str
    template: str
    code_version: str
    capabilities: PluginCapabilities

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        """Return the stable feature-spec payload used in cache keys."""

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        """Return the immutable input fingerprint without building derived features."""

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        """Build reusable derived features for this project."""

    def run_fast(self, context: ResearchRunContext, features: dict[str, Any]) -> dict[str, Any]:
        """Run the low-latency candidate screen."""

    def run_full(
        self,
        context: ResearchRunContext,
        features: dict[str, Any],
        shortlist: pd.DataFrame,
    ) -> dict[str, Any]:
        """Run shortlist refinement and produce cloud candidates."""

    def build_cloud_handoff(
        self,
        context: ResearchRunContext,
        cloud_candidates: pd.DataFrame,
    ) -> dict[str, Any] | None:
        """Return plugin-specific cloud handoff payload, if supported."""


def validate_baseline_exports(bundle: dict[str, Any]) -> list[str]:
    """Return missing baseline-export fields without raising."""

    return [field for field in BASELINE_REQUIRED_EXPORTS if field not in bundle]
