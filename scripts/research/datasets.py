"""CLI for repository-level immutable research datasets."""

from __future__ import annotations

import argparse
import json

from .platform.datasets import import_joinquant_price_json, import_audit_log_jsonl, import_backtest_run, load_snapshot


def _cmd_import(args: argparse.Namespace) -> int:
    snapshot = import_joinquant_price_json(
        args.source,
        dataset_id=args.dataset_id,
        snapshot_id=args.snapshot_id,
    )
    print(snapshot.root)
    return 0


def _cmd_import_audit(args: argparse.Namespace) -> int:
    snapshot = import_audit_log_jsonl(
        args.source,
        dataset_id=args.dataset_id,
        snapshot_id=args.snapshot_id,
    )
    print(snapshot.root)
    return 0


def _cmd_import_backtest_run(args: argparse.Namespace) -> int:
    snapshot = import_backtest_run(
        args.source,
        dataset_id=args.dataset_id,
        snapshot_id=args.snapshot_id,
    )
    print(snapshot.root)
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    snapshot = load_snapshot(args.dataset_id, args.snapshot_id)
    print(json.dumps(snapshot.metadata, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-price-json", help="import one JoinQuant price JSON export")
    import_parser.add_argument("source")
    import_parser.add_argument("--dataset-id", required=True)
    import_parser.add_argument("--snapshot-id")
    import_parser.set_defaults(func=_cmd_import)

    audit_import = subparsers.add_parser("import-audit-log", help="import one JoinQuant audit log JSONL file")
    audit_import.add_argument("source")
    audit_import.add_argument("--dataset-id", required=True)
    audit_import.add_argument("--snapshot-id")
    audit_import.set_defaults(func=_cmd_import_audit)

    run_import = subparsers.add_parser("import-backtest-run", help="import one complete backtest_runs/<run_id> directory")
    run_import.add_argument("source")
    run_import.add_argument("--dataset-id", required=True)
    run_import.add_argument("--snapshot-id")
    run_import.set_defaults(func=_cmd_import_backtest_run)

    inspect = subparsers.add_parser("inspect", help="print dataset metadata")
    inspect.add_argument("dataset_id")
    inspect.add_argument("snapshot_id")
    inspect.set_defaults(func=_cmd_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
