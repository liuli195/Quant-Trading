"""Orchestrate local PR preparation and GitHub synchronization."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import ai_review_gate
from .codex_review_contract import render_codex_review_request


MANAGED_BLOCK_START = "<!-- pr-flow:start -->"
MANAGED_BLOCK_END = "<!-- pr-flow:end -->"
AI_RISK_REVIEW_LABEL = "ai-risk-review"
CODEX_REVIEW_PENDING_EXIT_CODE = 3
WINDOWS_GOVERNANCE_GATE_COMMAND = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
    ".\\.githooks\\run-python.ps1 -m scripts.research.governance gate"
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        result = subprocess.run(
            command,
            cwd=cwd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return CommandResult(result.returncode, result.stdout, result.stderr)


class Runner(Protocol):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        ...


def select_local_checks(changed_files: Sequence[str]) -> list[str]:
    normalized = [_normalize_path(path) for path in changed_files]
    selected: list[str] = []
    needs_full_governance = False

    if any(path in {"requirements.txt", "requirements-dev.txt"} for path in normalized):
        _append_unique(selected, "pip-audit")
        needs_full_governance = True

    if any(path.startswith("scripts/research/governance/") for path in normalized):
        for check in (
            "ruff-governance",
            "bandit-governance",
            "mypy-governance",
            "pytest-governance",
            "governance-full",
        ):
            _append_unique(selected, check)
        needs_full_governance = True

    if any(path.startswith("strategies/") for path in normalized):
        for check in (
            "py-compile-strategy",
            "pytest-strategy-if-present",
            "governance-full",
        ):
            _append_unique(selected, check)
        needs_full_governance = True

    if needs_full_governance:
        _append_unique(selected, "governance-full")
        return selected

    _append_unique(selected, "governance-full")
    return selected


def prepare(
    *,
    repo_root: str | Path = ".",
    runner: Runner | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    changed_files = ai_review_gate._discover_changed_files(root)
    local = root / ".local" / "ai-review"
    latest = local / "latest.json"
    payload = _read_json_object(latest) if latest.is_file() else None
    report_files = (
        ai_review_gate._string_list(payload.get("changed_files"))
        if payload is not None
        else []
    )
    check_files = sorted({*(changed_files or []), *report_files})
    passed_checks: list[str] = []
    for check in select_local_checks(check_files):
        check_result = _run_local_check(check, root=root, runner=runner, changed_files=check_files)
        if check_result.returncode != 0:
            _print_command_failure(check, check_result)
            return check_result.returncode
        passed_checks.append(check)

    local.mkdir(parents=True, exist_ok=True)
    if not latest.is_file():
        draft = ai_review_gate.draft_review_payload(changed_files)
        (local / "latest.draft.json").write_text(
            json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("created .local/ai-review/latest.draft.json; fill latest.json before sync")
        return 1

    payload = payload or _read_json_object(latest)
    validation = ai_review_gate.validate_report_file(latest)
    if payload is None or not validation.ok:
        for error in validation.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    payload = _payload_with_prepare_evidence(
        payload,
        changed_files=check_files,
        passed_checks=passed_checks,
    )
    latest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    (local / "latest.md").write_text(
        ai_review_gate.render_markdown_report(payload),
        encoding="utf-8",
    )
    (local / "codex-review-scope.md").write_text(
        validation.review_scope,
        encoding="utf-8",
    )
    (local / "pr-body.md").write_text(
        ai_review_gate.render_pr_body(payload),
        encoding="utf-8",
    )
    return 0


def sync(
    *,
    repo_root: str | Path = ".",
    title: str | None = None,
    runner: Runner | None = None,
    existing_labels: Sequence[str] | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    local = root / ".local" / "ai-review"
    latest = local / "latest.json"
    payload = _read_json_object(latest)
    if payload is None:
        print(f"error: AI review report missing or invalid: {latest}", file=sys.stderr)
        return 1
    result = ai_review_gate.validate_report_file(latest)
    if not result.ok:
        for error in result.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    pr_body = ai_review_gate.render_pr_body(payload)
    pr_body_path = local / "pr-body.md"
    pr_body_path.write_text(pr_body, encoding="utf-8")
    branch = _command_stdout(runner.run(["git", "branch", "--show-current"], cwd=root))
    if not branch:
        print("error: current branch is empty", file=sys.stderr)
        return 1
    head_sha = _command_stdout(runner.run(["git", "rev-parse", "HEAD"], cwd=root))

    view = runner.run(["gh", "pr", "view", "--json", "number,url,state,isDraft"], cwd=root)
    if view.returncode == 0:
        metadata = _json_from_result(view)
        pr_number = str(metadata.get("number") or "")
        pr_url = str(metadata.get("url") or "")
        body_view = runner.run(["gh", "pr", "view", "--json", "body"], cwd=root)
        existing_body = ""
        if body_view.returncode == 0:
            existing_body = str(_json_from_result(body_view).get("body") or "")
        else:
            _print_command_failure("gh pr view --json body", body_view)
            return body_view.returncode
        body_file = _write_managed_body_file(local, existing_body, pr_body)
        edit = runner.run(["gh", "pr", "edit", pr_number, "--body-file", str(body_file)], cwd=root)
        if edit.returncode != 0:
            _print_command_failure("gh pr edit", edit)
            return edit.returncode
    else:
        if not title:
            print("error: --title is required when no PR exists", file=sys.stderr)
            return 1
        body_file = _write_managed_body_file(local, _pr_template_body(root), pr_body)
        create = runner.run(
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--title",
                title,
                "--body-file",
                str(body_file),
                "--head",
                branch,
            ],
            cwd=root,
        )
        if create.returncode != 0:
            _print_command_failure("gh pr create", create)
            return create.returncode
        pr_url = _command_stdout(create)
        pr_number = _pr_number_from_url(pr_url)

    labels = (
        tuple(existing_labels)
        if existing_labels is not None
        else _current_pr_labels(root, runner)
    )
    if result.risk_level in {"high", "unknown"}:
        label = runner.run(
            ["gh", "pr", "edit", pr_number, "--add-label", AI_RISK_REVIEW_LABEL],
            cwd=root,
        )
        if label.returncode != 0:
            _print_command_failure("gh pr edit --add-label", label)
            return label.returncode
    elif _has_label(labels, AI_RISK_REVIEW_LABEL):
        remove = runner.run(
            ["gh", "pr", "edit", pr_number, "--remove-label", AI_RISK_REVIEW_LABEL],
            cwd=root,
        )
        if remove.returncode != 0:
            _print_command_failure("gh pr edit --remove-label", remove)
            return remove.returncode

    if (
        result.requires_official_codex_review
        and not _official_codex_review_evidence_present(payload)
    ):
        scope_path = local / "codex-review-scope.md"
        scope_text = result.review_scope
        scope_path.write_text(scope_text, encoding="utf-8")
        scope_items = _scope_items(scope_text, payload)
        comment_body = render_codex_review_request(
            pr_url=pr_url,
            head_sha=head_sha,
            review_scope=scope_items,
        )
        comment_file = local / "codex-review-request.md"
        comment_file.write_text(comment_body, encoding="utf-8")
        comment = runner.run(
            ["gh", "pr", "comment", pr_number, "--body-file", str(comment_file)],
            cwd=root,
        )
        if comment.returncode != 0:
            _print_command_failure("gh pr comment", comment)
            return comment.returncode

    return 0


def wait(
    *,
    repo_root: str | Path = ".",
    pr: str | None = None,
    runner: Runner | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    pr_ref = pr or _current_pr_number(root, runner)
    if not pr_ref:
        print("error: PR not found for current branch", file=sys.stderr)
        return 1
    watched = runner.run(
        ["gh", "pr", "checks", pr_ref, "--required", "--watch", "--interval", "10"],
        cwd=root,
    )
    if watched.returncode == 0:
        print(watched.stdout, end="")
        return 0
    summary = runner.run(["gh", "pr", "checks", pr_ref, "--required"], cwd=root)
    failing = _failing_check_names(summary.stdout)
    if failing:
        print("failing required checks:")
        for name in failing:
            print(f"- {name}")
    else:
        print(summary.stdout, end="")
    return watched.returncode


def ready(
    *,
    repo_root: str | Path = ".",
    title: str | None = None,
    runner: Runner | None = None,
) -> int:
    runner = runner or CommandRunner()
    code = prepare(repo_root=repo_root, runner=runner)
    if code != 0:
        return code
    code = sync(repo_root=repo_root, title=title, runner=runner)
    if code != 0:
        return code
    root = Path(repo_root).resolve()
    latest = root / ".local" / "ai-review" / "latest.json"
    payload = _read_json_object(latest)
    result = ai_review_gate.validate_report_file(latest)
    if (
        payload is not None
        and result.requires_official_codex_review
        and not _official_codex_review_evidence_present(payload)
    ):
        print(
            "official Codex review requested; add official_codex_review evidence and rerun ready",
            file=sys.stderr,
        )
        return CODEX_REVIEW_PENDING_EXIT_CODE
    return wait(repo_root=repo_root, runner=runner)


def _run_local_check(
    check: str,
    *,
    root: Path,
    runner: Runner,
    changed_files: Sequence[str],
) -> CommandResult:
    if check == "governance-fast":
        return runner.run(
            [sys.executable, "-m", "scripts.research.governance", "gate", "--fast"],
            cwd=root,
        )
    if check == "pathref":
        return runner.run(
            [sys.executable, "-m", "scripts.tools.path_tools.refactor", "check"],
            cwd=root,
        )
    if check == "ruff-governance":
        return runner.run(
            [sys.executable, "-m", "ruff", "check", "scripts/research/governance"],
            cwd=root,
        )
    if check == "bandit-governance":
        return runner.run(
            [
                sys.executable,
                "-m",
                "bandit",
                "-q",
                "-r",
                "scripts/research/governance",
                "-x",
                "scripts/research/governance/tests",
                "-s",
                "B310,B404,B603,B607",
            ],
            cwd=root,
        )
    if check == "mypy-governance":
        return runner.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--explicit-package-bases",
                "--follow-imports=skip",
                "--ignore-missing-imports",
                "scripts/research/governance",
            ],
            cwd=root,
        )
    if check == "pytest-governance":
        return runner.run(
            [sys.executable, "-m", "pytest", "scripts/research/governance/tests", "-q"],
            cwd=root,
        )
    if check == "governance-full":
        return runner.run(
            [sys.executable, "-m", "scripts.research.governance", "gate"],
            cwd=root,
        )
    if check == "pip-audit":
        return runner.run([sys.executable, "-m", "pip_audit"], cwd=root)
    if check == "py-compile-strategy":
        files = [path for path in changed_files if path.startswith("strategies/") and path.endswith(".py")]
        if not files:
            return CommandResult(0, "", "")
        return runner.run([sys.executable, "-m", "py_compile", *files], cwd=root)
    if check == "pytest-strategy-if-present":
        test_dirs = sorted(_strategy_test_dirs(root, changed_files))
        if not test_dirs:
            return CommandResult(0, "", "")
        return runner.run([sys.executable, "-m", "pytest", *test_dirs, "-q"], cwd=root)
    return CommandResult(2, "", f"unknown check: {check}")


def _strategy_test_dirs(root: Path, changed_files: Sequence[str]) -> set[str]:
    dirs: set[str] = set()
    for path in changed_files:
        parts = _normalize_path(path).split("/")
        if len(parts) >= 2 and parts[0] == "strategies":
            candidate = root / "strategies" / parts[1] / "tests"
            if candidate.is_dir():
                dirs.add(candidate.relative_to(root).as_posix())
    return dirs


def _payload_with_prepare_evidence(
    payload: dict[str, Any],
    *,
    changed_files: Sequence[str],
    passed_checks: Sequence[str],
) -> dict[str, Any]:
    updated = dict(payload)
    if changed_files:
        updated["changed_files"] = sorted(dict.fromkeys(changed_files))
    checks = payload.get("checks")
    merged_checks = dict(checks) if isinstance(checks, dict) else {}
    for check in passed_checks:
        if check == "governance-full":
            merged_checks["governance gate"] = (
                f"{WINDOWS_GOVERNANCE_GATE_COMMAND}; passed"
            )
        elif check == "governance-fast":
            merged_checks["governance fast gate"] = "passed"
        elif check == "pathref":
            merged_checks["pathref"] = "passed"
        elif check == "ruff-governance":
            merged_checks["ruff governance"] = "passed"
        elif check == "bandit-governance":
            merged_checks["bandit governance"] = "passed"
        elif check == "mypy-governance":
            merged_checks["mypy governance"] = "passed"
        elif check == "pytest-governance":
            merged_checks["pytest governance tests"] = "passed"
        elif check == "pip-audit":
            merged_checks["pip-audit"] = "passed"
        elif check == "py-compile-strategy":
            merged_checks["py_compile strategy"] = "passed"
        elif check == "pytest-strategy-if-present":
            merged_checks["pytest strategy tests"] = "passed"
    if merged_checks:
        updated["checks"] = merged_checks
    return updated


def _write_managed_body_file(
    local: Path,
    existing_body: str,
    managed_body: str,
) -> Path:
    local.mkdir(parents=True, exist_ok=True)
    merged = _replace_managed_block(existing_body, managed_body)
    body_file = local / "pr-body.managed.md"
    body_file.write_text(merged, encoding="utf-8")
    return body_file


def _replace_managed_block(existing_body: str, managed_body: str) -> str:
    block = f"{MANAGED_BLOCK_START}\n{managed_body.strip()}\n{MANAGED_BLOCK_END}"
    if MANAGED_BLOCK_START in existing_body and MANAGED_BLOCK_END in existing_body:
        pattern = re.compile(
            rf"{re.escape(MANAGED_BLOCK_START)}.*?{re.escape(MANAGED_BLOCK_END)}",
            re.DOTALL,
        )
        return pattern.sub(block, existing_body)
    if existing_body.strip():
        return f"{existing_body.rstrip()}\n\n{block}\n"
    return f"{block}\n"


def _current_pr_number(root: Path, runner: Runner) -> str:
    view = runner.run(["gh", "pr", "view", "--json", "number,url,state,isDraft"], cwd=root)
    if view.returncode != 0:
        return ""
    return str(_json_from_result(view).get("number") or "")


def _current_pr_labels(root: Path, runner: Runner) -> tuple[str, ...]:
    view = runner.run(["gh", "pr", "view", "--json", "labels"], cwd=root)
    if view.returncode != 0:
        return ()
    labels = _json_from_result(view).get("labels")
    if not isinstance(labels, list):
        return ()
    return tuple(
        str(item.get("name") or "")
        for item in labels
        if isinstance(item, dict) and item.get("name")
    )


def _has_label(labels: Sequence[str], label: str) -> bool:
    return any(item.casefold() == label.casefold() for item in labels)


def _pr_template_body(root: Path) -> str:
    template = root / ".github" / "pull_request_template.md"
    if not template.is_file():
        return ""
    return template.read_text(encoding="utf-8", errors="ignore")


def _json_from_result(result: CommandResult) -> dict[str, Any]:
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _scope_items(scope_text: str, payload: dict[str, Any]) -> tuple[str, ...]:
    items: list[str] = []
    for line in scope_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped.removeprefix("- ").strip().strip("`")
        if "/" in item or item.startswith("."):
            items.append(item)
    if not items:
        items = ai_review_gate._string_list(payload.get("changed_files"))
    return tuple(dict.fromkeys(items))


def _official_codex_review_evidence_present(payload: dict[str, Any]) -> bool:
    return bool(ai_review_gate._render_official_codex_review_lines(payload))


def _failing_check_names(output: str) -> list[str]:
    failing: list[str] = []
    for line in output.splitlines():
        normalized = line.casefold()
        if any(token in normalized for token in ("fail", "failure", "cancel", "error")):
            name = line.split("\t", 1)[0].strip()
            failing.append(name or line.strip())
    return failing


def _command_stdout(result: CommandResult) -> str:
    return result.stdout.strip()


def _pr_number_from_url(url: str) -> str:
    match = re.search(r"/pull/(\d+)", url)
    return match.group(1) if match else url


def _print_command_failure(label: str, result: CommandResult) -> None:
    print(f"error: {label} failed with exit code {result.returncode}", file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--title")
    wait_parser = subparsers.add_parser("wait")
    wait_parser.add_argument("--pr")
    ready_parser = subparsers.add_parser("ready")
    ready_parser.add_argument("--title")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        return prepare(repo_root=args.repo_root)
    if args.command == "sync":
        return sync(repo_root=args.repo_root, title=args.title)
    if args.command == "wait":
        return wait(repo_root=args.repo_root, pr=args.pr)
    if args.command == "ready":
        return ready(repo_root=args.repo_root, title=args.title)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
