"""Audit-log parsing helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .pointers import read_text_file


def _iter_audit_rows(path: str | Path):
    for line in read_text_file(path).splitlines():
        if not line.strip():
            continue
        yield json.loads(line)


def load_rebalance_events(path: str | Path) -> list[dict]:
    """Return all `rebalance_signals` audit events in order."""

    return [row for row in _iter_audit_rows(path) if row.get("event") == "rebalance_signals"]


def load_run_start_params(path: str | Path) -> dict:
    """Return the parameter snapshot from the first `run_start` audit event."""

    for row in _iter_audit_rows(path):
        if row.get("event") == "run_start":
            return dict(row.get("params", {}))
    raise ValueError(f"run_start event not found in {path}")
