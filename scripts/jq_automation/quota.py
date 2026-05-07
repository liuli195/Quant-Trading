from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import quota_ledger_dir


DAILY_BUDGET_MINUTES = 60.0
MIN_REMAINING_WARNING_MINUTES = 10.0


class QuotaError(RuntimeError):
    """Raised when a planned cloud run would exceed the quota guardrail."""


def ledger_path_for(date_key: str | None = None) -> Path:
    key = date_key or datetime.now().strftime("%Y%m%d")
    return quota_ledger_dir() / f"{key}.json"


def load_ledger(path: str | Path | None = None) -> dict[str, Any]:
    ledger_path = Path(path) if path else ledger_path_for()
    if not ledger_path.is_file():
        return {
            "date": ledger_path.stem,
            "budget_minutes": DAILY_BUDGET_MINUTES,
            "runs": [],
        }
    return json.loads(ledger_path.read_text(encoding="utf-8"))


def save_ledger(ledger: dict[str, Any], path: str | Path | None = None) -> Path:
    ledger_path = Path(path) if path else ledger_path_for(str(ledger.get("date") or ""))
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return ledger_path


def used_minutes(ledger: dict[str, Any]) -> float:
    """Sum consumed minutes, preferring actual_minutes over estimated_minutes.

    ``actual_minutes`` is sourced from JoinQuant's /algorithm/backtest/runTimeInfo
    (field ``needSeconds`` converted to minutes) and reflects the real CPU time
    the platform billed.  When actual usage is known, it is counted even for a
    failed or cancelled run.
    """
    total = 0.0
    for item in ledger.get("runs", []):
        actual_minutes = item.get("actual_minutes")
        if actual_minutes not in (None, ""):
            total += float(actual_minutes)
        elif item.get("status") not in {"failed", "cancelled"}:
            total += float(item.get("estimated_minutes") or 0)
    return total


def update_actual_minutes(ledger: dict[str, Any], run_id: str, actual_minutes: float) -> dict[str, Any] | None:
    """Record the actual consumed minutes for a completed run.

    Call this after extracting ``needSeconds`` from the runtime API bundle.
    """
    for item in ledger.get("runs", []):
        if item.get("run_id") == run_id:
            item["actual_minutes"] = float(actual_minutes)
            return item
    return None


def extract_actual_minutes_from_bundle(bundle: dict[str, Any]) -> float | None:
    """Extract actual consumed minutes from an API bundle's runtime section.

    JoinQuant's runTimeInfo API returns ``data.needSeconds`` — the precise
    CPU-seconds consumed by the backtest.  We convert to minutes.
    """
    runtime = bundle.get("runtime", {})
    if not runtime and isinstance(bundle.get("supplemental_detail"), dict):
        runtime = bundle["supplemental_detail"].get("runtime", {})
    data = runtime.get("data", {}) if isinstance(runtime, dict) else {}
    need_seconds = data.get("needSeconds")
    if isinstance(need_seconds, (int, float)) and need_seconds > 0:
        return need_seconds / 60.0
    return None


def remaining_minutes(ledger: dict[str, Any]) -> float:
    return float(ledger.get("budget_minutes", DAILY_BUDGET_MINUTES)) - used_minutes(ledger)


def assert_quota_available(ledger: dict[str, Any], estimated_minutes: float) -> None:
    remaining = remaining_minutes(ledger)
    if remaining < MIN_REMAINING_WARNING_MINUTES:
        raise QuotaError(f"Remaining JoinQuant cloud budget is below {MIN_REMAINING_WARNING_MINUTES:g} minutes")
    if estimated_minutes and estimated_minutes > remaining:
        raise QuotaError(f"Estimated run needs {estimated_minutes:g} minutes, but only {remaining:g} remain")


def append_quota_entry(
    ledger: dict[str, Any],
    *,
    scenario_id: str,
    run_id: str,
    estimated_minutes: float,
    status: str,
) -> dict[str, Any]:
    item = {
        "scenario_id": scenario_id,
        "run_id": run_id,
        "estimated_minutes": float(estimated_minutes or 0),
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    ledger.setdefault("runs", []).append(item)
    return ledger
