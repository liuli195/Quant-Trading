from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .paths import resolve_run_dir, resolve_tabs_dir, repo_root


class ArtifactError(RuntimeError):
    """Raised when fetched browser data cannot be persisted."""


def save_api_bundle(
    bundle: dict[str, Any],
    *,
    strategy: str,
    run_id: str,
    detail_bundle: dict[str, Any] | None = None,
    allow_partial: bool = False,
) -> Path:
    run_dir = resolve_run_dir(strategy, run_id)
    tabs_dir = resolve_tabs_dir(strategy, run_id)
    api_path = run_dir / "api_export.json"
    api_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    detail_path = None
    if detail_bundle is not None:
        detail_path = run_dir / "detail_api_export.json"
        detail_path.write_text(json.dumps(detail_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    save_module = _load_save_backtest_data()
    save_module.save_api_data(
        str(api_path),
        str(run_dir),
        tabs_dir=str(tabs_dir),
        detail_api_json_path=str(detail_path) if detail_path else None,
        allow_partial=allow_partial,
    )
    return run_dir


def save_dom_tabs(dom_tabs: dict[str, str], *, strategy: str, run_id: str) -> Path:
    run_dir = resolve_run_dir(strategy, run_id)
    tabs_dir = resolve_tabs_dir(strategy, run_id)
    persisted_path = run_dir / "dom_tabs_persisted.json"
    payload = [{"text": "```json\n" + json.dumps(json.dumps(dom_tabs, ensure_ascii=False), ensure_ascii=False) + "\n```"}]
    persisted_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    save_module = _load_save_backtest_data()
    save_module.save_all(str(persisted_path), str(run_dir), tabs_dir=str(tabs_dir))
    return run_dir


@lru_cache(maxsize=1)
def _load_save_backtest_data():
    root = repo_root()
    candidates = [
        root / "scripts" / "tools" / "jq_automation" / "utils" / "save_backtest_data.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_jq_save_backtest_data", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise ArtifactError("Could not find save_backtest_data.py")
