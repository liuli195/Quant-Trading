"""Orchestrate local PR preparation and GitHub synchronization."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .affected import plan_checks
from . import ai_review_gate, pr_review_evidence
from .codex_review_contract import is_codex_review_request, render_codex_review_request


MANAGED_BLOCK_START = "<!-- pr-flow:start -->"
MANAGED_BLOCK_END = "<!-- pr-flow:end -->"
AI_RISK_REVIEW_LABEL = "ai-risk-review"
SUCCESS_EXIT_CODE = 0
GENERAL_FAILURE_EXIT_CODE = 1
CODEX_REVIEW_PENDING_EXIT_CODE = 3
DISPATCH_REQUIRED_EXIT_CODE = 4
REPLY_OR_FIX_REQUIRED_EXIT_CODE = 5
EXCEPTION_REQUIRED_EXIT_CODE = 6
WINDOWS_PR_BODY_VERIFY_FULL_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full"
)
POSIX_PR_BODY_VERIFY_FULL_COMMAND = (
    ".venv/bin/python -m scripts.research.governance verify full"
)
CODEX_REVIEW_AUTHORS = {"chatgpt-codex-connector", "chatgpt-codex-connector[bot]"}
DISQUALIFIED_CODEX_REVIEW_STATES = {"DISMISSED", "PENDING"}
CODEX_REVIEW_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)#pullrequestreview-(?P<review_id>\d+)"
)
CODEX_COMPLETION_COMMENT_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/(?:pull|issues)/(?P<number>\d+)#issuecomment-(?P<comment_id>\d+)"
)
CODEX_NO_MAJOR_ISSUES_PATTERN = re.compile(
    r"Codex Review:\s*(?:Didn['’]t|Did not) find any major issues",
    re.IGNORECASE,
)
BLOCKING_CODEX_FINDING_PATTERN = re.compile(r"\bP[01]\b|P[01]\s*Badge")
CODEX_THREAD_SEVERITY_PATTERN = re.compile(r"\bP(?P<level>[0-3])\b")
ACTIONS_CHECK_URL_PATTERN = re.compile(r"/actions/runs/(?P<run_id>\d+)/job/(?P<job_id>\d+)")
CHECKS_JSON_FIELDS = "name,state,bucket,link,workflow,startedAt,completedAt"
PR_DIAGNOSE_JSON_FIELDS = (
    "number,url,state,isDraft,headRefOid,baseRefName,mergeStateStatus,reviewDecision,body"
)
CODEX_REVIEW_WAIT_TIMEOUT_SECONDS = 1800.0
CODEX_REVIEW_WAIT_INTERVAL_SECONDS = 30.0
AUTO_ACCEPTED_REVIEW_THREAD_SEVERITIES = {"P2", "P3"}
CLOSED_REVIEW_THREAD_STATUSES = {"fixed", "false_positive"}
GITHUB_READ_MAX_ATTEMPTS = 3
GITHUB_READ_RETRY_BACKOFF_SECONDS = 0.1
PR_READY_PHASES = (
    "preflight",
    "freeze_diff",
    "local_review",
    "security_review",
    "build_evidence",
    "official_codex",
    "threads",
    "sync_pr_body",
    "wait_latest_checks",
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CodexReviewWaitResult:
    evidence: str | None
    state: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class PullRequestReviewRequirement:
    approval_required: bool
    source: str


@dataclass(frozen=True)
class GitHubErrorClassification:
    retryable: bool
    reason: str


@dataclass(frozen=True)
class StopStatus:
    state: str
    message: str
    reason_code: str
    phase: str
    retryable: bool
    dispatch_target: str
    blocking_items: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()

    def as_json(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "state": self.state,
            "message": self.message,
            "reason_code": self.reason_code,
            "phase": self.phase,
            "retryable": self.retryable,
            "dispatch_target": self.dispatch_target,
            "blocking_items": list(self.blocking_items),
            "evidence_refs": list(self.evidence_refs),
            "next_actions": list(self.next_actions),
        }


class GitHubDataUnavailable(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        details: Sequence[str] = (),
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.details = tuple(detail for detail in details if detail)
        self.retryable = retryable


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


def select_local_checks(changed_files: Sequence[str], *, repo_root: str | Path = ".") -> list[str]:
    affected = plan_checks(changed_files, repo_root=repo_root)
    selected: list[str] = []
    for check in affected.checked:
        for local_check in _local_checks_for_check_id(check.check_id):
            _append_unique(selected, local_check)
    _append_unique(selected, "governance-full")
    return selected


def _local_checks_for_check_id(check_id: str) -> tuple[str, ...]:
    return {
        "ruff.governance": ("ruff-governance",),
        "bandit.governance": ("bandit-governance",),
        "mypy.governance": ("mypy-governance",),
        "pytest.governance": ("pytest-governance",),
        "py_compile.strategy": ("py-compile-strategy",),
        "pytest.strategy": ("pytest-strategy-if-present",),
        "pip-audit.dependencies": ("pip-audit",),
    }.get(check_id, ())


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
    for check in select_local_checks(check_files, repo_root=root):
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
        root=root,
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

    view = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "view", "--json", "number,url,state,isDraft"],
    )
    if view.returncode == 0:
        metadata = _json_from_result(view)
        pr_number = str(metadata.get("number") or "")
        pr_url = str(metadata.get("url") or "")
        body_view = _run_github_read_command(
            root,
            runner,
            ["gh", "pr", "view", "--json", "body"],
        )
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
        remote_head = runner.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            cwd=root,
        )
        if remote_head.returncode != 0:
            _print_state(
                "EXCEPTION_REQUIRED",
                "remote branch status unavailable",
                details=[
                    _single_line_text(remote_head.stderr),
                    _single_line_text(remote_head.stdout),
                ],
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if not _command_stdout(remote_head):
            _print_state(
                "PUSH_REQUIRED",
                "remote branch missing for PR creation",
                details=[f"git push -u origin {branch}"],
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
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

    try:
        needs_codex_review_request = (
            result.requires_official_codex_review
            and not _official_codex_review_evidence_valid_for_current_pr(
                payload,
                pr_url=pr_url,
                head_sha=head_sha,
                root=root,
                runner=runner,
            )
            and not _current_head_codex_trigger_exists(
                pr_url=pr_url,
                head_sha=head_sha,
                root=root,
                runner=runner,
            )
        )
    except GitHubDataUnavailable as exc:
        _print_github_data_unavailable(exc)
        return EXCEPTION_REQUIRED_EXIT_CODE

    if needs_codex_review_request:
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
    watched = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "checks", pr_ref, "--required", "--watch", "--interval", "10"],
    )
    if watched.returncode == 0:
        print(watched.stdout, end="")
        return 0
    json_summary = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "checks", pr_ref, "--required", "--json", CHECKS_JSON_FIELDS],
    )
    latest_results = _latest_required_check_results(json_summary.stdout)
    if json_summary.returncode == 0 and latest_results is not None:
        failing = _failing_json_check_names(latest_results)
        pending = _pending_json_check_names(latest_results)
        if failing:
            _print_state(
                "EXCEPTION_REQUIRED",
                "failing required checks",
                repo_root=root,
                reason_code="REQUIRED_CHECKS_FAILED",
                phase="wait_required_checks",
                dispatch_target="github",
                details=failing,
                next_actions=("fix or rerun failing required checks",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if pending:
            _print_state(
                "EXCEPTION_REQUIRED",
                "pending required checks",
                repo_root=root,
                reason_code="REQUIRED_CHECKS_PENDING",
                phase="wait_required_checks",
                retryable=True,
                dispatch_target="github",
                details=pending,
                next_actions=("wait for pending required checks",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        print("required checks passed")
        return 0
    summary = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "checks", pr_ref, "--required"],
    )
    failing = _failing_check_names(summary.stdout)
    if failing:
        _print_state(
            "EXCEPTION_REQUIRED",
            "failing required checks",
            repo_root=root,
            reason_code="REQUIRED_CHECKS_FAILED",
            phase="wait_required_checks",
            dispatch_target="github",
            details=failing,
            next_actions=("fix or rerun failing required checks",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    if summary.returncode != 0:
        details = [
            detail
            for detail in (
                _single_line_text(watched.stderr),
                _single_line_text(json_summary.stderr),
                _single_line_text(summary.stderr),
            )
            if detail
        ]
        _print_state(
            "EXCEPTION_REQUIRED",
            "required checks unavailable",
            repo_root=root,
            reason_code="REQUIRED_CHECKS_UNAVAILABLE",
            phase="wait_required_checks",
            retryable=any(
                _classify_github_error(result).retryable
                for result in (watched, json_summary, summary)
            ),
            dispatch_target="github",
            details=details,
            next_actions=("restore GitHub checks/API access",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    else:
        print(summary.stdout, end="")
    return watched.returncode


def resolve_review_threads(
    *,
    repo_root: str | Path = ".",
    thread_ids: Sequence[str] = (),
    runner: Runner | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    normalized_thread_ids = tuple(
        thread_id.strip() for thread_id in thread_ids if thread_id.strip()
    )
    if not normalized_thread_ids:
        _print_state(
            "EXCEPTION_REQUIRED",
            "no review thread IDs provided",
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    for thread_id in normalized_thread_ids:
        result = runner.run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                "query=mutation($threadId:ID!){resolveReviewThread(input:{threadId:$threadId}){thread{id isResolved}}}",
                "-F",
                f"threadId={thread_id}",
            ],
            cwd=root,
        )
        if result.returncode != 0:
            _print_command_failure("gh api graphql resolveReviewThread", result)
            return EXCEPTION_REQUIRED_EXIT_CODE
        payload = _json_object_from_result(result, "gh api graphql resolveReviewThread")
        thread = (
            payload.get("data", {})
            .get("resolveReviewThread", {})
            .get("thread", {})
        )
        if not isinstance(thread, dict) or not bool(thread.get("isResolved")):
            _print_state(
                "EXCEPTION_REQUIRED",
                "review thread was not resolved",
                details=[thread_id],
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        print(f"resolved review thread: {thread_id}")
    return SUCCESS_EXIT_CODE


def diagnose(
    *,
    repo_root: str | Path = ".",
    pr: str | None = None,
    runner: Runner | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    try:
        metadata = _diagnose_pr_metadata(root, runner, pr=pr)
        pr_number = str(metadata.get("number") or pr or "")
        pr_url = _single_line_text(metadata.get("url"))
        head_sha = _single_line_text(metadata.get("headRefOid"))
        base_ref = _single_line_text(metadata.get("baseRefName"))
        state = _single_line_text(metadata.get("state")) or "UNKNOWN"
        is_draft = bool(metadata.get("isDraft"))
        merge_state = _single_line_text(metadata.get("mergeStateStatus")) or "UNKNOWN"
        review_decision = _single_line_text(metadata.get("reviewDecision")) or "UNKNOWN"
        if not pr_number or not pr_url or not head_sha:
            raise GitHubDataUnavailable(
                "GitHub PR metadata incomplete",
                details=("gh pr view --json " + PR_DIAGNOSE_JSON_FIELDS,),
            )

        print(f"PR_DIAGNOSE: #{pr_number} {state} head={_short_sha(head_sha)}")
        print(f"isDraft: {str(is_draft).lower()}")
        print(f"mergeStateStatus: {merge_state}")
        print(f"reviewDecision: {review_decision}")
        print(f"pr body evidence: {_diagnose_pr_body_evidence_state(metadata)}")

        check_state, check_details, checks_unavailable = _diagnose_required_checks(
            root=root,
            runner=runner,
            pr_number=pr_number,
        )
        print(f"required checks: {check_state}")
        for detail in check_details:
            print(f"- {detail}")

        pr_info = _github_pr_info_from_url(pr_url)
        unresolved_threads: tuple[str, ...] = ()
        codex_blockers: tuple[str, ...] = ()
        codex_review_evidence: str | None = None
        trigger_time = ""
        completion_time = ""
        if pr_info is None:
            raise GitHubDataUnavailable(
                "GitHub PR URL unsupported",
                details=(pr_url,),
            )
        review_requirement = _remote_pr_review_requirement(
            root=root,
            runner=runner,
            repo=pr_info[0],
            base_ref=base_ref,
        )
        if head_sha:
            repo, parsed_number = pr_info
            issue_comments = _gh_api_list(
                root,
                runner,
                f"repos/{repo}/issues/{parsed_number}/comments?per_page=100",
            )
            trigger_time = _latest_codex_trigger_time(
                issue_comments,
                pr_url=pr_url,
                head_sha=head_sha,
            )
            completion_time = _latest_codex_completion_comment_time(
                issue_comments,
                trigger_time=trigger_time,
            )
            unresolved_threads = _unresolved_blocking_codex_thread_findings(
                _current_pr_review_threads(
                    root=root,
                    runner=runner,
                    repo=repo,
                    pr_number=parsed_number,
                )
            )
            codex_review_evidence = _current_head_codex_review_evidence(
                pr_url=pr_url,
                head_sha=head_sha,
                root=root,
                runner=runner,
            )
            codex_blockers = _current_head_codex_blocking_findings(
                pr_url=pr_url,
                head_sha=head_sha,
                root=root,
                runner=runner,
            )
        print(f"codex trigger: {'present' if trigger_time else 'missing'}")
        print(f"codex completion: {'present' if completion_time else 'missing'}")
        print(
            "codex review evidence: "
            + ("present" if codex_review_evidence else "missing")
        )
        print(f"codex blockers: {len(codex_blockers)}")
        for detail in codex_blockers:
            print(f"- {detail}")
        print(f"review threads: unresolved={len(unresolved_threads)}")
        for detail in unresolved_threads:
            print(f"- {detail}")
        print(
            "approval requirement: "
            + ("required" if review_requirement.approval_required else "not required")
            + f" ({review_requirement.source})"
        )

        if state.upper() != "OPEN":
            print("next: reopen the PR before merge")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "PR is not open",
                reason_code="PR_NOT_OPEN",
                dispatch_target="author",
                blocking_items=(state,),
                next_actions=("reopen the PR before merge",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if is_draft:
            print("next: mark the PR ready for review")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "PR is draft",
                reason_code="PR_DRAFT",
                dispatch_target="author",
                blocking_items=(f"PR #{pr_number} is draft",),
                next_actions=("mark the PR ready for review",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if unresolved_threads:
            print("next: resolve unresolved review threads")
            _print_diagnose_stop(
                root,
                "REPLY_OR_FIX_REQUIRED",
                "unresolved review threads",
                reason_code="REVIEW_THREADS_UNRESOLVED",
                dispatch_target="author",
                blocking_items=unresolved_threads,
                next_actions=("resolve unresolved review threads",),
            )
            return REPLY_OR_FIX_REQUIRED_EXIT_CODE
        if codex_blockers:
            print("next: reply to or fix Codex blockers")
            _print_diagnose_stop(
                root,
                "REPLY_OR_FIX_REQUIRED",
                "current-head Codex blockers",
                reason_code="CODEX_BLOCKERS_PRESENT",
                dispatch_target="author",
                blocking_items=codex_blockers,
                next_actions=("reply to or fix Codex blockers",),
            )
            return REPLY_OR_FIX_REQUIRED_EXIT_CODE
        if checks_unavailable:
            print("next: restore GitHub checks/API access")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "required checks unavailable",
                reason_code="REQUIRED_CHECKS_UNAVAILABLE",
                retryable=True,
                dispatch_target="github",
                blocking_items=check_details,
                next_actions=("restore GitHub checks/API access",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if check_state == "failing":
            print("next: fix or rerun failing required checks")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "failing required checks",
                reason_code="REQUIRED_CHECKS_FAILED",
                dispatch_target="github",
                blocking_items=check_details,
                next_actions=("fix or rerun failing required checks",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if check_state == "pending":
            print("next: wait for pending required checks")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "pending required checks",
                reason_code="REQUIRED_CHECKS_PENDING",
                retryable=True,
                dispatch_target="github",
                blocking_items=check_details,
                next_actions=("wait for pending required checks",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if not _review_decision_allows_merge(
            review_decision,
            review_requirement=review_requirement,
        ):
            print("next: wait for approved review required by remote rules")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "remote review approval required",
                reason_code="APPROVAL_REQUIRED",
                dispatch_target="reviewer",
                blocking_items=(review_decision,),
                next_actions=("wait for approved review required by remote rules",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        if _merge_state_requires_attention(merge_state):
            print("next: inspect branch protection or ruleset blockers")
            _print_diagnose_stop(
                root,
                "EXCEPTION_REQUIRED",
                "merge state requires attention",
                reason_code="MERGE_STATE_REQUIRES_ATTENTION",
                dispatch_target="github",
                blocking_items=(merge_state,),
                next_actions=("inspect branch protection or ruleset blockers",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        print("next: PR automation state is merge-ready")
        return SUCCESS_EXIT_CODE
    except GitHubDataUnavailable as exc:
        _print_state(
            "EXCEPTION_REQUIRED",
            str(exc),
            repo_root=root,
            reason_code="GITHUB_DATA_UNAVAILABLE",
            phase="diagnose",
            retryable=exc.retryable,
            dispatch_target="github",
            details=exc.details,
            next_actions=("restore GitHub API access",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE


def ready(
    *,
    repo_root: str | Path = ".",
    title: str | None = None,
    resolve_threads: Sequence[str] = (),
    runner: Runner | None = None,
    codex_review_timeout_seconds: float = CODEX_REVIEW_WAIT_TIMEOUT_SECONDS,
    codex_review_poll_seconds: float = CODEX_REVIEW_WAIT_INTERVAL_SECONDS,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    runner = runner or CommandRunner()
    root = Path(repo_root).resolve()
    completed_phases: list[str] = []
    _record_pr_ready_phase(root, completed_phases, "preflight")
    code = prepare(repo_root=root, runner=runner)
    if code != 0:
        latest = root / ".local" / "ai-review" / "latest.json"
        if not latest.is_file():
            _print_state(
                "DISPATCH_REQUIRED",
                "missing .local/ai-review/latest.json; local AI review must be produced by humans or agents",
                repo_root=root,
                reason_code="LOCAL_AI_REVIEW_MISSING",
                phase="local_review",
                dispatch_target="review-agent",
                details=[
                    "run the required local AI review",
                    "record two independent reviewers",
                    "record security_review with codex-security evidence",
                ],
                next_actions=("produce .local/ai-review/latest.json",),
            )
            return DISPATCH_REQUIRED_EXIT_CODE
        payload = _read_json_object(latest)
        _record_pr_ready_phase(root, completed_phases, "freeze_diff")
        current_fingerprint = ai_review_gate.current_diff_fingerprint(root)
        _record_pr_ready_phase(root, completed_phases, "local_review")
        _record_pr_ready_phase(root, completed_phases, "security_review")
        result = ai_review_gate.validate_report_file(
            latest,
            current_diff_fingerprint=current_fingerprint,
        )
        if payload is None or not result.ok:
            _print_state(
                "DISPATCH_REQUIRED",
                "local AI review evidence is incomplete or invalid",
                repo_root=root,
                reason_code="LOCAL_AI_REVIEW_INVALID",
                phase="local_review",
                dispatch_target="review-agent",
                details=result.errors,
                next_actions=("repair .local/ai-review/latest.json",),
            )
            return DISPATCH_REQUIRED_EXIT_CODE
        _print_state(
            "EXCEPTION_REQUIRED",
            "prepare failed",
            repo_root=root,
            reason_code="PREPARE_FAILED",
            phase="preflight",
            dispatch_target="operator",
            details=[f"exit_code={code}"],
            next_actions=("inspect local prepare failure",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    _record_pr_ready_phase(root, completed_phases, "freeze_diff")
    latest = root / ".local" / "ai-review" / "latest.json"
    payload = _read_json_object(latest)
    if payload is None:
        _print_state(
            "DISPATCH_REQUIRED",
            "missing .local/ai-review/latest.json; local AI review must be produced by humans or agents",
            repo_root=root,
            reason_code="LOCAL_AI_REVIEW_MISSING",
            phase="local_review",
            dispatch_target="review-agent",
            details=[
                "run the required local AI review",
                "record two independent reviewers",
                "record security_review with codex-security evidence",
            ],
            next_actions=("produce .local/ai-review/latest.json",),
        )
        return DISPATCH_REQUIRED_EXIT_CODE
    current_fingerprint = ai_review_gate.current_diff_fingerprint(root)
    _record_pr_ready_phase(root, completed_phases, "local_review")
    _record_pr_ready_phase(root, completed_phases, "security_review")
    result = ai_review_gate.validate_report_file(
        latest,
        current_diff_fingerprint=current_fingerprint,
    )
    if not result.ok:
        _print_state(
            "DISPATCH_REQUIRED",
            "local AI review evidence is incomplete or invalid",
            repo_root=root,
            reason_code="LOCAL_AI_REVIEW_INVALID",
            phase="local_review",
            dispatch_target="review-agent",
            details=result.errors,
            next_actions=("repair .local/ai-review/latest.json",),
        )
        return DISPATCH_REQUIRED_EXIT_CODE
    _record_pr_ready_phase(root, completed_phases, "build_evidence")
    code = sync(repo_root=root, title=title, runner=runner)
    if code != 0:
        if code == EXCEPTION_REQUIRED_EXIT_CODE:
            return code
        _print_state(
            "EXCEPTION_REQUIRED",
            "sync failed",
            repo_root=root,
            reason_code="SYNC_FAILED",
            phase="sync_pr_body",
            dispatch_target="operator",
            details=[f"exit_code={code}"],
            next_actions=("inspect PR sync failure",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE

    try:
        metadata = _current_pr_metadata(root, runner, required=True)
        pr_url = str(metadata.get("url") or "")
        head_sha = _command_stdout(runner.run(["git", "rev-parse", "HEAD"], cwd=root))
        pr_info = _github_pr_info_from_url(pr_url)
        _record_pr_ready_phase(root, completed_phases, "official_codex")
        if (
            payload is not None
            and result.requires_official_codex_review
            and not _official_codex_review_evidence_valid_for_current_pr(
                payload,
                pr_url=pr_url,
                head_sha=head_sha,
                root=root,
                runner=runner,
            )
        ):
            print(
                "official Codex review requested; waiting for current-head Codex review evidence",
                file=sys.stderr,
            )
            wait_result = _wait_for_current_head_codex_review_evidence(
                pr_url=pr_url,
                head_sha=head_sha,
                root=root,
                runner=runner,
                timeout_seconds=codex_review_timeout_seconds,
                poll_seconds=codex_review_poll_seconds,
                sleeper=sleeper,
            )
            if wait_result.state == "head_changed":
                _print_state(
                    "EXCEPTION_REQUIRED",
                    "head changed during Codex review wait",
                    repo_root=root,
                    reason_code="HEAD_CHANGED_DURING_CODEX_REVIEW_WAIT",
                    phase="official_codex",
                    retryable=True,
                    dispatch_target="author",
                    details=wait_result.details,
                    next_actions=("refresh local branch and rerun pr-ready",),
                )
                return EXCEPTION_REQUIRED_EXIT_CODE
            if wait_result.state == "blocked":
                _print_state(
                    "REPLY_OR_FIX_REQUIRED",
                    "Codex review reported blocking current-head findings",
                    repo_root=root,
                    reason_code="CODEX_REVIEW_REPORTED_BLOCKING_CURRENT_HEAD_FINDINGS",
                    phase="official_codex",
                    dispatch_target="author",
                    details=wait_result.details,
                    next_actions=("fix or reply to official Codex P0/P1 findings",),
                )
                return REPLY_OR_FIX_REQUIRED_EXIT_CODE
            if not wait_result.evidence:
                _print_state(
                    "EXCEPTION_REQUIRED",
                    "official Codex review still pending",
                    repo_root=root,
                    reason_code="OFFICIAL_CODEX_REVIEW_PENDING",
                    phase="official_codex",
                    retryable=True,
                    dispatch_target="github",
                    details=[f"rerun: make pr-ready TITLE=\"{title or '<same title>'}\""],
                    next_actions=("wait for official Codex review completion",),
                )
                return CODEX_REVIEW_PENDING_EXIT_CODE
            payload = _payload_with_official_codex_review_evidence(
                payload,
                root=root,
                evidence=wait_result.evidence,
            )
            _write_ai_review_payload(root, payload)
        _record_pr_ready_phase(root, completed_phases, "threads")
        if resolve_threads:
            code = resolve_review_threads(
                repo_root=root,
                thread_ids=resolve_threads,
                runner=runner,
            )
            if code != SUCCESS_EXIT_CODE:
                return code
        if pr_info is not None:
            repo, pr_number = pr_info
            threads = _current_pr_review_threads(
                root=root,
                runner=runner,
                repo=repo,
                pr_number=pr_number,
            )
            code, payload, changed = _auto_process_official_codex_review_threads(
                root=root,
                runner=runner,
                repo=repo,
                pr_number=pr_number,
                threads=threads,
                payload=payload,
            )
            if code != SUCCESS_EXIT_CODE:
                return code
            if changed:
                _write_ai_review_payload(root, payload)
        blocking = _current_head_codex_blocking_findings(
            pr_url=pr_url,
            head_sha=head_sha,
            root=root,
            runner=runner,
        )
        if blocking:
            _print_state(
                "REPLY_OR_FIX_REQUIRED",
                "Codex review reported blocking current-head findings",
                repo_root=root,
                reason_code="CODEX_REVIEW_REPORTED_BLOCKING_CURRENT_HEAD_FINDINGS",
                phase="threads",
                dispatch_target="author",
                details=blocking,
                next_actions=("fix or reply to blocking review findings",),
            )
            return REPLY_OR_FIX_REQUIRED_EXIT_CODE
        _record_pr_ready_phase(root, completed_phases, "sync_pr_body")
        code = sync(repo_root=root, title=title, runner=runner)
        if code != 0:
            if code == EXCEPTION_REQUIRED_EXIT_CODE:
                return code
            _print_state(
                "EXCEPTION_REQUIRED",
                "sync failed",
                repo_root=root,
                reason_code="SYNC_FAILED",
                phase="sync_pr_body",
                dispatch_target="operator",
                details=[f"exit_code={code}"],
                next_actions=("inspect PR sync failure",),
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
    except GitHubDataUnavailable as exc:
        _print_state(
            "EXCEPTION_REQUIRED",
            str(exc),
            repo_root=root,
            reason_code="GITHUB_DATA_UNAVAILABLE",
            phase="github",
            retryable=exc.retryable,
            dispatch_target="github",
            details=exc.details,
            next_actions=("restore GitHub API access",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    _record_pr_ready_phase(root, completed_phases, "wait_latest_checks")
    code = wait(repo_root=root, runner=runner)
    if code == SUCCESS_EXIT_CODE:
        _record_pr_ready_merge_ready(root, completed_phases)
    return code


def ready_for_review(
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
    mark_ready = runner.run(["gh", "pr", "ready", pr_ref], cwd=root)
    if mark_ready.returncode != 0:
        _print_command_failure("gh pr ready", mark_ready)
        return EXCEPTION_REQUIRED_EXIT_CODE
    return wait(repo_root=root, pr=pr_ref, runner=runner)


def merge_pr(
    *,
    repo_root: str | Path = ".",
    pr: str | None = None,
    runner: Runner | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    code = diagnose(repo_root=root, pr=pr, runner=runner)
    if code != SUCCESS_EXIT_CODE:
        return code
    try:
        metadata = _diagnose_pr_metadata(root, runner, pr=pr)
    except GitHubDataUnavailable as exc:
        _print_github_data_unavailable(exc)
        return EXCEPTION_REQUIRED_EXIT_CODE
    pr_ref = str(metadata.get("number") or pr or "")
    head_sha = _single_line_text(metadata.get("headRefOid"))
    pr_url = _single_line_text(metadata.get("url"))
    base_ref = _single_line_text(metadata.get("baseRefName"))
    review_decision = _single_line_text(metadata.get("reviewDecision"))
    if not pr_ref or not head_sha or not pr_url:
        _print_state(
            "EXCEPTION_REQUIRED",
            "PR head metadata unavailable for merge",
            details=("gh pr view --json " + PR_DIAGNOSE_JSON_FIELDS,),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    pr_info = _github_pr_info_from_url(pr_url)
    if pr_info is None:
        _print_state(
            "EXCEPTION_REQUIRED",
            "GitHub PR URL unsupported",
            details=[pr_url],
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    try:
        review_requirement = _remote_pr_review_requirement(
            root=root,
            runner=runner,
            repo=pr_info[0],
            base_ref=base_ref,
        )
    except GitHubDataUnavailable as exc:
        _print_github_data_unavailable(exc)
        return EXCEPTION_REQUIRED_EXIT_CODE
    local_head = runner.run(["git", "rev-parse", "HEAD"], cwd=root)
    if local_head.returncode != 0:
        _print_command_failure("git rev-parse HEAD", local_head)
        return EXCEPTION_REQUIRED_EXIT_CODE
    local_head_sha = _command_stdout(local_head)
    if local_head_sha != head_sha:
        _print_state(
            "EXCEPTION_REQUIRED",
            "local HEAD does not match PR head",
            details=[f"local={local_head_sha}", f"pr={head_sha}"],
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    if not _review_decision_allows_merge(
        review_decision,
        review_requirement=review_requirement,
    ):
        _print_state(
            "EXCEPTION_REQUIRED",
            "approved review is required before merge",
            details=[
                f"reviewDecision={review_decision or 'UNKNOWN'}",
                f"source={review_requirement.source}",
            ],
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    merged = runner.run(
        ["gh", "pr", "merge", pr_ref, "--merge", "--match-head-commit", head_sha],
        cwd=root,
    )
    if merged.returncode != 0:
        _print_command_failure("gh pr merge", merged)
        return EXCEPTION_REQUIRED_EXIT_CODE
    print(f"merge: PR #{pr_ref} merged with head lock {_short_sha(head_sha)}")
    merge_output = _single_line_text(merged.stdout)
    if merge_output:
        print(f"merge: {merge_output}")
    return SUCCESS_EXIT_CODE


def cleanup_pr(
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
    view = runner.run(
        [
            "gh",
            "pr",
            "view",
            pr_ref,
            "--json",
            "number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
        ],
        cwd=root,
    )
    if view.returncode != 0:
        _print_command_failure("gh pr view --json merge cleanup fields", view)
        return EXCEPTION_REQUIRED_EXIT_CODE
    metadata = _json_object_from_result(
        view,
        "gh pr view --json number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
    )
    state = _single_line_text(metadata.get("state")).upper()
    merged_at = _single_line_text(metadata.get("mergedAt"))
    head_branch = _single_line_text(metadata.get("headRefName"))
    base_branch = _single_line_text(metadata.get("baseRefName")) or "main"
    is_cross_repository = bool(metadata.get("isCrossRepository"))
    if state != "MERGED" or not merged_at:
        _print_state("EXCEPTION_REQUIRED", "PR is not merged")
        return EXCEPTION_REQUIRED_EXIT_CODE
    if not head_branch:
        _print_state("EXCEPTION_REQUIRED", "merged PR head branch unavailable")
        return EXCEPTION_REQUIRED_EXIT_CODE
    print(f"cleanup: PR #{pr_ref} merged at {merged_at}")

    for label, command in (
        ("git fetch --prune origin", ["git", "fetch", "--prune", "origin"]),
        ("git switch base branch", ["git", "switch", base_branch]),
    ):
        result = runner.run(command, cwd=root)
        if result.returncode != 0:
            _print_command_failure(label, result)
            return EXCEPTION_REQUIRED_EXIT_CODE

    with _temporary_env(
        {
            "ALLOW_MAIN_REF_UPDATE": "1",
            "MAIN_REF_UPDATE_REASON": f"sync local {base_branch} after PR #{pr_ref} merge",
        }
    ):
        synced = runner.run(
            ["git", "merge", "--ff-only", f"origin/{base_branch}"],
            cwd=root,
        )
    if synced.returncode != 0:
        _print_command_failure("git merge --ff-only origin base", synced)
        return EXCEPTION_REQUIRED_EXIT_CODE
    print(f"cleanup: base {base_branch} synced with origin/{base_branch}")

    if is_cross_repository:
        print(f"skip head branch delete for fork PR: {head_branch}")
    else:
        local_delete = runner.run(["git", "branch", "-d", head_branch], cwd=root)
        if local_delete.returncode != 0:
            _print_command_failure("git branch -d", local_delete)
            return EXCEPTION_REQUIRED_EXIT_CODE
        print(f"cleanup: local branch deleted: {head_branch}")

        remote_delete = runner.run(
            ["git", "push", "origin", "--delete", head_branch],
            cwd=root,
        )
        if remote_delete.returncode != 0:
            _print_command_failure("git push origin --delete", remote_delete)
            return EXCEPTION_REQUIRED_EXIT_CODE
        print(f"cleanup: remote branch deleted: {head_branch}")

        remote_ref = runner.run(
            ["git", "ls-remote", "--heads", "origin", head_branch],
            cwd=root,
        )
        if remote_ref.returncode != 0:
            _print_command_failure("git ls-remote --heads", remote_ref)
            return EXCEPTION_REQUIRED_EXIT_CODE
        if _command_stdout(remote_ref):
            _print_state(
                "EXCEPTION_REQUIRED",
                "remote branch still exists after cleanup",
                details=[head_branch],
            )
            return EXCEPTION_REQUIRED_EXIT_CODE

    synced_state = runner.run(
        ["git", "rev-list", "--left-right", "--count", f"{base_branch}...origin/{base_branch}"],
        cwd=root,
    )
    if synced_state.returncode != 0:
        _print_command_failure("git rev-list main...origin/main", synced_state)
        return EXCEPTION_REQUIRED_EXIT_CODE
    if _command_stdout(synced_state) != "0\t0":
        _print_state(
            "EXCEPTION_REQUIRED",
            "local base branch is not synced to origin",
            details=[_command_stdout(synced_state)],
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    print(
        f"cleanup: final base sync verified: "
        f"{base_branch}...origin/{base_branch} = 0 0"
    )
    return SUCCESS_EXIT_CODE


def complete_pr(
    *,
    repo_root: str | Path = ".",
    title: str | None = None,
    pr: str | None = None,
    resolve_threads: Sequence[str] = (),
    runner: Runner | None = None,
    codex_review_timeout_seconds: float = CODEX_REVIEW_WAIT_TIMEOUT_SECONDS,
    codex_review_poll_seconds: float = CODEX_REVIEW_WAIT_INTERVAL_SECONDS,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    if pr:
        current_pr = _current_pr_number(root, runner)
        if current_pr != str(pr):
            _print_state(
                "EXCEPTION_REQUIRED",
                "explicit PR does not match current branch PR",
                details=[f"current={current_pr or 'none'}", f"requested={pr}"],
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
    code = ready(
        repo_root=root,
        title=title,
        resolve_threads=resolve_threads,
        runner=runner,
        codex_review_timeout_seconds=codex_review_timeout_seconds,
        codex_review_poll_seconds=codex_review_poll_seconds,
    )
    if code != SUCCESS_EXIT_CODE:
        return code
    pr_ref = str(pr or _current_pr_number(root, runner) or "")
    if not pr_ref:
        _print_state(
            "EXCEPTION_REQUIRED",
            "PR not found after ready step",
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    for step in (ready_for_review, merge_pr, cleanup_pr):
        code = step(repo_root=root, pr=pr_ref, runner=runner)
        if code != SUCCESS_EXIT_CODE:
            return code
    print(f"pr-complete: PR #{pr_ref} complete")
    return SUCCESS_EXIT_CODE


def _run_local_check(
    check: str,
    *,
    root: Path,
    runner: Runner,
    changed_files: Sequence[str],
) -> CommandResult:
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
            [sys.executable, "-m", "scripts.research.governance", "verify", "full"],
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
    root: Path,
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
            merged_checks["verify full"] = (
                f"{_verify_full_evidence_command(root)}; passed"
            )
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
    return ai_review_gate.payload_as_schema_v3(
        updated,
        repo_root=root,
        changed_files=changed_files or updated.get("changed_files"),
    )


def _verify_full_evidence_command(root: Path) -> str:
    executable = Path(sys.executable).resolve()
    candidates = (
        (
            (root / ".venv" / "Scripts" / "python.exe").resolve(),
            WINDOWS_PR_BODY_VERIFY_FULL_COMMAND,
        ),
        (
            (root / ".venv" / "bin" / "python").resolve(),
            POSIX_PR_BODY_VERIFY_FULL_COMMAND,
        ),
    )
    for candidate, command in candidates:
        if executable == candidate:
            return command
    return f"{sys.executable} -m scripts.research.governance verify full"


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
        return pattern.sub(lambda _match: block, existing_body)
    if existing_body.strip():
        return f"{existing_body.rstrip()}\n\n{block}\n"
    return f"{block}\n"


def _current_pr_metadata(
    root: Path,
    runner: Runner,
    *,
    required: bool = False,
) -> dict[str, Any]:
    view = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "view", "--json", "number,url,state,isDraft"],
    )
    if view.returncode != 0:
        if required:
            raise _github_data_unavailable(
                "GitHub PR metadata unavailable",
                "gh pr view --json number,url,state,isDraft",
                view,
            )
        return {}
    if required:
        return _json_object_from_result(
            view,
            "gh pr view --json number,url,state,isDraft",
        )
    return _json_from_result(view)


def _current_pr_number(root: Path, runner: Runner) -> str:
    return str(_current_pr_metadata(root, runner).get("number") or "")


def _diagnose_pr_metadata(
    root: Path,
    runner: Runner,
    *,
    pr: str | None,
) -> dict[str, Any]:
    command = ["gh", "pr", "view"]
    if pr:
        command.append(pr)
    command.extend(["--json", PR_DIAGNOSE_JSON_FIELDS])
    result = _run_github_read_command(root, runner, command)
    if result.returncode != 0:
        raise _github_data_unavailable(
            "GitHub PR metadata unavailable",
            " ".join(command),
            result,
        )
    return _json_object_from_result(result, " ".join(command))


def _diagnose_pr_body_evidence_state(metadata: dict[str, Any]) -> str:
    body = str(metadata.get("body") or "")
    if MANAGED_BLOCK_START not in body or MANAGED_BLOCK_END not in body:
        return "missing"
    if "## AI Review 风险分级" not in body:
        return "incomplete"
    return "present"


def _current_pr_labels(root: Path, runner: Runner) -> tuple[str, ...]:
    view = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "view", "--json", "labels"],
    )
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


def _json_object_from_result(result: CommandResult, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise GitHubDataUnavailable(
            "GitHub command returned invalid JSON",
            details=(label, str(exc)),
        ) from exc
    if not isinstance(payload, dict):
        raise GitHubDataUnavailable(
            "GitHub command returned unexpected payload",
            details=(label,),
        )
    return payload


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


def _official_codex_review_evidence_valid_for_current_pr(
    payload: dict[str, Any],
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
) -> bool:
    value = payload.get("official_codex_review")
    if not isinstance(value, dict):
        return False
    if not _official_codex_review_fields_are_passing(value):
        return False
    links = _official_codex_review_links(value, pr_url=pr_url)
    if not links:
        return False
    for kind, repo, pr_number, item_id in links:
        if kind == "review" and _codex_review_link_matches_current_head(
            repo=repo,
            pr_number=pr_number,
            review_id=item_id,
            head_sha=head_sha,
            pr_url=pr_url,
            root=root,
            runner=runner,
        ):
            return True
        if kind == "comment" and _codex_completion_comment_matches_current_head(
            repo=repo,
            pr_number=pr_number,
            comment_id=item_id,
            head_sha=head_sha,
            pr_url=pr_url,
            root=root,
            runner=runner,
        ):
            return True
    return False


def _wait_for_current_head_codex_review_evidence(
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
    timeout_seconds: float,
    poll_seconds: float,
    sleeper: Callable[[float], None],
) -> CodexReviewWaitResult:
    timeout_seconds = max(0.0, timeout_seconds)
    poll_seconds = max(0.0, poll_seconds)
    deadline = time.monotonic() + timeout_seconds
    while True:
        current_head = _current_pr_head_sha(root, runner)
        if current_head and current_head != head_sha:
            return CodexReviewWaitResult(
                evidence=None,
                state="head_changed",
                details=(f"expected={head_sha}", f"actual={current_head}"),
            )
        blocking = _current_head_codex_blocking_findings(
            pr_url=pr_url,
            head_sha=head_sha,
            root=root,
            runner=runner,
            include_threads=False,
        )
        if blocking:
            return CodexReviewWaitResult(
                evidence=None,
                state="blocked",
                details=blocking,
            )
        evidence = _current_head_codex_review_evidence(
            pr_url=pr_url,
            head_sha=head_sha,
            root=root,
            runner=runner,
        )
        if evidence:
            return CodexReviewWaitResult(evidence=evidence, state="completed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return CodexReviewWaitResult(evidence=None, state="pending")
        sleep_seconds = remaining if poll_seconds <= 0 else min(poll_seconds, remaining)
        print(
            f"waiting for Codex review on current head; retrying in {sleep_seconds:.0f}s",
            file=sys.stderr,
        )
        sleeper(sleep_seconds)


def _current_pr_head_sha(root: Path, runner: Runner) -> str:
    view = _run_github_read_command(
        root,
        runner,
        ["gh", "pr", "view", "--json", "headRefOid"],
    )
    if view.returncode != 0:
        raise _github_data_unavailable(
            "GitHub PR head unavailable",
            "gh pr view --json headRefOid",
            view,
        )
    return _single_line_text(
        _json_object_from_result(view, "gh pr view --json headRefOid").get("headRefOid")
    )


def _current_head_codex_review_evidence(
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
) -> str | None:
    pr_info = _github_pr_info_from_url(pr_url)
    if pr_info is None:
        return None
    repo, pr_number = pr_info
    issue_comments = _gh_api_list(
        root,
        runner,
        f"repos/{repo}/issues/{pr_number}/comments?per_page=100",
    )
    trigger_time = _latest_codex_trigger_time(
        issue_comments,
        pr_url=pr_url,
        head_sha=head_sha,
    )
    if not trigger_time:
        return None
    reviews = _gh_api_list(
        root,
        runner,
        f"repos/{repo}/pulls/{pr_number}/reviews?per_page=100",
    )
    for review in reversed(reviews):
        review_id = str(review.get("id", ""))
        if review_id and _codex_review_is_passing_current_head(
            review,
            head_sha=head_sha,
            trigger_time=trigger_time,
        ):
            return (
                f"https://github.com/{repo}/pull/{pr_number}"
                f"#pullrequestreview-{review_id}"
            )

    for comment in reversed(issue_comments):
        comment_id = str(comment.get("id", ""))
        if (
            comment_id
            and _is_codex_completion_comment(comment)
            and _codex_completion_comment_matches_current_head(
                repo=repo,
                pr_number=pr_number,
                comment_id=comment_id,
                head_sha=head_sha,
                pr_url=pr_url,
                root=root,
                runner=runner,
            )
        ):
            return _issue_comment_link(
                repo=repo,
                pr_number=pr_number,
                comment=comment,
            )
    return None


def _current_head_codex_trigger_exists(
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
) -> bool:
    pr_info = _github_pr_info_from_url(pr_url)
    if pr_info is None:
        return False
    repo, pr_number = pr_info
    issue_comments = _gh_api_list(
        root,
        runner,
        f"repos/{repo}/issues/{pr_number}/comments?per_page=100",
    )
    return bool(
        _latest_codex_trigger_time(
            issue_comments,
            pr_url=pr_url,
            head_sha=head_sha,
        )
    )


def _auto_process_official_codex_review_threads(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    pr_number: str,
    threads: Sequence[dict[str, Any]],
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any], bool]:
    updated = payload
    changed = False
    for thread in threads:
        action = _auto_review_thread_action(thread, updated)
        if action not in {"accept", "close"}:
            continue
        thread_id = _thread_id(thread)
        if not thread_id:
            continue
        finding = (
            _external_finding_for_review_thread(
                repo=repo,
                pr_number=pr_number,
                thread=thread,
                status="accepted",
            )
            if action == "accept"
            else _closed_external_finding_for_thread(updated, thread)
        )
        if finding is None:
            continue
        reply_body = (
            _accepted_review_thread_reply(finding)
            if action == "accept"
            else _closed_review_thread_reply(finding)
        )
        code = _reply_to_review_thread(
            root=root,
            runner=runner,
            thread_id=thread_id,
            body=reply_body,
        )
        if code != SUCCESS_EXIT_CODE:
            return code, updated, changed
        code = resolve_review_threads(
            repo_root=root,
            runner=runner,
            thread_ids=(thread_id,),
        )
        if code != SUCCESS_EXIT_CODE:
            return code, updated, changed
        thread["isResolved"] = True
        updated = _payload_with_external_finding(
            updated,
            repo_root=root,
            finding=finding,
        )
        changed = True
        verb = "accepted" if action == "accept" else "closed"
        print(f"{verb} official Codex review thread: {thread_id}")
    return SUCCESS_EXIT_CODE, updated, changed


def _auto_review_thread_action(
    thread: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    if _thread_is_resolved(thread):
        return ""
    severity = _codex_thread_severity(thread)
    if severity in AUTO_ACCEPTED_REVIEW_THREAD_SEVERITIES:
        return "accept"
    if (
        severity in {"P0", "P1"}
        and _thread_is_outdated(thread)
        and _closed_external_finding_for_thread(payload, thread) is not None
    ):
        return "close"
    return ""


def _reply_to_review_thread(
    *,
    root: Path,
    runner: Runner,
    thread_id: str,
    body: str,
) -> int:
    result = runner.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            "query=mutation($threadId:ID!,$body:String!){addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId,body:$body}){comment{id}}}",
            "-F",
            f"threadId={thread_id}",
            "-f",
            f"body={body}",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        _print_command_failure("gh api graphql addPullRequestReviewThreadReply", result)
        return EXCEPTION_REQUIRED_EXIT_CODE
    payload = _json_object_from_result(
        result,
        "gh api graphql addPullRequestReviewThreadReply",
    )
    comment = (
        payload.get("data", {})
        .get("addPullRequestReviewThreadReply", {})
        .get("comment", {})
    )
    if not isinstance(comment, dict) or not _single_line_text(comment.get("id")):
        _print_state(
            "EXCEPTION_REQUIRED",
            "review thread reply was not created",
            details=[thread_id],
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    return SUCCESS_EXIT_CODE


def _payload_with_external_finding(
    payload: dict[str, Any],
    *,
    repo_root: Path,
    finding: dict[str, Any],
) -> dict[str, Any]:
    changed_files = ai_review_gate._string_list(payload.get("changed_files"))
    updated = ai_review_gate.payload_as_schema_v3(
        payload,
        repo_root=repo_root,
        changed_files=changed_files,
    )
    external_findings = [
        item
        for item in updated.get("external_findings") or []
        if isinstance(item, dict)
    ]
    thread_id = _single_line_text(finding.get("thread_id"))
    source = _single_line_text(finding.get("source"))
    retained = [
        item
        for item in external_findings
        if not (
            _single_line_text(item.get("thread_id")) == thread_id
            and _single_line_text(item.get("source")) == source
        )
    ]
    retained.append(finding)
    updated["external_findings"] = retained
    return updated


def _write_ai_review_payload(root: Path, payload: dict[str, Any]) -> None:
    local = root / ".local" / "ai-review"
    local.mkdir(parents=True, exist_ok=True)
    (local / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (local / "latest.md").write_text(
        ai_review_gate.render_markdown_report(payload),
        encoding="utf-8",
    )
    (local / "pr-body.md").write_text(
        ai_review_gate.render_pr_body(payload),
        encoding="utf-8",
    )


def _external_finding_for_review_thread(
    *,
    repo: str,
    pr_number: str,
    thread: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    thread_id = _thread_id(thread)
    severity = _codex_thread_severity(thread)
    body = _codex_thread_body(thread)
    return {
        "id": f"EXT-CODEX-THREAD-{thread_id}",
        "source": "official_codex_review_thread",
        "thread_id": thread_id,
        "severity": severity,
        "title": _single_line_text(body)[:120] or "Official Codex review thread",
        "path": f"https://github.com/{repo}/pull/{pr_number}",
        "status": status,
        "evidence": f"https://github.com/{repo}/pull/{pr_number}#discussion_r{thread_id}",
        "defer_reason": (
            f"official Codex {severity} finding is not a P0/P1 merge blocker"
        ),
        "risk_acceptance": (
            "accepted as retained official Codex review advice for this PR"
        ),
        "handling": "fixed acceptance reply posted and review thread resolved",
        "body": _single_line_text(body),
    }


def _closed_external_finding_for_thread(
    payload: dict[str, Any],
    thread: dict[str, Any],
) -> dict[str, Any] | None:
    thread_id = _thread_id(thread)
    if not thread_id:
        return None
    for item in payload.get("external_findings") or []:
        if not isinstance(item, dict):
            continue
        if _single_line_text(item.get("thread_id")) != thread_id:
            continue
        if _single_line_text(item.get("severity")) not in {"P0", "P1"}:
            continue
        if _single_line_text(item.get("status")) not in CLOSED_REVIEW_THREAD_STATUSES:
            continue
        if not _single_line_text(item.get("evidence")):
            continue
        closed = dict(item)
        closed.setdefault(
            "handling",
            "structured fixed or false_positive evidence recorded; review thread resolved",
        )
        return closed
    return None


def _accepted_review_thread_reply(finding: dict[str, Any]) -> str:
    return (
        "已按 PR review 规则接受该官方 Codex 建议。\n\n"
        f"- finding: `{_single_line_text(finding.get('id'))}`\n"
        f"- severity: `{_single_line_text(finding.get('severity'))}`\n"
        "- status: `accepted`\n"
        f"- defer_reason: {_single_line_text(finding.get('defer_reason'))}\n"
        f"- risk_acceptance: {_single_line_text(finding.get('risk_acceptance'))}\n"
        f"- handling: {_single_line_text(finding.get('handling'))}\n"
    )


def _closed_review_thread_reply(finding: dict[str, Any]) -> str:
    return (
        "已按 PR review 规则关闭过期官方 Codex 阻断项。\n\n"
        f"- finding: `{_single_line_text(finding.get('id'))}`\n"
        f"- severity: `{_single_line_text(finding.get('severity'))}`\n"
        f"- status: `{_single_line_text(finding.get('status'))}`\n"
        f"- evidence: {_single_line_text(finding.get('evidence'))}\n"
        f"- handling: {_single_line_text(finding.get('handling'))}\n"
    )


def _current_head_codex_blocking_findings(
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
    include_threads: bool = True,
) -> tuple[str, ...]:
    pr_info = _github_pr_info_from_url(pr_url)
    if pr_info is None:
        return ()
    repo, pr_number = pr_info
    issue_comments = _gh_api_list(
        root,
        runner,
        f"repos/{repo}/issues/{pr_number}/comments?per_page=100",
    )
    trigger_time = _latest_codex_trigger_time(
        issue_comments,
        pr_url=pr_url,
        head_sha=head_sha,
    )
    completion_cutoff = _latest_codex_completion_comment_time(
        issue_comments,
        trigger_time=trigger_time,
    )
    reviews = _gh_api_list(
        root,
        runner,
        f"repos/{repo}/pulls/{pr_number}/reviews?per_page=100",
    )
    findings: list[str] = []
    for item in [*issue_comments, *reviews]:
        if not _is_current_head_codex_item(
            item,
            head_sha=head_sha,
            trigger_time=trigger_time,
        ):
            continue
        body = str(item.get("body") or "")
        if pr_review_evidence.CODEX_CONTEXT_INVALID_PATTERN.search(body):
            if completion_cutoff and _codex_item_time(item) < completion_cutoff:
                continue
            findings.append(
                f"{_item_link(repo, pr_number, item)} context invalid {_single_line_text(body)}"
            )
            continue
        if BLOCKING_CODEX_FINDING_PATTERN.search(body):
            findings.append(f"{_item_link(repo, pr_number, item)} {_single_line_text(body)}")
    if include_threads:
        findings.extend(
            _unresolved_blocking_codex_thread_findings(
                _current_pr_review_threads(
                    root=root,
                    runner=runner,
                    repo=repo,
                    pr_number=pr_number,
                )
            )
        )
    return tuple(findings)


def _current_pr_review_threads(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    pr_number: str,
) -> list[dict[str, Any]]:
    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            nodes {
              id
              isResolved
              isOutdated
              comments(first: 50) {
                nodes {
                  body
                  author {
                    login
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }
    }
    """
    threads: list[dict[str, Any]] = []
    cursor = ""
    while True:
        command = [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={pr_number}",
        ]
        if cursor:
            command.extend(["-F", f"cursor={cursor}"])
        result = _run_github_read_command(root, runner, command)
        if result.returncode != 0:
            raise _github_data_unavailable(
                "GitHub review threads unavailable",
                "gh api graphql reviewThreads",
                result,
            )
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise GitHubDataUnavailable(
                "GitHub review threads returned invalid JSON",
                details=("gh api graphql reviewThreads", str(exc)),
            ) from exc
        if payload.get("errors"):
            raise GitHubDataUnavailable(
                "GitHub review threads returned GraphQL errors",
                details=(
                    "gh api graphql reviewThreads",
                    _single_line_text(payload.get("errors")),
                ),
            )
        connection = _graphql_review_threads_connection(payload)
        if not connection:
            raise GitHubDataUnavailable(
                "GitHub review threads response missing reviewThreads",
                details=("gh api graphql reviewThreads",),
            )
        nodes = connection.get("nodes")
        if isinstance(nodes, list):
            threads.extend(node for node in nodes if isinstance(node, dict))
        else:
            raise GitHubDataUnavailable(
                "GitHub review threads response missing nodes",
                details=("gh api graphql reviewThreads",),
            )
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or not bool(page_info.get("hasNextPage")):
            return threads
        cursor = _single_line_text(page_info.get("endCursor"))
        if not cursor:
            raise GitHubDataUnavailable(
                "GitHub review threads pagination cursor missing",
                details=("gh api graphql reviewThreads",),
            )


