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
    status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    manifest_path = Path(path)
    data = load_manifest(manifest_path)
    scenarios = data.setdefault("scenarios", {})
    scenario = scenarios.setdefault(scenario_id, {})
    if run_id:
        scenario["primary_run_id"] = run_id
    if status:
        scenario["status"] = status
    if error:
        scenario["error"] = error
    else:
        scenario.pop("error", None)
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
