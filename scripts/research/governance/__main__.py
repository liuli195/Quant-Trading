"""Module entrypoint for ``python -m scripts.research.governance``."""

from __future__ import annotations

import argparse

from .audit import main as audit_main
from .gate import main as gate_main
from .verify import main as verify_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="run governance audit")
    audit.add_argument("--repo-root", default=".")
    audit.add_argument("--skip-cli-help", action="store_true")
    audit.add_argument("--skip-pathrefs", action="store_true")
    gate = subparsers.add_parser("gate", help="run governance audit and pathref gate")
    gate.add_argument("--repo-root", default=".")
    gate.add_argument("--skip-cli-help", action="store_true")
    verify = subparsers.add_parser("verify", help="run affected verification", add_help=False)
    verify.set_defaults(func=verify_main)
    args, extra = parser.parse_known_args(argv)
    if args.command in {"audit", "gate"} and extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    if args.command == "audit":
        forwarded = ["--repo-root", args.repo_root]
        if args.skip_cli_help:
            forwarded.append("--skip-cli-help")
        if args.skip_pathrefs:
            forwarded.append("--skip-pathrefs")
        return audit_main(forwarded)
    if args.command == "gate":
        forwarded = ["--repo-root", args.repo_root]
        if args.skip_cli_help:
            forwarded.append("--skip-cli-help")
        return gate_main(forwarded)
    if args.command == "verify":
        return verify_main(extra)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
