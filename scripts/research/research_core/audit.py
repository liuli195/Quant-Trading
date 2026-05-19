"""Audit-log parsing helpers."""

from __future__ import annotations

import gzip
import json
from pathlib import Path


def _iter_audit_rows(path: str | Path):
    for line in _read_text_file(Path(path)).splitlines():
        if not line.strip():
            continue
        yield json.loads(line)


def _read_text_file(path: Path) -> str:
    target = _resolve_data_center_pointer(path)
    if target is not None:
        return _read_text_file(target)
    raw = path.read_bytes()
    if path.suffix.lower() == ".gz":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8-sig")


def _resolve_data_center_pointer(path: Path) -> Path | None:
    if not path.is_file() or path.stat().st_size > 8192:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("kind") != "data_center_pointer":
        return None
    snapshot = Path(str(payload.get("dataset_snapshot", "")))
    dataset_file = str(payload.get("dataset_file", ""))
    if not dataset_file:
        return None
    target = snapshot / dataset_file
    if target.is_file():
        return target
    if not snapshot.is_absolute():
        cwd_target = Path.cwd() / snapshot / dataset_file
        if cwd_target.is_file():
            return cwd_target
    return target


def load_rebalance_events(path: str | Path) -> list[dict]:
    """Return all `rebalance_signals` audit events in order."""

    return [row for row in _iter_audit_rows(path) if row.get("event") == "rebalance_signals"]


def load_run_start_params(path: str | Path) -> dict:
    """Return the parameter snapshot from the first `run_start` audit event."""

    for row in _iter_audit_rows(path):
        if row.get("event") == "run_start":
            return dict(row.get("params", {}))
    raise ValueError(f"run_start event not found in {path}")
