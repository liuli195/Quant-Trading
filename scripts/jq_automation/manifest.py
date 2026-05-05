from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class ManifestError(RuntimeError):
    """Raised when a batch manifest cannot be updated safely."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ManifestError(f"Manifest does not exist: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def update_manifest(
    path: str | Path,
    *,
    scenario_id: str,
    run_id: str | None = None,
    label: str | None = None,
    params_diff: dict[str, Any] | None = None,
    status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Update the status/run_id for *one run* within a scenario.

    Migrates legacy ``primary_run_id`` to the ``runs`` array on first write.
    """
    manifest_path = Path(path)
    data = load_manifest(manifest_path)
    scenarios = data.setdefault("scenarios", {})
    scenario = scenarios.setdefault(scenario_id, {})

    # ---- migrate legacy primary_run_id ----
    if "primary_run_id" in scenario and "runs" not in scenario:
        legacy_id = scenario.pop("primary_run_id")
        legacy_status = scenario.get("status") or "unknown"
        scenario["runs"] = []
        if legacy_id:
            scenario["runs"].append({
                "run_id": legacy_id,
                "label": "default",
                "params_diff": {},
                "status": legacy_status,
            })
        if scenario.get("note") and scenario["runs"]:
            scenario["runs"][0]["note"] = scenario.pop("note")
        else:
            scenario.pop("note", None)

    runs: list[dict[str, Any]] = scenario.setdefault("runs", [])

    # ---- locate or create the target run entry ----
    target_label = label or "default"
    entry = _find_run(runs, target_label)
    if entry is None:
        # This single empty default entry is a placeholder created while
        # expanding an old scenario.  Rename it on the first real run update so
        # the manifest keeps one run entry instead of a stale default plus the
        # actual labeled run.
        if len(runs) == 1 and runs[0].get("label") == "default" and not runs[0].get("run_id") and target_label != "default":
            runs[0]["label"] = target_label
            entry = runs[0]
        else:
            entry = {"run_id": None, "label": target_label, "params_diff": params_diff or {}, "status": "pending"}
            runs.append(entry)

    if run_id:
        entry["run_id"] = run_id
    if status:
        entry["status"] = status
    if params_diff:
        entry["params_diff"] = params_diff
    if error:
        entry["error"] = error
    else:
        entry.pop("error", None)

    # ---- aggregate scenario-level status ----
    run_statuses = {r.get("status") for r in runs}
    if "failed" in run_statuses:
        scenario["status"] = "failed"
    elif "in_progress" in run_statuses or "started" in run_statuses:
        scenario["status"] = "in_progress"
    elif all(s == "completed" for s in run_statuses):
        scenario["status"] = "completed"
    elif run_statuses:
        scenario["status"] = "in_progress"

    scenario.pop("primary_run_id", None)  # ensure legacy key is gone
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def list_pending_runs(
    manifest: dict[str, Any],
    scenario_filter: set[str] | None = None,
) -> list[tuple[str, dict[str, Any] | None]]:
    """Return (scenario_id, run_entry_or_None) for every scenario with pending work.

    When a scenario has an empty (or absent) ``runs`` list and its
    status is still pending, it returns ``(scenario_id, None)`` —
    the caller should expand the scenario config and create run entries.
    """
    result = []
    for sid, scenario in manifest.get("scenarios", {}).items():
        if scenario_filter and sid not in scenario_filter:
            continue
        runs = scenario.get("runs")
        if runs and len(runs) > 0:
            for run_entry in runs:
                if run_entry.get("status") not in ("completed",):
                    result.append((sid, run_entry))
        else:
            status = scenario.get("status")
            if status not in ("completed", "failed"):
                result.append((sid, None))
    return result


def _find_run(runs: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
    for r in runs:
        if r.get("label") == label:
            return r
    return None


# ---------------------------------------------------------------------------
# AB experiment manifest helpers
# ---------------------------------------------------------------------------


def get_ab_experiment(manifest: dict[str, Any], experiment_id: str) -> dict[str, Any] | None:
    """Return the AB experiment entry from a manifest, or None."""
    return manifest.get("ab_experiments", {}).get(experiment_id)


def update_ab_experiment(
    path: str | Path,
    experiment_id: str,
    variant_label: str,
    **fields: Any,
) -> dict[str, Any]:
    """Update a single variant entry inside an AB experiment in the manifest."""
    manifest_path = Path(path)
    data = load_manifest(manifest_path)
    ab_exps = data.setdefault("ab_experiments", {})
    exp = ab_exps.setdefault(experiment_id, {
        "status": "pending",
        "baseline": "",
        "controls": [],
        "config_hash": "",
        "variants": [],
        "upload_session": {},
    })
    variants = exp.setdefault("variants", [])

    entry = None
    for v in variants:
        if v.get("label") == variant_label:
            entry = v
            break
    if entry is None:
        entry = {"label": variant_label, "status": "pending"}
        # Inherit upload_index from number of existing variants
        entry["upload_index"] = len(variants) + 1
        variants.append(entry)

    for key, value in fields.items():
        entry[key] = value

    _aggregate_ab_experiment_status(exp)
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return exp


def sync_ab_experiment_status(manifest: dict[str, Any], experiment_id: str) -> dict[str, Any] | None:
    """Recompute the experiment-level status from its variants."""
    exp = manifest.get("ab_experiments", {}).get(experiment_id)
    if not exp:
        return None
    _aggregate_ab_experiment_status(exp)
    return exp


def _aggregate_ab_experiment_status(exp: dict[str, Any]) -> dict[str, Any]:
    """Aggregate variant statuses into experiment status (mutates and returns)."""
    statuses = {v.get("status") for v in exp.get("variants", [])}
    if "failed" in statuses:
        exp["status"] = "failed"
    elif "in_progress" in statuses or "started" in statuses:
        exp["status"] = "in_progress"
    elif all(s == "completed" for s in statuses) and statuses:
        exp["status"] = "completed"
    else:
        exp["status"] = "pending"
    return exp
