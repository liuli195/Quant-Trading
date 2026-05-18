"""Local coded branch protection for repositories without remote rulesets."""

from __future__ import annotations

import argparse
import os
import sys


PROTECTED_BRANCHES = {"main", "master"}
BYPASS_ENV = "ALLOW_PROTECTED_BRANCH_PUSH"
REF_UPDATE_BYPASS_ENV = "ALLOW_MAIN_REF_UPDATE"
REF_UPDATE_REASON_ENV = "MAIN_REF_UPDATE_REASON"


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


def check_reference_transaction_input(input_text: str, *, environ: dict[str, str] | None = None) -> list[str]:
    """Return protected local branch ref updates from Git reference-transaction stdin."""

    violations = _protected_branches_from_reference_transaction(input_text)
    if not violations:
        return []

    env = environ if environ is not None else os.environ
    if env.get(REF_UPDATE_BYPASS_ENV) == "1" and env.get(REF_UPDATE_REASON_ENV, "").strip():
        return []
    return violations


def _protected_branches_from_reference_transaction(input_text: str) -> list[str]:
    violations: list[str] = []
    for line in input_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        _old_sha, _new_sha, ref = parts[:3]
        branch = _branch_from_ref(ref)
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
    reference_transaction = subparsers.add_parser(
        "reference-transaction",
        help="validate local protected branch ref updates from stdin",
    )
    reference_transaction.set_defaults(func=_cmd_reference_transaction)
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


def _cmd_reference_transaction(_args: argparse.Namespace) -> int:
    input_text = sys.stdin.read()
    violations = check_reference_transaction_input(input_text)
    if not violations:
        return 0

    branches = ", ".join(violations)
    message = [
        f"error: local update to protected branch blocked: {branches}",
        "Do not merge feature branches into main/master locally; open a PR instead.",
        (
            f"Audited sync/break-glass bypass: set {REF_UPDATE_BYPASS_ENV}=1 and "
            f"{REF_UPDATE_REASON_ENV}=<reason> for this command."
        ),
    ]
    if os.environ.get(REF_UPDATE_BYPASS_ENV) == "1" and not os.environ.get(REF_UPDATE_REASON_ENV, "").strip():
        message.insert(1, f"error: {REF_UPDATE_REASON_ENV} is required when {REF_UPDATE_BYPASS_ENV}=1")
    print("\n".join(message), file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
