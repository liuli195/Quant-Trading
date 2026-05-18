from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .artifacts import save_api_bundle, save_dom_tabs
from .config import load_config_mapping
from .dataset_registration import register_backtest_run_dataset
from .git_versioning import (
    GitVersionError,
    assert_file_at_commit,
    compute_uploaded_code_sha256,
    materialize_strategy_source,
    resolve_git_ref,
)
from .cli import _compile_date_range
from .local import apply_params_overrides, compile_strategy, generate_upload_file
from .manifest import load_manifest
from .metrics import DEFAULT_METRICS, METRIC_LABEL_CN, collect_all_metrics
from .paths import (
    detail_url_for,
    make_run_id,
    repo_root,
    resolve_batch_manifest,
    resolve_run_dir,
)
from .quota import (
    QuotaError,
    append_quota_entry,
    assert_quota_available,
    extract_actual_minutes_from_bundle,
    ledger_path_for,
    load_ledger,
    save_ledger,
    update_actual_minutes,
)
from scripts.tools.path_tools.aliases import resolve_path

# ---------------------------------------------------------------------------
# Error classes declared here so cli.main() can catch them without importing
# from abtest.py at parse time (avoids circular-import edge cases).
# ---------------------------------------------------------------------------


class ABConfigError(ValueError):
    """Raised when an AB experiment config is invalid."""


class ABExpandError(RuntimeError):
    """Raised when the expand phase cannot proceed."""


