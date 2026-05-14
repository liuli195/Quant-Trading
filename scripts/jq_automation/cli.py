from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .artifacts import save_api_bundle, save_dom_tabs
from .browser import AutomationError, CompileFailed, JoinQuantBrowser
from .config import ConfigError, ScenarioConfig, load_config_mapping, load_scenario_config
from .local import LocalCheckError, apply_params_overrides, compile_strategy, generate_upload_file
from .manifest import ManifestError, list_pending_runs, load_manifest, update_manifest
from .paths import (
    default_chrome_user_data_dir,
    extract_backtest_id,
    make_run_id,
    resolve_batch_manifest,
    repo_root,
)
from .quota import (
    QuotaError,
    append_quota_entry,
    assert_quota_available,
    extract_actual_minutes_from_bundle,
    ledger_path_for,
    load_ledger,
    remaining_minutes,
    save_ledger,
    update_actual_minutes,
)
from .research import EXTRACTION_METHOD as RESEARCH_EXTRACTION_METHOD
from .research import ResearchBacktestFetcher, ResearchFetchError


def _compile_date_range(end_date_cap: str | None = None) -> tuple[str, str]:
    """Return a short (start_date, end_date) pair for compile-safe backtest params.

    Uses the last 30 days capped at *end_date_cap* (when the configured backtest
    end date is in the past).  Extracted so the date arithmetc is testable.
    """
    today = datetime.now()
    end = today
    if end_date_cap:
        cap = datetime.strptime(end_date_cap, "%Y-%m-%d")
        end = min(today, cap)
    start = end - timedelta(days=30)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class FetchedBacktestData:
    method: str
    payload: dict[str, Any]
    detail_payload: dict[str, Any] | None = None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (AutomationError, CompileFailed, ConfigError, LocalCheckError, ManifestError, QuotaError, ResearchFetchError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Catch AB test errors and GitVersionError even if abtest module cannot
        # be imported (the ab subcommand handler will have already imported them).
        name = type(exc).__name__
        if name in ("ABConfigError", "ABExpandError", "ABReportError", "GitVersionError", "IntegrityError"):
            print(f"error: {exc}", file=sys.stderr)
            return 2
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jq-auto", description="Automate JoinQuant cloud backtests with Playwright + Chrome.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile-check", help="Run local py_compile for a strategy file.")
    compile_parser.add_argument("strategy_file")
    compile_parser.add_argument("--write-upload", action="store_true", help="Also generate <strategy>__upload.py.")
    compile_parser.set_defaults(func=cmd_compile_check)

    upload_parser = subparsers.add_parser("upload", help="Upload strategy code to an existing JoinQuant editor page.")
    upload_parser.add_argument("strategy_file")
    upload_parser.add_argument("--strategy-name")
    upload_parser.add_argument("--edit-url")
    upload_parser.add_argument("--no-compile", action="store_true", help="Skip browser-side compile after upload.")
    add_browser_args(upload_parser)
    upload_parser.set_defaults(func=cmd_upload)

    run_parser = subparsers.add_parser("run", help="Upload, compile, start, wait, fetch, and persist one scenario config.")
    run_parser.add_argument("scenario_config")
    run_parser.add_argument("--yes", action="store_true", help="Confirm this run was manually approved.")
    run_parser.add_argument("--backtest-timeout", type=int, default=180, help="Formal backtest wait timeout in seconds.")
    add_allow_partial_arg(run_parser)
    add_result_source_arg(run_parser)
    add_browser_args(run_parser)
    run_parser.set_defaults(func=cmd_run)

    fetch_parser = subparsers.add_parser("fetch", help="Read-only fetch of an existing JoinQuant backtest detail page.")
    fetch_parser.add_argument("target", help="Backtest detail URL or backtestId.")
    fetch_parser.add_argument("--strategy", required=True)
    fetch_parser.add_argument("--run-id")
    fetch_parser.add_argument("--strategy-name")
    fetch_parser.add_argument("--start-date", default="")
    fetch_parser.add_argument("--end-date", default="")
    fetch_parser.add_argument("--capital", type=float)
    fetch_parser.add_argument("--frequency", default="每天")
    fetch_parser.add_argument("--py-version", default="Python3")
    fetch_parser.add_argument("--backtest-timeout", type=int, default=180)
    fetch_parser.add_argument("--audit-token")
    fetch_parser.add_argument("--audit-path")
    add_allow_partial_arg(fetch_parser)
    add_result_source_arg(fetch_parser)
    add_browser_args(fetch_parser)
    fetch_parser.set_defaults(func=cmd_fetch)

    batch_parser = subparsers.add_parser("batch", help="Run pending scenarios whose scenario.json files sit beside a manifest.")
    batch_parser.add_argument("manifest_json")
    batch_parser.add_argument("--scenario", action="append", help="Limit to one scenario id; can be repeated.")
    batch_parser.add_argument("--yes", action="store_true", help="Confirm this batch was manually approved.")
    batch_parser.add_argument("--backtest-timeout", type=int, default=180)
    add_allow_partial_arg(batch_parser)
    add_result_source_arg(batch_parser)
    add_browser_args(batch_parser)
    batch_parser.set_defaults(func=cmd_batch)

    # -- ab subcommands --
    ab_parser = subparsers.add_parser("ab", help="AB test experiment management.")
    ab_sub = ab_parser.add_subparsers(dest="ab_command", required=True)

    expand_parser = ab_sub.add_parser("expand", help="Expand AB config into scenarios and manifest entry.")
    expand_parser.add_argument("ab_config", help="Path to AB experiment JSON config.")
    expand_parser.add_argument("--force-reset-pending", action="store_true")
    expand_parser.set_defaults(func=cmd_ab_expand)

    run_parser = ab_sub.add_parser("run", help="Run all pending AB variants in one upload session.")
    run_parser.add_argument("ab_config")
    run_parser.add_argument("--yes", action="store_true")
    run_parser.add_argument("--backtest-timeout", type=int, default=180)
    add_allow_partial_arg(run_parser)
    add_result_source_arg(run_parser)
    add_browser_args(run_parser)
    run_parser.set_defaults(func=cmd_ab_run)

    report_parser = ab_sub.add_parser("report", help="Generate AB comparison report.")
    report_parser.add_argument("ab_config_or_manifest", help="AB config or manifest JSON path.")
    report_parser.add_argument("--experiment", required=True)
    report_parser.add_argument("--allow-partial", action="store_true")
    report_parser.set_defaults(func=cmd_ab_report)

    return parser


def add_browser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--user-data-dir", default=str(default_chrome_user_data_dir()), help="Dedicated Chrome profile directory.")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo", type=int, default=0)


