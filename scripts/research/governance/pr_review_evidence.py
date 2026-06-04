"""Validate required PR review evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.research.governance import pr_flow_contract
from scripts.research.governance.codex_review_contract import (
    is_codex_review_request,
)


HIGH_RISK_PREFIXES = (
    "strategies/",
    "scripts/research/platform/",
    "scripts/research/governance/",
    ".github/",
    ".githooks/",
    "docs/rules/",
    "docs/adr/",
)
CODEX_REVIEW_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)#pullrequestreview-(?P<review_id>\d+)"
)
CODEX_COMPLETION_COMMENT_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/(?:pull|issues)/(?P<number>\d+)#issuecomment-(?P<comment_id>\d+)"
)
CODEX_REVIEW_AUTHORS = {"chatgpt-codex-connector", "chatgpt-codex-connector[bot]"}
DISQUALIFIED_CODEX_REVIEW_STATES = {"DISMISSED", "PENDING"}
MONITOR_STATE_PATTERN = re.compile(
    r"<!--\s*codex-review-monitor-state\s+(?P<payload>\{.*?\})\s*-->", re.DOTALL
)
ISSUE_INTENT_MACHINE_BLOCK_PATTERN = re.compile(
    r"<details>\s*<summary>PR Flow machine verification</summary>\s*"
    r"```json\s*(?P<payload>\{.*?\})\s*```\s*</details>",
    re.DOTALL,
)
BLOCKING_CODEX_FINDING_PATTERN = re.compile(
    r"(?:P[01] Badge|badge/P[01]-|(?:^|\n)\s*(?:\*\*)?\[P[01]\]\s+)",
    re.IGNORECASE,
)
CODEX_CONTEXT_INVALID_PATTERN = re.compile(
    r"(?:"
    r"(?:cannot|can(?:'|\u2019)t|can\s*not|unable\s+to|could\s+not|couldn(?:'|\u2019)t)\s+"
    r".*?(?:review|complete|read|access).*?(?:diff|code\s+diff|unified\s+diff)|"
    r"(?:cannot|can(?:'|\u2019)t|can\s*not|unable\s+to|could\s+not|couldn(?:'|\u2019)t)\s+"
    r"(?:see|view)\s+(?:the\s+)?(?:(?:current|PR|pull\s+request)\s+)?(?:diff|code\s+diff|unified\s+diff)|"
    r"(?:don(?:'|\u2019)t|do\s+not)\s+have\s+access\s+to\s+(?:the\s+)?(?:PR\s+)?diff|"
    r"(?:don(?:'|\u2019)t|do\s+not)\s+have\s+access\s+to\s+(?:the\s+)?"
    r"(?:repository|repo|codebase)\s+or\s+(?:the\s+)?(?:PR\s+|unified\s+)?diff|"
    r"conversation\s+did\s+not\s+include.*diff|"
    r"cannot\s+complete.*static\s+review.*diff|"
    r"could\s+not\s+read.*diff|"
    r"(?:provide|paste)\s+(?:the\s+)?(?:unified\s+)?diff\s+"
    r"(?:to|before|for|so\s+I\s+can)\s+(?:complete|perform|review)|"
    r"(?:provide|paste)\s+(?:the\s+)?PR\s+diff\s+so\s+I\s+can\s+review|"
    r"无法.*?(?:审查|完成|读取|获取|查看).*?(?:diff|差异|统一\s*diff)|"
    r"(?:缺少|未包含).*?(?:diff|差异|统一\s*diff)"
    r")",
    re.IGNORECASE | re.DOTALL,
)
CODEX_NO_MAJOR_ISSUES_PATTERN = re.compile(
    r"Codex Review:\s*(?:Didn(?:'|\u2019)t|Did not) find any major issues",
    re.IGNORECASE,
)
CONTEXT_HOSTILE_TRIGGER_PATTERN = re.compile(
    r"(?:"
    r"(?:do\s+not|don(?:'|\u2019)t)\s+(?:execute|run)\s+(?:any\s+)?(?:local\s+)?"
    r"(?:commands?|checks?|tests?)|"
    r"(?:do\s+not|don(?:'|\u2019)t)\s+use\s+tools?|"
    r"(?:do\s+not|don(?:'|\u2019)t)\s+read\s+(?:the\s+)?(?:repository|repo|GitHub\s+diff|diff)|"
    r"only\s+do\s+a\s+static\s+diff\s+review|"
    r"(?:不要|不)(?:执行|运行)(?![^。；;\n]*(?:破坏性|危险)).*?(?:命令|本地命令|检查|测试)|"
    r"(?:不要|不)(?:使用|读取).*?(?:工具|仓库|代码库|GitHub\s*diff|diff)|"
    r"(?:只|仅)(?:做|看|查看).*?(?:静态\s*)?(?:diff|差异|统一\s*diff)\s*(?:review|评审)?|"
    r"只做静态\s*diff\s*review"
    r")",
    re.IGNORECASE,
)
CONTEXT_INVALID_REVIEW_ERROR = "Codex review context is invalid for the current head"
CONTEXT_HOSTILE_TRIGGER_ERROR = (
    "required @codex review trigger must not disable repository context"
)
REQUIRED_TRIGGER_TOKENS = ("@codex review",)


@dataclass(frozen=True)
class EvidenceReport:
    ok: bool
    errors: tuple[str, ...]


def validate_pr_body(
    body: str,
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
    expected_diff_hash: str | None = None,
    expected_commit_shas: Sequence[str] | None = None,
    expected_head_created_at: str | None = None,
    comments: Sequence[object] | None = None,
    reviews: Sequence[Mapping[str, object]] | None = None,
    review_comments: Sequence[Mapping[str, object]] | None = None,
    review_threads: Sequence[Mapping[str, object]] | None = None,
    changed_files: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> EvidenceReport:
    """Return whether a PR body contains merge-blocking review evidence."""

    contract_payload, contract_errors = _extract_contract_v1_evidence(body)
    if contract_payload is not None or contract_errors:
        errors = list(contract_errors)
        if contract_payload is not None:
            errors.extend(
                _contract_v1_evidence_errors(
                    body,
                    contract_payload,
                    expected_head_sha=expected_head_sha,
                    expected_diff_hash=expected_diff_hash,
                    expected_commit_shas=expected_commit_shas,
                    changed_files=changed_files,
                    labels=labels,
                )
            )
        if (
            review_threads is not None
            and unresolved_blocking_codex_thread_count(review_threads) > 0
        ):
            errors.append("Codex review must not have unresolved review threads")
        return EvidenceReport(not errors, tuple(errors))

    errors = ["PR body missing PR Evidence JSON"]
    if (
        review_threads is not None
        and unresolved_blocking_codex_thread_count(review_threads) > 0
    ):
        errors.append("Codex review must not have unresolved review threads")
    return EvidenceReport(False, tuple(errors))

def _extract_contract_v1_evidence(
    body: str,
) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    contract = pr_flow_contract.load_contract(Path("."))
    if contract.marker_start not in body:
        return None, ()
    pattern = re.compile(
        rf"{re.escape(contract.marker_start)}\s*"
        rf"```{re.escape(contract.fenced_language)}\s*"
        r"(?P<payload>\{.*?\})\s*```\s*"
        rf"{re.escape(contract.marker_end)}",
        re.DOTALL,
    )
    match = pattern.search(body)
    if match is None:
        return None, ("PR Flow evidence block must contain fenced JSON",)
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return None, ("PR Flow evidence JSON must be valid JSON",)
    if not isinstance(payload, dict):
        return None, ("PR Flow evidence JSON must be an object",)
    return payload, ()


def _contract_v1_evidence_errors(
    body: str,
    payload: dict[str, object],
    *,
    expected_head_sha: str | None,
    expected_diff_hash: str | None,
    expected_commit_shas: Sequence[str] | None,
    changed_files: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> list[str]:
    contract = pr_flow_contract.load_contract(Path("."))
    errors: list[str] = []
    fields = tuple(payload)
    if fields != contract.pr_evidence_fields:
        errors.append(
            "PR Evidence JSON fields must be "
            + "/".join(contract.pr_evidence_fields)
        )
    schema = payload.get("schema")
    if schema != contract.version:
        errors.append(f"PR Evidence JSON schema must be {contract.version}")
    head = _single_line_text(payload.get("head"))
    diff = _single_line_text(payload.get("diff"))
    if expected_head_sha and head != expected_head_sha:
        errors.append("PR Evidence JSON head does not match current PR head")
    if expected_diff_hash and diff != expected_diff_hash:
        errors.append("PR Evidence JSON diff does not match current PR diff")
    if ISSUE_INTENT_MACHINE_BLOCK_PATTERN.search(body):
        errors.append("PR body must not contain legacy Issue intent machine block")
    errors.extend(_contract_v1_review_errors(payload.get("reviews"), head=head, diff=diff))
    errors.extend(_contract_v1_official_review_errors(payload.get("official_review")))
    errors.extend(
        _contract_v1_official_review_risk_errors(
            payload.get("official_review"),
            changed_files=changed_files,
            labels=labels,
        )
    )
    errors.extend(
        _contract_v1_issue_errors(
            payload.get("issues"),
            expected_commit_shas=expected_commit_shas,
        )
    )
    errors.extend(_contract_v1_retained_errors(payload.get("retained"), contract))
    return errors


def _contract_v1_official_review_errors(official_review: object) -> list[str]:
    if not isinstance(official_review, Mapping):
        return ["PR Evidence official_review must be an object"]
    decision = _single_line_text(official_review.get("decision"))
    if decision == "required":
        if tuple(official_review) != ("decision",):
            return ["PR Evidence official_review.required must only contain decision"]
        return []
    if decision == "skip_risk_low":
        if tuple(official_review) != ("decision",):
            return ["PR Evidence official_review.skip_risk_low must only contain decision"]
        return []
    if decision == "skip_user_authorized":
        errors: list[str] = []
        if tuple(official_review) != ("decision", "authorized_by", "evidence"):
            errors.append(
                "PR Evidence official_review.skip_user_authorized fields must be "
                "decision/authorized_by/evidence"
            )
        for field in ("authorized_by", "evidence"):
            if not _single_line_text(official_review.get(field)):
                errors.append(
                    f"PR Evidence official_review.skip_user_authorized missing {field}"
                )
        return errors
    return ["PR Evidence official_review.decision is invalid"]


def _contract_v1_official_review_risk_errors(
    official_review: object,
    *,
    changed_files: Sequence[str] | None,
    labels: Sequence[str] | None,
) -> list[str]:
    if not isinstance(official_review, Mapping):
        return []
    if _single_line_text(official_review.get("decision")) != "skip_risk_low":
        return []
    errors: list[str] = []
    if _high_risk_changed_files(changed_files):
        errors.append(
            "PR Evidence official_review.skip_risk_low is invalid for high-risk changed files"
        )
    if _has_ai_risk_review_label(labels):
        errors.append(
            "PR Evidence official_review.skip_risk_low is invalid with ai-risk-review label"
        )
    return errors


def _contract_v1_review_errors(
    reviews: object,
    *,
    head: str,
    diff: str,
) -> list[str]:
    if not isinstance(reviews, Mapping):
        return ["PR Evidence reviews must be an object"]
    errors: list[str] = []
    for role in ("standards", "spec", "security"):
        item = reviews.get(role)
        if not isinstance(item, Mapping):
            errors.append(f"PR Evidence reviews.{role} must be an object")
            continue
        if _single_line_text(item.get("head")) != head:
            errors.append(f"PR Evidence reviews.{role}.head must match head")
        if _single_line_text(item.get("diff")) != diff:
            errors.append(f"PR Evidence reviews.{role}.diff must match diff")
    return errors


def _contract_v1_issue_errors(
    issues: object,
    *,
    expected_commit_shas: Sequence[str] | None,
) -> list[str]:
    if not isinstance(issues, Mapping):
        return ["PR Evidence issues must be an object"]
    errors: list[str] = []
    commits = issues.get("commits")
    if not isinstance(commits, list):
        errors.append("PR Evidence issues.commits must be a list")
        commits = []
    recorded = {
        _single_line_text(item.get("sha"))
        for item in commits
        if isinstance(item, Mapping) and _single_line_text(item.get("sha"))
    }
    if expected_commit_shas is not None:
        missing = [
            _single_line_text(sha)
            for sha in expected_commit_shas
            if _single_line_text(sha) and _single_line_text(sha) not in recorded
        ]
        if missing:
            errors.append("PR Evidence issues.commits missing coverage: " + ", ".join(missing))
    for index, item in enumerate(commits):
        if not isinstance(item, Mapping):
            errors.append(f"PR Evidence issues.commits[{index}] must be an object")
            continue
        has_issue = isinstance(item.get("issues"), list) and bool(item.get("issues"))
        has_no_issue = bool(item.get("no_issue"))
        if has_issue == has_no_issue:
            errors.append(
                f"PR Evidence issues.commits[{index}] must have issues or no_issue"
            )
    refs = issues.get("refs")
    if not isinstance(refs, list):
        errors.append("PR Evidence issues.refs must be a list")
        return errors
    for index, item in enumerate(refs):
        if not isinstance(item, Mapping):
            errors.append(f"PR Evidence issues.refs[{index}] must be an object")
            continue
        role = _single_line_text(item.get("role"))
        if role not in {"reference", "closes"}:
            errors.append(f"PR Evidence issues.refs[{index}].role is invalid")
        if "ac_checked" in item:
            errors.append(
                f"PR Evidence issues.refs[{index}].ac_checked is not allowed"
            )
    return errors


def _contract_v1_retained_errors(
    retained: object,
    contract: pr_flow_contract.PRFlowContract,
) -> list[str]:
    if not isinstance(retained, list):
        return ["PR Evidence retained must be a list"]
    errors: list[str] = []
    for index, item in enumerate(retained):
        if not isinstance(item, Mapping):
            errors.append(f"PR Evidence retained[{index}] must be an object")
            continue
        severity = _single_line_text(item.get("severity"))
        source = _single_line_text(item.get("source"))
        detail = _single_line_text(item.get("detail"))
        if severity not in contract.retained_severities:
            errors.append(f"PR Evidence retained[{index}].severity must be P2 or P3")
        if source not in contract.retained_sources:
            errors.append(f"PR Evidence retained[{index}].source is invalid")
        if not detail:
            errors.append(f"PR Evidence retained[{index}].detail is required")
        if "\n" in detail or len(detail) > contract.detail_max_chars:
            errors.append(f"PR Evidence retained[{index}].detail must be one short line")
    return errors


def _high_risk_changed_files(changed_files: Sequence[str] | None) -> tuple[str, ...]:
    if changed_files is None:
        return ()
    return tuple(path for path in changed_files if _is_high_risk_path(path))


def _is_high_risk_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if _is_generated_strategy_artifact(normalized):
        return False
    return any(normalized.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)


def _is_generated_strategy_artifact(path: str) -> bool:
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "strategies" and parts[2] == "backtest_runs"


def _has_ai_risk_review_label(labels: Sequence[str] | None) -> bool:
    if labels is None:
        return False
    return any(str(label).casefold() == "ai-risk-review" for label in labels)


def _normalize_value(value: str) -> str:
    return value.strip().strip("`").strip()


def _single_line_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _positive_int(value: object) -> int | None:
    text = _single_line_text(value)
    if not text:
        return None
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def unresolved_blocking_codex_thread_count(
    review_threads: Sequence[Mapping[str, object]],
) -> int:
    """Count unresolved review threads that block conversation resolution."""

    count = 0
    for thread in review_threads:
        if _thread_is_resolved(thread):
            continue
        count += 1
    return count


def _thread_is_resolved(thread: Mapping[str, object]) -> bool:
    return bool(_first_thread_value(thread, "isResolved", "is_resolved"))


def _thread_is_outdated(thread: Mapping[str, object]) -> bool:
    return bool(_first_thread_value(thread, "isOutdated", "is_outdated"))


def _first_thread_value(thread: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in thread:
            return thread[key]
    return False


def _thread_comments(thread: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    comments = thread.get("comments")
    if isinstance(comments, list):
        return tuple(item for item in comments if isinstance(item, Mapping))
    if isinstance(comments, Mapping):
        nodes = comments.get("nodes")
        if isinstance(nodes, list):
            return tuple(item for item in nodes if isinstance(item, Mapping))
        edges = comments.get("edges")
        if isinstance(edges, list):
            extracted: list[Mapping[str, object]] = []
            for edge in edges:
                if not isinstance(edge, Mapping):
                    continue
                node = edge.get("node")
                if isinstance(node, Mapping):
                    extracted.append(node)
            return tuple(extracted)
    return ()


def _review_texts(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> tuple[str, ...]:
    texts = [str(review.get("body", ""))]
    if review_comments is not None:
        for comment in review_comments:
            if str(comment.get("pull_request_review_id", "")) == review_id:
                texts.append(str(comment.get("body", "")))
    return tuple(texts)


def _review_has_context_invalid_findings(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> bool:
    return any(
        CODEX_CONTEXT_INVALID_PATTERN.search(text)
        for text in _review_texts(
            review, review_id=review_id, review_comments=review_comments
        )
    )


def codex_context_invalid_review_count(
    reviews: Sequence[Mapping[str, object]],
    *,
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
    submitted_after: str | None = None,
) -> int:
    latest_review = _latest_effective_codex_review(
        reviews,
        expected_head_sha=expected_head_sha,
        submitted_after=submitted_after,
    )
    if latest_review is None:
        return 0
    return int(
        _review_has_context_invalid_findings(
            latest_review,
            review_id=str(latest_review.get("id", "")),
            review_comments=review_comments,
        )
    )


def _latest_effective_codex_review(
    reviews: Sequence[Mapping[str, object]],
    *,
    expected_head_sha: str | None,
    submitted_after: str | None = None,
) -> Mapping[str, object] | None:
    matched = []
    for review in reviews:
        if not is_effective_codex_review(review):
            continue
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            continue
        if not _review_is_after_time(review, submitted_after):
            continue
        matched.append(review)
    if not matched:
        return None
    return sorted(matched, key=_review_sort_key)[-1]


def _review_is_after_time(
    review: Mapping[str, object], submitted_after: str | None
) -> bool:
    if not submitted_after:
        return True
    submitted_at = _review_submitted_time(review)
    if not submitted_at:
        return True
    return submitted_after < submitted_at


def _review_sort_key(review: Mapping[str, object]) -> str:
    return _review_submitted_time(review) or str(review.get("id", ""))


def _review_submitted_time(review: Mapping[str, object]) -> str:
    return _first_value(review, "submitted_at", "created_at", "updated_at")


def _review_has_blocking_findings(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> bool:
    if _review_has_context_invalid_findings(
        review, review_id=review_id, review_comments=review_comments
    ):
        return False
    return any(
        BLOCKING_CODEX_FINDING_PATTERN.search(text)
        for text in _review_texts(
            review, review_id=review_id, review_comments=review_comments
        )
    )


def _current_head_has_blocking_codex_review(
    reviews: Sequence[Mapping[str, object]],
    *,
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
    submitted_after: str | None = None,
) -> bool:
    for review in reviews:
        if not is_effective_codex_review(review):
            continue
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            continue
        if not _review_is_after_time(review, submitted_after):
            continue
        if _review_has_blocking_findings(
            review, review_id=str(review.get("id", "")), review_comments=review_comments
        ):
            return True
    return False


def is_effective_codex_review(review: Mapping[str, object]) -> bool:
    if not is_codex_review(review):
        return False
    return _review_state(review) not in DISQUALIFIED_CODEX_REVIEW_STATES


def is_codex_review(review: Mapping[str, object]) -> bool:
    author = review.get("user")
    login = author.get("login") if isinstance(author, Mapping) else ""
    return str(login) in CODEX_REVIEW_AUTHORS


def _review_state(review: Mapping[str, object]) -> str:
    return str(review.get("state", "") or "").upper()


def _required_trigger_comments(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> tuple[object, ...]:
    matched: list[object] = []
    for comment in _trigger_candidate_comments(
        comments,
        expected_head_created_at=expected_head_created_at,
        before_or_at=before_or_at,
    ):
        if _is_required_trigger_comment(
            comment,
            expected_pr_url=expected_pr_url,
            expected_head_sha=expected_head_sha,
        ):
            matched.append(comment)
    return tuple(matched)


def _trigger_candidate_comments(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> tuple[object, ...]:
    matched: list[object] = []
    for comment in comments:
        if not _is_trigger_candidate_comment(comment):
            continue
        if isinstance(comment, Mapping):
            comment_time = _comment_effective_time(comment)
            if (
                expected_head_created_at
                and comment_time
                and comment_time < expected_head_created_at
            ):
                continue
            if before_or_at and comment_time and before_or_at < comment_time:
                continue
        matched.append(comment)
    return tuple(matched)


def _has_context_hostile_trigger_comment(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> bool:
    latest = _latest_trigger_candidate_comment(
        comments,
        expected_head_created_at=expected_head_created_at,
        before_or_at=before_or_at,
    )
    return latest is not None and _is_context_hostile_trigger_comment(latest)


def _latest_trigger_candidate_comment(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> object | None:
    latest: object | None = None
    latest_time = ""
    for comment in _trigger_candidate_comments(
        comments,
        expected_head_created_at=expected_head_created_at,
        before_or_at=before_or_at,
    ):
        comment_time = (
            _comment_effective_time(comment) if isinstance(comment, Mapping) else ""
        )
        if (
            latest is None
            or not comment_time
            or not latest_time
            or latest_time <= comment_time
        ):
            latest = comment
            latest_time = comment_time
    return latest


def _is_trigger_candidate_comment(comment: object) -> bool:
    if isinstance(comment, Mapping):
        user = comment.get("user")
        login = user.get("login") if isinstance(user, Mapping) else ""
        if str(login) in CODEX_REVIEW_AUTHORS:
            return False
    body = _comment_body(comment)
    return all(token in body for token in REQUIRED_TRIGGER_TOKENS)


def _is_context_hostile_trigger_comment(comment: object) -> bool:
    if not _is_trigger_candidate_comment(comment):
        return False
    body = _comment_body(comment)
    return not is_codex_review_request(body) or bool(
        CONTEXT_HOSTILE_TRIGGER_PATTERN.search(body)
    )


def _is_required_trigger_comment(
    comment: object,
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> bool:
    if not _is_trigger_candidate_comment(comment):
        return False
    return is_codex_review_request(
        _comment_body(comment),
        expected_pr_url=expected_pr_url,
        expected_head_sha=expected_head_sha,
    )


def _comment_body(comment: object) -> str:
    if isinstance(comment, str):
        return comment
    if isinstance(comment, Mapping):
        return str(comment.get("body", ""))
    return ""


def _find_comment_by_id(
    comments: Sequence[object], comment_id: str
) -> Mapping[str, object] | None:
    for comment in comments:
        if not isinstance(comment, Mapping):
            continue
        if str(comment.get("id", "")) == comment_id:
            return comment
    return None


def has_codex_completion_reaction(comment: Mapping[str, object]) -> bool:
    return _codex_completion_reaction_time(comment) is not None


def codex_completion_effective_time(
    comment: Mapping[str, object],
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> str:
    if _is_required_trigger_comment(
        comment,
        expected_pr_url=expected_pr_url,
        expected_head_sha=expected_head_sha,
    ):
        reaction_time = _codex_completion_reaction_time(comment)
        if reaction_time:
            return reaction_time
    return _comment_effective_time(comment)


def _codex_completion_reaction_time(comment: Mapping[str, object]) -> str | None:
    comment_time = _comment_effective_time(comment)
    matched_times: list[str] = []
    for reaction in _comment_reaction_items(comment):
        if str(reaction.get("content", "")) != "+1":
            continue
        user = reaction.get("user")
        login = user.get("login") if isinstance(user, Mapping) else ""
        if str(login) not in CODEX_REVIEW_AUTHORS:
            continue
        reaction_time = _first_value(reaction, "created_at")
        if reaction_time and comment_time and reaction_time < comment_time:
            continue
        matched_times.append(reaction_time or comment_time)
    if not matched_times:
        return None
    return max(matched_times)


def is_codex_completion_comment(comment: Mapping[str, object]) -> bool:
    user = comment.get("user")
    login = user.get("login") if isinstance(user, Mapping) else ""
    if str(login) not in CODEX_REVIEW_AUTHORS:
        return False
    body = str(comment.get("body", ""))
    if not CODEX_NO_MAJOR_ISSUES_PATTERN.search(body):
        return False
    return not BLOCKING_CODEX_FINDING_PATTERN.search(body)


def _comment_reaction_items(
    comment: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    for key in ("reactions_detail", "reaction_items"):
        value = comment.get(key)
        if isinstance(value, list):
            return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def render_monitor_head_state(*, head_sha: str, head_updated_at: str | None) -> str:
    payload = {
        "head_sha": head_sha,
        "head_updated_at": head_updated_at or "",
    }
    return f"<!-- codex-review-monitor-state {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))} -->"


def head_updated_at_from_monitor_state(
    comments: Sequence[object] | None,
    *,
    expected_head_sha: str | None,
) -> str | None:
    if comments is None or not expected_head_sha:
        return None
    matched: list[str] = []
    for comment in comments:
        for payload in MONITOR_STATE_PATTERN.findall(_comment_body(comment)):
            try:
                state = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(state, Mapping):
                continue
            if str(state.get("head_sha", "")) != expected_head_sha:
                continue
            head_updated_at = str(state.get("head_updated_at", "") or "")
            if head_updated_at:
                matched.append(head_updated_at)
    return max(matched) if matched else None


def _review_is_after_required_trigger(
    review: Mapping[str, object],
    trigger_comments: Sequence[object],
    *,
    expected_head_created_at: str | None,
) -> bool:
    review_time = _review_submitted_time(review)
    trigger_time = _latest_required_trigger_time(
        trigger_comments,
        expected_head_created_at=expected_head_created_at,
    )
    if not review_time or not trigger_time:
        return True
    return trigger_time <= review_time


def _has_required_trigger_after_current_head(
    trigger_comments: Sequence[object],
    expected_head_created_at: str | None,
) -> bool:
    if not expected_head_created_at:
        return True
    return (
        _latest_required_trigger_time(
            trigger_comments,
            expected_head_created_at=expected_head_created_at,
        )
        is not None
    )


def _latest_required_trigger_time(
    trigger_comments: Sequence[object],
    *,
    expected_head_created_at: str | None,
) -> str | None:
    trigger_times = [
        _comment_effective_time(comment)
        for comment in trigger_comments
        if isinstance(comment, Mapping)
    ]
    trigger_times = [value for value in trigger_times if value]
    if expected_head_created_at:
        trigger_times = [
            value for value in trigger_times if expected_head_created_at <= value
        ]
    return max(trigger_times) if trigger_times else None


def _comment_effective_time(comment: Mapping[str, object]) -> str:
    created_at = _first_value(comment, "created_at")
    updated_at = _first_value(comment, "updated_at")
    if created_at and updated_at:
        return max(created_at, updated_at)
    return updated_at or created_at


def _first_value(item: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _normalize_pr_url(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().rstrip("/") or None


def _github_api_url(*, repo: str, path: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"https://api.github.com/repos/{repo}/{path}{separator}per_page=100"


def _fetch_github_json_url(*, url: str, token: str) -> tuple[object, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
        next_url = _parse_next_link(response.headers.get("Link", ""))
        return payload, next_url


def _fetch_github_json(*, repo: str, path: str, token: str) -> object:
    payload, _ = _fetch_github_json_url(
        url=_github_api_url(repo=repo, path=path), token=token
    )
    return payload


def _fetch_github_text(
    *, repo: str, path: str, token: str, accept: str = "application/vnd.github+json"
) -> str:
    request = urllib.request.Request(
        _github_api_url(repo=repo, path=path),
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _fetch_github_graphql(
    *, query: str, variables: Mapping[str, object], token: str
) -> Mapping[str, object]:
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": dict(variables)}).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("GitHub GraphQL returned unexpected payload")
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(
            "GitHub GraphQL returned errors: " + " ".join(str(errors).split())
        )
    return payload


def _fetch_github_list(*, repo: str, path: str, token: str) -> list[object]:
    items: list[object] = []
    url: str | None = _github_api_url(repo=repo, path=path)
    while url:
        payload, url = _fetch_github_json_url(url=url, token=token)
        if not isinstance(payload, list):
            return items
        items.extend(payload)
    return items


def _parse_next_link(header: str) -> str | None:
    for part in header.split(","):
        pieces = part.split(";")
        if len(pieces) < 2:
            continue
        if not any(piece.strip() == 'rel="next"' for piece in pieces[1:]):
            continue
        url = pieces[0].strip()
        if url.startswith("<") and url.endswith(">"):
            return url[1:-1]
    return None


def _fetch_pr_metadata(
    *, repo: str, pr_number: str, token: str
) -> Mapping[str, object] | None:
    payload = _fetch_github_json(repo=repo, path=f"pulls/{pr_number}", token=token)
    return payload if isinstance(payload, Mapping) else None


def _fetch_pr_comments(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"issues/{pr_number}/comments", token=token
    )
    return _enrich_required_trigger_reactions(
        [item for item in payload if isinstance(item, Mapping)],
        repo=repo,
        token=token,
    )


def _enrich_required_trigger_reactions(
    comments: Sequence[Mapping[str, object]],
    *,
    repo: str,
    token: str,
) -> list[Mapping[str, object]]:
    enriched: list[Mapping[str, object]] = []
    for comment in comments:
        if not _is_required_trigger_comment(comment):
            enriched.append(comment)
            continue
        comment_id = comment.get("id")
        if comment_id is None:
            enriched.append(comment)
            continue
        item = dict(comment)
        item["reaction_items"] = _fetch_issue_comment_reactions(
            repo=repo, comment_id=str(comment_id), token=token
        )
        enriched.append(item)
    return enriched


def _fetch_issue_comment_reactions(
    *, repo: str, comment_id: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"issues/comments/{comment_id}/reactions", token=token
    )
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_reviews(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/reviews", token=token
    )
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_review_comments(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/comments", token=token
    )
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_changed_files(
    *, repo: str, pr_number: str, token: str
) -> tuple[str, ...]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/files", token=token
    )
    return tuple(
        str(item.get("filename", ""))
        for item in payload
        if isinstance(item, Mapping) and str(item.get("filename", "")).strip()
    )


def _local_pr_diff_hash(repo_root: Path | None = None) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "origin/main...HEAD",
        ],
        cwd=repo_root or Path.cwd(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = _single_line_text(result.stderr or result.stdout)
        raise RuntimeError(
            "git diff --binary origin/main...HEAD failed"
            + (f": {detail}" if detail else "")
        )
    return hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()


def _fetch_pr_diff_hash(*, repo: str, pr_number: str, token: str) -> str:
    return _local_pr_diff_hash()


def _fetch_pr_commit_shas(
    *, repo: str, pr_number: str, token: str
) -> tuple[str, ...]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/commits", token=token
    )
    return tuple(
        str(item.get("sha", ""))
        for item in payload
        if isinstance(item, Mapping) and str(item.get("sha", "")).strip()
    )


def _fetch_issue_metadata(
    *, repo: str, pr_number: str, token: str
) -> Mapping[str, object]:
    payload = _fetch_github_json(repo=repo, path=f"issues/{pr_number}", token=token)
    return payload if isinstance(payload, Mapping) else {}


def _issue_label_names(issue: Mapping[str, object]) -> tuple[str, ...]:
    labels = issue.get("labels")
    if not isinstance(labels, list):
        return ()
    names: list[str] = []
    for label in labels:
        if isinstance(label, Mapping):
            name = str(label.get("name", "")).strip()
        else:
            name = str(label).strip()
        if name:
            names.append(name)
    return tuple(names)


def _fetch_pr_review_threads(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            nodes {
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
    threads: list[Mapping[str, object]] = []
    cursor: str | None = None
    while True:
        payload = _fetch_github_graphql(
            query=query,
            variables={
                "owner": owner,
                "name": name,
                "number": int(pr_number),
                "cursor": cursor,
            },
            token=token,
        )
        connection = _graphql_review_threads_connection(payload)
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise RuntimeError("GitHub reviewThreads response missing nodes")
        threads.extend(item for item in nodes if isinstance(item, Mapping))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, Mapping):
            raise RuntimeError("GitHub reviewThreads response missing pageInfo")
        if not bool(page_info.get("hasNextPage")):
            break
        cursor = str(page_info.get("endCursor", "") or "")
        if not cursor:
            raise RuntimeError("GitHub reviewThreads pagination cursor missing")
    return threads


def _graphql_review_threads_connection(
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(
            "GitHub reviewThreads GraphQL errors: " + " ".join(str(errors).split())
        )
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise RuntimeError("GitHub reviewThreads response missing data")
    repository = data.get("repository")
    if not isinstance(repository, Mapping):
        raise RuntimeError("GitHub reviewThreads response missing repository")
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, Mapping):
        raise RuntimeError("GitHub reviewThreads response missing pullRequest")
    review_threads = pull_request.get("reviewThreads")
    if not isinstance(review_threads, Mapping):
        raise RuntimeError("GitHub reviewThreads response missing reviewThreads")
    return review_threads


def _read_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    return value if value else None


def _read_optional_file(path: Path | None) -> object | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_comments(payload: object | None) -> Sequence[object] | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        return ()
    comments: list[object] = []
    for item in payload:
        if isinstance(item, str):
            comments.append(item)
        elif isinstance(item, Mapping):
            comments.append(item)
    return comments


def _coerce_reviews(payload: object | None) -> Sequence[Mapping[str, object]] | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        return ()
    return [item for item in payload if isinstance(item, Mapping)]


def _coerce_review_threads(
    payload: object | None,
) -> Sequence[Mapping[str, object]] | None:
    return _coerce_reviews(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file", type=Path)
    source.add_argument("--body-env")
    parser.add_argument("--pr-url-env")
    parser.add_argument("--repo-env")
    parser.add_argument("--pr-number-env")
    parser.add_argument("--head-sha-env")
    parser.add_argument("--head-updated-at-env")
    parser.add_argument("--head-created-at-env", help=argparse.SUPPRESS)
    parser.add_argument("--github-token-env")
    parser.add_argument("--comments-file", type=Path)
    parser.add_argument("--reviews-file", type=Path)
    parser.add_argument("--review-comments-file", type=Path)
    parser.add_argument("--review-threads-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8", errors="replace")
    else:
        body = os.environ.get(args.body_env, "")

    comments = _coerce_comments(_read_optional_file(args.comments_file))
    reviews = _coerce_reviews(_read_optional_file(args.reviews_file))
    review_comments = _coerce_reviews(_read_optional_file(args.review_comments_file))
    review_threads = _coerce_review_threads(
        _read_optional_file(args.review_threads_file)
    )
    changed_files: Sequence[str] | None = None
    expected_diff_hash: str | None = None
    expected_commit_shas: Sequence[str] | None = None
    labels: Sequence[str] | None = None
    expected_pr_url = _read_env(args.pr_url_env)
    expected_head_sha = _read_env(args.head_sha_env)
    expected_head_created_at = _read_env(args.head_updated_at_env) or _read_env(
        args.head_created_at_env
    )

    repo = _read_env(args.repo_env)
    pr_number = _read_env(args.pr_number_env)
    token = _read_env(args.github_token_env)
    if repo and pr_number and token:
        pr_metadata: Mapping[str, object] | None = None
        pr_metadata = _fetch_pr_metadata(repo=repo, pr_number=pr_number, token=token)
        if pr_metadata is not None:
            if args.body_file is None:
                body = str(pr_metadata.get("body", ""))
            expected_pr_url = str(pr_metadata.get("html_url", "")) or expected_pr_url
            head = pr_metadata.get("head")
            if isinstance(head, Mapping):
                expected_head_sha = str(head.get("sha", "")) or expected_head_sha
        if comments is None:
            comments = _fetch_pr_comments(repo=repo, pr_number=pr_number, token=token)
        if not expected_head_created_at:
            expected_head_created_at = head_updated_at_from_monitor_state(
                comments,
                expected_head_sha=expected_head_sha,
            )
        if reviews is None:
            reviews = _fetch_pr_reviews(repo=repo, pr_number=pr_number, token=token)
        if review_comments is None:
            review_comments = _fetch_pr_review_comments(
                repo=repo, pr_number=pr_number, token=token
            )
        if review_threads is None:
            review_threads = _fetch_pr_review_threads(
                repo=repo, pr_number=pr_number, token=token
            )
        changed_files = _fetch_pr_changed_files(
            repo=repo, pr_number=pr_number, token=token
        )
        expected_diff_hash = _fetch_pr_diff_hash(
            repo=repo, pr_number=pr_number, token=token
        )
        fetched_commit_shas = _fetch_pr_commit_shas(
            repo=repo, pr_number=pr_number, token=token
        )
        expected_commit_shas = fetched_commit_shas or None
        labels = _issue_label_names(
            _fetch_issue_metadata(repo=repo, pr_number=pr_number, token=token)
        )

    if not expected_head_created_at:
        expected_head_created_at = head_updated_at_from_monitor_state(
            comments,
            expected_head_sha=expected_head_sha,
        )

    report = validate_pr_body(
        body,
        expected_pr_url=expected_pr_url,
        expected_head_sha=expected_head_sha,
        expected_diff_hash=expected_diff_hash,
        expected_commit_shas=expected_commit_shas,
        expected_head_created_at=expected_head_created_at,
        comments=comments,
        reviews=reviews,
        review_comments=review_comments,
        review_threads=review_threads,
        changed_files=changed_files,
        labels=labels,
    )
    if report.ok:
        print("PR review evidence ok")
        return 0
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
