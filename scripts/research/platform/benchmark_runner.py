"""Reusable performance-smoke helpers for local research plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .batch_executor import BatchExecutionResult, execute_batch


@dataclass(frozen=True)
class BenchmarkSummary:
    """Cold/warm benchmark summary for one representative batch."""

    sample_size: int
    full_item_count: int
    cold: BatchExecutionResult
    warm: BatchExecutionResult
    predicted_full_seconds: float
    target_seconds: float

    @property
    def passed(self) -> bool:
        """Whether the warm-path projection clears the target."""

        return (
            not self.cold.errors
            and not self.warm.errors
            and self.predicted_full_seconds <= self.target_seconds
        )


def run_smoke_benchmark(
    items: Iterable[Any],
    evaluator: Callable[[Any], dict[str, Any]],
    *,
    full_item_count: int,
    target_seconds: float,
) -> BenchmarkSummary:
    """Run representative cold/warm passes and project full-run time."""

    materialized = list(items)
    cold = execute_batch(materialized, evaluator)
    warm = execute_batch(materialized, evaluator)
    predicted_full_seconds = warm.per_item_seconds * int(full_item_count)
    return BenchmarkSummary(
        sample_size=len(materialized),
        full_item_count=int(full_item_count),
        cold=cold,
        warm=warm,
        predicted_full_seconds=predicted_full_seconds,
        target_seconds=float(target_seconds),
    )