def _graphql_review_thread_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    connection = _graphql_review_threads_connection(payload)
    nodes = connection.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [node for node in nodes if isinstance(node, dict)]


def _graphql_review_threads_connection(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    repository = data.get("repository") if isinstance(data, dict) else None
    pull_request = repository.get("pullRequest") if isinstance(repository, dict) else None
    review_threads = (
        pull_request.get("reviewThreads") if isinstance(pull_request, dict) else None
    )
    return review_threads if isinstance(review_threads, dict) else {}


def _unresolved_blocking_codex_thread_findings(
    threads: Sequence[dict[str, Any]],
) -> tuple[str, ...]:
    findings: list[str] = []
    for thread in threads:
        if _thread_is_resolved(thread):
            continue
        comments = _thread_comments(thread)
        if not comments:
            findings.append("unresolved review thread")
            continue
        codex_comment = next(
            (comment for comment in comments if _comment_author_login(comment) in CODEX_REVIEW_AUTHORS),
            None,
        )
        comment = codex_comment or comments[0]
        body = str(comment.get("body") or "")
        if (
            codex_comment is not None
            and pr_review_evidence.CODEX_CONTEXT_INVALID_PATTERN.search(body)
        ):
            findings.append(
                f"unresolved review thread context invalid {_single_line_text(body)}"
            )
        else:
            findings.append(f"unresolved review thread {_single_line_text(body)}")
    return tuple(findings)


def _thread_is_resolved(thread: dict[str, Any]) -> bool:
    return bool(thread.get("isResolved") or thread.get("is_resolved"))


def _thread_is_outdated(thread: dict[str, Any]) -> bool:
    return bool(thread.get("isOutdated") or thread.get("is_outdated"))


def _thread_id(thread: dict[str, Any]) -> str:
    return _single_line_text(thread.get("id") or thread.get("thread_id"))


def _codex_thread_body(thread: dict[str, Any]) -> str:
    comment = _codex_thread_comment(thread)
    return str(comment.get("body") or "") if comment is not None else ""


def _codex_thread_severity(thread: dict[str, Any]) -> str:
    comment = _codex_thread_comment(thread)
    if comment is None:
        return ""
    match = CODEX_THREAD_SEVERITY_PATTERN.search(str(comment.get("body") or ""))
    if not match:
        return ""
    return f"P{match.group('level')}"


def _codex_thread_comment(thread: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            comment
            for comment in _thread_comments(thread)
            if _comment_author_login(comment) in CODEX_REVIEW_AUTHORS
        ),
        None,
    )


