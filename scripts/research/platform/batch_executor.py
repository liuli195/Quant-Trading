"""Reusable batch-execution helpers for local research plugins."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class BatchExecutionResult:
    """One measured batch execution."""

    rows: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    item_count: int
    runtime_seconds: float

    @property
    def per_item_seconds(self) -> float:
        """Average runtime per attempted item."""

        return 0.0 if self.item_count == 0 else self.runtime_seconds / self.item_count


def execute_batch(
    items: Iterable[Any],
    evaluator: Callable[[Any], dict[str, Any]],
) -> BatchExecutionResult:
    """Evaluate items sequentially while collecting structured failures."""

    materialized = list(items)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, item in enumerate(materialized):
        try:
            rows.append(evaluator(item))
        except Exception as exc:  # pragma: no cover - exercised via focused unit test
            errors.append(
                {
                    "index": index,
                    "item": item,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    runtime_seconds = time.perf_counter() - started
    return BatchExecutionResult(
        rows=rows,
        errors=errors,
        item_count=len(materialized),
        runtime_seconds=runtime_seconds,
    )