def add_result_source_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--result-source",
        choices=("auto", "research", "detail"),
        default=None,
        help="Backtest result source: auto (research then detail fallback), research, or detail.",
    )


def add_allow_partial_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Persist incomplete artifacts instead of failing the run integrity gate.",
    )


def cmd_compile_check(args: argparse.Namespace) -> int:
    result = compile_strategy(args.strategy_file)
    print(f"OK: {result.message}: {result.strategy_file}")
    if args.write_upload:
        upload_path = generate_upload_file(result.strategy_file)
        print(f"Generated upload file: {upload_path}")
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    compile_strategy(args.strategy_file)
    upload_path = generate_upload_file(args.strategy_file)
    code = upload_path.read_text(encoding="utf-8")
    strategy_name = args.strategy_name or Path(args.strategy_file).stem
    return asyncio.run(_upload_code(args, strategy_name, code, compile_after=not args.no_compile))


def cmd_run(args: argparse.Namespace) -> int:
    config = load_scenario_config(args.scenario_config)
    runs = config.expand_runs()
    if len(runs) != 1:
        raise ConfigError(f"Scenario config must expand to exactly 1 run, got {len(runs)}")
    config = config.for_run(runs[0])
    return asyncio.run(_run_scenario(args, config, already_confirmed=args.yes))


