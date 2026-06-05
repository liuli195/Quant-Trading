"""Orchestrate local PR preparation and GitHub synchronization."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import pr_flow_contract, pr_review_evidence
from .codex_review_contract import is_codex_review_request, render_codex_review_request


MANAGED_BLOCK_START = "<!-- pr-flow:start -->"
MANAGED_BLOCK_END = "<!-- pr-flow:end -->"
GITHUB_NATIVE_LINKS_START = "<!-- github-native-links:start -->"
GITHUB_NATIVE_LINKS_END = "<!-- github-native-links:end -->"
AI_RISK_REVIEW_LABEL = "ai-risk-review"
SUCCESS_EXIT_CODE = 0
GENERAL_FAILURE_EXIT_CODE = 1
DISPATCH_REQUIRED_EXIT_CODE = 4
REPLY_OR_FIX_REQUIRED_EXIT_CODE = 5
EXCEPTION_REQUIRED_EXIT_CODE = 6
CODEX_REVIEW_AUTHORS = {"chatgpt-codex-connector", "chatgpt-codex-connector[bot]"}
CODEX_NO_MAJOR_ISSUES_PATTERN = re.compile(
    r"Codex Review:\s*(?:Didn['’]t|Did not) find any major issues",
    re.IGNORECASE,
)
BLOCKING_CODEX_FINDING_PATTERN = re.compile(r"\bP[01]\b|P[01]\s*Badge")
CODEX_THREAD_SEVERITY_PATTERN = re.compile(r"\bP(?P<level>[0-3])\b")
ACTIONS_CHECK_URL_PATTERN = re.compile(r"/actions/runs/(?P<run_id>\d+)/job/(?P<job_id>\d+)")
STATUS_CHECK_ROLLUP_JSON_FIELDS = "url,baseRefName,isDraft,headRefOid,statusCheckRollup"
REQUIRED_STATUS_CHECK_NAMES = {
    "PR Flow / review-status",
    "Research Governance / verify-full",
    "PR Flow / evidence",
}
CODEX_REVIEW_WAIT_TIMEOUT_SECONDS = 600.0
CODEX_REVIEW_WAIT_INTERVAL_SECONDS = 30.0
AUTO_ACCEPTED_REVIEW_THREAD_SEVERITIES = {"P2", "P3"}
CLOSED_REVIEW_THREAD_STATUSES = {"fixed", "false_positive"}
GITHUB_READ_MAX_ATTEMPTS = 3
GITHUB_READ_RETRY_BACKOFF_SECONDS = 0.1
VALID_INTENT_ROLES = {"reference", "closes"}
PENDING_INTENT_PATH = Path(".local") / "pr-flow" / "pending-intent.json"
THREAD_PROCESSING_SCHEMA_VERSION = 4
HIGH_RISK_PREFIXES = (
    "strategies/",
    "scripts/research/platform/",
    "scripts/research/governance/",
    ".github/",
    ".githooks/",
    "docs/rules/",
    "docs/adr/",
)
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


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


@dataclass(frozen=True)
class SubmitReviewState:
    reviews: dict[str, dict[str, str]]
    retained: list[dict[str, str]]
    official_review: dict[str, str]

    @property
    def requires_official_codex_review(self) -> bool:
        return self.official_review.get("decision") == "required"


@dataclass(frozen=True)
class SubmitSyncResult:
    exit_code: int
    pr_number: str = ""
    pr_url: str = ""
    reason_code: str = "PR_SYNC_FAILED"
    phase: str = "submit_sync_pr"
    retryable: bool = True
    failures: tuple[pr_flow_contract.SubmitFailure, ...] = ()


@dataclass(frozen=True)
class SubmitSnapshotContext:
    repository: str = ""
    pr_number: str = ""
    head_branch: str = ""


@dataclass(frozen=True)
class RequiredCheckWaitResult:
    failures: tuple[pr_flow_contract.SubmitFailure, ...] = ()
    diagnostics: tuple[pr_flow_contract.SubmitFailure, ...] = ()
    checkpoint_statuses: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class RequiredCheckRollup:
    failures: tuple[pr_flow_contract.SubmitFailure, ...] = ()
    pending: tuple[pr_flow_contract.SubmitFailure, ...] = ()
    diagnostics: tuple[pr_flow_contract.SubmitFailure, ...] = ()
    checkpoint_statuses: tuple[dict[str, str], ...] = ()


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


class CommitIntentError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        details: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.details = tuple(detail for detail in details if detail)


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


def stage_commit_intent(
    *,
    repo_root: str | Path = ".",
    runner: Runner | None = None,
    issue_bindings: Sequence[str] = (),
    no_issue_reason: str | None = None,
    no_issue_authorized_by: str | None = None,
    no_issue_evidence: str | None = None,
    correction_reason: str | None = None,
    now: str | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    try:
        branch = _current_branch(root, runner)
        fingerprint = _current_staged_diff_fingerprint(root, runner)
        created_by = _git_config_value(root, runner, "user.email") or "unknown"
        if issue_bindings:
            issues = _validated_intent_issues(root, runner, issue_bindings)
            intent: dict[str, Any] = {
                "schema_version": 1,
                "branch": branch,
                "staged_diff_fingerprint": fingerprint,
                "issue_policy": "issues",
                "issues": issues,
                "created_at": now or _utc_now(),
                "created_by": created_by,
                "consumed": False,
            }
            correction = _single_line_text(correction_reason)
            if correction:
                intent["correction_reason"] = correction
        else:
            reason = _single_line_text(no_issue_reason)
            authorized_by = _single_line_text(no_issue_authorized_by)
            evidence = _single_line_text(no_issue_evidence)
            if not reason or not authorized_by or not evidence:
                raise CommitIntentError(
                    "no-Issue authorization requires reason, authorized_by, and evidence",
                    reason_code="NO_ISSUE_AUTHORIZATION_INCOMPLETE",
                    details=(
                        "--no-issue-reason",
                        "--no-issue-authorized-by",
                        "--no-issue-evidence",
                    ),
                )
            intent = {
                "schema_version": 1,
                "branch": branch,
                "staged_diff_fingerprint": fingerprint,
                "issue_policy": "no_issue",
                "no_issue_authorization": {
                    "reason": reason,
                    "authorized_by": authorized_by,
                    "evidence": evidence,
                },
                "created_at": now or _utc_now(),
                "created_by": created_by,
                "consumed": False,
            }
        path = _pending_intent_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(intent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"recorded commit intent for {branch}")
        return SUCCESS_EXIT_CODE
    except CommitIntentError as exc:
        _print_state(
            "DISPATCH_REQUIRED",
            str(exc),
            repo_root=root,
            reason_code=exc.reason_code,
            phase="intent_stage",
            dispatch_target="author",
            details=exc.details,
            next_actions=("stage files, then record a fresh commit intent",),
        )
        return DISPATCH_REQUIRED_EXIT_CODE


def validate_pending_commit_intent(
    *,
    repo_root: str | Path = ".",
    runner: Runner | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    try:
        _matching_pending_intent(root, runner)
        return SUCCESS_EXIT_CODE
    except CommitIntentError as exc:
        _print_state(
            "DISPATCH_REQUIRED",
            str(exc),
            repo_root=root,
            reason_code=exc.reason_code,
            phase="pre_commit",
            dispatch_target="author",
            details=exc.details,
            next_actions=("run pr_flow intent stage for the current staged diff",),
        )
        return DISPATCH_REQUIRED_EXIT_CODE


def record_committed_intent(
    *,
    repo_root: str | Path = ".",
    runner: Runner | None = None,
    now: str | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    try:
        pending = _pending_intent(root)
        if bool(pending.get("consumed")):
            raise CommitIntentError(
                "pending commit intent has already been consumed",
                reason_code="COMMIT_INTENT_CONSUMED",
            )
        branch = _current_branch(root, runner)
        pending_branch = _single_line_text(pending.get("branch"))
        if pending_branch != branch:
            raise CommitIntentError(
                "pending commit intent belongs to another branch",
                reason_code="COMMIT_INTENT_BRANCH_MISMATCH",
                details=(f"expected={branch}", f"actual={pending_branch}"),
            )
        commit_sha = _command_stdout(runner.run(["git", "rev-parse", "HEAD"], cwd=root))
        if not commit_sha:
            raise CommitIntentError(
                "committed HEAD SHA is unavailable",
                reason_code="COMMIT_INTENT_HEAD_UNAVAILABLE",
            )
        consumed_at = now or _utc_now()
        consumed = dict(pending)
        consumed.update(
            {
                "commit_sha": commit_sha,
                "consumed": True,
                "consumed_at": consumed_at,
            }
        )
        branch_path = _branch_intent_path(root, branch)
        branch_payload = _read_json_object(branch_path) or {}
        merged = _branch_intent_with_commit(
            branch_payload,
            branch=branch,
            commit_intent=consumed,
            updated_at=consumed_at,
        )
        branch_path.parent.mkdir(parents=True, exist_ok=True)
        branch_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _pending_intent_path(root).write_text(
            json.dumps(consumed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"recorded commit intent for {commit_sha[:12]}")
        return SUCCESS_EXIT_CODE
    except CommitIntentError as exc:
        _print_state(
            "DISPATCH_REQUIRED",
            str(exc),
            repo_root=root,
            reason_code=exc.reason_code,
            phase="post_commit",
            dispatch_target="author",
            details=exc.details,
            next_actions=("inspect pending commit intent and branch intent",),
        )
        return DISPATCH_REQUIRED_EXIT_CODE


def check_branch_intent_coverage(
    *,
    repo_root: str | Path = ".",
    runner: Runner | None = None,
    base_ref: str = "origin/main",
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    try:
        _validate_branch_intent_coverage(root, runner, base_ref=base_ref)
        return SUCCESS_EXIT_CODE
    except CommitIntentError as exc:
        _print_state(
            "DISPATCH_REQUIRED",
            str(exc),
            repo_root=root,
            reason_code=exc.reason_code,
            phase="branch_intent",
            dispatch_target="author",
            details=exc.details,
            next_actions=("rebuild or confirm commit intent for rewritten commits",),
        )
        return DISPATCH_REQUIRED_EXIT_CODE


def _validate_branch_intent_coverage(
    root: Path,
    runner: Runner,
    *,
    base_ref: str = "origin/main",
    pr_number: str | None = None,
) -> None:
    try:
        branch = _current_branch(root, runner)
    except CommitIntentError:
        commits_without_branch = _current_branch_commit_shas(
            root,
            runner,
            base_ref=base_ref,
        )
        if not commits_without_branch:
            return
        raise
    commits = _current_branch_commit_shas(root, runner, base_ref=base_ref)
    if not commits:
        return
    branch_intent = _read_json_object(_branch_intent_path(root, branch)) or {}
    recorded = {
        _single_line_text(item.get("commit_sha"))
        for item in branch_intent.get("commits", [])
        if isinstance(item, dict) and _single_line_text(item.get("commit_sha"))
    }
    current = set(commits)
    missing = [
        sha
        for sha in commits
        if sha not in recorded
        and not _is_github_update_branch_merge_commit(
            root,
            runner,
            sha,
            base_ref=base_ref,
            pr_number=pr_number,
        )
    ]
    if missing:
        raise CommitIntentError(
            "branch intent does not cover all current branch commits",
            reason_code="BRANCH_INTENT_COVERAGE_MISSING",
            details=missing,
        )
    stale = sorted(sha for sha in recorded if sha not in current)
    if stale:
        raise CommitIntentError(
            "branch intent contains commits outside the current branch",
            reason_code="BRANCH_INTENT_STALE_COMMITS",
            details=stale,
        )


def payload_with_branch_intent(
    payload: dict[str, Any],
    *,
    repo_root: str | Path = ".",
    runner: Runner | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    try:
        branch = _current_branch(root, runner)
    except CommitIntentError:
        return dict(payload)
    branch_intent = _read_json_object(_branch_intent_path(root, branch)) or {}
    commits = [
        item for item in branch_intent.get("commits", []) if isinstance(item, dict)
    ]
    current_commits = set(_current_branch_commit_shas(root, runner, base_ref="origin/main"))
    if current_commits:
        commits = [
            item
            for item in commits
            if _single_line_text(item.get("commit_sha")) in current_commits
        ]
        branch_intent = dict(branch_intent)
        branch_intent["commits"] = commits
        branch_intent["issues"] = _aggregate_intent_issues(commits)
        branch_intent["no_issue_authorizations"] = _no_issue_authorizations(commits)
    if not commits:
        return dict(payload)
    updated = dict(payload)
    spec_ref = updated.get("spec_ref")
    spec_ref = dict(spec_ref) if isinstance(spec_ref, dict) else {}
    spec_ref["issues"] = _spec_issues_from_branch_intent(branch_intent)
    spec_ref.setdefault("design_docs", [])
    spec_ref.setdefault("adrs", [])
    updated["spec_ref"] = spec_ref
    head_sha = _command_stdout(runner.run(["git", "rev-parse", "HEAD"], cwd=root))
    issue_intent = {
        "schema_version": 1,
        "head_sha": head_sha,
        "branch": _single_line_text(branch_intent.get("branch")) or branch,
        "commits": commits,
        "issues": [
            item for item in branch_intent.get("issues", []) if isinstance(item, dict)
        ],
        "no_issue_authorizations": [
            item
            for item in branch_intent.get("no_issue_authorizations", [])
            if isinstance(item, dict)
        ],
    }
    updated["issue_intent"] = issue_intent
    return updated


def submit(
    *,
    repo_root: str | Path = ".",
    title: str | None = None,
    pr: str | None = None,
    runner: Runner | None = None,
    watch_timeout_seconds: float = CODEX_REVIEW_WAIT_TIMEOUT_SECONDS,
    watch_poll_seconds: float = CODEX_REVIEW_WAIT_INTERVAL_SECONDS,
    official_review_skip_authorized_by: str | None = None,
    official_review_skip_evidence: str | None = None,
) -> int:
    root = Path(repo_root).resolve()
    runner = runner or CommandRunner()
    contract = pr_flow_contract.load_contract(root)
    head_sha = _command_stdout(runner.run(["git", "rev-parse", "HEAD"], cwd=root))
    snapshot_context = _submit_snapshot_context(root, runner, target_pr=pr)
    _clear_submit_status(root, contract)
    auth_failure = _official_review_skip_authorization_failure(
        authorized_by=official_review_skip_authorized_by,
        evidence=official_review_skip_evidence,
    )
    if auth_failure is not None:
        print(f"error: {auth_failure.check}: {auth_failure.detail}", file=sys.stderr)
        return _fail_submit(
            root, contract, EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="OFFICIAL_REVIEW_SKIP_AUTH_INCOMPLETE",
            phase="submit_preflight",
            retryable=False,
            failures=[auth_failure],
        )
    try:
        failures = _submit_preflight_failures(
            root=root,
            runner=runner,
            contract=contract,
        )
    except GitHubDataUnavailable as exc:
        failures = [
            pr_flow_contract.SubmitFailure(
                check="github",
                source="",
                detail=str(exc),
            )
        ]
    if failures:
        for failure in failures:
            print(f"error: {failure.check}: {failure.detail}", file=sys.stderr)
        return _fail_submit(
            root, contract, EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="PREFLIGHT_CHECK_FAILED",
            phase="submit_preflight",
            retryable=False,
            failures=failures,
        )
    failures = _submit_branch_intent_failures(root=root, runner=runner)
    if failures:
        for failure in failures:
            print(f"error: {failure.check}: {failure.detail}", file=sys.stderr)
        return _fail_submit(
            root, contract, DISPATCH_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="BRANCH_INTENT_COVERAGE_INCOMPLETE",
            phase="submit_branch_intent",
            retryable=True,
            failures=failures,
        )
    try:
        diff_hash = _submit_current_diff_hash(root, runner)
    except GitHubDataUnavailable as exc:
        diff_failures = [
            pr_flow_contract.SubmitFailure(
                check="github",
                source="",
                detail=str(exc),
            )
        ]
        return _fail_submit(
            root, contract, EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="DIFF_HASH_UNAVAILABLE",
            phase="submit_diff",
            retryable=True,
            failures=diff_failures,
        )
    failures, has_blocking = _submit_first_stage_fragment_failures(
        root=root,
        contract=contract,
        head_sha=head_sha,
        diff_hash=diff_hash,
    )
    if failures:
        for failure in failures:
            print(f"error: {failure.check}: {failure.detail}", file=sys.stderr)
        return _fail_submit(
            root, contract,
            REPLY_OR_FIX_REQUIRED_EXIT_CODE if has_blocking else DISPATCH_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="FRAGMENT_BLOCKING" if has_blocking else "FRAGMENT_MISSING",
            phase="submit_fragments",
            retryable=not has_blocking,
            failures=failures,
        )
    failures, has_blocking = _submit_security_fragment_failures(
        root=root,
        contract=contract,
        head_sha=head_sha,
        diff_hash=diff_hash,
    )
    if failures:
        for failure in failures:
            print(f"error: {failure.check}: {failure.detail}", file=sys.stderr)
        return _fail_submit(
            root, contract,
            REPLY_OR_FIX_REQUIRED_EXIT_CODE if has_blocking else DISPATCH_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="SECURITY_BLOCKING" if has_blocking else "SECURITY_FRAGMENT_MISSING",
            phase="submit_security",
            retryable=not has_blocking,
            failures=failures,
        )
    try:
        review_state, failures = _submit_review_state(
            root=root,
            runner=runner,
            contract=contract,
            head_sha=head_sha,
            diff_hash=diff_hash,
            official_review_skip_authorized_by=official_review_skip_authorized_by,
            official_review_skip_evidence=official_review_skip_evidence,
        )
        if failures:
            return _fail_submit(
                root, contract, DISPATCH_REQUIRED_EXIT_CODE,
                head_sha=head_sha,
                snapshot_context=snapshot_context,
                reason_code="REVIEW_STATE_INCOMPLETE",
                phase="submit_review_state",
                retryable=True,
                failures=failures,
            )
        evidence = _submit_pr_evidence(
            root=root,
            runner=runner,
            contract=contract,
            head_sha=head_sha,
            diff_hash=diff_hash,
            review_state=review_state,
        )
        sync_result = _sync_submit_pr_evidence(
            root=root,
            runner=runner,
            contract=contract,
            title=title,
            target_pr=pr,
            evidence=evidence,
        )
    except CommitIntentError as exc:
        intent_failures = [
            pr_flow_contract.SubmitFailure(
                check="issue-intent",
                source=".local/pr-flow/intents",
                detail=_commit_intent_failure_detail(exc),
            )
        ]
        print(
            f"error: issue-intent: {_commit_intent_failure_detail(exc)}",
            file=sys.stderr,
        )
        return _fail_submit(
            root, contract, DISPATCH_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="COMMIT_INTENT_INVALID",
            phase="submit_evidence",
            retryable=True,
            failures=intent_failures,
        )
    except GitHubDataUnavailable as exc:
        github_failures = [
            pr_flow_contract.SubmitFailure(
                check="github",
                source="",
                detail=str(exc),
            )
        ]
        return _fail_submit(
            root, contract, EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="GITHUB_DATA_UNAVAILABLE",
            phase="submit_sync",
            retryable=exc.retryable,
            failures=github_failures,
        )
    if sync_result.exit_code != SUCCESS_EXIT_CODE:
        return _fail_submit(
            root,
            contract,
            sync_result.exit_code,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code=sync_result.reason_code,
            phase=sync_result.phase,
            retryable=sync_result.retryable,
            failures=sync_result.failures,
        )
    pr_number = sync_result.pr_number
    pr_url = sync_result.pr_url
    snapshot_context = SubmitSnapshotContext(
        repository=snapshot_context.repository,
        pr_number=pr or pr_number or snapshot_context.pr_number,
        head_branch=snapshot_context.head_branch,
    )
    try:
        head_failures = _submit_pr_head_failures(
            root=root,
            runner=runner,
            pr_number=pr or pr_number,
            expected_head_sha=head_sha,
        )
    except GitHubDataUnavailable as exc:
        head_failures = [
            pr_flow_contract.SubmitFailure(
                check="github",
                source="",
                detail=str(exc),
            )
        ]
    if head_failures:
        return _fail_submit(
            root, contract, EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="PR_HEAD_MISMATCH",
            phase="submit_verify",
            retryable=True,
            failures=head_failures,
        )
    merged_metadata = _submit_merged_pr_metadata(
        root=root,
        runner=runner,
        pr_number=pr or pr_number,
    )
    if merged_metadata is not None:
        cleanup_code = _submit_cleanup_merged_pr(
            root=root,
            runner=runner,
            contract=contract,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            metadata=merged_metadata,
        )
        if cleanup_code != SUCCESS_EXIT_CODE:
            _ensure_submit_status_failure(
                root,
                contract,
                head_sha=head_sha,
                snapshot_context=snapshot_context,
                failure=pr_flow_contract.SubmitFailure(
                    check="pr-lifecycle",
                    source=f"PR #{pr or pr_number}",
                    detail="post-merge cleanup failed",
                ),
            )
        return cleanup_code
    if review_state.requires_official_codex_review:
        request_code = _submit_request_codex_review(
            root=root,
            runner=runner,
            pr_number=pr or pr_number,
            pr_url=pr_url,
            head_sha=head_sha,
        )
        if request_code != SUCCESS_EXIT_CODE:
            _ensure_submit_status_failure(
                root,
                contract,
                head_sha=head_sha,
                snapshot_context=snapshot_context,
                failure=pr_flow_contract.SubmitFailure(
                    check="official-codex-review",
                    source=pr_url,
                    detail="official Codex review request failed",
                ),
            )
            return request_code
    current_fingerprint = _submit_current_diff_fingerprint(root, runner)
    current_diff_hash = _fingerprint_diff_files_hash(current_fingerprint)
    review_thread_failures: tuple[pr_flow_contract.SubmitFailure, ...] = ()
    review_thread_artifacts: tuple[dict[str, str], ...] = ()
    # Auto-process official Codex P2/P3 retained threads before waiting for CI.
    # P0/P1 closure evidence is not part of the #65 submit chain; unresolved
    # blocking threads must remain visible to PR Flow / review-status.
    try:
        pr_info = _github_pr_info_from_url(pr_url)
        if pr_info is not None:
            repo, resolved_pr_number = pr_info
            try:
                threads = _current_pr_review_threads(
                    root=root,
                    runner=runner,
                    repo=repo,
                    pr_number=resolved_pr_number,
                )
            except GitHubDataUnavailable as exc:
                _print_github_data_unavailable(exc)
                failures = [
                    pr_flow_contract.SubmitFailure(
                        check="official-codex-review-thread",
                        source=pr_url,
                        detail=f"official Codex review thread read failed: {exc}",
                    ),
                ]
                return _fail_submit(
                    root,
                    contract,
                    EXCEPTION_REQUIRED_EXIT_CODE,
                    head_sha=head_sha,
                    snapshot_context=snapshot_context,
                    reason_code="CODEX_THREAD_READ_UNAVAILABLE",
                    phase="submit_review_threads",
                    retryable=exc.retryable,
                    failures=failures,
                )
            if threads:
                auto_payload = _submit_thread_processing_payload(root, current_fingerprint)
                auto_code, _auto_payload, auto_changed = (
                    _auto_process_official_codex_review_threads(
                        root=root,
                        runner=runner,
                        repo=repo,
                        pr_number=resolved_pr_number,
                        threads=threads,
                        payload=auto_payload,
                        current_head_sha=head_sha,
                        current_diff_hash=current_diff_hash,
                    )
                )
                if auto_code != SUCCESS_EXIT_CODE:
                    failures = [
                        pr_flow_contract.SubmitFailure(
                            check="official-codex-review-thread",
                            source=pr_url,
                            detail="official Codex review thread auto-processing failed",
                        ),
                    ]
                    return _fail_submit(
                        root,
                        contract,
                        EXCEPTION_REQUIRED_EXIT_CODE,
                        head_sha=head_sha,
                        snapshot_context=snapshot_context,
                        reason_code="CODEX_THREAD_AUTO_PROCESS_FAILED",
                        phase="submit_review_threads",
                        retryable=True,
                        failures=failures,
                    )
                if auto_changed:
                    review_state = _review_state_with_retained(
                        review_state,
                        _submit_official_codex_retained_from_payload(
                            _auto_payload,
                            contract=contract,
                        ),
                    )
                    # Threads were auto-processed. Rebuild evidence so
                    # CI sees any updated retained findings, then re-sync
                    # the PR body.
                    evidence = _submit_pr_evidence(
                        root=root,
                        runner=runner,
                        contract=contract,
                        head_sha=head_sha,
                        diff_hash=diff_hash,
                        review_state=review_state,
                    )
                    sync_result = _sync_submit_pr_evidence(
                        root=root,
                        runner=runner,
                        contract=contract,
                        title=title,
                        target_pr=pr,
                        evidence=evidence,
                    )
                    if sync_result.exit_code != SUCCESS_EXIT_CODE:
                        return _fail_submit(
                            root,
                            contract,
                            sync_result.exit_code,
                            head_sha=head_sha,
                            snapshot_context=snapshot_context,
                            reason_code=sync_result.reason_code,
                            phase=sync_result.phase,
                            retryable=sync_result.retryable,
                            failures=sync_result.failures,
                        )
                unresolved_threads = [
                    thread for thread in threads if not _thread_is_resolved(thread)
                ]
                if unresolved_threads:
                    artifact = _write_resolve_threads_plan(
                        root=root,
                        contract=contract,
                        repo=repo,
                        pr_number=resolved_pr_number,
                        head_sha=head_sha,
                        diff_hash=current_diff_hash,
                        threads=unresolved_threads,
                    )
                    review_thread_artifacts = (artifact,)
                    review_thread_failures = _review_thread_blocking_failures(
                        unresolved_threads,
                        artifact_path=artifact["artifact_path"],
                    )
    except Exception as exc:
        failures = [
            pr_flow_contract.SubmitFailure(
                check="official-codex-review-thread",
                source=pr_url,
                detail=f"official Codex review thread inspection failed: {exc}",
            ),
        ]
        return _fail_submit(
            root,
            contract,
            EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="CODEX_THREAD_INSPECTION_FAILED",
            phase="submit_review_threads",
            retryable=True,
            failures=failures,
        )
    watch_result = _submit_wait_required_checks(
        root=root,
        runner=runner,
        contract=contract,
        pr_number=pr or pr_number,
        timeout_seconds=watch_timeout_seconds,
        poll_seconds=watch_poll_seconds,
    )
    if watch_result.failures:
        try:
            retry_code, retry_checks = _submit_accept_official_codex_retained_threads(
                root=root,
                runner=runner,
                contract=contract,
                pr_number=pr or pr_number,
                pr_url=pr_url,
                failures=watch_result.failures,
            )
        except GitHubDataUnavailable as exc:
            _print_github_data_unavailable(exc)
            failures = [
                pr_flow_contract.SubmitFailure(
                    check="official-codex-review-thread",
                    source=pr_url,
                    detail=f"official Codex retained thread read failed: {exc}",
                ),
            ]
            return _fail_submit(
                root,
                contract,
                EXCEPTION_REQUIRED_EXIT_CODE,
                head_sha=head_sha,
                snapshot_context=snapshot_context,
                reason_code="CODEX_THREAD_RETRY_UNAVAILABLE",
                phase="submit_review_threads",
                retryable=exc.retryable,
                failures=failures,
            )
        if retry_code != SUCCESS_EXIT_CODE:
            _ensure_submit_status_failure(
                root,
                contract,
                head_sha=head_sha,
                snapshot_context=snapshot_context,
                failure=pr_flow_contract.SubmitFailure(
                    check="official-codex-review-thread",
                    source=pr_url,
                    detail="official Codex retained thread auto-processing failed",
                ),
            )
            return retry_code
        if retry_checks:
            watch_result = _submit_wait_required_checks(
                root=root,
                runner=runner,
                contract=contract,
                pr_number=pr or pr_number,
                timeout_seconds=watch_timeout_seconds,
                poll_seconds=watch_poll_seconds,
            )
    if watch_result.failures or review_thread_failures:
        final_failures = (*review_thread_failures, *watch_result.failures)
        return _fail_submit(
            root, contract, EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="REQUIRED_CHECKS_FAILED",
            phase="submit_wait_checks",
            retryable=True,
            failures=final_failures,
            diagnostics=watch_result.diagnostics,
            checkpoint_statuses=watch_result.checkpoint_statuses,
            evidence_artifacts=review_thread_artifacts,
        )
    lifecycle_code = _submit_complete_lifecycle(
        root=root,
        runner=runner,
        contract=contract,
        pr_number=pr or pr_number,
        head_sha=head_sha,
        snapshot_context=snapshot_context,
        timeout_seconds=watch_timeout_seconds,
        poll_seconds=watch_poll_seconds,
    )
    if lifecycle_code != SUCCESS_EXIT_CODE:
        _ensure_submit_status_failure(
            root,
            contract,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            failure=pr_flow_contract.SubmitFailure(
                check="pr-lifecycle",
                source=f"PR #{pr or pr_number}",
                detail="PR lifecycle or cleanup failed",
            ),
        )
        return lifecycle_code  # _submit_complete_lifecycle emits its own stop status
    _clear_submit_status(root, contract)
    return SUCCESS_EXIT_CODE


def _submit_preflight_failures(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    base_branch: str = "main",
) -> list[pr_flow_contract.SubmitFailure]:
    failures: list[pr_flow_contract.SubmitFailure] = []
    repo = _current_github_repo(root, runner)
    settings = _gh_api_object(root, runner, f"repos/{repo}")
    for key, expected in contract.required_settings.items():
        actual = bool(settings.get(key))
        if actual == expected:
            continue
        suffix = "enabled" if expected else "disabled"
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="github-settings",
                source=f"repos/{repo}",
                detail=f"{key} must be {suffix}",
            )
        )
    configured = _required_status_check_names(
        root=root,
        runner=runner,
        repo=repo,
        branch=base_branch,
    )
    missing = [name for name in contract.required_checks if name not in configured]
    if missing:
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="required-checks",
                source=base_branch,
                detail="missing required checks: " + ", ".join(missing),
            )
        )
    return failures


def _submit_branch_intent_failures(
    *,
    root: Path,
    runner: Runner,
) -> list[pr_flow_contract.SubmitFailure]:
    try:
        _validate_branch_intent_coverage(
            root,
            runner,
            pr_number=_current_pr_number(root, runner),
        )
    except CommitIntentError as exc:
        return [
            pr_flow_contract.SubmitFailure(
                check="issue-intent",
                source=".local/pr-flow/intents",
                detail=_commit_intent_failure_detail(exc),
            )
        ]
    return []


def _commit_intent_failure_detail(exc: CommitIntentError) -> str:
    if not exc.details:
        return str(exc)
    return f"{exc}: " + ", ".join(exc.details)


def _current_github_repo(root: Path, runner: Runner) -> str:
    result = _run_github_read_command(
        root,
        runner,
        ["gh", "repo", "view", "--json", "nameWithOwner"],
    )
    if result.returncode != 0:
        raise _github_data_unavailable(
            "GitHub repository metadata unavailable",
            "gh repo view --json nameWithOwner",
            result,
        )
    payload = _json_object_from_result(result, "gh repo view --json nameWithOwner")
    repo = _single_line_text(payload.get("nameWithOwner"))
    if not repo:
        raise GitHubDataUnavailable(
            "GitHub repository metadata incomplete",
            details=("nameWithOwner",),
        )
    return repo


def _submit_snapshot_context(
    root: Path,
    runner: Runner,
    *,
    target_pr: str | None = None,
) -> SubmitSnapshotContext:
    repository = ""
    pr_number = _single_line_text(target_pr)
    head_branch = ""
    try:
        repository = _current_github_repo(root, runner)
    except GitHubDataUnavailable:
        repository = ""
    try:
        head_branch = _current_branch(root, runner)
    except CommitIntentError:
        head_branch = ""
    if not pr_number:
        try:
            pr_number = _current_pr_number(root, runner)
        except GitHubDataUnavailable:
            pr_number = ""
    return SubmitSnapshotContext(
        repository=repository,
        pr_number=pr_number,
        head_branch=head_branch,
    )


def _submit_first_stage_fragment_failures(
    *,
    root: Path,
    contract: pr_flow_contract.PRFlowContract,
    head_sha: str,
    diff_hash: str,
) -> tuple[list[pr_flow_contract.SubmitFailure], bool]:
    failures: list[pr_flow_contract.SubmitFailure] = []
    has_blocking = False
    for role in ("standards", "spec"):
        role_failures, role_blocking = _submit_fragment_failures_for_role(
            root=root,
            contract=contract,
            role=role,
            expected_head_sha=head_sha,
            expected_diff_hash=diff_hash,
        )
        failures.extend(role_failures)
        has_blocking = has_blocking or role_blocking
    return failures, has_blocking


def _submit_fragment_failures_for_role(
    *,
    root: Path,
    contract: pr_flow_contract.PRFlowContract,
    role: str,
    expected_head_sha: str | None = None,
    expected_diff_hash: str | None = None,
) -> tuple[list[pr_flow_contract.SubmitFailure], bool]:
    relative = contract.reviewer_fragments[role]
    path = root / relative
    source = relative.as_posix()
    if not path.is_file():
        return [
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment is missing",
            )
        ], False
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return [
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment is invalid JSON",
            )
        ], False
    if not isinstance(payload, dict):
        return [
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment must be a JSON object",
            )
        ], False
    failures: list[pr_flow_contract.SubmitFailure] = []
    if tuple(payload) != contract.fragment_fields:
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment fields must be schema/head/diff/findings",
            )
        )
    if payload.get("schema") != contract.version:
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment schema must be {contract.version}",
            )
        )
    if (
        not failures
        and expected_head_sha is not None
        and expected_diff_hash is not None
        and _single_line_text(payload.get("head")) != expected_head_sha
        and _single_line_text(payload.get("diff")) == expected_diff_hash
    ):
        payload["head"] = expected_head_sha
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} fragment head refresh failed",
                )
            )
    if (
        expected_head_sha is not None
        and _single_line_text(payload.get("head")) != expected_head_sha
    ):
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment head is stale",
            )
        )
    if (
        expected_diff_hash is not None
        and _single_line_text(payload.get("diff")) != expected_diff_hash
    ):
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment diff is stale",
            )
        )
    freshness_failed = any(
        failure.detail
        in {f"{role} fragment head is stale", f"{role} fragment diff is stale"}
        for failure in failures
    )
    findings = payload.get("findings")
    if not isinstance(findings, list):
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="local-review",
                source=source,
                detail=f"{role} fragment findings must be a list",
            )
        )
        return failures, False
    has_blocking = False
    allowed = set(contract.blocking_severities) | set(contract.retained_severities)
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} finding {index} must be an object",
                )
            )
            continue
        if tuple(finding) != contract.fragment_finding_fields:
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} finding {index} fields must be severity/detail",
                )
            )
            continue
        severity = _single_line_text(finding.get("severity"))
        detail = pr_flow_contract.normalize_detail(
            finding.get("detail"),
            max_chars=contract.detail_max_chars,
        )
        if severity not in allowed:
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} finding {index} severity is invalid",
                )
            )
            continue
        if not detail:
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} finding {index} detail is required",
                )
            )
            continue
        if severity in contract.blocking_severities:
            if not freshness_failed:
                has_blocking = True
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} {severity}: {detail}",
                )
            )
    return failures, has_blocking


def _submit_security_fragment_failures(
    *,
    root: Path,
    contract: pr_flow_contract.PRFlowContract,
    head_sha: str,
    diff_hash: str,
) -> tuple[list[pr_flow_contract.SubmitFailure], bool]:
    return _submit_fragment_failures_for_role(
        root=root,
        contract=contract,
        role="security",
        expected_head_sha=head_sha,
        expected_diff_hash=diff_hash,
    )


def _submit_current_diff_hash(root: Path, runner: Runner) -> str:
    result = runner.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "origin/main...HEAD",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        raise GitHubDataUnavailable(
            "current PR diff unavailable",
            details=(_single_line_text(result.stderr), _single_line_text(result.stdout)),
        )
    return hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()


def _submit_review_state(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    head_sha: str,
    diff_hash: str,
    official_review_skip_authorized_by: str | None = None,
    official_review_skip_evidence: str | None = None,
) -> tuple[SubmitReviewState, list[pr_flow_contract.SubmitFailure]]:
    reviews: dict[str, dict[str, str]] = {}
    retained: list[dict[str, str]] = []
    failures: list[pr_flow_contract.SubmitFailure] = []
    for role in ("standards", "spec", "security"):
        relative = contract.reviewer_fragments[role]
        source = relative.as_posix()
        payload = _read_json_object(root / relative) or {}
        fragment_head = _single_line_text(payload.get("head"))
        fragment_diff = _single_line_text(payload.get("diff"))
        if fragment_head != head_sha:
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} fragment head is stale",
                )
            )
        if fragment_diff != diff_hash:
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check="local-review",
                    source=source,
                    detail=f"{role} fragment diff is stale",
                )
            )
        reviews[role] = {"head": head_sha, "diff": diff_hash}
        findings = payload.get("findings")
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            severity = _single_line_text(finding.get("severity"))
            if severity not in contract.retained_severities:
                continue
            retained.append(
                {
                    "severity": severity,
                    "source": role,
                    "detail": pr_flow_contract.normalize_detail(
                        finding.get("detail"),
                        max_chars=contract.detail_max_chars,
                    ),
                }
            )
    return (
        SubmitReviewState(
            reviews=reviews,
            retained=retained,
            official_review=_submit_official_review_decision(
                root=root,
                runner=runner,
                authorized_by=official_review_skip_authorized_by,
                evidence=official_review_skip_evidence,
            ),
        ),
        failures,
    )


def _submit_official_review_decision(
    *,
    root: Path,
    runner: Runner,
    authorized_by: str | None = None,
    evidence: str | None = None,
) -> dict[str, str]:
    authorized_by_text = _single_line_text(authorized_by)
    evidence_text = _single_line_text(evidence)
    if authorized_by_text and evidence_text:
        return {
            "decision": "skip_user_authorized",
            "authorized_by": authorized_by_text,
            "evidence": evidence_text,
        }
    if _submit_requires_official_codex_review(root=root, runner=runner):
        return {"decision": "required"}
    return {"decision": "skip_risk_low"}


def _official_review_skip_authorization_failure(
    *,
    authorized_by: str | None = None,
    evidence: str | None = None,
) -> pr_flow_contract.SubmitFailure | None:
    authorized_by_text = _single_line_text(authorized_by)
    evidence_text = _single_line_text(evidence)
    if bool(authorized_by_text) == bool(evidence_text):
        return None
    return pr_flow_contract.SubmitFailure(
        check="PR Flow / evidence",
        source="official_review",
        detail=(
            "official review skip authorization requires both "
            "authorized_by and evidence"
        ),
    )


def _submit_requires_official_codex_review(*, root: Path, runner: Runner) -> bool:
    changed_files = _submit_current_changed_files(root, runner)
    if changed_files is None:
        return True
    return any(_is_high_risk_path(path) for path in changed_files)


def _submit_current_changed_files(root: Path, runner: Runner) -> tuple[str, ...] | None:
    result = runner.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-only",
            "origin/main...HEAD",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return None
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def _submit_current_diff_fingerprint(root: Path, runner: Runner) -> dict[str, Any] | None:
    changed_files = _submit_current_changed_files(root, runner)
    if changed_files is None:
        return None
    try:
        diff_hash = _submit_current_diff_hash(root, runner)
    except GitHubDataUnavailable:
        return None
    head = runner.run(["git", "rev-parse", "HEAD"], cwd=root)
    if head.returncode != 0:
        return None
    return {
        "base_ref": "origin/main",
        "head_sha": _command_stdout(head),
        "diff_files_hash": diff_hash,
        "changed_files": list(changed_files),
    }


def _submit_pr_evidence(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    head_sha: str,
    diff_hash: str,
    review_state: SubmitReviewState,
) -> dict[str, Any]:
    return {
        "schema": contract.version,
        "head": head_sha,
        "diff": diff_hash,
        "reviews": review_state.reviews,
        "official_review": review_state.official_review,
        "issues": _submit_issue_evidence(root=root, runner=runner),
        "retained": review_state.retained,
    }


def _submit_thread_processing_payload(
    root: Path,
    current_fingerprint: dict[str, Any] | None,
) -> dict[str, Any]:
    fingerprint = current_fingerprint if isinstance(current_fingerprint, dict) else {}
    closure_evidence = _read_thread_closure_evidence(root)
    return {
        "schema_version": THREAD_PROCESSING_SCHEMA_VERSION,
        "changed_files": _string_list(fingerprint.get("changed_files")),
        "diff_fingerprint": fingerprint,
        "external_findings": closure_evidence,
    }


def _read_thread_closure_evidence(root: Path) -> list[dict[str, Any]]:
    path = root / ".local" / "pr-flow" / "thread-closure-evidence.json"
    payload = _read_json_object(path)
    if not payload:
        return []
    findings = payload.get("external_findings")
    if not isinstance(findings, list):
        return []
    return [item for item in findings if isinstance(item, dict)]


def _fingerprint_diff_files_hash(fingerprint: dict[str, Any] | None) -> str:
    if not isinstance(fingerprint, dict):
        return ""
    return _single_line_text(fingerprint.get("diff_files_hash"))


def _submit_official_codex_retained_from_payload(
    payload: dict[str, Any],
    *,
    contract: pr_flow_contract.PRFlowContract,
) -> list[dict[str, str]]:
    retained: list[dict[str, str]] = []
    for item in payload.get("external_findings") or []:
        if not isinstance(item, dict):
            continue
        if _single_line_text(item.get("source")) != "official_codex_review_thread":
            continue
        severity = _single_line_text(item.get("severity"))
        if severity not in contract.retained_severities:
            continue
        detail = pr_flow_contract.normalize_detail(
            item.get("body") or item.get("detail") or item.get("title"),
            max_chars=contract.detail_max_chars,
        )
        if not detail:
            detail = f"official Codex {severity} retained finding"
        retained.append(
            {
                "severity": severity,
                "source": "official_codex",
                "detail": detail,
            }
        )
    return retained


def _review_state_with_retained(
    review_state: SubmitReviewState,
    retained: Sequence[dict[str, str]],
) -> SubmitReviewState:
    if not retained:
        return review_state
    merged = [dict(item) for item in review_state.retained]
    seen = {
        (
            _single_line_text(item.get("severity")),
            _single_line_text(item.get("source")),
            _single_line_text(item.get("detail")),
        )
        for item in merged
    }
    for entry in retained:
        key = (
            _single_line_text(entry.get("severity")),
            _single_line_text(entry.get("source")),
            _single_line_text(entry.get("detail")),
        )
        if key in seen:
            continue
        merged.append(dict(entry))
        seen.add(key)
    return SubmitReviewState(
        reviews=review_state.reviews,
        retained=merged,
        official_review=review_state.official_review,
    )


def _submit_issue_evidence(*, root: Path, runner: Runner) -> dict[str, Any]:
    branch = _current_branch(root, runner)
    pr_number = _current_pr_number(root, runner)
    branch_intent = _read_json_object(_branch_intent_path(root, branch)) or {}
    commits = [
        item for item in branch_intent.get("commits", []) if isinstance(item, dict)
    ]
    by_sha = {
        _single_line_text(item.get("commit_sha")): item
        for item in commits
        if _single_line_text(item.get("commit_sha"))
    }
    evidence_commits: list[dict[str, Any]] = []
    for sha in _current_branch_commit_shas(root, runner, base_ref="origin/main"):
        item = by_sha.get(sha)
        if item is None:
            if _is_github_update_branch_merge_commit(
                root,
                runner,
                sha,
                base_ref="origin/main",
                pr_number=pr_number,
            ):
                evidence_commits.append({"sha": sha, "no_issue": True})
                continue
            raise CommitIntentError(
                "branch intent does not cover all current branch commits",
                reason_code="BRANCH_INTENT_COVERAGE_MISSING",
                details=(sha,),
            )
        issue_policy = _single_line_text(item.get("issue_policy"))
        if issue_policy == "no_issue":
            authorization = item.get("no_issue_authorization")
            if not _valid_no_issue_authorization(authorization):
                raise CommitIntentError(
                    "no-Issue commit intent is missing authorization",
                    reason_code="NO_ISSUE_AUTHORIZATION_MISSING",
                    details=(sha,),
                )
            evidence_commits.append({"sha": sha, "no_issue": True})
            continue
        if issue_policy != "issues":
            raise CommitIntentError(
                "commit intent issue policy is invalid",
                reason_code="COMMIT_ISSUE_POLICY_INVALID",
                details=(sha,),
            )
        issues = [
            {
                "number": _positive_int_from_payload(issue.get("number")),
                "role": _single_line_text(issue.get("role")),
            }
            for issue in item.get("issues", [])
            if isinstance(issue, dict)
            and _positive_int_from_payload(issue.get("number")) is not None
            and _single_line_text(issue.get("role")) in VALID_INTENT_ROLES
        ] if isinstance(item.get("issues"), list) else []
        if issues:
            evidence_commits.append({"sha": sha, "issues": issues})
            continue
        raise CommitIntentError(
            "commit intent is missing valid issue bindings",
            reason_code="COMMIT_ISSUE_BINDING_MISSING",
            details=(sha,),
        )
    refs: list[dict[str, Any]] = []
    seen_refs: set[tuple[int, str]] = set()
    for item in evidence_commits:
        commit_issues = item.get("issues")
        if not isinstance(commit_issues, list):
            continue
        for issue in commit_issues:
            if not isinstance(issue, dict):
                continue
            number = _positive_int_from_payload(issue.get("number"))
            role = _single_line_text(issue.get("role"))
            if number is None or role not in VALID_INTENT_ROLES:
                continue
            key = (number, role)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            refs.append({"number": number, "role": role})
    return {"commits": evidence_commits, "refs": refs}


def _valid_no_issue_authorization(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        _single_line_text(value.get(field))
        for field in ("reason", "authorized_by", "evidence")
    )


def _sync_submit_pr_evidence(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    title: str | None,
    target_pr: str | None,
    evidence: dict[str, Any],
) -> SubmitSyncResult:
    local = root / ".local" / "pr-flow"
    managed_body = _render_submit_managed_body(contract, evidence)
    native_links_body = _render_submit_github_native_links(evidence)
    view = _run_github_read_command(
        root,
        runner,
        _gh_pr_view_command(target_pr, "number,url,state,isDraft"),
    )
    if view.returncode == 0:
        metadata = _json_from_result(view)
        pr_number = str(metadata.get("number") or "")
        pr_url = _single_line_text(metadata.get("url"))
        body_view = _run_github_read_command(
            root,
            runner,
            _gh_pr_view_command(pr_number, "body"),
        )
        if body_view.returncode != 0:
            _print_command_failure("gh pr view --json body", body_view)
            return _submit_sync_failure(
                body_view.returncode,
                pr_number=pr_number,
                pr_url=pr_url,
                reason_code="PR_BODY_UNAVAILABLE",
                check="github",
                source="gh pr view --json body",
                detail=_command_failure_detail("gh pr view --json body", body_view),
            )
        existing_body = str(_json_from_result(body_view).get("body") or "")
        body_file = _write_managed_body_file(
            local,
            existing_body,
            managed_body,
            native_links_body,
        )
        edit = runner.run(
            ["gh", "pr", "edit", pr_number, "--body-file", str(body_file)],
            cwd=root,
        )
        if edit.returncode != 0:
            _print_command_failure("gh pr edit", edit)
            return _submit_sync_failure(
                edit.returncode,
                pr_number=pr_number,
                pr_url=pr_url,
                reason_code="PR_BODY_SYNC_FAILED",
                check="github",
                source="gh pr edit",
                detail=_command_failure_detail("gh pr edit", edit),
            )
        return SubmitSyncResult(SUCCESS_EXIT_CODE, pr_number=pr_number, pr_url=pr_url)
    if target_pr:
        _print_command_failure("gh pr view", view)
        return _submit_sync_failure(
            view.returncode,
            pr_number=target_pr,
            reason_code="PR_METADATA_UNAVAILABLE",
            check="github",
            source="gh pr view",
            detail=_command_failure_detail("gh pr view", view),
        )
    if not title:
        print("error: --title is required when no PR exists", file=sys.stderr)
        return _submit_sync_failure(
            GENERAL_FAILURE_EXIT_CODE,
            reason_code="PR_TITLE_REQUIRED",
            check="pr-sync",
            source="--title",
            detail="--title is required when no PR exists",
            retryable=True,
        )
    branch = _current_branch(root, runner)
    remote_head = runner.run(["git", "ls-remote", "--heads", "origin", branch], cwd=root)
    if remote_head.returncode != 0 or not _command_stdout(remote_head):
        detail = (
            _command_failure_detail("git ls-remote --heads origin", remote_head)
            if remote_head.returncode != 0
            else f"remote branch missing: git push -u origin {branch}"
        )
        return _submit_sync_failure(
            EXCEPTION_REQUIRED_EXIT_CODE,
            reason_code="REMOTE_BRANCH_MISSING",
            check="git-remote",
            source=f"origin/{branch}",
            detail=detail,
        )
    body_file = _write_managed_body_file(
        local,
        _pr_template_body(root),
        managed_body,
        native_links_body,
    )
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
        return _submit_sync_failure(
            create.returncode,
            reason_code="PR_CREATE_FAILED",
            check="github",
            source="gh pr create",
            detail=_command_failure_detail("gh pr create", create),
        )
    pr_url = _command_stdout(create)
    return SubmitSyncResult(
        SUCCESS_EXIT_CODE,
        pr_number=_pr_number_from_url(pr_url),
        pr_url=pr_url,
    )


def _submit_sync_failure(
    exit_code: int,
    *,
    reason_code: str,
    check: str,
    source: str,
    detail: str,
    pr_number: str = "",
    pr_url: str = "",
    retryable: bool = True,
) -> SubmitSyncResult:
    return SubmitSyncResult(
        exit_code=exit_code or EXCEPTION_REQUIRED_EXIT_CODE,
        pr_number=pr_number,
        pr_url=pr_url,
        reason_code=reason_code,
        phase="submit_sync_pr",
        retryable=retryable,
        failures=(
            pr_flow_contract.SubmitFailure(
                check=check,
                source=source,
                detail=detail,
            ),
        ),
    )


def _gh_pr_view_command(pr_number: str | None, fields: str) -> list[str]:
    command = ["gh", "pr", "view"]
    if pr_number:
        command.append(pr_number)
    command.extend(["--json", fields])
    return command


def _submit_request_codex_review(
    *,
    root: Path,
    runner: Runner,
    pr_number: str,
    pr_url: str,
    head_sha: str,
) -> int:
    try:
        if _current_head_codex_trigger_exists(
            pr_url=pr_url,
            head_sha=head_sha,
            root=root,
            runner=runner,
        ):
            return SUCCESS_EXIT_CODE
    except GitHubDataUnavailable as exc:
        _print_github_data_unavailable(exc)
        return EXCEPTION_REQUIRED_EXIT_CODE
    local = root / ".local" / "pr-flow"
    local.mkdir(parents=True, exist_ok=True)
    body = render_codex_review_request(
        pr_url=pr_url,
        head_sha=head_sha,
        review_scope=(),
    )
    comment_file = local / "codex-review-request.md"
    comment_file.write_text(body, encoding="utf-8")
    comment = runner.run(
        ["gh", "pr", "comment", pr_number, "--body-file", str(comment_file)],
        cwd=root,
    )
    if comment.returncode != 0:
        _print_command_failure("gh pr comment", comment)
        return comment.returncode
    return SUCCESS_EXIT_CODE


def _submit_accept_official_codex_retained_threads(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    pr_number: str,
    pr_url: str,
    failures: Sequence[pr_flow_contract.SubmitFailure],
) -> tuple[int, bool]:
    if not _submit_should_retry_official_codex_retained(failures):
        return SUCCESS_EXIT_CODE, False
    pr_info = _github_pr_info_from_url(pr_url)
    if pr_info is None:
        return SUCCESS_EXIT_CODE, False
    repo, resolved_pr_number = pr_info
    threads = _current_pr_review_threads(
        root=root,
        runner=runner,
        repo=repo,
        pr_number=resolved_pr_number,
    )
    retained: list[dict[str, str]] = []
    changed = False
    for thread in threads:
        if _thread_is_resolved(thread):
            continue
        entry = _submit_official_codex_retained_entry(
            contract=contract,
            thread=thread,
        )
        if entry is None:
            continue
        thread_id = _thread_id(thread)
        if not thread_id:
            continue
        finding = _external_finding_for_review_thread(
            repo=repo,
            pr_number=resolved_pr_number,
            thread=thread,
            status="accepted",
        )
        code = _reply_to_review_thread(
            root=root,
            runner=runner,
            thread_id=thread_id,
            body=_accepted_review_thread_reply(finding),
        )
        if code != SUCCESS_EXIT_CODE:
            return code, changed
        code = resolve_review_threads(
            repo_root=root,
            runner=runner,
            thread_ids=(thread_id,),
        )
        if code != SUCCESS_EXIT_CODE:
            return code, changed
        thread["isResolved"] = True
        retained.append(entry)
        changed = True
        print(f"accepted official Codex review thread: {thread_id}")
    if not retained:
        return SUCCESS_EXIT_CODE, changed
    code = _submit_append_retained_to_pr_body(
        root=root,
        runner=runner,
        contract=contract,
        pr_number=pr_number,
        retained=retained,
    )
    if code != SUCCESS_EXIT_CODE:
        return code, changed
    return SUCCESS_EXIT_CODE, changed


def _submit_should_retry_official_codex_retained(
    failures: Sequence[pr_flow_contract.SubmitFailure],
) -> bool:
    for failure in failures:
        if failure.check != "PR Flow / review-status":
            continue
        detail = failure.detail.casefold()
        if "pending" in detail or "timed out" in detail:
            continue
        return True
    return False


def _submit_official_codex_retained_entry(
    *,
    contract: pr_flow_contract.PRFlowContract,
    thread: dict[str, Any],
) -> dict[str, str] | None:
    severity = _codex_thread_severity(thread)
    if severity not in contract.retained_severities:
        return None
    detail = pr_flow_contract.normalize_detail(
        _codex_thread_body(thread),
        max_chars=contract.detail_max_chars,
    )
    if not detail:
        detail = f"official Codex {severity} retained finding"
    return {
        "severity": severity,
        "source": "official_codex",
        "detail": detail,
    }


def _submit_append_retained_to_pr_body(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    pr_number: str,
    retained: Sequence[dict[str, str]],
) -> int:
    body_view = _run_github_read_command(
        root,
        runner,
        _gh_pr_view_command(pr_number, "body"),
    )
    if body_view.returncode != 0:
        _print_command_failure("gh pr view --json body", body_view)
        return EXCEPTION_REQUIRED_EXIT_CODE
    existing_body = str(_json_from_result(body_view).get("body") or "")
    payload, errors = pr_review_evidence._extract_contract_v1_evidence(existing_body)
    if payload is None or errors:
        details = list(errors) or ["PR Flow evidence block is missing"]
        _print_state(
            "EXCEPTION_REQUIRED",
            "PR Evidence JSON unavailable for retained findings",
            repo_root=root,
            reason_code="PR_EVIDENCE_UNAVAILABLE",
            phase="submit_official_codex",
            dispatch_target="github",
            details=details,
            next_actions=("rerun pr-submit after PR Evidence is synced",),
        )
        return EXCEPTION_REQUIRED_EXIT_CODE
    updated: dict[str, Any] = dict(payload)
    current_retained = [
        dict(item)
        for item in updated.get("retained", [])
        if isinstance(item, dict)
    ]
    seen = {
        (
            _single_line_text(item.get("severity")),
            _single_line_text(item.get("source")),
            _single_line_text(item.get("detail")),
        )
        for item in current_retained
    }
    for entry in retained:
        key = (
            _single_line_text(entry.get("severity")),
            _single_line_text(entry.get("source")),
            _single_line_text(entry.get("detail")),
        )
        if key in seen:
            continue
        current_retained.append(dict(entry))
        seen.add(key)
    updated["retained"] = current_retained
    managed_body = _render_submit_managed_body(contract, updated)
    body_file = _write_managed_body_file(
        root / ".local" / "pr-flow",
        existing_body,
        managed_body,
    )
    edit = runner.run(
        ["gh", "pr", "edit", pr_number, "--body-file", str(body_file)],
        cwd=root,
    )
    if edit.returncode != 0:
        _print_command_failure("gh pr edit", edit)
        return EXCEPTION_REQUIRED_EXIT_CODE
    return SUCCESS_EXIT_CODE


def _submit_wait_required_checks(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    pr_number: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> RequiredCheckWaitResult:
    deadline = time.monotonic() + max(timeout_seconds, 0)
    while True:
        rollup = _submit_required_check_failures(
            root=root,
            runner=runner,
            contract=contract,
            pr_number=pr_number,
        )
        if not rollup.pending:
            return RequiredCheckWaitResult(
                failures=rollup.failures,
                diagnostics=rollup.diagnostics,
                checkpoint_statuses=rollup.checkpoint_statuses,
            )
        if time.monotonic() >= deadline:
            failure_by_check = {failure.check: failure for failure in rollup.failures}
            pending_by_check = {failure.check: failure for failure in rollup.pending}
            timed_out: list[pr_flow_contract.SubmitFailure] = []
            for name in contract.required_checks:
                failure = failure_by_check.get(name)
                if failure is not None:
                    timed_out.append(failure)
                    continue
                pending_failure = pending_by_check.get(name)
                if pending_failure is not None:
                    timed_out.append(
                        pr_flow_contract.SubmitFailure(
                            check=pending_failure.check,
                            source=pending_failure.source,
                            detail="required check timed out while pending",
                        )
                    )
            checkpoints = _required_check_checkpoint_statuses(
                contract=contract,
                failures=timed_out,
                pending=(),
            )
            return RequiredCheckWaitResult(
                failures=tuple(timed_out),
                diagnostics=rollup.diagnostics,
                checkpoint_statuses=checkpoints,
            )
        time.sleep(max(poll_seconds, 0))


def _submit_required_check_failures(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    pr_number: str,
) -> RequiredCheckRollup:
    rollup_latest, rollup_diagnostics = _current_head_required_check_results(
        root=root,
        runner=runner,
        contract=contract,
        pr_number=pr_number,
    )
    if rollup_latest is not None:
        latest = rollup_latest
        diagnostics = rollup_diagnostics
    else:
        failure = pr_flow_contract.SubmitFailure(
            check="required-checks",
            source="",
            detail="current-head required checks unavailable",
        )
        return RequiredCheckRollup(failures=(failure,))
    by_name = {_json_check_display_name(check): check for check in latest}
    failures: list[pr_flow_contract.SubmitFailure] = []
    pending: list[pr_flow_contract.SubmitFailure] = []
    for name in contract.required_checks:
        check = by_name.get(name)
        if check is None:
            pending.append(
                pr_flow_contract.SubmitFailure(
                    check=name,
                    source="",
                    detail="required check is pending",
                )
            )
            continue
        source = _single_line_text(check.get("link"))
        if _json_check_failed(check):
            failures.append(
                pr_flow_contract.SubmitFailure(
                    check=name,
                    source=source,
                    detail=_json_check_failure_detail(check),
                )
            )
        elif not _json_check_passed(check):
            pending.append(
                pr_flow_contract.SubmitFailure(
                    check=name,
                    source=source,
                    detail="required check is pending",
                )
            )
    return RequiredCheckRollup(
        failures=tuple(failures),
        pending=tuple(pending),
        diagnostics=tuple(diagnostics),
        checkpoint_statuses=_required_check_checkpoint_statuses(
            contract=contract,
            failures=failures,
            pending=pending,
        ),
    )


def _required_check_checkpoint_statuses(
    *,
    contract: pr_flow_contract.PRFlowContract,
    failures: Sequence[pr_flow_contract.SubmitFailure],
    pending: Sequence[pr_flow_contract.SubmitFailure],
) -> tuple[dict[str, str], ...]:
    _ = contract
    if failures:
        return (
            {
                "checkpoint_name": "required_checks",
                "status": "failed",
                "summary": "; ".join(f"{failure.check}: {failure.detail}" for failure in failures),
                "evidence_location": next(
                    (failure.source for failure in failures if failure.source),
                    "",
                ),
            },
        )
    if pending:
        return (
            {
                "checkpoint_name": "required_checks",
                "status": "pending",
                "summary": "; ".join(f"{failure.check}: {failure.detail}" for failure in pending),
                "evidence_location": next(
                    (failure.source for failure in pending if failure.source),
                    "",
                ),
            },
        )
    return (
        {
            "checkpoint_name": "required_checks",
            "status": "passed",
            "summary": "all required checks passed",
            "evidence_location": "",
        },
    )


def _submit_pr_head_failures(
    *,
    root: Path,
    runner: Runner,
    pr_number: str,
    expected_head_sha: str,
) -> list[pr_flow_contract.SubmitFailure]:
    view = _run_github_read_command(
        root,
        runner,
        _gh_pr_view_command(pr_number, "headRefOid"),
    )
    if view.returncode != 0:
        raise _github_data_unavailable(
            "GitHub PR head unavailable",
            "gh pr view --json headRefOid",
            view,
        )
    metadata = _json_object_from_result(view, "gh pr view --json headRefOid")
    actual_head = _single_line_text(metadata.get("headRefOid"))
    if not actual_head:
        raise GitHubDataUnavailable(
            "GitHub PR head unavailable",
            details=("gh pr view --json headRefOid",),
        )
    if actual_head == expected_head_sha:
        return []
    return [
        pr_flow_contract.SubmitFailure(
            check="github",
            source="",
            detail="PR head does not match local HEAD",
        )
    ]


def _submit_complete_lifecycle(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    pr_number: str,
    head_sha: str,
    snapshot_context: SubmitSnapshotContext,
    timeout_seconds: float,
    poll_seconds: float,
) -> int:
    ready = runner.run(["gh", "pr", "ready", pr_number], cwd=root)
    if ready.returncode != 0 and not _pr_ready_already_ready(ready):
        return _submit_lifecycle_command_failure(
            root=root,
            contract=contract,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            command_label="gh pr ready",
            phase="submit_ready",
            result=ready,
        )
    merge = runner.run(
        [
            "gh",
            "pr",
            "merge",
            pr_number,
            "--merge",
            "--auto",
            "--match-head-commit",
            head_sha,
        ],
        cwd=root,
    )
    if merge.returncode != 0 and not _auto_merge_already_enabled(merge):
        return _submit_lifecycle_command_failure(
            root=root,
            contract=contract,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            command_label="gh pr merge --auto",
            phase="submit_merge",
            result=merge,
        )
    metadata = _submit_wait_for_merged_pr(
        root=root,
        runner=runner,
        pr_number=pr_number,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    if metadata is None:
        failures = (
            pr_flow_contract.SubmitFailure(
                check="pr-lifecycle",
                source=f"PR #{pr_number}",
                detail="PR merge timed out",
            ),
        )
        return _fail_submit(
            root,
            contract,
            EXCEPTION_REQUIRED_EXIT_CODE,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            reason_code="PR_MERGE_TIMEOUT",
            phase="submit_merge",
            retryable=True,
            failures=failures,
        )
    return _submit_cleanup_merged_pr(
        root=root,
        runner=runner,
        contract=contract,
        head_sha=head_sha,
        snapshot_context=snapshot_context,
        metadata=metadata,
    )


def _submit_lifecycle_command_failure(
    *,
    root: Path,
    contract: pr_flow_contract.PRFlowContract,
    head_sha: str,
    snapshot_context: SubmitSnapshotContext,
    command_label: str,
    phase: str,
    result: CommandResult,
) -> int:
    _print_command_failure(command_label, result)
    return _fail_submit(
        root,
        contract,
        EXCEPTION_REQUIRED_EXIT_CODE,
        head_sha=head_sha,
        snapshot_context=snapshot_context,
        reason_code="PR_LIFECYCLE_COMMAND_FAILED",
        phase=phase,
        retryable=True,
        failures=(
            pr_flow_contract.SubmitFailure(
                check="pr-lifecycle",
                source=command_label,
                detail=_command_failure_detail(command_label, result),
            ),
        ),
    )


def _command_failure_detail(command_label: str, result: CommandResult) -> str:
    detail = (
        _single_line_text(result.stderr)
        or _single_line_text(result.stdout)
        or f"exit_code={result.returncode}"
    )
    return f"{command_label} failed: {detail}"


def _submit_merged_pr_metadata(
    *,
    root: Path,
    runner: Runner,
    pr_number: str,
) -> dict[str, Any] | None:
    view = runner.run(
        [
            "gh",
            "pr",
            "view",
            pr_number,
            "--json",
            "number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
        ],
        cwd=root,
    )
    if view.returncode != 0:
        return None
    metadata = _json_object_from_result(
        view,
        "gh pr view --json number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
    )
    if _single_line_text(metadata.get("state")).upper() == "MERGED":
        return metadata
    return None


def _submit_wait_for_merged_pr(
    *,
    root: Path,
    runner: Runner,
    pr_number: str,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(timeout_seconds, 0)
    while True:
        metadata = _submit_merged_pr_metadata(
            root=root,
            runner=runner,
            pr_number=pr_number,
        )
        if metadata is not None:
            return metadata
        if time.monotonic() >= deadline:
            return None
        time.sleep(max(poll_seconds, 0))


def _pr_ready_already_ready(result: CommandResult) -> bool:
    text = f"{result.stdout}\n{result.stderr}".casefold()
    return ("already" in text and "ready" in text) or "not a draft" in text


def _auto_merge_already_enabled(result: CommandResult) -> bool:
    text = f"{result.stdout}\n{result.stderr}".casefold()
    return "already" in text and ("auto-merge" in text or "auto merge" in text)


def _submit_cleanup_merged_pr(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract | None = None,
    head_sha: str = "",
    snapshot_context: SubmitSnapshotContext | None = None,
    metadata: dict[str, Any],
) -> int:
    pr_ref = _single_line_text(metadata.get("number")) or "unknown"
    code = _cleanup_merged_pr_metadata(
        root=root,
        runner=runner,
        metadata=metadata,
        pr_ref=pr_ref,
    )
    if (
        code != SUCCESS_EXIT_CODE
        and contract is not None
        and _single_line_text(head_sha)
    ):
        _ensure_submit_status_failure(
            root,
            contract,
            head_sha=head_sha,
            snapshot_context=snapshot_context,
            failure=pr_flow_contract.SubmitFailure(
                check="pr-lifecycle",
                source=f"PR #{pr_ref}",
                detail="post-merge cleanup failed",
            ),
        )
    return code


def _cleanup_merged_pr_metadata(
    *,
    root: Path,
    runner: Runner,
    metadata: dict[str, Any],
    pr_ref: str,
) -> int:
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

    fetch = runner.run(["git", "fetch", "--prune", "origin"], cwd=root)
    if fetch.returncode != 0:
        _print_command_failure("git fetch --prune origin", fetch)
        return EXCEPTION_REQUIRED_EXIT_CODE

    base_worktree = _branch_worktree_path(root, runner, base_branch)
    sync_root = base_worktree or root
    if base_worktree is None:
        switched = runner.run(["git", "switch", base_branch], cwd=root)
        if switched.returncode != 0:
            _print_command_failure("git switch base branch", switched)
            return EXCEPTION_REQUIRED_EXIT_CODE
    else:
        detached = runner.run(
            ["git", "switch", "--detach", f"origin/{base_branch}"],
            cwd=root,
        )
        if detached.returncode != 0:
            _print_command_failure("git switch --detach origin base", detached)
            return EXCEPTION_REQUIRED_EXIT_CODE

    with _temporary_env(
        {
            "ALLOW_MAIN_REF_UPDATE": "1",
            "MAIN_REF_UPDATE_REASON": f"sync local {base_branch} after PR #{pr_ref} merge",
        }
    ):
        synced = runner.run(
            ["git", "merge", "--ff-only", f"origin/{base_branch}"],
            cwd=sync_root,
        )
    if synced.returncode != 0:
        _print_command_failure("git merge --ff-only origin base", synced)
        return EXCEPTION_REQUIRED_EXIT_CODE
    if base_worktree is None:
        print(f"cleanup: base {base_branch} synced with origin/{base_branch}")
    else:
        print(
            f"cleanup: base {base_branch} synced in worktree "
            f"{base_worktree} with origin/{base_branch}"
        )

    if head_branch and not is_cross_repository:
        deleted = runner.run(["git", "branch", "-d", head_branch], cwd=root)
        if deleted.returncode != 0:
            _print_command_failure("git branch -d", deleted)
            return EXCEPTION_REQUIRED_EXIT_CODE
        print(f"cleanup: local branch deleted: {head_branch}")
        print(f"cleanup: remote branch deletion delegated to GitHub: {head_branch}")
    elif is_cross_repository:
        print(f"skip head branch delete for fork PR: {head_branch}")

    synced_state = runner.run(
        ["git", "rev-list", "--left-right", "--count", f"{base_branch}...origin/{base_branch}"],
        cwd=sync_root,
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


def _render_submit_managed_body(
    contract: pr_flow_contract.PRFlowContract,
    evidence: dict[str, Any],
) -> str:
    return (
        f"```{contract.fenced_language}\n"
        + json.dumps(
            evidence,
            ensure_ascii=contract.json_ensure_ascii,
            indent=contract.json_indent,
        )
        + "\n```"
    )


def _render_submit_github_native_links(evidence: dict[str, Any]) -> str:
    issues = evidence.get("issues")
    refs = issues.get("refs") if isinstance(issues, dict) else None
    if not isinstance(refs, list):
        return ""
    closes = sorted(
        {
            number
            for item in refs
            if isinstance(item, dict)
            and _single_line_text(item.get("role")) == "closes"
            and (number := _positive_int_from_payload(item.get("number"))) is not None
        }
    )
    if not closes:
        return ""
    return "Closes " + ", closes ".join(f"#{number}" for number in closes)


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
        reread_thread = _read_review_thread_resolution(
            root=root,
            runner=runner,
            thread_id=thread_id,
        )
        if reread_thread is None or not bool(reread_thread.get("isResolved")):
            _print_state(
                "EXCEPTION_REQUIRED",
                "review thread was not resolved after re-read",
                details=[thread_id],
            )
            return EXCEPTION_REQUIRED_EXIT_CODE
        print(f"resolved review thread: {thread_id}")
    return SUCCESS_EXIT_CODE


def _read_review_thread_resolution(
    *,
    root: Path,
    runner: Runner,
    thread_id: str,
) -> dict[str, Any] | None:
    result = runner.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            "query=query($threadId:ID!){node(id:$threadId){... on PullRequestReviewThread{id isResolved}}}",
            "-F",
            f"threadId={thread_id}",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        _print_command_failure("gh api graphql reviewThread re-read", result)
        return None
    payload = _json_object_from_result(result, "gh api graphql reviewThread re-read")
    node = payload.get("data", {}).get("node", {})
    return node if isinstance(node, dict) else None


def _branch_worktree_path(root: Path, runner: Runner, branch: str) -> Path | None:
    result = runner.run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if result.returncode != 0:
        return None
    current_path: Path | None = None
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            current_path = None
            continue
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ").strip())
            continue
        if line == f"branch refs/heads/{branch}" and current_path is not None:
            resolved = current_path.resolve()
            return None if resolved == root.resolve() else resolved
    return None


def _pending_intent_path(root: Path) -> Path:
    return root / PENDING_INTENT_PATH


def _branch_intent_path(root: Path, branch: str) -> Path:
    return root / ".local" / "pr-flow" / "intents" / f"{branch}.json"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _current_branch(root: Path, runner: Runner) -> str:
    branch = _command_stdout(runner.run(["git", "branch", "--show-current"], cwd=root))
    if not branch:
        raise CommitIntentError(
            "current branch is empty",
            reason_code="COMMIT_INTENT_BRANCH_UNAVAILABLE",
        )
    return branch


def _git_config_value(root: Path, runner: Runner, key: str) -> str:
    return _command_stdout(runner.run(["git", "config", key], cwd=root))


def _current_staged_diff_fingerprint(root: Path, runner: Runner) -> dict[str, Any]:
    diff_command = [
        "git",
        "-c",
        "core.quotePath=false",
        "diff",
        "--binary",
        "--no-ext-diff",
        "--cached",
    ]
    diff = runner.run(diff_command, cwd=root)
    if diff.returncode != 0:
        raise CommitIntentError(
            "staged diff unavailable",
            reason_code="STAGED_DIFF_UNAVAILABLE",
            details=(_single_line_text(diff.stderr), _single_line_text(diff.stdout)),
        )
    if not diff.stdout.strip():
        raise CommitIntentError(
            "no staged diff; stage files before recording commit intent",
            reason_code="STAGED_DIFF_MISSING",
        )
    files_result = runner.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-only",
            "--cached",
        ],
        cwd=root,
    )
    if files_result.returncode != 0:
        raise CommitIntentError(
            "staged file list unavailable",
            reason_code="STAGED_DIFF_UNAVAILABLE",
            details=(
                _single_line_text(files_result.stderr),
                _single_line_text(files_result.stdout),
            ),
        )
    files = sorted(
        {
            _normalize_path(line)
            for line in files_result.stdout.splitlines()
            if _normalize_path(line)
        }
    )
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(diff.stdout.encode("utf-8")).hexdigest(),
        "changed_files": files,
    }


def _validated_intent_issues(
    root: Path,
    runner: Runner,
    issue_bindings: Sequence[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    seen: set[int] = set()
    for binding in issue_bindings:
        number, role = _parse_intent_issue_binding(binding)
        if number in seen:
            continue
        seen.add(number)
        command = ["gh", "issue", "view", str(number), "--json", "state,title"]
        result = _run_github_read_command(root, runner, command)
        if result.returncode != 0:
            raise CommitIntentError(
                "linked GitHub Issue does not exist or is unavailable",
                reason_code="COMMIT_INTENT_ISSUE_UNAVAILABLE",
                details=(f"#{number}", _single_line_text(result.stderr)),
            )
        issue = _json_object_from_result(result, "gh issue view " + str(number))
        state = _single_line_text(issue.get("state")).upper()
        if role == "closes" and state == "CLOSED":
            raise CommitIntentError(
                "closed Issue cannot be declared as closes; use reference or a new open Issue",
                reason_code="COMMIT_INTENT_CLOSED_ISSUE_CLOSE_REJECTED",
                details=(f"#{number}",),
            )
        issues.append(
            {
                "number": number,
                "role": role,
                "title": _single_line_text(issue.get("title")),
            }
        )
    if not issues:
        raise CommitIntentError(
            "commit intent requires at least one Issue binding or no-Issue authorization",
            reason_code="COMMIT_INTENT_BINDING_MISSING",
        )
    return issues


def _parse_intent_issue_binding(binding: str) -> tuple[int, str]:
    raw = _single_line_text(binding)
    match = re.fullmatch(r"#?(?P<number>\d+)\s*(?::|=)\s*(?P<role>[A-Za-z_]+)", raw)
    if match is None:
        raise CommitIntentError(
            "Issue binding must use NUMBER:reference or NUMBER:closes",
            reason_code="COMMIT_INTENT_ISSUE_BINDING_INVALID",
            details=(binding,),
        )
    number = int(match.group("number"))
    role = match.group("role").casefold()
    if number <= 0 or role not in VALID_INTENT_ROLES:
        raise CommitIntentError(
            "Issue role must be reference or closes",
            reason_code="COMMIT_INTENT_ISSUE_ROLE_INVALID",
            details=(binding,),
        )
    return number, role


def _pending_intent(root: Path) -> dict[str, Any]:
    path = _pending_intent_path(root)
    payload = _read_json_object(path)
    if payload is None:
        raise CommitIntentError(
            "pending commit intent is missing",
            reason_code="COMMIT_INTENT_MISSING",
            details=(str(path.relative_to(root)),),
        )
    return payload


def _matching_pending_intent(root: Path, runner: Runner) -> dict[str, Any]:
    pending = _pending_intent(root)
    if bool(pending.get("consumed")):
        raise CommitIntentError(
            "pending commit intent has already been consumed",
            reason_code="COMMIT_INTENT_CONSUMED",
        )
    branch = _current_branch(root, runner)
    pending_branch = _single_line_text(pending.get("branch"))
    if pending_branch != branch:
        raise CommitIntentError(
            "pending commit intent belongs to another branch",
            reason_code="COMMIT_INTENT_BRANCH_MISMATCH",
            details=(f"expected={branch}", f"actual={pending_branch}"),
        )
    current = _current_staged_diff_fingerprint(root, runner)
    recorded = pending.get("staged_diff_fingerprint")
    if not isinstance(recorded, dict) or recorded != current:
        raise CommitIntentError(
            "pending commit intent does not match the current staged diff",
            reason_code="COMMIT_INTENT_STALE",
            details=("run pr_flow intent stage again after changing staged files",),
        )
    return pending


def _current_branch_commit_shas(
    root: Path,
    runner: Runner,
    *,
    base_ref: str,
) -> tuple[str, ...]:
    result = runner.run(["git", "rev-list", "--reverse", f"{base_ref}..HEAD"], cwd=root)
    if result.returncode != 0:
        raise CommitIntentError(
            "current branch commits are unavailable",
            reason_code="BRANCH_COMMITS_UNAVAILABLE",
            details=(_single_line_text(result.stderr), _single_line_text(result.stdout)),
        )
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def _is_github_update_branch_merge_commit(
    root: Path,
    runner: Runner,
    sha: str,
    *,
    base_ref: str,
    pr_number: str | None = None,
) -> bool:
    result = runner.run(["git", "show", "-s", "--format=%P%n%s", sha], cwd=root)
    if result.returncode != 0:
        return False
    lines = result.stdout.splitlines()
    if len(lines) < 2:
        return False
    parents = [parent for parent in lines[0].split() if parent]
    if len(parents) < 2:
        return False
    base_branch = _base_branch_name(base_ref)
    subject = lines[1].strip()
    patterns = (
        rf"^Merge branch '{re.escape(base_branch)}' into .+",
        rf"^Merge remote-tracking branch 'origin/{re.escape(base_branch)}' into .+",
    )
    if not any(re.match(pattern, subject) for pattern in patterns):
        return False
    if not pr_number:
        return False
    return _pr_commit_has_github_update_branch_evidence(
        root=root,
        runner=runner,
        pr_number=pr_number,
        sha=sha,
    )


def _pr_commit_has_github_update_branch_evidence(
    *,
    root: Path,
    runner: Runner,
    pr_number: str,
    sha: str,
) -> bool:
    try:
        repo = _current_github_repo(root, runner)
        commits = _gh_api_list(
            root,
            runner,
            f"repos/{repo}/pulls/{pr_number}/commits?per_page=100",
        )
    except GitHubDataUnavailable:
        return False
    for item in commits:
        if _single_line_text(item.get("sha")) != sha:
            continue
        if _github_commit_actor_is_web_flow(item.get("author")):
            return True
        if _github_commit_actor_is_web_flow(item.get("committer")):
            return True
    return False


def _github_commit_actor_is_web_flow(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return _single_line_text(value.get("login")).casefold() == "web-flow"


def _base_branch_name(base_ref: str) -> str:
    normalized = base_ref.strip().replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] if normalized else "main"


def _branch_intent_with_commit(
    branch_payload: dict[str, Any],
    *,
    branch: str,
    commit_intent: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    commit_sha = _single_line_text(commit_intent.get("commit_sha"))
    existing_commits = branch_payload.get("commits")
    commits = [
        item
        for item in existing_commits
        if isinstance(item, dict)
        and _single_line_text(item.get("commit_sha")) != commit_sha
    ] if isinstance(existing_commits, list) else []
    commits.append(dict(commit_intent))
    payload = {
        "schema_version": 1,
        "branch": branch,
        "updated_at": updated_at,
        "commits": commits,
        "issues": _aggregate_intent_issues(commits),
        "no_issue_authorizations": _no_issue_authorizations(commits),
    }
    return payload


def _aggregate_intent_issues(commits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_number: dict[int, dict[str, Any]] = {}
    for commit in commits:
        correction_reason = _single_line_text(commit.get("correction_reason"))
        issues = commit.get("issues")
        if not isinstance(issues, list):
            continue
        for item in issues:
            if not isinstance(item, dict):
                continue
            number = _positive_int_from_payload(item.get("number"))
            role = _single_line_text(item.get("role"))
            if number is None or role not in VALID_INTENT_ROLES:
                continue
            current = by_number.get(number)
            if current is None:
                by_number[number] = {
                    "number": number,
                    "role": role,
                    "title": _single_line_text(item.get("title")),
                }
                continue
            if current["role"] == "closes" and role == "reference":
                if correction_reason:
                    current["role"] = "reference"
                    current["correction_reason"] = correction_reason
                continue
            if role == "closes":
                current["role"] = "closes"
            if not current.get("title"):
                current["title"] = _single_line_text(item.get("title"))
    return [by_number[number] for number in sorted(by_number)]


def _no_issue_authorizations(commits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    authorizations: list[dict[str, Any]] = []
    for commit in commits:
        if _single_line_text(commit.get("issue_policy")) != "no_issue":
            continue
        authorization = commit.get("no_issue_authorization")
        if not isinstance(authorization, dict):
            continue
        entry = dict(authorization)
        entry["commit_sha"] = _single_line_text(commit.get("commit_sha"))
        authorizations.append(entry)
    return authorizations


def _spec_issues_from_branch_intent(
    branch_intent: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in branch_intent.get("issues", []):
        if not isinstance(item, dict):
            continue
        number = _positive_int_from_payload(item.get("number"))
        role = _single_line_text(item.get("role"))
        if number is None or role not in VALID_INTENT_ROLES:
            continue
        issues.append({"number": number, "role": role})
    return issues


def _positive_int_from_payload(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _pr_template_body(root: Path) -> str:
    template = root / ".github" / "pull_request_template.md"
    if not template.is_file():
        return ""
    return template.read_text(encoding="utf-8", errors="ignore")


def _github_pr_info_from_url(pr_url: str) -> tuple[str, str] | None:
    match = re.match(
        r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)",
        pr_url,
    )
    if not match:
        return None
    return match.group("repo"), match.group("number")


def _write_managed_body_file(
    local: Path,
    existing_body: str,
    managed_body: str,
    native_links_body: str = "",
) -> Path:
    local.mkdir(parents=True, exist_ok=True)
    merged = _replace_managed_block(existing_body, managed_body)
    merged = _replace_github_native_links_block(merged, native_links_body)
    body_file = local / "pr-evidence-body.md"
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


def _replace_github_native_links_block(existing_body: str, links_body: str) -> str:
    pattern = re.compile(
        rf"{re.escape(GITHUB_NATIVE_LINKS_START)}.*?"
        rf"{re.escape(GITHUB_NATIVE_LINKS_END)}",
        re.DOTALL,
    )
    if links_body.strip():
        block = (
            f"{GITHUB_NATIVE_LINKS_START}\n"
            f"{links_body.strip()}\n"
            f"{GITHUB_NATIVE_LINKS_END}"
        )
        if GITHUB_NATIVE_LINKS_START in existing_body and GITHUB_NATIVE_LINKS_END in existing_body:
            return pattern.sub(lambda _match: block, existing_body)
        if existing_body.strip():
            return f"{existing_body.rstrip()}\n\n{block}\n"
        return f"{block}\n"
    if GITHUB_NATIVE_LINKS_START in existing_body and GITHUB_NATIVE_LINKS_END in existing_body:
        return pattern.sub("", existing_body).strip() + "\n"
    return existing_body


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
    current_head_sha: str = "",
    current_diff_hash: str = "",
) -> tuple[int, dict[str, Any], bool]:
    updated = payload
    changed = False
    for thread in threads:
        action = _auto_review_thread_action(
            thread,
            updated,
            current_head_sha=current_head_sha,
            current_diff_hash=current_diff_hash,
        )
        if action not in {"accept", "close"}:
            continue
        thread_id = _thread_id(thread)
        if not thread_id:
            continue
        finding: dict[str, Any] | None
        if action == "accept":
            finding = _external_finding_for_review_thread(
                repo=repo,
                pr_number=pr_number,
                thread=thread,
                status="accepted",
            )
        elif action == "close":
            finding = _closed_external_finding_for_thread(
                updated,
                thread,
                current_head_sha=current_head_sha,
                current_diff_hash=current_diff_hash,
            )
        else:
            continue
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


def _write_resolve_threads_plan(
    *,
    root: Path,
    contract: pr_flow_contract.PRFlowContract,
    repo: str,
    pr_number: str,
    head_sha: str,
    diff_hash: str,
    threads: Sequence[dict[str, Any]],
) -> dict[str, str]:
    rel_path = Path(".local") / "pr-flow" / "resolve-threads-plan.json"
    path = root / rel_path
    unresolved = [thread for thread in threads if not _thread_is_resolved(thread)]
    payload = {
        "schema_version": 1,
        "repository": repo,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "diff_hash": diff_hash,
        "threads": [
            _resolve_thread_plan_entry(contract=contract, thread=thread)
            for thread in unresolved
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    count = len(unresolved)
    noun = "thread" if count == 1 else "threads"
    return {
        "artifact_type": "resolve_threads_plan",
        "artifact_path": rel_path.as_posix(),
        "artifact_summary": f"{count} unresolved review {noun} requires explicit action",
    }


def _resolve_thread_plan_entry(
    *,
    contract: pr_flow_contract.PRFlowContract,
    thread: dict[str, Any],
) -> dict[str, Any]:
    root_comment = _thread_root_comment(thread) or {}
    body = _single_line_text(root_comment.get("body") or _codex_thread_body(thread))
    severity = _codex_thread_severity(thread)
    return {
        "thread_id": _thread_id(thread),
        "root_author": _comment_author_login(root_comment),
        "comment_url": _single_line_text(root_comment.get("url")),
        "path": _single_line_text(thread.get("path")),
        "line": _optional_int(thread.get("line") or thread.get("originalLine")),
        "is_outdated": _thread_is_outdated(thread),
        "severity": severity,
        "summary": pr_flow_contract.normalize_detail(
            body or "unresolved review thread",
            max_chars=contract.detail_max_chars,
        ),
        "closure_evidence_state": _thread_closure_evidence_state(thread),
        "suggested_action": _thread_suggested_action(thread),
    }


def _thread_closure_evidence_state(thread: dict[str, Any]) -> str:
    if _thread_is_official_codex(thread) and _codex_thread_severity(thread) in {"P0", "P1"}:
        return "missing"
    return "manual"


def _thread_suggested_action(thread: dict[str, Any]) -> str:
    if _thread_is_official_codex(thread) and _codex_thread_severity(thread) in {"P0", "P1"}:
        return "provide current-head fixed or false_positive evidence before resolving"
    return "inspect thread and resolve explicit ID only after review intent is satisfied"


def _review_thread_blocking_failures(
    threads: Sequence[dict[str, Any]],
    *,
    artifact_path: str,
) -> tuple[pr_flow_contract.SubmitFailure, ...]:
    failures: list[pr_flow_contract.SubmitFailure] = []
    for thread in threads:
        thread_id = _thread_id(thread) or "unknown"
        failures.append(
            pr_flow_contract.SubmitFailure(
                check="official-codex-review-thread",
                source=artifact_path,
                detail=f"unresolved review thread {thread_id} requires closure evidence",
            )
        )
    return tuple(failures)


def _auto_review_thread_action(
    thread: dict[str, Any],
    payload: dict[str, Any],
    *,
    current_head_sha: str = "",
    current_diff_hash: str = "",
) -> str:
    if _thread_is_resolved(thread) or not _thread_is_official_codex(thread):
        return ""
    severity = _codex_thread_severity(thread)
    if severity in AUTO_ACCEPTED_REVIEW_THREAD_SEVERITIES:
        return "accept"
    # human threads are never auto-resolved — they continue to block.
    if (
        severity in {"P0", "P1"}
        and _closed_external_finding_for_thread(
            payload,
            thread,
            current_head_sha=current_head_sha,
            current_diff_hash=current_diff_hash,
        )
        is not None
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
    _ = repo_root
    updated = dict(payload)
    updated["schema_version"] = THREAD_PROCESSING_SCHEMA_VERSION
    updated["changed_files"] = _string_list(payload.get("changed_files"))
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
    *,
    current_head_sha: str = "",
    current_diff_hash: str = "",
) -> dict[str, Any] | None:
    thread_id = _thread_id(thread)
    if not thread_id:
        return None
    expected_head = _single_line_text(current_head_sha)
    expected_diff = _single_line_text(current_diff_hash)
    if not expected_head or not expected_diff:
        fingerprint = payload.get("diff_fingerprint")
        if not isinstance(fingerprint, dict):
            return None
        expected_head = expected_head or _single_line_text(fingerprint.get("head_sha"))
        expected_diff = expected_diff or _single_line_text(
            fingerprint.get("diff_files_hash")
        )
    if not expected_head or not expected_diff:
        return None
    for item in payload.get("external_findings") or []:
        if not isinstance(item, dict):
            continue
        if _single_line_text(item.get("source")) != "official_codex_review_thread":
            continue
        if _single_line_text(item.get("thread_id")) != thread_id:
            continue
        if _single_line_text(item.get("severity")) not in {"P0", "P1"}:
            continue
        if _single_line_text(item.get("status")) not in CLOSED_REVIEW_THREAD_STATUSES:
            continue
        if not _single_line_text(item.get("evidence")):
            continue
        finding_head = _single_line_text(item.get("head_sha"))
        if not finding_head or finding_head != expected_head:
            continue
        finding_diff = _single_line_text(item.get("diff_files_hash"))
        if not finding_diff or finding_diff != expected_diff:
            continue
        status = _single_line_text(item.get("status"))
        if status == "fixed":
            if not _single_line_text(item.get("fix_commit") or item.get("commit_sha")):
                continue
            if not _single_line_text(
                item.get("verification_command") or item.get("verification")
            ):
                continue
        elif status == "false_positive" and not _false_positive_rationale(item):
            continue
        closed = dict(item)
        closed.setdefault(
            "handling",
            "structured fixed or false_positive evidence recorded; review thread resolved",
        )
        return closed
    return None


def _false_positive_rationale(finding: dict[str, Any]) -> str:
    return (
        _single_line_text(finding.get("rationale"))
        or _single_line_text(finding.get("reason"))
        or _single_line_text(finding.get("false_positive_reason"))
    )


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
    if _single_line_text(finding.get("status")) == "false_positive":
        return (
            "已按 PR review 规则关闭官方 Codex false positive 阻断项。\n\n"
            f"- finding: `{_single_line_text(finding.get('id'))}`\n"
            f"- thread_id: `{_single_line_text(finding.get('thread_id'))}`\n"
            f"- severity: `{_single_line_text(finding.get('severity'))}`\n"
            "- status: `false_positive`\n"
            f"- current_head: `{_single_line_text(finding.get('head_sha'))}`\n"
            f"- rationale: {_false_positive_rationale(finding)}\n"
            f"- evidence: {_single_line_text(finding.get('evidence'))}\n"
            f"- handling: {_single_line_text(finding.get('handling'))}\n"
        )
    fix_commit = _single_line_text(finding.get("fix_commit") or finding.get("commit_sha"))
    verification = _single_line_text(
        finding.get("verification_command") or finding.get("verification")
    )
    return (
        "已按 PR review 规则关闭过期官方 Codex 阻断项。\n\n"
        f"- finding: `{_single_line_text(finding.get('id'))}`\n"
        f"- thread_id: `{_single_line_text(finding.get('thread_id'))}`\n"
        f"- severity: `{_single_line_text(finding.get('severity'))}`\n"
        f"- status: `{_single_line_text(finding.get('status'))}`\n"
        f"- fix_commit: `{fix_commit}`\n"
        f"- current_head: `{_single_line_text(finding.get('head_sha'))}`\n"
        f"- verification: `{verification}`\n"
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
              path
              line
              comments(first: 50) {
                nodes {
                  body
                  url
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


def _thread_is_official_codex(thread: dict[str, Any]) -> bool:
    """Return True if the thread is from an official Codex reviewer."""
    comment = _thread_root_comment(thread)
    if not isinstance(comment, dict):
        return False
    return _comment_author_login(comment) in CODEX_REVIEW_AUTHORS


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
    comment = _thread_root_comment(thread)
    if comment is None:
        return None
    if _comment_author_login(comment) not in CODEX_REVIEW_AUTHORS:
        return None
    return comment


def _thread_root_comment(thread: dict[str, Any]) -> dict[str, Any] | None:
    comments = _thread_comments(thread)
    return comments[0] if comments else None


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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if isinstance(item, str) and (text := item.strip())]


def _single_line_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _optional_int(value: Any) -> int | None:
    try:
        return int(_single_line_text(value))
    except ValueError:
        return None


def _failing_check_names(output: str) -> list[str]:
    failing: list[str] = []
    for line in output.splitlines():
        normalized = line.casefold()
        if any(token in normalized for token in ("fail", "failure", "cancel", "error")):
            name = line.split("\t", 1)[0].strip()
            failing.append(name or line.strip())
    return failing


def _latest_required_check_results(output: str) -> list[dict[str, Any]] | None:
    latest, _diagnostics = _latest_required_check_results_with_diagnostics(
        output,
        contract=None,
    )
    return latest


def _latest_required_check_results_with_diagnostics(
    output: str,
    *,
    contract: pr_flow_contract.PRFlowContract | None,
) -> tuple[list[dict[str, Any]] | None, tuple[pr_flow_contract.SubmitFailure, ...]]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return None, ()
    if not isinstance(payload, list):
        return None, ()
    latest: dict[
        tuple[str, str],
        tuple[tuple[int, str, int, int, int], dict[str, Any], int],
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
            latest[key] = (rank, check, index)
        elif rank > current[0]:
            latest[key] = (rank, check, index)
    selected_indexes = {item[2] for item in latest.values()}
    required_checks = set(contract.required_checks) if contract is not None else set()
    diagnostics: list[pr_flow_contract.SubmitFailure] = []
    for index, check in enumerate(payload):
        if index in selected_indexes or not isinstance(check, dict):
            continue
        display_name = _json_check_display_name(check)
        if required_checks and display_name not in required_checks:
            continue
        if not _json_check_failed(check):
            continue
        diagnostics.append(
            pr_flow_contract.SubmitFailure(
                check=display_name,
                source=_single_line_text(check.get("link")),
                detail=f"stale required check ignored: {_json_check_failure_detail(check)}",
            )
        )
    return [latest[key][1] for key in order], tuple(diagnostics)


def _current_head_required_check_results(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    pr_number: str,
) -> tuple[list[dict[str, Any]] | None, tuple[pr_flow_contract.SubmitFailure, ...]]:
    result = _run_github_read_command(
        root,
        runner,
        [
            "gh",
            "pr",
            "view",
            pr_number,
            "--json",
            STATUS_CHECK_ROLLUP_JSON_FIELDS,
        ],
    )
    if result.returncode != 0:
        return None, ()
    payload = _json_from_result(result)
    if not payload:
        return None, ()
    latest, diagnostics = _status_check_rollup_required_check_results(
        root=root,
        runner=runner,
        contract=contract,
        payload=payload,
    )
    return latest, diagnostics


def _fallback_required_check_results(
    root: Path,
    runner: Runner,
    pr_number: str,
) -> list[dict[str, Any]] | None:
    result = _run_github_read_command(
        root,
        runner,
        [
            "gh",
            "pr",
            "view",
            pr_number,
            "--json",
            STATUS_CHECK_ROLLUP_JSON_FIELDS,
        ],
    )
    if result.returncode != 0:
        return None
    payload = _json_from_result(result)
    rollup_checks = [
        check
        for item in _status_check_rollup_items(payload.get("statusCheckRollup"))
        if (check := _check_from_status_rollup_item(item)) is not None
    ]
    required_names: set[str] = set(REQUIRED_STATUS_CHECK_NAMES)
    pr_info = _github_pr_info_from_url(_single_line_text(payload.get("url")))
    if pr_info is not None:
        repo, _ = pr_info
        required_names.update(
            _required_status_check_names(
                root=root,
                runner=runner,
                repo=repo,
                branch=_single_line_text(payload.get("baseRefName")),
            )
        )
    if not required_names:
        return rollup_checks
    matched = [
        check
        for check in rollup_checks
        if _json_check_display_name(check) in required_names
        or _single_line_text(check.get("name")) in required_names
    ]
    matched_names = {
        name
        for check in matched
        for name in (
            _json_check_display_name(check),
            _single_line_text(check.get("name")),
        )
        if name
    }
    missing = sorted(name for name in required_names if name not in matched_names)
    missing_checks = [
        {
            "name": name,
            "state": "PENDING",
            "bucket": "pending",
            "workflow": "",
        }
        for name in missing
    ]
    return [*matched, *missing_checks]


def _status_check_rollup_required_check_results(
    *,
    root: Path,
    runner: Runner,
    contract: pr_flow_contract.PRFlowContract,
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]] | None, tuple[pr_flow_contract.SubmitFailure, ...]]:
    expected_head = _single_line_text(payload.get("headRefOid"))
    required_names: set[str] = set(contract.required_checks)
    pr_info = _github_pr_info_from_url(_single_line_text(payload.get("url")))
    if pr_info is not None:
        repo, _ = pr_info
        required_names.update(
            _required_status_check_names(
                root=root,
                runner=runner,
                repo=repo,
                branch=_single_line_text(payload.get("baseRefName")),
            )
        )
    checks: list[dict[str, Any]] = []
    diagnostics: list[pr_flow_contract.SubmitFailure] = []
    for item in _status_check_rollup_items(payload.get("statusCheckRollup")):
        check = _check_from_status_rollup_item(item)
        if check is None:
            continue
        display_name = _json_check_display_name(check)
        raw_name = _single_line_text(check.get("name"))
        if display_name not in required_names and raw_name not in required_names:
            continue
        check_head = _check_head_sha(check)
        if expected_head and check_head and check_head != expected_head:
            if _json_check_failed(check):
                diagnostics.append(
                    pr_flow_contract.SubmitFailure(
                        check=display_name,
                        source=_single_line_text(check.get("link")),
                        detail=(
                            "stale required check ignored: "
                            f"{_json_check_failure_detail(check)}"
                        ),
                    )
                )
            continue
        checks.append(check)
    latest, stale_diagnostics = _latest_required_check_results_with_diagnostics(
        json.dumps(checks),
        contract=contract,
    )
    diagnostics.extend(stale_diagnostics)
    if latest is None:
        return None, tuple(diagnostics)
    matched_names = {
        name
        for check in latest
        for name in (
            _json_check_display_name(check),
            _single_line_text(check.get("name")),
        )
        if name
    }
    missing = sorted(name for name in contract.required_checks if name not in matched_names)
    missing_checks = [
        {
            "name": name,
            "state": "PENDING",
            "bucket": "pending",
            "workflow": "",
        }
        for name in missing
    ]
    return [*latest, *missing_checks], tuple(diagnostics)


def _status_check_rollup_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        nodes = value.get("nodes")
        if isinstance(nodes, list):
            return [item for item in nodes if isinstance(item, dict)]
    return []


def _check_from_status_rollup_item(item: dict[str, Any]) -> dict[str, Any] | None:
    name = _single_line_text(item.get("name") or item.get("context"))
    if not name:
        return None
    workflow = item.get("workflow")
    workflow_name = (
        _single_line_text(workflow.get("name"))
        if isinstance(workflow, dict)
        else _single_line_text(item.get("workflowName"))
    )
    state = _single_line_text(
        item.get("state") or item.get("conclusion") or item.get("status")
    ).upper()
    bucket = "pending"
    if state in {"SUCCESS", "SKIPPED", "NEUTRAL"}:
        bucket = "pass"
    elif state in {
        "ACTION_REQUIRED",
        "CANCELLED",
        "ERROR",
        "FAILURE",
        "STARTUP_FAILURE",
        "TIMED_OUT",
    }:
        bucket = "fail"
    return {
        "name": name,
        "workflow": workflow_name,
        "state": state,
        "bucket": bucket,
        "link": _single_line_text(item.get("detailsUrl") or item.get("targetUrl")),
        "startedAt": _single_line_text(item.get("startedAt")),
        "completedAt": _single_line_text(item.get("completedAt")),
        "headSha": _status_check_item_head_sha(item),
    }


def _status_check_item_head_sha(item: dict[str, Any]) -> str:
    direct = _single_line_text(
        item.get("headSha")
        or item.get("head_sha")
        or item.get("commitOid")
        or item.get("commit_id")
    )
    if direct:
        return direct
    commit = item.get("commit")
    if isinstance(commit, dict):
        value = _single_line_text(commit.get("oid") or commit.get("sha"))
        if value:
            return value
    suite = item.get("checkSuite")
    if isinstance(suite, dict):
        value = _single_line_text(
            suite.get("headSha") or suite.get("head_sha") or suite.get("commitOid")
        )
        if value:
            return value
    return ""


def _check_head_sha(check: dict[str, Any]) -> str:
    return _single_line_text(check.get("headSha") or check.get("head_sha"))


def _required_status_check_names(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    branch: str,
) -> set[str]:
    names: set[str] = set()
    try:
        rulesets = _gh_api_list(
            root,
            runner,
            f"repos/{repo}/rulesets?includes_parents=true",
        )
        for summary in rulesets:
            ruleset = _ruleset_detail(
                root=root,
                runner=runner,
                repo=repo,
                summary=summary,
            )
            if not _ruleset_applies_to_branch(ruleset, branch):
                continue
            for rule in ruleset.get("rules") or []:
                if not isinstance(rule, dict):
                    continue
                if _single_line_text(rule.get("type")) != "required_status_checks":
                    continue
                parameters = rule.get("parameters")
                if not isinstance(parameters, dict):
                    continue
                for item in parameters.get("required_status_checks") or []:
                    if isinstance(item, dict):
                        name = _single_line_text(
                            item.get("context") or item.get("name")
                        )
                        if name:
                            names.add(name)
                    elif (name := _single_line_text(item)):
                        names.add(name)
    except GitHubDataUnavailable:
        pass
    names.update(
        _legacy_required_status_check_names(
            root=root,
            runner=runner,
            repo=repo,
            branch=branch,
        )
    )
    return names


def _legacy_required_status_check_names(
    *,
    root: Path,
    runner: Runner,
    repo: str,
    branch: str,
) -> set[str]:
    if not branch:
        return set()
    path = f"repos/{repo}/branches/{branch}/protection/required_status_checks"
    result = _run_github_read_command(root, runner, ["gh", "api", path])
    if result.returncode != 0:
        return set()
    payload = _json_from_result(result)
    names = set(_string_list(payload.get("contexts")))
    checks = payload.get("checks")
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict):
                continue
            name = _single_line_text(item.get("context") or item.get("name"))
            if name:
                names.add(name)
    return names


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
    if _json_check_has_skipped_state(check):
        return not _json_check_allows_skipped_success(check)
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
    if _json_check_has_skipped_state(check):
        return _json_check_allows_skipped_success(check)
    return bucket == "pass" or state == "success"


def _json_check_has_skipped_state(check: dict[str, Any]) -> bool:
    bucket = _single_line_text(check.get("bucket")).casefold()
    state = _single_line_text(check.get("state")).casefold()
    return bucket == "skipping" or state in {"neutral", "skipped"}


def _json_check_allows_skipped_success(check: dict[str, Any]) -> bool:
    return _json_check_display_name(check) == "PR Flow / review-status"


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


def _fail_submit(
    root: str | Path,
    contract: pr_flow_contract.PRFlowContract,
    exit_code: int,
    *,
    head_sha: str,
    snapshot_context: SubmitSnapshotContext | None = None,
    reason_code: str,
    phase: str,
    retryable: bool = False,
    failures: Sequence[pr_flow_contract.SubmitFailure] = (),
    diagnostics: Sequence[pr_flow_contract.SubmitFailure] = (),
    checkpoint_statuses: Sequence[dict[str, str]] = (),
    evidence_artifacts: Sequence[dict[str, str]] = (),
) -> int:
    """Write submit status and emit structured stop status, then return exit code."""
    context = snapshot_context or SubmitSnapshotContext()
    if failures:
        pr_flow_contract.write_submit_status(
            root,
            contract,
            head=head_sha,
            repository=context.repository,
            pr_number=context.pr_number,
            head_branch=context.head_branch,
            failures=failures,
            stop_state=_submit_state_for_exit_code(exit_code),
            reason_code=reason_code,
            phase=phase,
            retryable=retryable,
            diagnostics=diagnostics,
            checkpoint_statuses=checkpoint_statuses,
            evidence_artifacts=evidence_artifacts,
        )
    return _stop_submit(
        root,
        exit_code,
        reason_code=reason_code,
        phase=phase,
        retryable=retryable,
        failures=failures,
    )


def _ensure_submit_status_failure(
    root: str | Path,
    contract: pr_flow_contract.PRFlowContract,
    *,
    head_sha: str,
    snapshot_context: SubmitSnapshotContext | None = None,
    failure: pr_flow_contract.SubmitFailure,
) -> None:
    status = _read_json_object(Path(root).resolve() / contract.submit_status_path) or {}
    failures = status.get("failures")
    blocking_signals = status.get("blocking_signals")
    if isinstance(failures, list) and failures:
        return
    if isinstance(blocking_signals, list) and blocking_signals:
        return
    context = snapshot_context or SubmitSnapshotContext()
    pr_flow_contract.write_submit_status(
        root,
        contract,
        head=head_sha,
        repository=context.repository,
        pr_number=context.pr_number,
        head_branch=context.head_branch,
        failures=[failure],
        stop_state="EXCEPTION_REQUIRED",
        reason_code="SUBMIT_STATUS_FAILURE",
        phase="submit_status",
        retryable=True,
    )


def _clear_submit_status(
    root: str | Path,
    contract: pr_flow_contract.PRFlowContract,
) -> None:
    path = Path(root).resolve() / contract.submit_status_path
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _submit_state_for_exit_code(exit_code: int) -> str:
    return {
        DISPATCH_REQUIRED_EXIT_CODE: "DISPATCH_REQUIRED",
        REPLY_OR_FIX_REQUIRED_EXIT_CODE: "REPLY_OR_FIX_REQUIRED",
        EXCEPTION_REQUIRED_EXIT_CODE: "EXCEPTION_REQUIRED",
    }.get(exit_code, "EXCEPTION_REQUIRED")


def _stop_submit(
    root: str | Path,
    exit_code: int,
    *,
    reason_code: str,
    phase: str,
    retryable: bool = False,
    failures: Sequence[pr_flow_contract.SubmitFailure] = (),
) -> int:
    """Emit structured stop status and return exit code.

    Ensures every non-zero exit from submit produces a CLI stop summary.
    """
    blocking_items = tuple(
        f"{f.check}: {f.detail}" for f in failures
    ) if failures else ()
    evidence_refs = tuple(
        f.source for f in failures if f.source
    )
    message = reason_code.replace("_", " ").title()
    if failures:
        message = "; ".join(blocking_items) if blocking_items else message
    state = _submit_state_for_exit_code(exit_code)

    _print_state(
        state,
        message,
        repo_root=root,
        reason_code=reason_code,
        phase=phase,
        retryable=retryable,
        dispatch_target=_default_dispatch_target(state),
        blocking_items=blocking_items,
        evidence_refs=evidence_refs,
        next_actions=_stop_next_actions(exit_code, failures),
    )
    return exit_code


def _stop_next_actions(
    exit_code: int,
    failures: Sequence[pr_flow_contract.SubmitFailure],
) -> tuple[str, ...]:
    if exit_code == DISPATCH_REQUIRED_EXIT_CODE:
        return ("dispatch review agents to regenerate fragments",)
    if exit_code == REPLY_OR_FIX_REQUIRED_EXIT_CODE:
        return ("address blocking findings and re-run pr-submit",)
    if exit_code == EXCEPTION_REQUIRED_EXIT_CODE:
        if any("github" in f.check.casefold() for f in failures):
            return (
                "verify GitHub API access and re-run pr-submit",
                "check .local/pr-flow/status.json for details",
            )
        return ("inspect .local/pr-flow/status.json for details",)
    return ()


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


def _reason_code_from_message(message: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", message.strip()).strip("_")
    return normalized.upper() or "UNKNOWN_STOP"


def _default_dispatch_target(state: str) -> str:
    return {
        "DISPATCH_REQUIRED": "agent",
        "REPLY_OR_FIX_REQUIRED": "author",
        "EXCEPTION_REQUIRED": "operator",
    }.get(state, "operator")


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _is_high_risk_path(path: str) -> bool:
    normalized = _normalize_path(path)
    if _is_generated_strategy_artifact(normalized):
        return False
    return any(normalized.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)


def _is_generated_strategy_artifact(path: str) -> bool:
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "strategies" and parts[2] == "backtest_runs"


def _short_sha(sha: str) -> str:
    return sha[:12] if sha else "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--title")
    submit_parser.add_argument("--pr")
    submit_parser.add_argument("--official-review-skip-authorized-by")
    submit_parser.add_argument("--official-review-skip-evidence")
    resolve_threads_parser = subparsers.add_parser("resolve-threads")
    resolve_threads_parser.add_argument("thread_ids", nargs="*")
    resolve_threads_parser.add_argument("--thread", action="append", default=[])
    intent_parser = subparsers.add_parser("intent")
    intent_subparsers = intent_parser.add_subparsers(
        dest="intent_command",
        required=True,
    )
    intent_stage_parser = intent_subparsers.add_parser("stage")
    intent_stage_parser.add_argument("--issue", action="append", default=[])
    intent_stage_parser.add_argument("--no-issue-reason")
    intent_stage_parser.add_argument("--no-issue-authorized-by")
    intent_stage_parser.add_argument("--no-issue-evidence")
    intent_stage_parser.add_argument("--correction-reason")
    intent_subparsers.add_parser("pre-commit")
    intent_subparsers.add_parser("post-commit")
    coverage_parser = intent_subparsers.add_parser("check-coverage")
    coverage_parser.add_argument("--base-ref", default="origin/main")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "submit":
        return submit(
            repo_root=args.repo_root,
            title=args.title,
            pr=args.pr,
            official_review_skip_authorized_by=(
                args.official_review_skip_authorized_by
            ),
            official_review_skip_evidence=args.official_review_skip_evidence,
        )
    if args.command == "resolve-threads":
        return resolve_review_threads(
            repo_root=args.repo_root,
            thread_ids=tuple(args.thread_ids) + tuple(args.thread),
        )
    if args.command == "intent":
        if args.intent_command == "stage":
            return stage_commit_intent(
                repo_root=args.repo_root,
                issue_bindings=tuple(args.issue),
                no_issue_reason=args.no_issue_reason,
                no_issue_authorized_by=args.no_issue_authorized_by,
                no_issue_evidence=args.no_issue_evidence,
                correction_reason=args.correction_reason,
            )
        if args.intent_command == "pre-commit":
            return validate_pending_commit_intent(repo_root=args.repo_root)
        if args.intent_command == "post-commit":
            return record_committed_intent(repo_root=args.repo_root)
        if args.intent_command == "check-coverage":
            return check_branch_intent_coverage(
                repo_root=args.repo_root,
                base_ref=args.base_ref,
            )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
