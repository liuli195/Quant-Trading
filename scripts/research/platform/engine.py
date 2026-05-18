"""Project orchestration for local-first research."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.research.research_core.layout import ResearchProjectLayout

from .contracts import ResearchRunContext
from .features import FeatureStore
from .plugins import get_plugin


SCHEMA_VERSION = 1
DEFAULT_TEMPLATES = {
    "factor_scan": "factor_scan",
    "parameter_followup": "parameter_followup",
    "robustness_check": "robustness_check",
    "generic": "generic",
    "portfolio_volatility": "portfolio_volatility",
}
PROJECT_LIFECYCLES = {"active", "superseded", "archived"}


def create_project(
    *,
    project_dir: str | Path,
    strategy: str,
    project: str,
    template: str,
    plugin: str | None = None,
    datasets: list[dict[str, Any]] | None = None,
    raw_data: str | None = None,
    extra_inputs: dict[str, Any] | None = None,
) -> Path:
    """Create a new local-first research project skeleton."""

    if template not in DEFAULT_TEMPLATES:
        raise ValueError(f"unknown template: {template}")
    selected_plugin = plugin or DEFAULT_TEMPLATES[template]
    get_plugin(selected_plugin)
    layout = ResearchProjectLayout.from_path(project_dir)
    layout.ensure_project_dirs()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "strategy": strategy,
        "project": project,
        "owner": "research-platform",
        "created_by": "research-platform",
        "updated_by": "research-platform",
        "created_at": now,
        "updated_at": now,
        "lifecycle": "active",
        "template": template,
        "plugin": selected_plugin,
        "datasets": datasets or [],
        "inputs": {
            **({} if raw_data is None else {"raw_data": raw_data}),
            **(extra_inputs or {}),
        },
        "runtime": {
            "fast_top_k": 20,
            "cloud_top_k": 3,
            "fast_mode_slo_seconds": 3.0,
            "full_mode_slo_seconds": 30.0,
        },
    }
    errors = validate_project_config(payload)
    if errors:
        raise ValueError(f"invalid project config: {'; '.join(errors)}")
    config_path = layout.root / "project.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_project_docs(layout.root, payload)
    return config_path


def load_project(project_dir: str | Path) -> dict[str, Any]:
    path = Path(project_dir) / "project.json"
    if not path.is_file():
        raise FileNotFoundError(f"project.json not found: {path}")
    project = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_project_config(project)
    if errors:
        raise ValueError(f"invalid project config {path}: {'; '.join(errors)}")
    return project


def validate_project_config(project: dict[str, Any]) -> list[str]:
    """Validate a research ``project.json`` control-plane record."""

    errors: list[str] = []
    if not isinstance(project, dict):
        return ["project config must be an object"]
    if project.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    for field in ("strategy", "project", "template", "plugin", "owner", "created_at", "updated_at", "lifecycle"):
        if not isinstance(project.get(field), str) or not str(project.get(field)).strip():
            errors.append(f"{field} is required")
    template = str(project.get("template", ""))
    if template and template not in DEFAULT_TEMPLATES:
        errors.append(f"unknown template: {template}")
    plugin = str(project.get("plugin", ""))
    if plugin:
        try:
            get_plugin(plugin)
        except KeyError:
            errors.append(f"unknown plugin: {plugin}")
    if project.get("lifecycle") not in PROJECT_LIFECYCLES:
        errors.append(f"lifecycle must be one of {sorted(PROJECT_LIFECYCLES)}")
    datasets = project.get("datasets")
    if not isinstance(datasets, list):
        errors.append("datasets must be a list")
    else:
        for index, dataset in enumerate(datasets):
            if not isinstance(dataset, dict):
                errors.append(f"datasets[{index}] must be an object")
                continue
            for field in ("dataset_id", "snapshot_id"):
                if not isinstance(dataset.get(field), str) or not dataset[field].strip():
                    errors.append(f"datasets[{index}].{field} is required")
    if not isinstance(project.get("inputs"), dict):
        errors.append("inputs must be an object")
    runtime = project.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime must be an object")
    else:
        for field in ("fast_top_k", "cloud_top_k"):
            value = runtime.get(field)
            if not isinstance(value, int) or value < 0:
                errors.append(f"runtime.{field} must be a non-negative integer")
        for field in ("fast_mode_slo_seconds", "full_mode_slo_seconds"):
            value = runtime.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                errors.append(f"runtime.{field} must be a positive number")
    return errors


def run_project(
    *,
    project_dir: str | Path,
    run_id: str,
    mode: str,
    top_k: int | None = None,
    cloud_top_k: int | None = None,
    shortlist: pd.DataFrame | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    """Run one fast or full project execution."""

    if mode not in {"fast", "full"}:
        raise ValueError("mode must be fast or full")
    project = load_project(project_dir)
    plugin = get_plugin(project["plugin"])
    layout = ResearchProjectLayout.from_path(project_dir)
    run = layout.run(run_id)
    run.ensure_dirs()
    runtime = project.get("runtime", {})
    context = ResearchRunContext(
        project_dir=layout.root,
        project=project,
        run=run,
        mode=mode,
        top_k=int(top_k or runtime.get("fast_top_k", 20)),
        cloud_top_k=int(cloud_top_k or runtime.get("cloud_top_k", 3)),
        source_run_id=source_run_id,
    )
    _write_request(
        context,
        {
            "mode": mode,
            "top_k": context.top_k,
            "cloud_top_k": context.cloud_top_k,
            "source_run_id": source_run_id,
        },
    )

    raw_feature_spec = plugin.build_feature_spec(project)
    dataset_fingerprint = plugin.dataset_fingerprint(project)
    store = FeatureStore()
    key = store.cache_key(
        dataset_fingerprint=dataset_fingerprint,
        feature_spec=raw_feature_spec,
        code_version=plugin.code_version,
    )
    features = store.load_or_build(key, lambda: plugin.build_features(project))
    context = replace(
        context,
        feature_cache_hit=features.cache_hit,
        feature_cold_build_seconds=features.build_seconds,
    )

    started = time.perf_counter()
    if mode == "fast":
        result = plugin.run_fast(context, features.payload)
        _write_fast_artifacts(context, result)
    else:
        effective_shortlist = shortlist if shortlist is not None else _load_shortlist_for_full(context)
        result = plugin.run_full(context, features.payload, effective_shortlist)
        _write_full_artifacts(context, result)
    runtime_seconds = time.perf_counter() - started
    _write_benchmark(
        context,
        runtime_seconds=runtime_seconds,
        cache_hit=features.cache_hit,
        cold_build_seconds=features.build_seconds,
    )
    manifest = _write_manifest(
        context,
        plugin_name=plugin.name,
        capabilities=plugin.capabilities,
        feature_cache={
            "cache_key": features.cache_key,
            "cache_hit": features.cache_hit,
            "cold_build_seconds": features.build_seconds,
        },
        runtime_seconds=runtime_seconds,
    )
    _write_status(
        context,
        {
            "mode": mode,
            "state": "completed",
            "runtime_seconds": runtime_seconds,
            "feature_cache_hit": features.cache_hit,
            "feature_cold_build_seconds": features.build_seconds,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return {"result": result, "manifest": manifest}


def promote_run(
    *,
    project_dir: str | Path,
    fast_run_id: str,
    full_run_id: str,
    top_k: int | None = None,
    cloud_top_k: int | None = None,
) -> dict[str, Any]:
    project = load_project(project_dir)
    plugin = get_plugin(project["plugin"])
    fast_shortlist = (
        ResearchProjectLayout.from_path(project_dir).run(fast_run_id).tables_dir / "shortlist.csv"
    )
    if not fast_shortlist.is_file():
        raise FileNotFoundError(f"fast shortlist not found: {fast_shortlist}")
    shortlist = pd.read_csv(fast_shortlist)
    if top_k is not None:
        shortlist = shortlist.head(top_k)
    validate_promotion = getattr(plugin, "validate_promotion", None)
    if callable(validate_promotion):
        validate_promotion(
            project_dir=Path(project_dir),
            fast_run_id=fast_run_id,
            shortlist=shortlist,
        )
    return run_project(
        project_dir=project_dir,
        run_id=full_run_id,
        mode="full",
        top_k=top_k,
        cloud_top_k=cloud_top_k,
        shortlist=shortlist,
        source_run_id=fast_run_id,
    )


def handoff_cloud(
    *,
    project_dir: str | Path,
    run_id: str,
) -> dict[str, Any]:
    project = load_project(project_dir)
    plugin = get_plugin(project["plugin"])
    layout = ResearchProjectLayout.from_path(project_dir)
    run = layout.run(run_id)
    cloud_path = run.tables_dir / "cloud_candidates.csv"
    cloud_candidates = pd.read_csv(cloud_path) if cloud_path.is_file() else pd.DataFrame()
    context = ResearchRunContext(
        project_dir=layout.root,
        project=project,
        run=run,
        mode="handoff",
        top_k=int(project.get("runtime", {}).get("fast_top_k", 20)),
        cloud_top_k=int(project.get("runtime", {}).get("cloud_top_k", 3)),
    )
    payload = plugin.build_cloud_handoff(context, cloud_candidates)
    if payload is None:
        payload = {"status": "unsupported", "commands": []}
    (run.tables_dir / "cloud_handoff.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def resume_run(
    *,
    project_dir: str | Path,
    run_id: str,
) -> dict[str, Any]:
    layout = ResearchProjectLayout.from_path(project_dir)
    request_path = layout.run(run_id).root / "request.json"
    if not request_path.is_file():
        raise FileNotFoundError(f"request.json not found: {request_path}")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request["mode"] == "full" and request.get("source_run_id"):
        return promote_run(
            project_dir=project_dir,
            fast_run_id=request["source_run_id"],
            full_run_id=run_id,
            top_k=request.get("top_k"),
            cloud_top_k=request.get("cloud_top_k"),
        )
    return run_project(
        project_dir=project_dir,
        run_id=run_id,
        mode=request["mode"],
        top_k=request.get("top_k"),
        cloud_top_k=request.get("cloud_top_k"),
        source_run_id=request.get("source_run_id"),
    )


def _write_fast_artifacts(context: ResearchRunContext, result: dict[str, Any]) -> None:
    result["grid"].to_csv(context.run.tables_dir / "fast_grid.csv", index=False)
    funnel = result["funnel"]
    funnel.ranked.to_csv(context.run.tables_dir / "candidate_ranking.csv", index=False)
    funnel.discarded.to_csv(context.run.tables_dir / "discarded_candidates.csv", index=False)
    funnel.shortlist.to_csv(context.run.tables_dir / "shortlist.csv", index=False)
    (context.run.tables_dir / "fast_decision.json").write_text(
        json.dumps(result["decision"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_full_artifacts(context: ResearchRunContext, result: dict[str, Any]) -> None:
    reviewed = result["reviewed"]
    funnel = result["funnel"]
    reviewed.to_csv(context.run.tables_dir / "full_candidate_review.csv", index=False)
    funnel.discarded.to_csv(context.run.tables_dir / "discarded_candidates.csv", index=False)
    funnel.shortlist.to_csv(context.run.tables_dir / "shortlist.csv", index=False)
    funnel.cloud_candidates.to_csv(context.run.tables_dir / "cloud_candidates.csv", index=False)
    (context.run.tables_dir / "full_decision.json").write_text(
        json.dumps(result["decision"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_shortlist_for_full(context: ResearchRunContext) -> pd.DataFrame:
    shortlist_path = context.run.tables_dir / "shortlist.csv"
    if not shortlist_path.is_file():
        raise ValueError("full mode requires a shortlist or promote from a fast run")
    return pd.read_csv(shortlist_path)


def _write_manifest(
    context: ResearchRunContext,
    *,
    plugin_name: str,
    capabilities: Any,
    feature_cache: dict[str, Any],
    runtime_seconds: float,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "project": context.project["project"],
        "strategy": context.project["strategy"],
        "run_id": context.run.run_id,
        "mode": context.mode,
        "plugin": plugin_name,
        "source_run_id": context.source_run_id,
        "datasets": context.project.get("datasets", []),
        "inputs": context.project.get("inputs", {}),
        "capabilities": {
            "local_capabilities": list(capabilities.local_capabilities),
            "replayable_params": list(capabilities.replayable_params),
            "required_exports": list(capabilities.required_exports),
            "unsupported_changes": list(capabilities.unsupported_changes),
            "fidelity_level": str(capabilities.fidelity_level),
        },
        "feature_cache": feature_cache,
        "runtime_seconds": runtime_seconds,
        "artifacts": {
            "reports": sorted(path.name for path in context.run.reports_dir.iterdir() if path.is_file()),
            "tables": sorted(path.name for path in context.run.tables_dir.iterdir() if path.is_file()),
            "curves": sorted(path.name for path in context.run.curves_dir.iterdir() if path.is_file()),
            "checkpoints": sorted(path.name for path in context.run.checkpoints_dir.iterdir() if path.is_file()),
        },
    }
    context.run.manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _write_status(context: ResearchRunContext, payload: dict[str, Any]) -> None:
    context.run.status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_request(context: ResearchRunContext, payload: dict[str, Any]) -> None:
    (context.run.root / "request.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_benchmark(
    context: ResearchRunContext,
    *,
    runtime_seconds: float,
    cache_hit: bool,
    cold_build_seconds: float,
) -> None:
    runtime = context.project.get("runtime", {})
    target = runtime.get("fast_mode_slo_seconds") if context.mode == "fast" else runtime.get("full_mode_slo_seconds")
    payload = {
        "mode": context.mode,
        "cache_hit": cache_hit,
        "cold_build_seconds": cold_build_seconds,
        "runtime_seconds": runtime_seconds,
        "target_seconds": target,
        "slo_passed": None if target is None else runtime_seconds <= float(target),
    }
    (context.run.tables_dir / "benchmark.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_project_docs(root: Path, project: dict[str, Any]) -> None:
    docs = {
        "README.md": f"# {project['project']}\n\n- template: `{project['template']}`\n- plugin: `{project['plugin']}`\n",
        "docs/research_spec.md": "# 研究规格\n\n",
        "docs/data_contract.md": "# 数据契约\n\n",
        "docs/execution_plan.md": "# 执行计划\n\n",
        "docs/cloud_confirmation_plan.md": "# 云端确认计划\n\n",
        "docs/performance_plan.md": "# 性能计划\n\n",
        "docs/decision_log.md": "# 决策记录\n\n",
    }
    for relative, text in docs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(text, encoding="utf-8")
