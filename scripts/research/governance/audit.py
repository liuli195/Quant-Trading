"""Command-line governance audit."""

from __future__ import annotations

import argparse
import json

from .rules import run_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--skip-cli-help", action="store_true")
    parser.add_argument("--skip-pathrefs", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_audit(
        args.repo_root,
        check_cli_help=not args.skip_cli_help,
        check_pathrefs=not args.skip_pathrefs,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
