from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from .artifacts import save_api_bundle, save_dom_tabs
from .browser import AutomationError, CompileFailed, JoinQuantBrowser
from .config import ConfigError, ScenarioConfig, load_config_mapping, load_scenario_config
from .local import LocalCheckError, compile_strategy, generate_upload_file
from .manifest import ManifestError, load_manifest, update_manifest
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
    ledger_path_for,
    load_ledger,
    remaining_minutes,
    save_ledger,
)


@dataclass(frozen=True)
class FetchedBacktestData:
    method: str
    payload: dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (AutomationError, CompileFailed, ConfigError, LocalCheckError, ManifestError, QuotaError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


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
    add_browser_args(fetch_parser)
    fetch_parser.set_defaults(func=cmd_fetch)

    batch_parser = subparsers.add_parser("batch", help="Run pending scenarios whose scenario.json files sit beside a manifest.")
    batch_parser.add_argument("manifest_json")
    batch_parser.add_argument("--scenario", action="append", help="Limit to one scenario id; can be repeated.")
    batch_parser.add_argument("--yes", action="store_true", help="Confirm this batch was manually approved.")
    batch_parser.add_argument("--backtest-timeout", type=int, default=180)
    add_browser_args(batch_parser)
    batch_parser.set_defaults(func=cmd_batch)
    return parser


def add_browser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--user-data-dir", default=str(default_chrome_user_data_dir()), help="Dedicated Chrome profile directory.")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo", type=int, default=0)


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
    return asyncio.run(_run_scenario(args, config, already_confirmed=args.yes))


def cmd_fetch(args: argparse.Namespace) -> int:
    return asyncio.run(_fetch_existing(args))


def cmd_batch(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest_json).resolve()
    manifest = load_manifest(manifest_path)
    scenario_filter = set(args.scenario or [])
    scenario_ids = [
        scenario_id
        for scenario_id, info in manifest.get("scenarios", {}).items()
        if (not scenario_filter or scenario_id in scenario_filter) and info.get("status") != "completed"
    ]
    if not scenario_ids:
        print("No pending scenarios selected.")
        return 0

    print("Selected scenarios:")
    for scenario_id in scenario_ids:
        print(f"  - {scenario_id}")
    if not args.yes and not _confirm("Type RUN to start the selected JoinQuant cloud scenarios: "):
        print("Cancelled.")
        return 1

    for scenario_id in scenario_ids:
        scenario_path = manifest_path.parent / "scenarios" / scenario_id / "scenario.json"
        if not scenario_path.is_file():
            update_manifest(manifest_path, scenario_id=scenario_id, status="failed", error=f"Missing {scenario_path}")
            print(f"Missing scenario config: {scenario_path}", file=sys.stderr)
            continue
        data = load_config_mapping(scenario_path)
        data.setdefault("batch_id", manifest.get("batch_id"))
        data.setdefault("strategy", manifest.get("strategy"))
        data.setdefault("scenario_id", scenario_id)
        config = ScenarioConfig.from_mapping(data, base_dir=scenario_path.parent)
        result = asyncio.run(_run_scenario(args, config, already_confirmed=True, manifest_path=manifest_path))
        if result:
            return result
    return 0


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
) -> int:
    compile_strategy(config.strategy_file)
    upload_path = generate_upload_file(config.strategy_file)
    code = upload_path.read_text(encoding="utf-8")

    ledger_path = ledger_path_for()
    ledger = load_ledger(ledger_path)
    assert_quota_available(ledger, config.estimated_minutes)
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
            await browser.write_strategy_code(code)
            await browser.click_compile()
            await browser.wait_compile_complete()
            effective = await browser.apply_backtest_params(config.start_date, config.end_date, config.capital)
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
            fetched = await _fetch_with_dom_fallback(browser, _bundle_options(config))
            if not run_id:
                backtest_id = browser.current_backtest_id() or fetched.payload.get("metadata", {}).get("backtest_id", "")
                run_id = config.run_id or make_run_id(backtest_id)
            if fetched.method == "api":
                run_dir = save_api_bundle(fetched.payload, strategy=config.strategy, run_id=run_id)
            else:
                run_dir = save_dom_tabs(fetched.payload, strategy=config.strategy, run_id=run_id)
    except Exception as exc:
        manifest_file = manifest_path or _config_manifest_path(config)
        if manifest_file and manifest_file.is_file():
            update_manifest(manifest_file, scenario_id=config.scenario_id, status="failed", error=str(exc))
        raise

    manifest_file = manifest_path or _config_manifest_path(config)
    if manifest_file and manifest_file.is_file():
        update_manifest(manifest_file, scenario_id=config.scenario_id, run_id=run_id, status="completed")

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
        }
        fetched = await _fetch_with_dom_fallback(browser, options)
        if not args.run_id:
            run_id = make_run_id(browser.current_backtest_id() or fetched.payload.get("metadata", {}).get("backtest_id", backtest_id))
        if fetched.method == "api":
            run_dir = save_api_bundle(fetched.payload, strategy=args.strategy, run_id=run_id)
        else:
            run_dir = save_dom_tabs(fetched.payload, strategy=args.strategy, run_id=run_id)
    print(f"Saved existing backtest artifacts: {run_dir}")
    return 0


async def _fetch_with_dom_fallback(browser: JoinQuantBrowser, options: dict[str, Any]) -> FetchedBacktestData:
    try:
        return FetchedBacktestData(method="api", payload=await browser.fetch_api_bundle(options))
    except Exception as exc:
        print(f"API bundle failed, falling back to DOM tabs: {exc}", file=sys.stderr)
        return FetchedBacktestData(method="dom", payload=await browser.collect_dom_tabs())


def _bundle_options(config: ScenarioConfig) -> dict[str, Any]:
    return {
        "strategy": config.strategy,
        "strategyName": config.strategy_name or config.strategy,
        "startDate": config.start_date,
        "endDate": config.end_date,
        "capital": config.capital,
        "frequency": config.frequency,
        "pyVersion": config.py_version,
    }


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


def _set_quota_status(ledger: dict[str, Any], run_id: str, status: str) -> None:
    for item in reversed(ledger.get("runs", [])):
        if item.get("run_id") == run_id:
            item["status"] = status
            return


def _confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False
    return input(prompt).strip() == "RUN"


if __name__ == "__main__":
    raise SystemExit(main())