def _thread_comments(thread: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    comments = thread.get("comments")
    if isinstance(comments, list):
        return tuple(item for item in comments if isinstance(item, dict))
    if isinstance(comments, dict):
        nodes = comments.get("nodes")
        if isinstance(nodes, list):
            return tuple(item for item in nodes if isinstance(item, dict))
    return ()


def _comment_author_login(comment: dict[str, Any]) -> str:
    author = comment.get("author")
    if not isinstance(author, dict):
        author = comment.get("user")
    return str(author.get("login", "")) if isinstance(author, dict) else ""


def _is_current_head_codex_item(
    item: dict[str, Any],
    *,
    head_sha: str,
    trigger_time: str,
) -> bool:
    user = item.get("user")
    login = str(user.get("login", "")) if isinstance(user, dict) else ""
    if login not in CODEX_REVIEW_AUTHORS:
        return False
    item_head = _single_line_text(item.get("commit_id") or item.get("original_commit_id"))
    if item_head and item_head != head_sha:
        return False
    if item_head:
        return True
    body = str(item.get("body") or "")
    if head_sha in body:
        return True
    if trigger_time:
        return _codex_item_time(item) >= trigger_time
    return False


def _item_link(repo: str, pr_number: str, item: dict[str, Any]) -> str:
    html_url = _single_line_text(item.get("html_url"))
    if html_url:
        return html_url
    item_id = _single_line_text(item.get("id")) or "unknown"
    return f"https://github.com/{repo}/pull/{pr_number}#issuecomment-{item_id}"


def _codex_review_is_passing_current_head(
    review: dict[str, Any],
    *,
    head_sha: str,
    trigger_time: str,
) -> bool:
    user = review.get("user")
    login = str(user.get("login", "")) if isinstance(user, dict) else ""
    state = str(review.get("state", "")).upper()
    if login not in CODEX_REVIEW_AUTHORS:
        return False
    if state in DISQUALIFIED_CODEX_REVIEW_STATES:
        return False
    if str(review.get("commit_id", "")) != head_sha:
        return False
    review_time = _single_line_text(review.get("submitted_at"))
    if trigger_time and (not review_time or review_time < trigger_time):
        return False
    if pr_review_evidence.CODEX_CONTEXT_INVALID_PATTERN.search(str(review.get("body", ""))):
        return False
    if BLOCKING_CODEX_FINDING_PATTERN.search(str(review.get("body", ""))):
        return False
    return True


def _issue_comment_link(
    *,
    repo: str,
    pr_number: str,
    comment: dict[str, Any],
) -> str:
    html_url = _single_line_text(comment.get("html_url"))
    if html_url:
        return html_url
    return (
        f"https://github.com/{repo}/pull/{pr_number}"
        f"#issuecomment-{comment.get('id')}"
    )


def _payload_with_official_codex_review_evidence(
    payload: dict[str, Any],
    *,
    root: Path,
    evidence: str,
) -> dict[str, Any]:
    updated = dict(payload)
    updated["official_codex_review"] = {
        "reviewer": "Codex",
        "trigger": "@codex review",
        "conclusion": "通过",
        "blocking_issues": "无",
        "evidence": [
            evidence,
            _verify_full_evidence_command(root),
        ],
    }
    return updated


def _official_codex_review_fields_are_passing(value: dict[str, Any]) -> bool:
    reviewer = _single_line_text(value.get("reviewer")) or "Codex"
    trigger = _single_line_text(value.get("trigger"))
    conclusion = _single_line_text(value.get("conclusion")).casefold()
    blockers = _single_line_text(value.get("blocking_issues")).casefold()
    return (
        reviewer == "Codex"
        and "@codex review" in trigger
        and conclusion in {"通过", "pass", "passed", "approved"}
        and blockers in {"无", "none", "no", "n/a", "na", "0"}
    )


def _official_codex_review_links(
    value: dict[str, Any],
    *,
    pr_url: str,
) -> tuple[tuple[str, str, str, str], ...]:
    pr_info = _github_pr_info_from_url(pr_url)
    if pr_info is None:
        return ()
    expected_repo, expected_number = pr_info
    links: list[tuple[str, str, str, str]] = []
    for item in _string_or_list(value.get("evidence")):
        text = item.strip("`")
        review_match = CODEX_REVIEW_URL_PATTERN.search(text)
        if review_match and _github_link_matches_pr(
            review_match,
            expected_repo=expected_repo,
            expected_number=expected_number,
        ):
            links.append(
                (
                    "review",
                    review_match.group("repo"),
                    review_match.group("number"),
                    review_match.group("review_id"),
                )
            )
            continue
        comment_match = CODEX_COMPLETION_COMMENT_URL_PATTERN.search(text)
        if comment_match and _github_link_matches_pr(
            comment_match,
            expected_repo=expected_repo,
            expected_number=expected_number,
        ):
            links.append(
                (
                    "comment",
                    comment_match.group("repo"),
                    comment_match.group("number"),
                    comment_match.group("comment_id"),
                )
            )
    return tuple(links)


def _github_pr_info_from_url(pr_url: str) -> tuple[str, str] | None:
    match = re.match(
        r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)",
        pr_url,
    )
    if not match:
        return None
    return match.group("repo"), match.group("number")