class ABReportError(RuntimeError):
    """Raised when report generation cannot proceed."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ABCodeSource:
    """Resolved (frozen) code source for a single variant."""
    type: str  # "git"
    ref: str   # original ref string (branch / tag / SHA)
    commit: str  # frozen full commit SHA (set by expand)
    path: str  # repo-relative path to the strategy file


@dataclass(frozen=True)
class ABVariantSpec:
    """Parsed specification of a single AB variant from the experiment config."""
    label: str
    role: str  # "control" or "variant"
    variant_id: str | None
    code_source: ABCodeSource
    params_mode: str  # "params_diff" or "baked_in_git"
    params_diff: dict[str, Any]
    scan_source: dict[str, Any] | None
    note: str | None


@dataclass(frozen=True)
class ABExperimentConfig:
    """Fully parsed and validated AB experiment configuration."""
    experiment_id: str
    strategy: str
    batch_id: str
    baseline: str
    controls: list[str]
    base: dict[str, Any]
    variants: list[ABVariantSpec]
    metrics: list[dict[str, str]]
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Config loading & validation
# ---------------------------------------------------------------------------


def load_ab_config(path_or_dict: str | Path | dict[str, Any]) -> ABExperimentConfig:
    """Read and validate an AB experiment JSON config file (or accept a dict for testing)."""
    if isinstance(path_or_dict, dict):
        raw = path_or_dict
    else:
        raw = load_config_mapping(path_or_dict)

    # -- required top-level keys --
    experiment_id = str(raw.get("experiment_id") or "")
    if not experiment_id:
        raise ABConfigError("experiment_id is required and must be non-empty")

    strategy = str(raw.get("strategy") or "")
    if not strategy:
        raise ABConfigError("strategy is required and must be non-empty")

    batch_id = str(raw.get("batch_id") or "")
    if not batch_id:
        raise ABConfigError("batch_id is required and must be non-empty")

    base = raw.get("base")
    if not isinstance(base, dict):
        raise ABConfigError("base is required and must be a dict")

    # Validate base required fields
    for key in ("start_date", "end_date", "capital"):
        if base.get(key) in (None, ""):
            raise ABConfigError(f"base.{key} is required")

    variants_raw = raw.get("variants")
    if not isinstance(variants_raw, list) or len(variants_raw) == 0:
        raise ABConfigError("variants must be a non-empty list")

    baseline = str(raw.get("baseline") or "")
    if not baseline:
        raise ABConfigError("baseline is required and must be non-empty")

    controls_raw = raw.get("controls")
    controls: list[str] = []
    if isinstance(controls_raw, list):
        controls = [str(c) for c in controls_raw if c]

    # -- parse base code_source --
    base_code_source_raw = base.get("code_source")
    if not isinstance(base_code_source_raw, dict) or base_code_source_raw.get("type") != "git":
        raise ABConfigError("base.code_source.type must be 'git'")
    base_cs_kwargs = _parse_code_source(base_code_source_raw)

    # -- parse variants --
    variant_labels: set[str] = set()
    variants: list[ABVariantSpec] = []

    for i, v in enumerate(variants_raw):
        if not isinstance(v, dict):
            raise ABConfigError(f"variants[{i}] must be a dict")

        label = str(v.get("label") or "")
        if not label:
            raise ABConfigError(f"variants[{i}].label is required")
        if label in variant_labels:
            raise ABConfigError(f"Duplicate variant label: '{label}'")
        variant_labels.add(label)

        role = str(v.get("role") or "variant")
        if role not in ("control", "variant"):
            raise ABConfigError(f"variants[{i}].role must be 'control' or 'variant', got: {role}")

        variant_id_raw = v.get("variant_id")
        variant_id = str(variant_id_raw).strip() if variant_id_raw not in (None, "") else None

        params_mode = str(v.get("params_mode") or "params_diff")
        if params_mode not in ("params_diff", "baked_in_git"):
            raise ABConfigError(
                f"variants[{i}].params_mode must be 'params_diff' or 'baked_in_git', got: {params_mode}"
            )

        params_diff = _dictify(v.get("params_diff"))
        # Forbid 'note' inside params_diff
        if "note" in params_diff:
            raise ABConfigError(
                f"variants[{i}].params_diff contains 'note' key; "
                f"set note at the variant top-level instead"
            )

        scan_source = v.get("scan_source")
        if scan_source is not None and not isinstance(scan_source, dict):
            raise ABConfigError(f"variants[{i}].scan_source must be a dict or null")

        note = v.get("note")
        if note is not None:
            note = str(note)

        registered_variant = None
        if variant_id:
            if "params_diff" in v and params_diff:
                raise ABConfigError(
                    f"variants[{i}] uses variant_id, so params_diff must be stored in the variant registry"
                )
            if isinstance(v.get("code_source"), dict):
                raise ABConfigError(
                    f"variants[{i}] uses variant_id, so code_source must be stored in the variant registry"
                )
            registered_variant = _load_registered_variant(
                strategy=strategy,
                base_code_path=base_cs_kwargs["path"],
                variant_id=variant_id,
            )
            params_diff = _registered_params_diff(registered_variant)
            if params_diff and params_mode == "baked_in_git":
                raise ABConfigError(
                    f"variants[{i}] variant_id '{variant_id}' has registered params_diff; "
                    "use params_mode='params_diff'"
                )
            if scan_source is None:
                scan_source = {"variant_id": variant_id}
            if note is None and registered_variant.get("description"):
                note = str(registered_variant["description"])

        # Merge code_source: variant registry > variant-level override > base
        variant_cs_raw = _registered_code_source(registered_variant) if registered_variant else v.get("code_source")
        if isinstance(variant_cs_raw, dict):
            cs_kwargs = _parse_code_source(variant_cs_raw)
        else:
            cs_kwargs = dict(base_cs_kwargs)

        code_source = ABCodeSource(
            type=cs_kwargs["type"],
            ref=cs_kwargs["ref"],
            commit="",  # frozen during expand
            path=cs_kwargs["path"],
        )

        variants.append(ABVariantSpec(
            label=label,
            role=role,
            variant_id=variant_id,
            code_source=code_source,
            params_mode=params_mode,
            params_diff=params_diff,
            scan_source=scan_source,
            note=note,
        ))

    # -- validate baseline matches a variant --
    if baseline not in variant_labels:
        raise ABConfigError(f"baseline '{baseline}' does not match any variant label")

    # -- validate controls --
    for c in controls:
        if c not in variant_labels:
            raise ABConfigError(f"controls label '{c}' does not match any variant label")

    # -- parse metrics --
    metrics_raw = raw.get("metrics")
    if isinstance(metrics_raw, list) and metrics_raw:
        metrics = []
        for m in metrics_raw:
            if isinstance(m, dict) and "key" in m:
                metrics.append({"key": str(m["key"]), "direction": str(m.get("direction", "maximize"))})
    else:
        metrics = list(DEFAULT_METRICS)

    return ABExperimentConfig(
        experiment_id=experiment_id,
        strategy=strategy,
        batch_id=batch_id,
        baseline=baseline,
        controls=controls,
        base=base,
        variants=variants,
        metrics=metrics,
        raw=raw,
    )


def compute_config_hash(raw: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash of the raw config dict."""
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------


def resolve_ab_code_sources(config: ABExperimentConfig) -> ABExperimentConfig:
    """Freeze every variant's code_source.ref into a commit SHA."""
    root = repo_root()
    frozen_variants: list[ABVariantSpec] = []
    for v in config.variants:
        try:
            commit = assert_file_at_commit(v.code_source.ref, v.code_source.path, root=root)
        except GitVersionError as exc:
            raise ABExpandError(f"Cannot resolve variant '{v.label}': {exc}") from exc
        frozen_cs = ABCodeSource(
            type=v.code_source.type,
            ref=v.code_source.ref,
            commit=commit,
            path=v.code_source.path,
        )
        frozen_variants.append(ABVariantSpec(
            label=v.label,
            role=v.role,
            variant_id=v.variant_id,
            code_source=frozen_cs,
            params_mode=v.params_mode,
            params_diff=v.params_diff,
            scan_source=v.scan_source,
            note=v.note,
        ))
    return ABExperimentConfig(
        experiment_id=config.experiment_id,
        strategy=config.strategy,
        batch_id=config.batch_id,
        baseline=config.baseline,
        controls=config.controls,
        base=config.base,
        variants=frozen_variants,
        metrics=config.metrics,
        raw=config.raw,
    )


