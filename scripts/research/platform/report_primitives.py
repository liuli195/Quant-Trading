"""Small shared helpers for research markdown reports."""

from __future__ import annotations

import pandas as pd

from scripts.research.research_core.reporting import markdown_table

from .benchmark_runner import BenchmarkSummary


def percent(value: float) -> str:
    """Render a ratio as a percentage."""

    return f"{value:.2%}"


def seconds(value: float) -> str:
    """Render elapsed seconds compactly."""

    return f"{value:.3f}s"


def benchmark_frame(summary: BenchmarkSummary) -> pd.DataFrame:
    """Return a two-row cold/warm benchmark table."""

    return pd.DataFrame(
        [
            {
                "pass": "cold",
                "sample_size": summary.sample_size,
                "runtime_seconds": seconds(summary.cold.runtime_seconds),
                "per_item_ms": f"{summary.cold.per_item_seconds * 1000:.3f}",
                "error_count": len(summary.cold.errors),
            },
            {
                "pass": "warm",
                "sample_size": summary.sample_size,
                "runtime_seconds": seconds(summary.warm.runtime_seconds),
                "per_item_ms": f"{summary.warm.per_item_seconds * 1000:.3f}",
                "error_count": len(summary.warm.errors),
            },
        ]
    )


def markdown_section(title: str, frame: pd.DataFrame) -> str:
    """Render one markdown heading plus table."""

    return "\n".join([f"## {title}", "", markdown_table(frame)])
