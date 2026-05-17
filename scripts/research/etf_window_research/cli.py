"""Project-oriented CLI for ETF window research workflows."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .analysis import analyze_project
from .fetch_remote_data import fetch_remote_price_bundle
from .layout import ResearchProjectLayout
from .research_export import (
    DEFAULT_EXPORT_PATH,
    DEFAULT_HISTORY_START,
    build_joinquant_research_export_script,
)


def _cmd_export_script(args: argparse.Namespace) -> int:
    project = ResearchProjectLayout.from_path(args.project_dir)
    project.ensure_project_dirs()
    output = Path(args.output) if args.output else project.joinquant_export_script_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_joinquant_research_export_script(
            export_path=args.export_path,
            history_start=args.history_start,
        ),
        encoding="utf-8",
    )
    print(output)
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    project = ResearchProjectLayout.from_path(args.project_dir)
    project.ensure_project_dirs()
    output = Path(args.output) if args.output else project.raw_price_bundle_path()
    fetched = asyncio.run(
        fetch_remote_price_bundle(
            output=output,
            export_path=args.export_path,
            history_start=args.history_start,
            user_data_dir=args.user_data_dir,
            headless=args.headless,
            slow_mo=args.slow_mo,
        )
    )
    print(fetched)
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    analyze_project(
        project_dir=args.project_dir,
        run_id=args.run_id,
        raw_data_path=args.raw_data,
        audit_log_path=args.audit_log,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-script", help="write the JoinQuant export script")
    export_parser.add_argument("--project-dir", required=True)
    export_parser.add_argument("--output")
    export_parser.add_argument("--export-path", default=DEFAULT_EXPORT_PATH)
    export_parser.add_argument("--history-start", default=DEFAULT_HISTORY_START)
    export_parser.set_defaults(func=_cmd_export_script)

    fetch_parser = subparsers.add_parser("fetch", help="fetch the raw JoinQuant price bundle")
    fetch_parser.add_argument("--project-dir", required=True)
    fetch_parser.add_argument("--output")
    fetch_parser.add_argument("--export-path", default=DEFAULT_EXPORT_PATH)
    fetch_parser.add_argument("--history-start", default=DEFAULT_HISTORY_START)
    fetch_parser.add_argument("--user-data-dir", default=".local/chrome-jq")
    fetch_parser.add_argument("--headless", action="store_true")
    fetch_parser.add_argument("--slow-mo", type=int, default=0)
    fetch_parser.set_defaults(func=_cmd_fetch)

    analyze_parser = subparsers.add_parser("analyze", help="run a local analysis and persist one run")
    analyze_parser.add_argument("--project-dir", required=True)
    analyze_parser.add_argument("--run-id", required=True)
    analyze_parser.add_argument("--raw-data")
    analyze_parser.add_argument("--audit-log")
    analyze_parser.set_defaults(func=_cmd_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