def _remote_pr_review_requirement(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    base_ref: str,
) -> PullRequestReviewRequirement:
    branch = base_ref or "main"
    rulesets = _gh_api_list(
        root,
        runner,
        f"repos/{repo}/rulesets?includes_parents=true",
    )
    saw_pull_request_rule = False
    for summary in rulesets:
        ruleset = _ruleset_detail(root=root, runner=runner, repo=repo, summary=summary)
        if not _ruleset_applies_to_branch(ruleset, branch):
            continue
        pull_request_parameters = _pull_request_rule_parameters(ruleset)
        if pull_request_parameters is None:
            continue
        saw_pull_request_rule = True
        if _pull_request_rule_requires_approval(pull_request_parameters):
            return PullRequestReviewRequirement(
                approval_required=True,
                source=f"ruleset:{_single_line_text(ruleset.get('name')) or 'unnamed'}",
            )
    if saw_pull_request_rule:
        return PullRequestReviewRequirement(
            approval_required=False,
            source="rulesets",
        )
    return _legacy_branch_protection_review_requirement(
        root=root,
        runner=runner,
        repo=repo,
        branch=branch,
    )


def _ruleset_detail(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(summary.get("rules"), list):
        return summary
    ruleset_id = summary.get("id")
    if not ruleset_id:
        raise GitHubDataUnavailable(
            "GitHub ruleset metadata incomplete",
            details=(f"repos/{repo}/rulesets?includes_parents=true",),
        )
    return _gh_api_object(root, runner, f"repos/{repo}/rulesets/{ruleset_id}")


def _ruleset_applies_to_branch(ruleset: dict[str, Any], branch: str) -> bool:
    if _single_line_text(ruleset.get("target")) != "branch":
        return False
    if _single_line_text(ruleset.get("enforcement")) != "active":
        return False
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        return True
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return True
    includes = _string_or_list(ref_name.get("include"))
    excludes = _string_or_list(ref_name.get("exclude"))
    if any(_ref_pattern_matches(pattern, branch) for pattern in excludes):
        return False
    if not includes:
        return True
    return any(_ref_pattern_matches(pattern, branch) for pattern in includes)


def _ref_pattern_matches(pattern: str, branch: str) -> bool:
    ref = f"refs/heads/{branch}"
    return (
        pattern == "~DEFAULT_BRANCH"
        or fnmatch.fnmatchcase(ref, pattern)
        or fnmatch.fnmatchcase(branch, pattern)
    )


def _pull_request_rule_parameters(ruleset: dict[str, Any]) -> dict[str, Any] | None:
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        return None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if _single_line_text(rule.get("type")) != "pull_request":
            continue
        parameters = rule.get("parameters")
        return parameters if isinstance(parameters, dict) else {}
    return None


def _pull_request_rule_requires_approval(parameters: dict[str, Any]) -> bool:
    return (
        _int_value(parameters.get("required_approving_review_count")) > 0
        or bool(parameters.get("require_code_owner_review"))
        or bool(parameters.get("require_last_push_approval"))
    )


def _legacy_branch_protection_review_requirement(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    branch: str,
) -> PullRequestReviewRequirement:
    path = f"repos/{repo}/branches/{branch}/protection/required_pull_request_reviews"
    result = _run_github_read_command(root, runner, ["gh", "api", path])
    if result.returncode != 0:
        text = f"{result.stdout}\n{result.stderr}"
        if "404" in text or "Not Found" in text:
            return PullRequestReviewRequirement(
                approval_required=False,
                source="branch-protection:none",
            )
        raise _github_data_unavailable(
            "GitHub branch protection review rule unavailable",
            f"gh api {path}",
            result,
        )
    payload = _json_object_from_result(result, f"gh api {path}")
    return PullRequestReviewRequirement(
        approval_required=(
            _int_value(payload.get("required_approving_review_count")) > 0
            or bool(payload.get("require_code_owner_reviews"))
            or bool(payload.get("require_last_push_approval"))
        ),
        source="branch-protection",
    )


def _github_link_matches_pr(
    match: re.Match[str],
    *,
    expected_repo: str,
    expected_number: str,
) -> bool:
    return (
        match.group("repo") == expected_repo
        and match.group("number") == expected_number
    )


def _codex_review_link_matches_current_head(
    *,
    repo: str,
    pr_number: str,
    review_id: str,
    head_sha: str,
    pr_url: str,
    root: Path,
    runner: Runner,
) -> bool:
    reviews = _gh_api_list(root, runner, f"repos/{repo}/pulls/{pr_number}/reviews?per_page=100")
    matched_review: dict[str, Any] | None = None
    for review in reviews:
        if str(review.get("id", "")) == review_id:
            matched_review = review
            break
    if matched_review is None:
        return False
    user = matched_review.get("user")
    login = str(user.get("login", "")) if isinstance(user, dict) else ""
    state = str(matched_review.get("state", "")).upper()
    if login not in CODEX_REVIEW_AUTHORS:
        return False
    if state in DISQUALIFIED_CODEX_REVIEW_STATES:
        return False
    if str(matched_review.get("commit_id", "")) != head_sha:
        return False
    issue_comments = _gh_api_list(root, runner, f"repos/{repo}/issues/{pr_number}/comments?per_page=100")
    trigger_time = _latest_codex_trigger_time(
        issue_comments,
        pr_url=pr_url,
        head_sha=head_sha,
    )
    if not trigger_time:
        return False
    return _codex_review_is_passing_current_head(
        matched_review,
        head_sha=head_sha,
        trigger_time=trigger_time,
    )


def _codex_completion_comment_matches_current_head(
    *,
    repo: str,
    pr_number: str,
    comment_id: str,
    head_sha: str,
    pr_url: str,
    root: Path,
    runner: Runner,
) -> bool:
    comments = _gh_api_list(root, runner, f"repos/{repo}/issues/{pr_number}/comments?per_page=100")
    matched_comment = next(
        (comment for comment in comments if str(comment.get("id", "")) == comment_id),
        None,
    )
    if matched_comment is None:
        return False
    trigger_time = _latest_codex_trigger_time(comments, pr_url=pr_url, head_sha=head_sha)
    if not trigger_time:
        return False
    if _is_codex_trigger_comment(matched_comment, pr_url=pr_url, head_sha=head_sha):
        if not _codex_trigger_has_completion_reaction(
            repo=repo,
            comment_id=comment_id,
            comment_time=_comment_time(matched_comment),
            root=root,
            runner=runner,
        ):
            return False
    elif not _is_codex_completion_comment(matched_comment):
        return False
    return _comment_time(matched_comment) >= trigger_time


def _gh_api_list(root: Path, runner: Runner, path: str) -> list[dict[str, Any]]:
    result = _run_github_read_command(
        root,
        runner,
        ["gh", "api", "--paginate", "--slurp", path],
    )
    if result.returncode != 0:
        raise _github_data_unavailable("GitHub API list unavailable", f"gh api {path}", result)
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise GitHubDataUnavailable(
            "GitHub API list returned invalid JSON",
            details=(f"gh api {path}", str(exc)),
        ) from exc
    if not isinstance(payload, list):
        raise GitHubDataUnavailable(
            "GitHub API list returned unexpected payload",
            details=(f"gh api {path}",),
        )
    if all(isinstance(item, list) for item in payload):
        flattened: list[dict[str, Any]] = []
        for page in payload:
            flattened.extend(item for item in page if isinstance(item, dict))
        return flattened
    return [item for item in payload if isinstance(item, dict)]


def _gh_api_object(root: Path, runner: Runner, path: str) -> dict[str, Any]:
    result = _run_github_read_command(root, runner, ["gh", "api", path])
    if result.returncode != 0:
        raise _github_data_unavailable(
            "GitHub API object unavailable",
            f"gh api {path}",
            result,
        )
    return _json_object_from_result(result, f"gh api {path}")


def _run_github_read_command(
    root: Path,
    runner: Runner,
    command: list[str],
) -> CommandResult:
    result = CommandResult(1, "", "GitHub command was not attempted")
    for attempt in range(1, GITHUB_READ_MAX_ATTEMPTS + 1):
        result = runner.run(command, cwd=root)
        if result.returncode == 0:
            return result
        classification = _classify_github_error(result)
        if not classification.retryable or attempt >= GITHUB_READ_MAX_ATTEMPTS:
            return result
        time.sleep(GITHUB_READ_RETRY_BACKOFF_SECONDS * attempt)
    return result


def _classify_github_error(result: CommandResult) -> GitHubErrorClassification:
    text = f"{result.stdout}\n{result.stderr}".casefold()
    if any(
        token in text
        for token in (
            "authentication",
            "permission",
            "forbidden",
            "not found",
            "404",
            "graphql errors",
            "validation failed",
            "merge policy",
            "required checks failed",
        )
    ):
        return GitHubErrorClassification(False, "non_retryable")
    if any(
        token in text
        for token in (
            "eof",
            "tls",
            "connection reset",
            "timeout",
            "timed out",
            "temporary failure",
            "secondary rate limit",
            "500",
            "502",
            "503",
            "504",
            "5xx",
        )
    ):
        return GitHubErrorClassification(True, "transient")
    return GitHubErrorClassification(False, "unknown")


def _latest_codex_trigger_time(
    comments: Sequence[dict[str, Any]],
    *,
    pr_url: str,
    head_sha: str,
) -> str:
    times = [
        _comment_time(comment)
        for comment in comments
        if _is_codex_trigger_comment(comment, pr_url=pr_url, head_sha=head_sha)
    ]
    return max(times) if times else ""


def _latest_codex_completion_comment_time(
    comments: Sequence[dict[str, Any]],
    *,
    trigger_time: str,
) -> str:
    times = [
        _comment_time(comment)
        for comment in comments
        if _is_codex_completion_comment(comment)
        and (not trigger_time or _comment_time(comment) >= trigger_time)
    ]
    return max(times) if times else ""


def _is_codex_trigger_comment(
    comment: dict[str, Any],
    *,
    pr_url: str,
    head_sha: str,
) -> bool:
    body = str(comment.get("body", ""))
    return is_codex_review_request(
        body,
        expected_pr_url=pr_url,
        expected_head_sha=head_sha,
    )


def _is_codex_completion_comment(comment: dict[str, Any]) -> bool:
    user = comment.get("user")
    login = str(user.get("login", "")) if isinstance(user, dict) else ""
    body = str(comment.get("body", ""))
    return (
        login in CODEX_REVIEW_AUTHORS
        and CODEX_NO_MAJOR_ISSUES_PATTERN.search(body) is not None
        and pr_review_evidence.CODEX_CONTEXT_INVALID_PATTERN.search(body) is None
        and BLOCKING_CODEX_FINDING_PATTERN.search(body) is None
    )


def _codex_trigger_has_completion_reaction(
    *,
    repo: str,
    comment_id: str,
    comment_time: str,
    root: Path,
    runner: Runner,
) -> bool:
    reactions = _gh_api_list(root, runner, f"repos/{repo}/issues/comments/{comment_id}/reactions?per_page=100")
    for reaction in reactions:
        user = reaction.get("user")
        login = str(user.get("login", "")) if isinstance(user, dict) else ""
        reaction_time = _single_line_text(reaction.get("created_at"))
        if (
            str(reaction.get("content", "")) == "+1"
            and login in CODEX_REVIEW_AUTHORS
            and reaction_time
            and (not comment_time or reaction_time >= comment_time)
        ):
            return True
    return False


def _comment_time(comment: dict[str, Any]) -> str:
    created = str(comment.get("created_at", ""))
    updated = str(comment.get("updated_at", ""))
    if created and updated:
        return max(created, updated)
    return updated or created


def _codex_item_time(item: dict[str, Any]) -> str:
    return _single_line_text(item.get("submitted_at")) or _comment_time(item)


def _string_or_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := _single_line_text(item))]
    text = _single_line_text(value)
    return [text] if text else []


