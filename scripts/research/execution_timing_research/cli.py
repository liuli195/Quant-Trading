from __future__ import annotations

import argparse
import json

from .analysis import analyze_project, default_project_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="execution timing local research")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="run the local execution-timing study")
    analyze.add_argument("--project-dir", default=str(default_project_dir()))
    analyze.add_argument("--run-id", required=True)
    analyze.add_argument("--raw-price-path")
    analyze.add_argument("--audit-log-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "analyze":
        payload = analyze_project(
            project_dir=args.project_dir,
            run_id=args.run_id,
            raw_price_path=args.raw_price_path,
            audit_log_path=args.audit_log_path,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
