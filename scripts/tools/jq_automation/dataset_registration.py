from __future__ import annotations

import re
from pathlib import Path


class DatasetRegistrationError(RuntimeError):
    """Raised when a saved JoinQuant run cannot be registered as a dataset."""


def register_backtest_run_dataset(
    run_dir: str | Path,
    *,
    strategy: str,
    run_id: str,
    datasets_root: str | Path = "research_datasets",
    enabled: bool = True,
    allow_partial: bool = False,
    compact_source: bool = True,
) -> Path | None:
    """Register a saved ``backtest_runs/<run_id>`` directory in the data center.

    A duplicate snapshot is treated as already registered.  In partial fetch
    mode, incomplete artifacts are kept but the dataset registration warning is
    non-fatal so the caller can still inspect the partial run.
    """

    if not enabled:
        return None

    from scripts.research.platform.datasets import DatasetError, compact_backtest_run_source, import_backtest_run

    dataset_id = f"{_safe_component(strategy)}_backtest_runs"
    snapshot_id = _safe_component(run_id)
    snapshot_root = Path(datasets_root) / dataset_id / snapshot_id
    try:
        snapshot = import_backtest_run(
            run_dir,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            datasets_root=datasets_root,
        )
    except DatasetError as exc:
        message = str(exc)
        if "dataset snapshot already exists" in message:
            print(f"Dataset snapshot already registered: {dataset_id}/{snapshot_id}")
            if compact_source:
                compact_backtest_run_source(
                    run_dir,
                    dataset_id=dataset_id,
                    snapshot_id=snapshot_id,
                    snapshot_root=snapshot_root,
                )
            return None
        if allow_partial:
            print(f"Dataset registration skipped for partial run: {message}")
            return None
        raise DatasetRegistrationError(message) from exc

    if compact_source:
        compact_backtest_run_source(
            run_dir,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            snapshot_root=snapshot.root,
        )
    print(f"Registered dataset snapshot: {snapshot.root}")
    return snapshot.root


def _safe_component(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-")
    return safe or "unnamed"