def _single_line_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _failing_check_names(output: str) -> list[str]:
    failing: list[str] = []
    for line in output.splitlines():
        normalized = line.casefold()
        if any(token in normalized for token in ("fail", "failure", "cancel", "error")):
            name = line.split("\t", 1)[0].strip()
            failing.append(name or line.strip())
    return failing


def _latest_required_check_results(output: str) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    latest: dict[
        tuple[str, str],
        tuple[tuple[int, str, int, int, int], dict[str, Any]],
    ] = {}
    order: list[tuple[str, str]] = []
    for index, check in enumerate(payload):
        if not isinstance(check, dict):
            continue
        name = _single_line_text(check.get("name"))
        if not name:
            continue
        workflow = _single_line_text(check.get("workflow"))
        key = (workflow, name)
        rank = _required_check_rank(check, index)
        current = latest.get(key)
        if current is None:
            order.append(key)
            latest[key] = (rank, check)
        elif rank > current[0]:
            latest[key] = (rank, check)
    return [latest[key][1] for key in order]


def _required_check_rank(check: dict[str, Any], index: int) -> tuple[int, str, int, int, int]:
    timestamp = _single_line_text(check.get("completedAt")) or _single_line_text(
        check.get("startedAt")
    )
    link = str(check.get("link") or "")
    match = ACTIONS_CHECK_URL_PATTERN.search(link)
    if match:
        return (
            2,
            timestamp,
            int(match.group("run_id")),
            int(match.group("job_id")),
            index,
        )
    if timestamp:
        return (1, timestamp, 0, 0, index)
    return (0, "", 0, 0, index)