def expand_ab_experiment(
    config: ABExperimentConfig,
    manifest_path: Path,
    *,
    force_reset_pending: bool = False,
) -> dict[str, Any]:
    """Expand an AB experiment config into scenario files and a manifest entry.

    Returns the manifest ``ab_experiments[experiment_id]`` dict.
    """
    # 1. Freeze git refs
    frozen = resolve_ab_code_sources(config)
    config_hash = compute_config_hash(config.raw)

    # 2. Load manifest, check for conflicts
    manifest = load_manifest(manifest_path) if manifest_path.is_file() else {}
    ab_exps = manifest.setdefault("ab_experiments", {})
    existing = ab_exps.get(config.experiment_id)

    if existing:
        existing_hash = existing.get("config_hash", "")
        if existing_hash and existing_hash != config_hash:
            # Config changed — check if any variant completed
            any_completed = any(
                v.get("status") == "completed"
                for v in existing.get("variants", [])
            )
            if any_completed:
                raise ABExpandError(
                    f"Config hash changed for completed experiment '{config.experiment_id}'. "
                    f"Create a new experiment_id or archive the old one."
                )
        if force_reset_pending:
            _reset_pending_variants(existing)

    # 3. Generate scenarios
    scenarios_dir = manifest_path.parent / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    candidate_order: list[str] = []
    variant_entries: list[dict[str, Any]] = []

    for idx, v in enumerate(frozen.variants, start=1):
        scenario_id = f"ab-{_sanitize(config.experiment_id)}-{_sanitize(v.label)}"
        candidate_order.append(v.label)
        run_label = v.label

        # Preserve existing backtest data if scenario already exists and is completed
        existing_va = _find_variant_entry(existing, v.label) if existing else None
        preserved_run_id = existing_va.get("run_id") if existing_va and existing_va.get("status") == "completed" else None
        preserved_backtest_id = existing_va.get("backtest_id") if existing_va and existing_va.get("status") == "completed" else None
        preserved_backtest_url = existing_va.get("backtest_url") if existing_va and existing_va.get("status") == "completed" else None
        preserved_sha256 = existing_va.get("uploaded_code_sha256") if existing_va and existing_va.get("status") == "completed" else None
        preserved_status = "completed" if preserved_run_id else "pending"

        variant_entry = {
            "label": v.label,
            "scenario_id": scenario_id,
            "run_label": run_label,
            "run_id": preserved_run_id,
            "role": v.role,
            "variant_id": v.variant_id,
            "is_baseline": v.label == config.baseline,
            "upload_index": idx,
            "code_source": {
                "type": v.code_source.type,
                "ref": v.code_source.ref,
                "commit": v.code_source.commit,
                "path": v.code_source.path,
            },
            "params_mode": v.params_mode,
            "params_diff": v.params_diff,
            "scan_source": v.scan_source,
            "uploaded_code_sha256": preserved_sha256,
            "backtest_id": preserved_backtest_id,
            "backtest_url": preserved_backtest_url,
            "status": preserved_status,
        }
        variant_entries.append(variant_entry)

        # Write scenario.json
        scenario_json_path = scenarios_dir / scenario_id / "scenario.json"
        scenario_json_path.parent.mkdir(parents=True, exist_ok=True)

        # Build scenario config: inherit from base, add variant params
        scenario_cfg = {
            "strategy_file": str(materialize_strategy_source(
                v.code_source.commit, v.code_source.path,
                config.experiment_id, v.label,
            )),
            "scenario_id": scenario_id,
            "start_date": config.base["start_date"],
            "end_date": config.base["end_date"],
            "capital": config.base["capital"],
            "frequency": str(config.base.get("frequency") or "每天"),
            "py_version": str(config.base.get("py_version") or "Python3"),
            "estimated_minutes": _parse_minutes(config.base),
            "batch_id": config.batch_id,
            "strategy": config.strategy,
            "params_diff": v.params_diff,
            "variant_id": v.variant_id,
            "_params_mode": v.params_mode,
            "_scan_source": v.scan_source,
            "_experiment_id": config.experiment_id,
        }
        scenario_json_path.write_text(
            json.dumps(scenario_cfg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 4. Build experiment manifest entry
    experiment_entry = {
        "status": "pending",
        "baseline": config.baseline,
        "controls": config.controls,
        "config_hash": config_hash,
        "variants": variant_entries,
        "upload_session": {},
    }
    _sync_experiment_status(experiment_entry)

    # Merge into manifest
    manifest["ab_experiments"] = ab_exps
    manifest["ab_experiments"][config.experiment_id] = experiment_entry
    manifest["batch_id"] = manifest.get("batch_id") or config.batch_id
    manifest["strategy"] = manifest.get("strategy") or config.strategy
    manifest["updated"] = datetime.now().isoformat(timespec="seconds")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return experiment_entry


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_ab_experiment(args: Any, config: ABExperimentConfig, manifest_path: Path) -> int:
    """Execute all pending/failed AB variants in a single browser/editor session.

    *args* is the argparse Namespace with at least: ``user_data_dir``,
    ``headless``, ``slow_mo``, ``backtest_timeout``, and ``yes``.
    """
    # 1. Expand first (idempotent)
    experiment_entry = expand_ab_experiment(config, manifest_path)

    # 2. Find pending/failed variants
    pending = [
        v for v in experiment_entry.get("variants", [])
        if v.get("status") in ("pending", "failed")
    ]
    if not pending:
        print("All variants already completed — nothing to run.")
        return 0

    # Print run plan
    print(f"\nAB Experiment: {config.experiment_id}")
    print(f"  Strategy: {config.strategy}")
    print(f"  Batch: {config.batch_id}")
    print(f"  Variants to run: {len(pending)}")
    for v in pending:
        cs = v.get("code_source", {})
        print(f"    [{v['upload_index']}] {v['label']} "
              f"(ref={cs.get('ref', '?')}, params_mode={v.get('params_mode', '?')})")
    print()

    if not getattr(args, "yes", False):
        from .cli import _confirm as cli_confirm
        if not cli_confirm("Type RUN to start AB backtests: "):
            print("Cancelled.")
            return 1

    # We import these lazily to avoid circular imports at module level.
    from .browser import AutomationError, CompileFailed, JoinQuantBrowser
    from .cli import _allow_partial, _bundle_options, _fetch_backtest_data, _make_audit_token, _selected_result_source
    from .cli import _set_quota_status as cli_set_quota_status

    import asyncio
    return asyncio.run(
        _ab_run_session(
            args, config, manifest_path, experiment_entry, pending,
            JoinQuantBrowser=JoinQuantBrowser,
            AutomationError=AutomationError,
            CompileFailed=CompileFailed,
            _bundle_options=_bundle_options,
            _fetch_backtest_data=_fetch_backtest_data,
            _make_audit_token=_make_audit_token,
            _selected_result_source=_selected_result_source,
            _allow_partial=_allow_partial,
            cli_set_quota_status=cli_set_quota_status,
        )
    )


async def _ab_run_session(
    args: Any,
    config: ABExperimentConfig,
    manifest_path: Path,
    experiment_entry: dict[str, Any],
    pending_variants: list[dict[str, Any]],
    JoinQuantBrowser: Any,
    AutomationError: Any,
    CompileFailed: Any,
    _bundle_options: Any,
    _fetch_backtest_data: Any,
    _make_audit_token: Any,
    _selected_result_source: Any,
    _allow_partial: Any,
    cli_set_quota_status: Any,
) -> int:
    """Core async session: one browser, one editor, sequential variant uploads."""
    from .manifest import update_ab_experiment

    session_started_at = datetime.now().isoformat(timespec="seconds")
    overall_status = 0

    # Look up the frozen config to map label -> ABVariantSpec
    variant_map: dict[str, ABVariantSpec] = {v.label: v for v in config.variants}

    # Quota ledger
    ledger_path = ledger_path_for()
    ledger = load_ledger(ledger_path)

    async with JoinQuantBrowser(
        user_data_dir=args.user_data_dir,
        headless=getattr(args, "headless", False),
        slow_mo=getattr(args, "slow_mo", 0),
    ) as browser:
        # Open the strategy editor once for the entire session
        strategy_name = config.base.get("strategy_name") or config.strategy
        edit_url = config.base.get("edit_url")

        for v_entry in pending_variants:
            label = v_entry["label"]
            scenario_id = v_entry["scenario_id"]
            upload_index = v_entry["upload_index"]
            spec = variant_map.get(label)
            if spec is None:
                print(f"Skipping unknown variant '{label}' — not in config.", file=sys.stderr)
                overall_status = 1
                continue

            print(f"\n--- [{upload_index}] {label} ---")

            # Update status to in_progress
            update_ab_experiment(manifest_path, config.experiment_id, label, status="in_progress")
            run_id = ""
            tmp_file = None

            try:
                # -- materialize source (use frozen commit from manifest, not raw config) --
                code_src = v_entry.get("code_source", {})
                frozen_commit = code_src.get("commit") or spec.code_source.commit
                frozen_path = code_src.get("path") or spec.code_source.path
                source_path = materialize_strategy_source(
                    frozen_commit, frozen_path,
                    config.experiment_id, label,
                )

                # -- apply params --
                if spec.params_mode == "params_diff" and spec.params_diff:
                    tmp_file = apply_params_overrides(source_path, spec.params_diff)
                    working_path = tmp_file
                else:
                    working_path = source_path

                # -- local compile --
                compile_strategy(working_path)
                audit_token = _make_audit_token(config.strategy, config.experiment_id, label)
                upload_path = generate_upload_file(working_path, audit_token=audit_token)
                code = upload_path.read_text(encoding="utf-8")

                # -- daily quota check --
                daily_usage = await browser.read_daily_runtime_usage()
                estimated = _parse_minutes(config.base)
                if (daily_usage.get("used_minutes_today") is not None
                        and daily_usage.get("free_limit_minutes") is not None):
                    actual_rem = (daily_usage["free_limit_minutes"]
                                  - daily_usage["used_minutes_today"])
                    if actual_rem <= 0:
                        raise QuotaError("JoinQuant daily free quota exhausted")
                    if estimated and estimated > actual_rem:
                        raise QuotaError(
                            f"Estimated {estimated:g} min exceeds JoinQuant remaining {actual_rem:g} min"
                        )
                else:
                    assert_quota_available(ledger, estimated)

                # -- navigate to editor (first variant opens, subsequent just reuse) --
                await browser.open_strategy_editor(strategy_name, edit_url=edit_url)

                # -- upload & compile (short date range to avoid quota waste) --
                await browser.write_strategy_code(code)
                short_start, short_end = _compile_date_range(end_date_cap=config.base["end_date"])
                await browser.apply_backtest_params(
                    short_start, short_end, config.base["capital"],
                    frequency=str(config.base.get("frequency") or "每天"),
                    py_version=str(config.base.get("py_version") or "Python3"),
                )
                await browser.click_compile()
                await browser.wait_compile_complete()

                # -- set backtest params & start --
                effective = await browser.apply_backtest_params(
                    config.base["start_date"],
                    config.base["end_date"],
                    config.base["capital"],
                    frequency=str(config.base.get("frequency") or "每天"),
                    py_version=str(config.base.get("py_version") or "Python3"),
                )
                print(f"  Backtest params: {json.dumps(effective, ensure_ascii=False)}")

                await browser.start_full_backtest()
                backtest_id = browser.current_backtest_id()
                run_id = make_run_id(backtest_id)

                # -- record quota entry --
                append_quota_entry(
                    ledger,
                    scenario_id=scenario_id,
                    run_id=run_id,
                    estimated_minutes=estimated,
                    status="started",
                )
                save_ledger(ledger, ledger_path)

                # -- wait & fetch --
                timeout_s = getattr(args, "backtest_timeout", 180)
                await browser.wait_backtest_complete(timeout_ms=timeout_s * 1000)

                bundle_opts = {
                    "strategy": config.strategy,
                    "strategyName": strategy_name,
                    "startDate": config.base["start_date"],
                    "endDate": config.base["end_date"],
                    "capital": config.base["capital"],
                    "frequency": str(config.base.get("frequency") or "每天"),
                    "pyVersion": str(config.base.get("py_version") or "Python3"),
                    "resultSource": str(config.base.get("result_source") or "auto"),
                    "auditToken": audit_token,
                    "auditPath": f"jq_auto_audit/{audit_token}.jsonl",
                    "allowPartial": _allow_partial(args, bool(config.base.get("allow_partial", False))),
                }
                fetched = await _fetch_backtest_data(
                    browser,
                    bundle_opts,
                    result_source=_selected_result_source(
                        args,
                        str(config.base.get("result_source") or "auto"),
                    ),
                )

                if fetched.method in {"api", "research"}:
                    run_dir = save_api_bundle(
                        fetched.payload,
                        strategy=config.strategy,
                        run_id=run_id,
                        detail_bundle=fetched.detail_payload,
                        allow_partial=_allow_partial(args, bool(config.base.get("allow_partial", False))),
                    )
                    actual_minutes = extract_actual_minutes_from_bundle(fetched.payload)
                else:
                    run_dir = save_dom_tabs(fetched.payload, strategy=config.strategy, run_id=run_id)
                    actual_seconds = await browser.fetch_runtime_seconds()
                    actual_minutes = (actual_seconds / 60.0) if actual_seconds else None

                register_backtest_run_dataset(
                    run_dir,
                    strategy=config.strategy,
                    run_id=run_id,
                    datasets_root=getattr(args, "datasets_root", "research_datasets"),
                    enabled=not getattr(args, "no_dataset_register", False),
                    allow_partial=_allow_partial(args, bool(config.base.get("allow_partial", False))),
                )

                if actual_minutes is not None:
                    update_actual_minutes(ledger, run_id, actual_minutes)
                    print(f"  Actual compute: {actual_minutes:.2f} min")

                # -- compute uploaded code sha256 --
                uploaded_sha256 = compute_uploaded_code_sha256(upload_path)

                # -- update manifest (success) --
                update_ab_experiment(
                    manifest_path, config.experiment_id, label,
                    run_id=run_id,
                    backtest_id=backtest_id,
                    backtest_url=detail_url_for(backtest_id),
                    uploaded_code_sha256=uploaded_sha256,
                    status="completed",
                )
                cli_set_quota_status(ledger, run_id, "completed")
                save_ledger(ledger, ledger_path)

                print(f"  Done: run_id={run_id} backtest_id={backtest_id}")
                print(f"  Artifacts: {run_dir}")

            except Exception as exc:
                if run_id:
                    cli_set_quota_status(ledger, run_id, "failed")
                    save_ledger(ledger, ledger_path)
                update_ab_experiment(
                    manifest_path, config.experiment_id, label,
                    status="failed",
                )
                print(f"  FAILED: {exc}", file=sys.stderr)
                overall_status = 1
                # Fail-fast: stop the session on any error
                break
            finally:
                if tmp_file and tmp_file.exists():
                    tmp_file.unlink()

    # -- Write session metadata only (variant statuses already written individually) --
    manifest = load_manifest(manifest_path)
    exp_entry = (manifest.get("ab_experiments", {}).get(config.experiment_id)
                 if "ab_experiments" in manifest else None)
    if exp_entry:
        exp_entry["upload_session"] = {
            "session_started_at": session_started_at,
            "session_finished_at": datetime.now().isoformat(timespec="seconds"),
            "strategy_name": strategy_name,
            "edit_url": edit_url,
            "candidate_order": [v["label"] for v in experiment_entry.get("variants", [])],
        }
        _sync_experiment_status(exp_entry)
    manifest["updated"] = datetime.now().isoformat(timespec="seconds")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return overall_status


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def write_ab_report(
    config_or_manifest: Path,
    experiment_id: str,
    *,
    allow_partial: bool = False,
) -> int:
    """Generate AB comparison report (Markdown + JSON) from manifest and run artifacts."""
    # Determine if input is a manifest or an AB config
    path = Path(config_or_manifest)
    if path.name == "manifest.json":
        manifest_path = path
        manifest = load_manifest(manifest_path)
    else:
        # Assume it's an AB config; resolve the manifest
        ab_config = load_ab_config(path)
        manifest_path = resolve_batch_manifest(ab_config.strategy, ab_config.batch_id)
        if not manifest_path.is_file():
            raise ABReportError(f"Manifest not found: {manifest_path}")
        manifest = load_manifest(manifest_path)

    ab_exps = manifest.get("ab_experiments", {})
    experiment = ab_exps.get(experiment_id)
    if not experiment:
        raise ABReportError(
            f"Experiment '{experiment_id}' not found in manifest at {manifest_path}"
        )

    variants_data = experiment.get("variants", [])
    if not variants_data:
        raise ABReportError(f"No variants recorded for experiment '{experiment_id}'")

    # -- collect metrics for each variant --
    from .metrics import VariantMetrics
    metrics_config = DEFAULT_METRICS  # fallback; AB config may have custom
    all_vm: list[VariantMetrics] = []

    for vd in variants_data:
        label = vd["label"]
        run_id = vd.get("run_id")
        status = vd.get("status", "unknown")

        if status != "completed":
            all_vm.append(VariantMetrics(
                label=label,
                role=vd.get("role", "variant"),
                is_baseline=vd.get("is_baseline", False),
                metrics={},
                metadata={"status": status, "error": vd.get("error", "")},
                artifacts_present={"has_backtest_report": False, "has_strategy_analysis": False, "has_performance_analysis": False},
                issues=[f"Status: {status} (not completed)"],
            ))
            continue

        if not run_id:
            all_vm.append(VariantMetrics(
                label=label,
                role=vd.get("role", "variant"),
                is_baseline=vd.get("is_baseline", False),
                metrics={},
                metadata={"status": status},
                artifacts_present={},
                issues=["Missing run_id in manifest"],
            ))
            continue

        # resolve_run_dir needs strategy and run_id; we have strategy from manifest
        strategy = manifest.get("strategy", "")
        if not strategy:
            # Try to infer from batch path
            import re as _re
            m = _re.search(r'strategies[\\/]([^\\/]+)', str(manifest_path))
            strategy = m.group(1) if m else ""

        try:
            run_dir = resolve_run_dir(strategy, run_id)
        except Exception:
            all_vm.append(VariantMetrics(
                label=label,
                role=vd.get("role", "variant"),
                is_baseline=vd.get("is_baseline", False),
                metrics={},
                metadata={"status": status, "run_id": run_id},
                artifacts_present={},
                issues=[f"Cannot resolve run dir for run_id={run_id}"],
            ))
            continue

        vm = collect_all_metrics(run_dir, run_id, metrics_config)
        vm.label = label
        vm.role = vd.get("role", "variant")
        vm.is_baseline = vd.get("is_baseline", False)
        all_vm.append(vm)

    # -- validate completeness --
    baseline_vm = next((vm for vm in all_vm if vm.is_baseline), None)
    if baseline_vm is None and not allow_partial:
        return 1  # no baseline, can't proceed
    if baseline_vm and baseline_vm.issues and not allow_partial:
        return 1  # baseline not complete

    # -- generate reports --
    report_dir = resolve_path(
        "test_batch_report_dir",
        strategy=manifest.get("strategy", ""),
        batch_id=manifest.get("batch_id", ""),
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    # JSON summary
    json_path = report_dir / f"ab-{_sanitize(experiment_id)}-summary.json"
    summary = _build_summary(experiment, all_vm)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown report
    md_path = report_dir / f"ab-{_sanitize(experiment_id)}-comparison.md"
    md_content = _build_markdown_report(experiment, all_vm, manifest)
    md_path.write_text(md_content, encoding="utf-8")

    print(f"AB report written:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON:     {json_path}")

    return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_code_source(raw: dict[str, Any]) -> dict[str, str]:
    ref = str(raw.get("ref") or raw.get("commit") or "")
    if not ref:
        raise ABConfigError("code_source.ref is required")
    path = str(raw.get("path") or "")
    if not path:
        raise ABConfigError("code_source.path is required")
    return {"type": "git", "ref": ref, "path": path}


def _load_registered_variant(*, strategy: str, base_code_path: str, variant_id: str) -> dict[str, Any]:
    """Load one strategy variant from the central variant registry."""
    try:
        from scripts.research.platform.strategy_variants import VariantRegistry, VariantError

        strategy_root = _strategy_root_for_variant_registry(strategy, base_code_path)
        return VariantRegistry(strategy_root).get(variant_id)
    except VariantError as exc:
        raise ABConfigError(f"variant_id '{variant_id}' cannot be loaded from registry: {exc}") from exc


def _strategy_root_for_variant_registry(strategy: str, base_code_path: str) -> Path:
    root = repo_root()
    code_path = Path(base_code_path)
    if code_path.is_absolute():
        return code_path.parent
    from_code_source = (root / code_path).resolve().parent
    if from_code_source.exists():
        return from_code_source
    return (root / "strategies" / strategy).resolve()


def _registered_params_diff(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    params = (
        record.get("params_diff")
        or payload.get("params_diff")
        or payload.get("param_overrides")
        or {}
    )
    return _dictify(params)


def _registered_code_source(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    code_source = record.get("code_source") or payload.get("code_source")
    return code_source if isinstance(code_source, dict) else None


def _dictify(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _parse_minutes(base: dict[str, Any]) -> float:
    val = base.get("estimated_minutes", 0)
    if val in (None, ""):
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _sanitize(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", str(label)).strip("-") or "unnamed"


def _find_variant_entry(experiment: dict[str, Any] | None, label: str) -> dict[str, Any] | None:
    if not experiment:
        return None
    for v in experiment.get("variants", []):
        if v.get("label") == label:
            return v
    return None


def _reset_pending_variants(experiment: dict[str, Any]) -> None:
    for v in experiment.get("variants", []):
        if v.get("status") in ("pending", "failed"):
            v["status"] = "pending"
            v.pop("run_id", None)
            v.pop("backtest_id", None)
            v.pop("backtest_url", None)
            v.pop("uploaded_code_sha256", None)
            v.pop("error", None)


def _sync_experiment_status(experiment_entry: dict[str, Any]) -> dict[str, Any]:
    """Aggregate variant statuses into experiment-level status (mutates and returns)."""
    statuses = {v.get("status") for v in experiment_entry.get("variants", [])}
    if "failed" in statuses:
        experiment_entry["status"] = "failed"
    elif "in_progress" in statuses or "started" in statuses:
        experiment_entry["status"] = "in_progress"
    elif all(s == "completed" for s in statuses) and statuses:
        experiment_entry["status"] = "completed"
    else:
        experiment_entry["status"] = "pending"
    return experiment_entry


def _build_summary(
    experiment: dict[str, Any],
    all_vm: list[Any],
) -> dict[str, Any]:
    """Build a JSON-serialisable summary dict."""
    variants_summary = []
    for vm in all_vm:
        entry = _find_variant_entry(experiment, vm.label) or {}
        variants_summary.append({
            "label": vm.label,
            "role": vm.role,
            "variant_id": entry.get("variant_id"),
            "is_baseline": vm.is_baseline,
            "metrics": vm.metrics,
            "metadata": vm.metadata,
            "artifacts_present": vm.artifacts_present,
            "issues": vm.issues,
        })

    return {
        "status": experiment.get("status"),
        "baseline": experiment.get("baseline"),
        "controls": experiment.get("controls", []),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "variants": variants_summary,
    }


def _build_markdown_report(
    experiment: dict[str, Any],
    all_vm: list[Any],
    manifest: dict[str, Any],
) -> str:
    """Build the full Markdown comparison report."""
    experiment_id = experiment.get("baseline", "")
    # Find actual experiment_id from the ab_experiments key
    for eid, exp in manifest.get("ab_experiments", {}).items():
        if exp is experiment:
            experiment_id = eid
            break

    baseline = experiment.get("baseline", "")
    controls = experiment.get("controls", [])
    lines: list[str] = []

    lines.append(f"# AB 对比报告: {experiment_id}")
    lines.append("")
    lines.append(f"**状态:** {experiment.get('status', 'unknown')}")
    lines.append(f"**Baseline:** `{baseline}`")
    if controls:
        lines.append(f"**额外对照:** {', '.join(f'`{c}`' for c in controls)}")
    lines.append(f"**生成时间:** {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    # --- Core metrics table ---
    completed = [vm for vm in all_vm if not vm.issues]
    if completed:
        metric_keys = list(completed[0].metrics.keys())
        metric_keys = [k for k in metric_keys if completed[0].metrics.get(k) is not None]

        lines.append("## 核心指标对比")
        lines.append("")
        header = "| Variant | Role | " + " | ".join(METRIC_LABEL_CN.get(k, k) for k in metric_keys) + " |"
        lines.append(header)
        sep = "| --- | --- | " + " | ".join(" --- " for _ in metric_keys) + " |"
        lines.append(sep)
        for vm in all_vm:
            role_tag = vm.role
            if vm.is_baseline:
                role_tag += " ★"
            cells = [vm.label, role_tag]
            for k in metric_keys:
                v = vm.metrics.get(k)
                if v is not None:
                    # Format percentages nicely
                    if k in ("total_return", "annual_return", "benchmark_return", "excess_return",
                             "max_drawdown", "alpha", "volatility", "benchmark_volatility",
                             "win_ratio", "profit_loss_ratio", "day_win_ratio",
                             "excess_max_drawdown", "excess_sharpe", "daily_excess_return"):
                        cells.append(f"{v * 100:.2f}%")
                    elif k in ("actual_minutes",):
                        cells.append(f"{v:.1f}")
                    else:
                        cells.append(f"{v:.3f}")
                else:
                    cells.append("-")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        lines.append("★ = baseline")

        # --- Delta vs baseline ---
        baseline_vm = next((vm for vm in all_vm if vm.is_baseline), None)
        if baseline_vm:
            lines.append("")
            lines.append("## 相对 Baseline 的变化")
            lines.append("")
            lines.append(f"Baseline: **{baseline_vm.label}**")
            lines.append("")
            header2 = "| Variant | " + " | ".join(METRIC_LABEL_CN.get(k, k) for k in metric_keys) + " |"
            lines.append(header2)
            sep2 = "| --- | " + " | ".join(" --- " for _ in metric_keys) + " |"
            lines.append(sep2)
            for vm in all_vm:
                if vm.is_baseline:
                    continue
                cells = [vm.label]
                for k in metric_keys:
                    bv = baseline_vm.metrics.get(k)
                    vv = vm.metrics.get(k)
                    if bv is not None and vv is not None and bv != 0:
                        if k in ("total_return", "annual_return", "benchmark_return", "excess_return",
                                 "max_drawdown", "alpha", "volatility", "benchmark_volatility"):
                            delta = (vv - bv) * 100  # percentage points
                            sign = "+" if delta >= 0 else ""
                            cells.append(f"{sign}{delta:.2f} pp")
                        else:
                            delta_pct = (vv - bv) / abs(bv) * 100
                            sign = "+" if delta_pct >= 0 else ""
                            cells.append(f"{sign}{delta_pct:.1f}%")
                    else:
                        cells.append("-")
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")

    # --- Variants detail ---
    lines.append("## 变体详情")
    lines.append("")
    for vm in all_vm:
        entry = _find_variant_entry(experiment, vm.label) or {}
        lines.append(f"### {vm.label}")
        lines.append(f"- **Role:** {vm.role}" + (" (baseline)" if vm.is_baseline else ""))
        if entry.get("variant_id"):
            lines.append(f"- **Variant ID:** {entry['variant_id']}")
        lines.append(f"- **Issues:** {', '.join(vm.issues) if vm.issues else 'none'}")
        if vm.metadata.get("run_id"):
            lines.append(f"- **Run ID:** {vm.metadata['run_id']}")
        if vm.metadata.get("backtest_id"):
            lines.append(f"- **Backtest ID:** {vm.metadata['backtest_id']}")
        if vm.metadata.get("backtest_url"):
            lines.append(f"- **Backtest URL:** {vm.metadata['backtest_url']}")
        artifacts = vm.artifacts_present
        if artifacts:
            present = [k for k, v in artifacts.items() if v]
            missing = [k for k, v in artifacts.items() if not v]
            if present:
                lines.append(f"- **Artifacts present:** {', '.join(present)}")
            if missing:
                lines.append(f"- **Artifacts missing:** {', '.join(missing)} (建议运行分析流程补充)")
        lines.append("")

    # --- Missing items ---
    broken = [vm for vm in all_vm if vm.issues]
    if broken:
        lines.append("## 异常与缺失项")
        lines.append("")
        for vm in broken:
            lines.append(f"- **{vm.label}**: {'; '.join(vm.issues)}")
        lines.append("")

    return "\n".join(lines)