def cmd_fetch(args: argparse.Namespace) -> int:
    return asyncio.run(_fetch_existing(args))


def cmd_batch(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest_json).resolve()
    manifest = load_manifest(manifest_path)
    scenario_filter = set(args.scenario) if args.scenario else None

    # Resolve pending runs — supports both old (primary_run_id) and new (runs[])
    pending = list_pending_runs(manifest, scenario_filter)
    if not pending:
        print("No pending runs selected.")
        return 0

    print("Selected runs:")
    for sid, run_entry in pending:
        label = run_entry.get("label") if run_entry else "(unexpanded)"
        print(f"  {sid}/{label}")
    if not args.yes and not _confirm("Type RUN to start the selected JoinQuant cloud runs: "):
        print("Cancelled.")
        return 1

    for sid, run_entry in pending:
        scenario_path = manifest_path.parent / "scenarios" / sid / "scenario.json"
        if not scenario_path.is_file():
            label = run_entry.get("label", "default") if run_entry else "default"
            update_manifest(manifest_path, scenario_id=sid,
                            label=label, status="failed",
                            error=f"Missing {scenario_path}")
            print(f"Missing scenario config: {scenario_path}", file=sys.stderr)
            continue

        data = load_config_mapping(scenario_path)
        data.setdefault("batch_id", manifest.get("batch_id"))
        data.setdefault("strategy", manifest.get("strategy"))
        data.setdefault("scenario_id", sid)
        config = ScenarioConfig.from_mapping(data, base_dir=scenario_path.parent)

        # If the scenario isn't expanded yet, expand from config now
        if run_entry is None:
            for run_spec in config.expand_runs():
                update_manifest(manifest_path, scenario_id=sid,
                                label=run_spec.label,
                                params_diff=run_spec.params_diff,
                                status="pending")
            # Reload manifest each iteration to avoid stale run status
            manifest = load_manifest(manifest_path)
            for _sid, _entry in list_pending_runs(manifest, {sid}):
                if _entry is None:
                    continue
                if _run_one(args, manifest_path, _sid, _entry, config):
                    return 1
                manifest = load_manifest(manifest_path)  # refresh after each run
            continue

        if _run_one(args, manifest_path, sid, run_entry, config):
            return 1
    return 0


def _run_one(args: argparse.Namespace, manifest_path: Path, sid: str,
             run_entry: dict[str, Any], config: ScenarioConfig) -> int:
    """Execute a single run within a batch scenario."""
    merged_params = {**config.params_base, **run_entry.get("params_diff", {})}

    tmp_file = None
    try:
        if merged_params:
            tmp_file = apply_params_overrides(config.strategy_file, merged_params)
            run_config = ScenarioConfig(
                strategy_file=tmp_file,
                strategy=config.strategy,
                scenario_id=config.scenario_id,
                start_date=config.start_date,
                end_date=config.end_date,
                capital=config.capital,
                frequency=config.frequency,
                py_version=config.py_version,
                batch_id=config.batch_id,
                strategy_name=config.strategy_name,
                edit_url=config.edit_url,
                estimated_minutes=config.estimated_minutes,
                raw={**config.raw, "_run_label": run_entry.get("label"),
                     "_run_params_diff": run_entry.get("params_diff", {})},
                result_source=config.result_source,
            )
        else:
            run_config = config

        label = run_entry.get("label", "default")
        update_manifest(manifest_path, scenario_id=sid, label=label,
                        params_diff=run_entry.get("params_diff"),
                        status="in_progress")

        result = asyncio.run(_run_scenario(args, run_config, already_confirmed=True,
                                           manifest_path=manifest_path,
                                           manifest_label=label))
        return result or 0
    except Exception as exc:
        label = run_entry.get("label", "default")
        update_manifest(manifest_path, scenario_id=sid, label=label,
                        status="failed", error=str(exc))
        print(f"Run failed: {sid}/{label}: {exc}", file=sys.stderr)
        return 1
    finally:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()


