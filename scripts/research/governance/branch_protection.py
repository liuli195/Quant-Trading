"""Local coded branch protection for repositories without remote rulesets."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence


PROTECTED_BRANCHES = {"main", "master"}
BYPASS_ENV = "ALLOW_PROTECTED_BRANCH_PUSH"
BYPASS_REASON_ENV = "PROTECTED_BRANCH_PUSH_REASON"
DIRECT_MAIN_WRITE_ENV = "ALLOW_DIRECT_MAIN_WRITE"
DIRECT_MAIN_WRITE_REASON_ENV = "DIRECT_MAIN_WRITE_REASON"
REF_UPDATE_BYPASS_ENV = "ALLOW_MAIN_REF_UPDATE"
REF_UPDATE_REASON_ENV = "MAIN_REF_UPDATE_REASON"
HISTORY_REWRITE_BYPASS_ENV = "ALLOW_BRANCH_HISTORY_REWRITE"
HISTORY_REWRITE_REASON_ENV = "BRANCH_HISTORY_REWRITE_REASON"
ZERO_SHA = "0" * 40


def check_pre_push_input(input_text: str, *, environ: dict[str, str] | None = None) -> list[str]:
    """Return protected branch push violations from Git pre-push stdin."""

    env = environ if environ is not None else os.environ
    if _env_pair_enabled(env, DIRECT_MAIN_WRITE_ENV, DIRECT_MAIN_WRITE_REASON_ENV):
        return []
    if _env_pair_enabled(env, BYPASS_ENV, BYPASS_REASON_ENV):
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


def check_reference_transaction_input(
    input_text: str,
    *,
    environ: dict[str, str] | None = None,
    remote_heads: Mapping[str, str | None] | None = None,
    is_ancestor: Callable[[str, str], bool] | None = None,
) -> list[str]:
    """Return protected local branch ref updates from Git reference-transaction stdin."""

    updates = _protected_branch_updates_from_reference_transaction(input_text)
    env = environ if environ is not None else os.environ
    violations: list[str] = []
    if updates:
        branches = sorted({branch for _old_sha, _new_sha, branch in updates})
        if _env_pair_enabled(env, DIRECT_MAIN_WRITE_ENV, DIRECT_MAIN_WRITE_REASON_ENV):
            violations.extend(
                sorted(
                    {
                        branch
                        for old_sha, new_sha, branch in updates
                        if not _is_fast_forward_update(
                            old_sha,
                            new_sha,
                            is_ancestor=is_ancestor,
                        )
                    }
                )
            )
        elif (
            env.get(REF_UPDATE_BYPASS_ENV) != "1"
            or not env.get(REF_UPDATE_REASON_ENV, "").strip()
        ):
            violations.extend(branches)
        else:
            for old_sha, new_sha, branch in updates:
                remote_sha = _remote_head_for_branch(
                    branch,
                    remote_heads=remote_heads,
                )
                if remote_sha != new_sha or not _is_fast_forward_update(
                    old_sha,
                    new_sha,
                    is_ancestor=is_ancestor,
                ):
                    violations.append(branch)

    history_rewrite_violations = _history_rewrite_branch_violations(
        input_text,
        environ=env,
        is_ancestor=is_ancestor,
    )
    violations.extend(
        branch
        for branch in history_rewrite_violations
        if branch not in PROTECTED_BRANCHES
    )
    return sorted(set(violations))


def _protected_branch_updates_from_reference_transaction(input_text: str) -> list[tuple[str, str, str]]:
    return [
        (old_sha, new_sha, branch)
        for old_sha, new_sha, branch in _branch_updates_from_reference_transaction(
            input_text
        )
        if branch in PROTECTED_BRANCHES
    ]


def _branch_updates_from_reference_transaction(input_text: str) -> list[tuple[str, str, str]]:
    updates: list[tuple[str, str, str]] = []
    for line in input_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        old_sha, new_sha, ref = parts[:3]
        branch = _branch_from_ref(ref)
        if branch:
            updates.append((old_sha, new_sha, branch))
    return updates


def _history_rewrite_branch_violations(
    input_text: str,
    *,
    environ: Mapping[str, str],
    is_ancestor: Callable[[str, str], bool] | None = None,
) -> list[str]:
    if _env_pair_enabled(
        environ,
        HISTORY_REWRITE_BYPASS_ENV,
        HISTORY_REWRITE_REASON_ENV,
    ):
        return []
    violations: list[str] = []
    for old_sha, new_sha, branch in _branch_updates_from_reference_transaction(
        input_text
    ):
        if old_sha == ZERO_SHA or new_sha == ZERO_SHA:
            continue
        if not _is_fast_forward_update(old_sha, new_sha, is_ancestor=is_ancestor):
            violations.append(branch)
    return sorted(set(violations))


def run_authorized_history_rewrite(
    command: Sequence[str],
    reason: str,
    *,
    environ: Mapping[str, str] | None = None,
    run: Callable[[Sequence[str], Mapping[str, str]], int] | None = None,
) -> int:
    """Run one Git command with history rewrite authorization scoped to the child."""

    normalized = [item for item in command if item]
    if normalized and normalized[0] == "--":
        normalized = normalized[1:]
    if not normalized:
        raise ValueError("authorized history rewrite command is required")
    executable = normalized[0].lower()
    if executable not in {"git", "git.exe"}:
        raise ValueError("authorized history rewrite wrapper only runs git commands")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError(f"{HISTORY_REWRITE_REASON_ENV} is required")
    parent_env = dict(environ if environ is not None else os.environ)
    child_env = dict(parent_env)
    child_env[HISTORY_REWRITE_BYPASS_ENV] = "1"
    child_env[HISTORY_REWRITE_REASON_ENV] = normalized_reason
    if run is not None:
        return run(normalized, child_env)
    result = subprocess.run(normalized, env=child_env, check=False)
    return int(result.returncode)


def run_authorized_main(
    command: Sequence[str],
    *,
    action: str,
    reason: str,
    environ: Mapping[str, str] | None = None,
    run: Callable[[Sequence[str], Mapping[str, str]], int] | None = None,
) -> int:
    """Run one Git command with main authorization scoped to the child."""

    normalized = [item for item in command if item]
    if normalized and normalized[0] == "--":
        normalized = normalized[1:]
    if not normalized:
        raise ValueError("authorized main command is required")
    executable = normalized[0].lower()
    if executable not in {"git", "git.exe"}:
        raise ValueError("authorized main wrapper only runs git commands")
    normalized_reason = reason.strip()
    if action == "direct-write":
        flag_env = DIRECT_MAIN_WRITE_ENV
        reason_env = DIRECT_MAIN_WRITE_REASON_ENV
    elif action == "ref-sync":
        flag_env = REF_UPDATE_BYPASS_ENV
        reason_env = REF_UPDATE_REASON_ENV
    else:
        raise ValueError("authorized main action must be direct-write or ref-sync")
    _validate_authorized_main_command(normalized, action=action)
    if not normalized_reason:
        raise ValueError(f"{reason_env} is required")
    parent_env = dict(environ if environ is not None else os.environ)
    child_env = dict(parent_env)
    for name in _MAIN_AUTH_ENV_NAMES:
        child_env.pop(name, None)
    child_env[flag_env] = "1"
    child_env[reason_env] = normalized_reason
    if run is not None:
        return run(normalized, child_env)
    result = subprocess.run(normalized, env=child_env, check=False)
    return int(result.returncode)


_MAIN_AUTH_ENV_NAMES = {
    BYPASS_ENV,
    BYPASS_REASON_ENV,
    DIRECT_MAIN_WRITE_ENV,
    DIRECT_MAIN_WRITE_REASON_ENV,
    REF_UPDATE_BYPASS_ENV,
    REF_UPDATE_REASON_ENV,
}


def _validate_authorized_main_command(command: Sequence[str], *, action: str) -> None:
    lowered = [item.lower() for item in command]
    parsed = _parse_git_command(lowered)
    if parsed is None:
        raise ValueError("authorized main wrapper does not allow git global options")
    subcommand, args = parsed
    if action == "ref-sync" and [lowered[0], subcommand, *args] != [
        lowered[0],
        "merge",
        "--ff-only",
        "origin/main",
    ]:
        raise ValueError("ref-sync only runs git merge --ff-only origin/main")
    if _authorized_main_command_is_destructive(subcommand, args):
        raise ValueError("authorized main wrapper does not allow destructive git commands")


def _parse_git_command(lowered: Sequence[str]) -> tuple[str, list[str]] | None:
    if len(lowered) < 2:
        return None
    subcommand = lowered[1]
    if subcommand.startswith("-"):
        return None
    return subcommand, list(lowered[2:])


def _authorized_main_command_is_destructive(subcommand: str, args: Sequence[str]) -> bool:
    if subcommand in {"reset", "rebase", "update-ref"}:
        return True
    if subcommand == "push":
        return any(
            arg
            in {
                "--force",
                "-f",
                "--force-with-lease",
                "--delete",
                "-d",
                "--mirror",
                "--prune",
            }
            or arg.startswith("--force")
            or arg.startswith(("+", ":"))
            for arg in args
        )
    if subcommand == "branch":
        return any(arg in {"-d", "-D", "--delete", "-m", "-M", "--move"} for arg in args)
    if subcommand == "checkout":
        return any(arg in {"-B", "-b"} or arg.startswith("-B") for arg in args)
    if subcommand == "switch":
        return any(arg in {"-C", "-c"} or arg.startswith("-C") for arg in args)
    return False


def _remote_head_for_branch(branch: str, *, remote_heads: Mapping[str, str | None] | None = None) -> str | None:
    if remote_heads is not None:
        return remote_heads.get(branch)

    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/remotes/origin/{branch}^{{commit}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_fast_forward_update(
    old_sha: str,
    new_sha: str,
    *,
    is_ancestor: Callable[[str, str], bool] | None = None,
) -> bool:
    if old_sha == ZERO_SHA:
        return True
    if new_sha == ZERO_SHA:
        return False
    if is_ancestor is not None:
        return is_ancestor(old_sha, new_sha)

    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", old_sha, new_sha],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _env_pair_enabled(env: Mapping[str, str], flag: str, reason: str) -> bool:
    return env.get(flag) == "1" and bool(env.get(reason, "").strip())


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
    allow_history_rewrite = subparsers.add_parser(
        "allow-history-rewrite",
        help="run one Git command with local branch history rewrite authorization",
    )
    allow_history_rewrite.add_argument("--reason", required=True)
    allow_history_rewrite.add_argument("git_command", nargs=argparse.REMAINDER)
    allow_history_rewrite.set_defaults(func=_cmd_allow_history_rewrite)
    authorize_main = subparsers.add_parser(
        "authorize-main",
        help="run one Git command with scoped main-branch authorization",
    )
    authorize_main.add_argument(
        "--action",
        choices=("direct-write", "ref-sync"),
        required=True,
    )
    authorize_main.add_argument("--reason", required=True)
    authorize_main.add_argument("git_command", nargs=argparse.REMAINDER)
    authorize_main.set_defaults(func=_cmd_authorize_main)
    return parser


def _cmd_pre_push(_args: argparse.Namespace) -> int:
    violations = check_pre_push_input(sys.stdin.read())
    if not violations:
        return 0
    branches = ", ".join(violations)
    message = [f"error: direct push to protected branch blocked: {branches}"]
    if os.environ.get(DIRECT_MAIN_WRITE_ENV) == "1" and not os.environ.get(DIRECT_MAIN_WRITE_REASON_ENV, "").strip():
        message.append(f"error: {DIRECT_MAIN_WRITE_REASON_ENV} is required when {DIRECT_MAIN_WRITE_ENV}=1")
    if os.environ.get(BYPASS_ENV) == "1" and not os.environ.get(BYPASS_REASON_ENV, "").strip():
        message.append(f"error: {BYPASS_REASON_ENV} is required when {BYPASS_ENV}=1")
    message.extend(
        [
            "Create a feature branch and open a PR instead.",
            (
                "Explicit direct-main path: run "
                "branch_protection authorize-main --action direct-write "
                "--reason <reason> -- git <main-command>."
            ),
        ]
    )
    print(
        "\n".join(message),
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
        f"error: local branch ref update blocked: {branches}",
        "Local branch history rewrite is blocked by default; use an additional commit instead.",
        "Do not merge feature branches into main/master locally; open a PR instead.",
        (
            "Explicit direct-main path: run "
            "branch_protection authorize-main --action direct-write "
            "--reason <reason> -- git <main-command>."
        ),
        "After a remote PR merge, local main/master may only fast-forward to refs/remotes/origin/<branch>.",
        (
            "Audited sync bypass: run "
            "branch_protection authorize-main --action ref-sync "
            "--reason <reason> -- git merge --ff-only origin/main."
        ),
        (
            "Single-command history rewrite exception: run "
            "branch_protection allow-history-rewrite --reason <reason> -- git <command>."
        ),
    ]
    if os.environ.get(DIRECT_MAIN_WRITE_ENV) == "1" and not os.environ.get(DIRECT_MAIN_WRITE_REASON_ENV, "").strip():
        message.insert(1, f"error: {DIRECT_MAIN_WRITE_REASON_ENV} is required when {DIRECT_MAIN_WRITE_ENV}=1")
    if os.environ.get(REF_UPDATE_BYPASS_ENV) == "1" and not os.environ.get(REF_UPDATE_REASON_ENV, "").strip():
        message.insert(1, f"error: {REF_UPDATE_REASON_ENV} is required when {REF_UPDATE_BYPASS_ENV}=1")
    if os.environ.get(HISTORY_REWRITE_BYPASS_ENV) == "1" and not os.environ.get(HISTORY_REWRITE_REASON_ENV, "").strip():
        message.insert(1, f"error: {HISTORY_REWRITE_REASON_ENV} is required when {HISTORY_REWRITE_BYPASS_ENV}=1")
    print("\n".join(message), file=sys.stderr)
    return 1


def _cmd_allow_history_rewrite(args: argparse.Namespace) -> int:
    try:
        return run_authorized_history_rewrite(args.git_command, args.reason)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _cmd_authorize_main(args: argparse.Namespace) -> int:
    try:
        return run_authorized_main(
            args.git_command,
            action=args.action,
            reason=args.reason,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