def _failing_json_check_names(checks: Sequence[dict[str, Any]]) -> list[str]:
    return [
        _json_check_failure_detail(check)
        for check in checks
        if _json_check_failed(check)
    ]


def _pending_json_check_names(checks: Sequence[dict[str, Any]]) -> list[str]:
    return [
        _json_check_display_name(check)
        for check in checks
        if not _json_check_passed(check) and not _json_check_failed(check)
    ]


def _json_check_display_name(check: dict[str, Any]) -> str:
    name = _single_line_text(check.get("name"))
    workflow = _single_line_text(check.get("workflow"))
    return f"{workflow} / {name}" if workflow else name


def _json_check_failure_detail(check: dict[str, Any]) -> str:
    display = _json_check_display_name(check)
    link = _single_line_text(check.get("link"))
    return f"{display} {link}" if link else display


def _json_check_failed(check: dict[str, Any]) -> bool:
    bucket = _single_line_text(check.get("bucket")).casefold()
    state = _single_line_text(check.get("state")).casefold()
    return bucket == "fail" or state in {
        "action_required",
        "cancelled",
        "error",
        "failure",
        "startup_failure",
        "timed_out",
    }


def _json_check_passed(check: dict[str, Any]) -> bool:
    bucket = _single_line_text(check.get("bucket")).casefold()
    state = _single_line_text(check.get("state")).casefold()
    return bucket in {"pass", "skipping"} or state in {"neutral", "skipped", "success"}


