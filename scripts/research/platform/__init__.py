"""Local-first research platform primitives."""

from .contracts import (
    BASELINE_REQUIRED_EXPORTS,
    FidelityLevel,
    PluginCapabilities,
    ResearchPlugin,
    ResearchRunContext,
    validate_baseline_exports,
)
from .engine import create_project, handoff_cloud, promote_run, run_project

__all__ = [
    "BASELINE_REQUIRED_EXPORTS",
    "FidelityLevel",
    "PluginCapabilities",
    "ResearchPlugin",
    "ResearchRunContext",
    "create_project",
    "handoff_cloud",
    "promote_run",
    "run_project",
    "validate_baseline_exports",
]