async def _upload_code(args: argparse.Namespace, strategy_name: str, code: str, *, compile_after: bool) -> int:
    async with JoinQuantBrowser(
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        slow_mo=args.slow_mo,
    ) as browser:
        await browser.open_strategy_editor(strategy_name, edit_url=args.edit_url)
        result = await browser.write_strategy_code(code)
        print(f"Uploaded {result['length']} chars to Ace editor.")
        if compile_after:
            short_start, short_end = _compile_date_range()
            await browser.apply_backtest_params(
                short_start, short_end, 100000,
                frequency="day", py_version="Python3",
            )
            await browser.click_compile()
            await browser.wait_compile_complete()
            print("JoinQuant compile finished without ERROR/Traceback.")
    return 0


async def _run_scenario(
    args: argparse.Namespace,
    config: ScenarioConfig,
    *,
    already_confirmed: bool,
    manifest_path: Path | None = None,
    manifest_label: str | None = None,
) -> int:
    compile_strategy(config.strategy_file)
    audit_token = _make_audit_token(config.strategy, config.scenario_id)
    upload_path = generate_upload_file(config.strategy_file, audit_token=audit_token)
    code = upload_path.read_text(encoding="utf-8")

    ledger_path = ledger_path_for()
    ledger = load_ledger(ledger_path)
    _print_run_plan(config, ledger_path, remaining_minutes(ledger), upload_path)
    if not already_confirmed and not _confirm("Type RUN to start this formal JoinQuant cloud backtest: "):
        print("Cancelled.")
        return 1

    run_id = ""
    try:
        async with JoinQuantBrowser(
            user_data_dir=args.user_data_dir,
            headless=args.headless,
            slow_mo=args.slow_mo,
        ) as browser:
            await browser.open_strategy_editor(config.strategy_name or config.strategy_file.stem, edit_url=config.edit_url)

            # --- read actual daily quota from JoinQuant's editor page ---
            daily_usage = await browser.read_daily_runtime_usage()
            if daily_usage["used_minutes_today"] is not None and daily_usage["free_limit_minutes"] is not None:
                actual_remaining = daily_usage["free_limit_minutes"] - daily_usage["used_minutes_today"]
                print(f"JoinQuant daily usage: {daily_usage['used_minutes_today']:g} / {daily_usage['free_limit_minutes']:g} min (remaining {actual_remaining:g} min)")
                if actual_remaining <= 0:
                    raise QuotaError(
                        f"JoinQuant daily free quota exhausted "
                        f"({daily_usage['used_minutes_today']:g} / {daily_usage['free_limit_minutes']:g} min)"
                    )
                if config.estimated_minutes and config.estimated_minutes > actual_remaining:
                    raise QuotaError(
                        f"Estimated {config.estimated_minutes:g} min exceeds "
                        f"JoinQuant remaining {actual_remaining:g} min"
                    )
            else:
                # Fall back to local ledger when page parsing fails
                assert_quota_available(ledger, config.estimated_minutes)
            await browser.write_strategy_code(code)
            short_start, short_end = _compile_date_range(end_date_cap=config.end_date)
            await browser.apply_backtest_params(
                short_start, short_end, config.capital,
                frequency=config.frequency, py_version=config.py_version,
            )
            await browser.click_compile()
            await browser.wait_compile_complete()
            effective = await browser.apply_backtest_params(
                config.start_date, config.end_date, config.capital,
                frequency=config.frequency, py_version=config.py_version,
            )
            print(f"Effective backtest params: {json.dumps(effective, ensure_ascii=False)}")
            await browser.start_full_backtest()
            backtest_id = browser.current_backtest_id()
            run_id = config.run_id or make_run_id(backtest_id)
            append_quota_entry(
                ledger,
                scenario_id=config.scenario_id,
                run_id=run_id,
                estimated_minutes=config.estimated_minutes,
                status="started",
            )
            save_ledger(ledger, ledger_path)
            await browser.wait_backtest_complete(timeout_ms=args.backtest_timeout * 1000)
            fetch_options = _bundle_options(config, audit_token=audit_token)
            fetch_options["allowPartial"] = _allow_partial(args, config.allow_partial)
            fetched = await _fetch_backtest_data(
                browser,
                fetch_options,
                result_source=_selected_result_source(args, config.result_source),
            )
            if not run_id:
                backtest_id = browser.current_backtest_id() or fetched.payload.get("metadata", {}).get("backtest_id", "")
                run_id = config.run_id or make_run_id(backtest_id)
            if fetched.method in {"api", "research"}:
                run_dir = save_api_bundle(
                    fetched.payload,
                    strategy=config.strategy,
                    run_id=run_id,
                    detail_bundle=fetched.detail_payload,
                    allow_partial=_allow_partial(args, config.allow_partial),
                )
                actual_minutes = extract_actual_minutes_from_bundle(fetched.payload)
            else:
                run_dir = save_dom_tabs(fetched.payload, strategy=config.strategy, run_id=run_id)
                actual_seconds = await browser.fetch_runtime_seconds()
                actual_minutes = (actual_seconds / 60.0) if actual_seconds else None

            if actual_minutes is not None:
                update_actual_minutes(ledger, run_id, actual_minutes)
                print(f"JoinQuant actual compute time: {actual_minutes:.2f} min")
    except Exception as exc:
        if run_id and _set_quota_status(ledger, run_id, "failed"):
            save_ledger(ledger, ledger_path)
        manifest_file = manifest_path or _config_manifest_path(config)
        if manifest_file and manifest_file.is_file():
            update_manifest(manifest_file, scenario_id=config.scenario_id,
                            label=manifest_label, status="failed", error=str(exc))
        raise

    manifest_file = manifest_path or _config_manifest_path(config)
    if manifest_file and manifest_file.is_file():
        params_diff = config.raw.get("_run_params_diff")
        update_manifest(manifest_file, scenario_id=config.scenario_id,
                        run_id=run_id, label=manifest_label,
                        params_diff=params_diff, status="completed")

    _set_quota_status(ledger, run_id, "completed")
    save_ledger(ledger, ledger_path)
    print(f"Saved run artifacts: {run_dir}")
    print(f"Recorded quota ledger: {ledger_path}")
    return 0