def _diagnose_required_checks(
    *,
    root: Path,
    runner: Runner,
    pr_number: str,
) -> tuple[str, tuple[str, ...], bool]:
    result = runner.run(
        ["gh", "pr", "checks", pr_number, "--required", "--json", CHECKS_JSON_FIELDS],
        cwd=root,
    )
    if result.returncode != 0:
        details = tuple(
            detail
            for detail in (
                _single_line_text(result.stderr),
                _single_line_text(result.stdout),
            )
            if detail
        )
        return "unavailable", details, True
    checks = _latest_required_check_results(result.stdout)
    if checks is None:
        return "unavailable", ("required check JSON was invalid",), True
    failing = tuple(_failing_json_check_names(checks))
    if failing:
        return "failing", failing, False
    pending = tuple(_pending_json_check_names(checks))
    if pending:
        return "pending", pending, False
    return "passed", (), False


def _merge_state_requires_attention(merge_state: str) -> bool:
    normalized = merge_state.upper()
    return bool(normalized and normalized not in {"CLEAN", "HAS_HOOKS"})


def _review_decision_allows_merge(
    review_decision: str,
    *,
    review_requirement: PullRequestReviewRequirement,
) -> bool:
    if not review_requirement.approval_required:
        return True
    return review_decision.upper() == "APPROVED"


