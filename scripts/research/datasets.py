"""CLI for repository-level immutable research datasets."""

from __future__ import annotations

import argparse
import json

from .platform.datasets import import_joinquant_price_json, load_snapshot


def _cmd_import(args: argparse.Namespace) -> int:
    snapshot = import_joinquant_price_json(
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