async def _fetch_existing(args: argparse.Namespace) -> int:
    backtest_id = extract_backtest_id(args.target)
    run_id = args.run_id or make_run_id(backtest_id)
    async with JoinQuantBrowser(
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        slow_mo=args.slow_mo,
    ) as browser:
        await browser.open_backtest_detail(args.target)
        await browser.wait_backtest_complete(timeout_ms=args.backtest_timeout * 1000)
        options = {
            "strategy": args.strategy,
            "strategyName": args.strategy_name or args.strategy,
            "startDate": args.start_date,
            "endDate": args.end_date,
            "capital": args.capital,
            "frequency": args.frequency,
            "pyVersion": args.py_version,
            "allowPartial": bool(args.allow_partial),
        }
        audit_token = args.audit_token or ""
        if audit_token:
            options["auditToken"] = audit_token
            options["auditPath"] = f"jq_auto_audit/{audit_token}.jsonl"
        if args.audit_path:
            options["auditPath"] = args.audit_path
        fetched = await _fetch_backtest_data(
            browser,
            options,
            result_source=_selected_result_source(args, "auto"),
        )
        if not args.run_id:
            run_id = make_run_id(browser.current_backtest_id() or fetched.payload.get("metadata", {}).get("backtest_id", backtest_id))
        if fetched.method in {"api", "research"}:
            run_dir = save_api_bundle(
                fetched.payload,
                strategy=args.strategy,
                run_id=run_id,
                detail_bundle=fetched.detail_payload,
                allow_partial=bool(args.allow_partial),
            )
        else:
            run_dir = save_dom_tabs(fetched.payload, strategy=args.strategy, run_id=run_id)
    print(f"Saved existing backtest artifacts: {run_dir}")
    return 0


