"""CLI for report indexing and document utilities."""

from __future__ import annotations

import argparse
import json

from .platform.docs_index import DocsIndexer


def _cmd_index(args: argparse.Namespace) -> int:
    payload = DocsIndexer(args.repo_root).write(args.output_dir)
    print(json.dumps({"count": payload["count"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    index = subparsers.add_parser("index", help="build docs/indexes report catalog")
    index.add_argument("--repo-root", default=".")
    index.add_argument("--output-dir", default="docs/indexes")
    index.set_defaults(func=_cmd_index)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