class _temporary_env:
    def __init__(self, updates: dict[str, str]) -> None:
        self.updates = updates
        self.originals: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.updates.items():
            self.originals[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, *_exc: object) -> None:
        for key, value in self.originals.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _command_stdout(result: CommandResult) -> str:
    return result.stdout.strip()


def _pr_number_from_url(url: str) -> str:
    match = re.search(r"/pull/(\d+)", url)
    return match.group(1) if match else url


def _print_command_failure(label: str, result: CommandResult) -> None:
    print(f"error: {label} failed with exit code {result.returncode}", file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)


def _github_data_unavailable(
    message: str,
    label: str,
    result: CommandResult,
) -> GitHubDataUnavailable:
    classification = _classify_github_error(result)
    details = [label, f"exit_code={result.returncode}"]
    if result.stderr.strip():
        details.append(_single_line_text(result.stderr))
    if result.stdout.strip():
        details.append(_single_line_text(result.stdout))
    return GitHubDataUnavailable(
        message,
        details=details,
        retryable=classification.retryable,
    )


def _print_github_data_unavailable(exc: GitHubDataUnavailable) -> None:
    _print_state(
        "EXCEPTION_REQUIRED",
        str(exc),
        reason_code="GITHUB_DATA_UNAVAILABLE",
        phase="github",
        retryable=exc.retryable,
        dispatch_target="github",
        details=exc.details,
        next_actions=("restore GitHub API access",),
    )


def _print_state(
    state: str,
    message: str,
    *,
    details: Sequence[str] = (),
    repo_root: str | Path | None = None,
    reason_code: str | None = None,
    phase: str = "unknown",
    retryable: bool = False,
    dispatch_target: str | None = None,
    blocking_items: Sequence[str] | None = None,
    evidence_refs: Sequence[str] = (),
    next_actions: Sequence[str] = (),
) -> None:
    status = StopStatus(
        state=state,
        message=message,
        reason_code=reason_code or _reason_code_from_message(message),
        phase=phase,
        retryable=retryable,
        dispatch_target=dispatch_target or _default_dispatch_target(state),
        blocking_items=tuple(blocking_items if blocking_items is not None else details),
        evidence_refs=tuple(evidence_refs),
        next_actions=tuple(next_actions),
    )
    _emit_stop_status(status, stream=sys.stderr, repo_root=repo_root)


def _print_diagnose_stop(
    repo_root: str | Path,
    state: str,
    message: str,
    *,
    reason_code: str,
    retryable: bool = False,
    dispatch_target: str,
    blocking_items: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    next_actions: Sequence[str] = (),
) -> None:
    status = StopStatus(
        state=state,
        message=message,
        reason_code=reason_code,
        phase="diagnose",
        retryable=retryable,
        dispatch_target=dispatch_target,
        blocking_items=tuple(blocking_items),
        evidence_refs=tuple(evidence_refs),
        next_actions=tuple(next_actions),
    )
    _emit_stop_status(status, stream=sys.stdout, repo_root=repo_root)


def _emit_stop_status(
    status: StopStatus,
    *,
    stream: Any,
    repo_root: str | Path | None,
) -> None:
    print(f"{status.state}: {status.message}", file=stream)
    print(f"reason_code: {status.reason_code}", file=stream)
    print(f"phase: {status.phase}", file=stream)
    print(f"retryable: {str(status.retryable).lower()}", file=stream)
    print(f"dispatch_target: {status.dispatch_target}", file=stream)
    if status.blocking_items:
        print("blocking_items:", file=stream)
        for item in status.blocking_items:
            print(f"- {item}", file=stream)
    if status.evidence_refs:
        print("evidence_refs:", file=stream)
        for item in status.evidence_refs:
            print(f"- {item}", file=stream)
    if status.next_actions:
        print("next_actions:", file=stream)
        for item in status.next_actions:
            print(f"- {item}", file=stream)
    if repo_root is not None:
        _write_last_status(repo_root, status)


def _write_last_status(repo_root: str | Path, status: StopStatus) -> None:
    path = Path(repo_root).resolve() / ".local" / "pr-flow" / "last-status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status.as_json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _record_pr_ready_phase(
    root: Path,
    completed_phases: list[str],
    phase: str,
) -> None:
    if phase not in PR_READY_PHASES:
        raise ValueError(f"unknown pr-ready phase: {phase}")
    _append_unique(completed_phases, phase)
    _write_pr_flow_state(
        root,
        state="running",
        current_phase=phase,
        completed_phases=completed_phases,
        next_action="continue",
    )


def _record_pr_ready_merge_ready(
    root: Path,
    completed_phases: list[str],
) -> None:
    _write_pr_flow_state(
        root,
        state="merge-ready",
        current_phase="merge_ready",
        completed_phases=completed_phases,
        next_action="pr-complete",
    )


def _write_pr_flow_state(
    root: Path,
    *,
    state: str,
    current_phase: str,
    completed_phases: Sequence[str],
    next_action: str,
) -> None:
    path = root / ".local" / "pr-flow" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "command": "pr-ready",
                "state": state,
                "current_phase": current_phase,
                "completed_phases": list(completed_phases),
                "next_action": next_action,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _reason_code_from_message(message: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", message.strip()).strip("_")
    return normalized.upper() or "UNKNOWN_STOP"


def _default_dispatch_target(state: str) -> str:
    return {
        "DISPATCH_REQUIRED": "agent",
        "REPLY_OR_FIX_REQUIRED": "author",
        "EXCEPTION_REQUIRED": "operator",
    }.get(state, "operator")


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _short_sha(sha: str) -> str:
    return sha[:12] if sha else "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--title")
    wait_parser = subparsers.add_parser("wait")
    wait_parser.add_argument("--pr")
    diagnose_parser = subparsers.add_parser("diagnose")
    diagnose_parser.add_argument("--pr")
    resolve_threads_parser = subparsers.add_parser("resolve-threads")
    resolve_threads_parser.add_argument("thread_ids", nargs="*")
    resolve_threads_parser.add_argument("--thread", action="append", default=[])
    ready_for_review_parser = subparsers.add_parser("ready-for-review")
    ready_for_review_parser.add_argument("--pr")
    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--pr")
    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--pr")
    ready_parser = subparsers.add_parser("ready")
    ready_parser.add_argument("--title")
    ready_parser.add_argument("--resolve-thread", action="append", default=[])
    ready_parser.add_argument(
        "--codex-review-timeout-seconds",
        type=float,
        default=CODEX_REVIEW_WAIT_TIMEOUT_SECONDS,
    )
    ready_parser.add_argument(
        "--codex-review-poll-seconds",
        type=float,
        default=CODEX_REVIEW_WAIT_INTERVAL_SECONDS,
    )
    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--title")
    complete_parser.add_argument("--pr")
    complete_parser.add_argument("--resolve-thread", action="append", default=[])
    complete_parser.add_argument(
        "--codex-review-timeout-seconds",
        type=float,
        default=CODEX_REVIEW_WAIT_TIMEOUT_SECONDS,
    )
    complete_parser.add_argument(
        "--codex-review-poll-seconds",
        type=float,
        default=CODEX_REVIEW_WAIT_INTERVAL_SECONDS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        return prepare(repo_root=args.repo_root)
    if args.command == "sync":
        return sync(repo_root=args.repo_root, title=args.title)
    if args.command == "wait":
        return wait(repo_root=args.repo_root, pr=args.pr)
    if args.command == "diagnose":
        return diagnose(repo_root=args.repo_root, pr=args.pr)
    if args.command == "resolve-threads":
        return resolve_review_threads(
            repo_root=args.repo_root,
            thread_ids=tuple(args.thread_ids) + tuple(args.thread),
        )
    if args.command == "ready-for-review":
        return ready_for_review(repo_root=args.repo_root, pr=args.pr)
    if args.command == "merge":
        return merge_pr(repo_root=args.repo_root, pr=args.pr)
    if args.command == "cleanup":
        return cleanup_pr(repo_root=args.repo_root, pr=args.pr)
    if args.command == "ready":
        return ready(
            repo_root=args.repo_root,
            title=args.title,
            resolve_threads=tuple(args.resolve_thread),
            codex_review_timeout_seconds=args.codex_review_timeout_seconds,
            codex_review_poll_seconds=args.codex_review_poll_seconds,
        )
    if args.command == "complete":
        return complete_pr(
            repo_root=args.repo_root,
            title=args.title,
            pr=args.pr,
            resolve_threads=tuple(args.resolve_thread),
            codex_review_timeout_seconds=args.codex_review_timeout_seconds,
            codex_review_poll_seconds=args.codex_review_poll_seconds,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
