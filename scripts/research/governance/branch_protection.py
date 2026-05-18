"""Local coded branch protection for repositories without remote rulesets."""

from __future__ import annotations

import argparse
import os
import sys


PROTECTED_BRANCHES = {"main", "master"}
BYPASS_ENV = "ALLOW_PROTECTED_BRANCH_PUSH"


def check_pre_push_input(input_text: str, *, environ: dict[str, str] | None = None) -> list[str]:
    """Return protected branch push violations from Git pre-push stdin."""

    env = environ if environ is not None else os.environ
    if env.get(BYPASS_ENV) == "1":
        return []

    violations: list[str] = []
    for line in input_text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        _local_ref, _local_sha, remote_ref, _remote_sha = parts[:4]
        branch = _branch_from_ref(remote_ref)
        if branch in PROTECTED_BRANCHES:
            violations.append(branch)
    return sorted(set(violations))


def _branch_from_ref(ref: str) -> str | None:
    prefix = "refs/heads/"
    if not ref.startswith(prefix):
        return None
    return ref.removeprefix(prefix)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pre_push = subparsers.add_parser("pre-push", help="validate Git pre-push refs from stdin")
    pre_push.set_defaults(func=_cmd_pre_push)
    return parser


def _cmd_pre_push(_args: argparse.Namespace) -> int:
    violations = check_pre_push_input(sys.stdin.read())
    if not violations:
        return 0
    branches = ", ".join(violations)
    print(
        "\n".join(
            [
                f"error: direct push to protected branch blocked: {branches}",
                "Create a feature branch and open a PR instead.",
                f"Emergency bypass: set {BYPASS_ENV}=1 for this command and record the reason in the PR/audit trail.",
            ]
        ),
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
