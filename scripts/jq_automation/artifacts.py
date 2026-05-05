from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from .paths import resolve_run_dir, resolve_tabs_dir, repo_root


class ArtifactError(RuntimeError):
    """Raised when fetched browser data cannot be persisted."""


def save_api_bundle(bundle: dict[str, Any], *, strategy: str, run_id: str) -> Path:
    run_dir = resolve_run_dir(strategy, run_id)
    tabs_dir = resolve_tabs_dir(strategy, run_id)
    api_path = run_dir / "api_export.json"
    api_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    save_module = _load_save_backtest_data()
    save_module.save_api_data(str(api_path), str(run_dir), tabs_dir=str(tabs_dir))
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


def _load_save_backtest_data():
    root = repo_root()
    candidates = [
        root / ".agents" / "skills" / "jq-run" / "scripts" / "save_backtest_data.py",
        root / ".claude" / "skills" / "jq-run" / "scripts" / "save_backtest_data.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_jq_save_backtest_data", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise ArtifactError("Could not find jq-run save_backtest_data.py")