async def _fetch_with_dom_fallback(browser: JoinQuantBrowser, options: dict[str, Any]) -> FetchedBacktestData:
    try:
        return FetchedBacktestData(method="api", payload=await browser.fetch_api_bundle(options))
    except Exception as exc:
        if not options.get("allowPartial"):
            raise
        print(f"API bundle failed, falling back to DOM tabs: {exc}", file=sys.stderr)
        return FetchedBacktestData(method="dom", payload=await browser.collect_dom_tabs())


def _supplemental_from_detail_bundle(detail_payload: dict[str, Any]) -> dict[str, Any]:
    metadata = detail_payload.get("metadata", {}) if isinstance(detail_payload, dict) else {}
    counts = detail_payload.get("counts", {}) if isinstance(detail_payload, dict) else {}
    partial = detail_payload.get("partial", {}) if isinstance(detail_payload, dict) else {}
    error_logs = detail_payload.get("error_logs", {}) if isinstance(detail_payload, dict) else {}
    return {
        "detail_api_used": True,
        "detail_backtest_id": metadata.get("backtest_id", ""),
        "internal_backtest_id": metadata.get("internal_backtest_id", ""),
        "runtime": detail_payload.get("runtime"),
        "source": detail_payload.get("source"),
        "profile_text": detail_payload.get("profile_text", ""),
        "logs_partial": bool(partial.get("logs")),
        "logs_count": counts.get("logs"),
        "error_logs_partial": bool(error_logs.get("partial", False)),
        "error_logs_count": counts.get("error_logs"),
    }


async def _fetch_backtest_data(
    browser: JoinQuantBrowser,
    options: dict[str, Any],
    *,
    result_source: str = "auto",
) -> FetchedBacktestData:
    if result_source == "detail":
        return await _fetch_with_dom_fallback(browser, options)

    backtest_id = browser.current_backtest_id() or str(options.get("backtestId") or options.get("backtest_id") or "")
    supplemental_detail: dict[str, Any] = {}
    detail_payload: dict[str, Any] | None = None
    try:
        detail_payload = await browser.fetch_api_bundle({**options, "backtestId": backtest_id})
        supplemental_detail = _supplemental_from_detail_bundle(detail_payload)
    except Exception as exc:
        supplemental_detail = {"detail_api_used": False, "detail_supplemental_error": str(exc)}

    try:
        if os.environ.get("JQ_AUTO_FORCE_RESEARCH_FAILURE"):
            raise ResearchFetchError("forced research failure via JQ_AUTO_FORCE_RESEARCH_FAILURE")
        payload = await ResearchBacktestFetcher(browser).fetch(
            backtest_id,
            {**options, "backtestId": backtest_id},
            supplemental_detail=supplemental_detail,
        )
        return FetchedBacktestData(method="research", payload=payload, detail_payload=detail_payload)
    except Exception as exc:
        if result_source == "research":
            raise ResearchFetchError(str(exc)) from exc
        print(f"Research bundle failed, falling back to detail API/DOM: {exc}", file=sys.stderr)
        if detail_payload is not None:
            fallback = FetchedBacktestData(method="api", payload=detail_payload)
        else:
            await browser.open_backtest_detail(backtest_id)
            fallback = await _fetch_with_dom_fallback(browser, options)
        _annotate_research_fallback(fallback.payload, fallback.method, exc)
        return fallback


