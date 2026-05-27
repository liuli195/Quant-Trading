"""Governance gate for local hooks and CI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .rules import run_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--skip-cli-help", action="store_true")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="run governance audit only; skip CLI help and pathref checks",
    )
    return parser


def run_gate(
    repo_root: str | Path = ".",
    *,
    check_cli_help: bool = True,
    check_pathrefs: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    audit = run_audit(
        root,
        check_cli_help=check_cli_help,
        check_pathrefs=False,
    )
    pathref_result: dict[str, Any]
    if check_pathrefs:
        pathref = subprocess.run(
            [sys.executable, "-m", "scripts.tools.path_tools.refactor", "check"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        pathref_ok = pathref.returncode == 0
        pathref_result = {
            "ok": pathref_ok,
            "returncode": pathref.returncode,
            "stdout": pathref.stdout.strip(),
            "stderr": pathref.stderr.strip(),
        }
    else:
        pathref_ok = True
        pathref_result = {
            "ok": True,
            "skipped": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }
    return {
        "ok": audit.ok and pathref_ok,
        "audit": audit.to_dict(),
        "pathref": pathref_result,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    report = run_gate(
        args.repo_root,
        check_cli_help=not (args.skip_cli_help or args.fast),
        check_pathrefs=not args.fast,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
