"""Local-first research platform primitives."""

from .contracts import (
    BASELINE_REQUIRED_EXPORTS,
    FidelityLevel,
    PluginCapabilities,
    ResearchPlugin,
    ResearchRunContext,
    validate_baseline_exports,
)
from .batch_executor import BatchExecutionResult, execute_batch
from .benchmark_runner import BenchmarkSummary, run_smoke_benchmark
from .coverage_audit import ScanCoverageSlice, audit_scan_coverage, coverage_is_complete
from .engine import create_project, handoff_cloud, promote_run, run_project

__all__ = [
    "BASELINE_REQUIRED_EXPORTS",
    "BatchExecutionResult",
    "BenchmarkSummary",
    "FidelityLevel",
    "PluginCapabilities",
    "ResearchPlugin",
    "ResearchRunContext",
    "ScanCoverageSlice",
    "audit_scan_coverage",
    "coverage_is_complete",
    "create_project",
    "execute_batch",
    "handoff_cloud",
    "promote_run",
    "run_smoke_benchmark",
    "run_project",
    "validate_baseline_exports",
]