def _annotate_research_fallback(payload: dict[str, Any], method: str, exc: Exception) -> None:
    if not isinstance(payload, dict):
        return
    metadata = payload.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata
    actual_method = str(metadata.get("extraction_method") or method)
    metadata.setdefault("attempted_primary_extraction_method", RESEARCH_EXTRACTION_METHOD)
    metadata["primary_extraction_method"] = actual_method
    metadata["fallback_extraction_method"] = actual_method
    metadata["research_downloaded"] = False
    metadata["research_fetch_failed"] = True
    metadata["research_fetch_error"] = str(exc)
    metadata["detail_api_used"] = method == "api"


def _bundle_options(config: ScenarioConfig, *, audit_token: str | None = None) -> dict[str, Any]:
    options = {
        "strategy": config.strategy,
        "strategyName": config.strategy_name or config.strategy,
        "startDate": config.start_date,
        "endDate": config.end_date,
        "capital": config.capital,
        "frequency": config.frequency,
        "pyVersion": config.py_version,
        "resultSource": config.result_source,
        "allowPartial": config.allow_partial,
    }
    if audit_token:
        options["auditToken"] = audit_token
        options["auditPath"] = f"jq_auto_audit/{audit_token}.jsonl"
    return options


def _selected_result_source(args: argparse.Namespace, config_value: str | None = None) -> str:
    value = getattr(args, "result_source", None) or config_value or "auto"
    return str(value).lower()


def _allow_partial(args: argparse.Namespace, config_value: bool | None = None) -> bool:
    return bool(getattr(args, "allow_partial", False) or config_value)


def _make_audit_token(*parts: str) -> str:
    raw = "-".join(part for part in parts if part)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-") or "run"
    return f"{safe}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _config_manifest_path(config: ScenarioConfig) -> Path | None:
    if not config.batch_id:
        return None
    return resolve_batch_manifest(config.strategy, config.batch_id)


def _print_run_plan(config: ScenarioConfig, ledger_path: Path, remaining: float, upload_path: Path) -> None:
    print("JoinQuant formal backtest plan")
    print(f"  strategy: {config.strategy}")
    print(f"  scenario: {config.scenario_id}")
    print(f"  range: {config.start_date} -> {config.end_date}")
    print(f"  capital: {config.capital}")
    print(f"  estimated minutes: {config.estimated_minutes:g}")
    print(f"  remaining ledger minutes: {remaining:g}")
    print(f"  ledger: {ledger_path}")
    print(f"  upload file: {upload_path}")


def _set_quota_status(ledger: dict[str, Any], run_id: str, status: str) -> bool:
    for item in reversed(ledger.get("runs", [])):
        if item.get("run_id") == run_id:
            item["status"] = status
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            return True
    return False


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    return input(prompt).strip() == "RUN"


# ---------------------------------------------------------------------------
# AB test command handlers
# ---------------------------------------------------------------------------


def cmd_ab_expand(args: argparse.Namespace) -> int:
    from .abtest import ABConfigError, ABExpandError, load_ab_config, expand_ab_experiment

    config = load_ab_config(args.ab_config)
    manifest_path = resolve_batch_manifest(config.strategy, config.batch_id)
    expand_ab_experiment(config, manifest_path, force_reset_pending=args.force_reset_pending)
    print(f"AB experiment '{config.experiment_id}' expanded successfully.")
    return 0


def cmd_ab_run(args: argparse.Namespace) -> int:
    from .abtest import ABConfigError, ABExpandError, load_ab_config, run_ab_experiment

    config = load_ab_config(args.ab_config)
    manifest_path = resolve_batch_manifest(config.strategy, config.batch_id)
    return run_ab_experiment(args, config, manifest_path)


def cmd_ab_report(args: argparse.Namespace) -> int:
    from .abtest import ABConfigError, ABReportError, write_ab_report

    return write_ab_report(
        Path(args.ab_config_or_manifest),
        args.experiment,
        allow_partial=args.allow_partial,
    )


if __name__ == "__main__":
    raise SystemExit(main())
