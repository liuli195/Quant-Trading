"""Monitor Codex Code Review status on a pull request."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.research.governance import pr_flow_contract
from scripts.research.governance.codex_review_contract import (
    is_codex_review_request,
)
from scripts.research.governance.pr_review_evidence import (
    AI_REVIEW_SECTION_HEADER,
    BLOCKING_CODEX_FINDING_PATTERN,
    CODEX_CONTEXT_INVALID_PATTERN,
    CONTEXT_HOSTILE_TRIGGER_PATTERN,
    CODEX_REVIEW_AUTHORS,
    _extract_contract_v1_evidence,
    _fetch_pr_review_threads,
    _fetch_issue_metadata,
    _fetch_pr_changed_files,
    _issue_label_names,
    _official_codex_required,
    codex_context_invalid_review_count,
    codex_completion_effective_time,
    has_codex_completion_reaction,
    head_updated_at_from_monitor_state,
    is_codex_completion_comment,
    is_effective_codex_review,
    official_codex_review_skip_authorized,
    render_monitor_head_state,
    unresolved_blocking_codex_thread_count,
)


MONITOR_MARKER = "<!-- codex-review-monitor -->"
REQUIRED_TRIGGER_TOKENS = ("@codex review",)
P2_FINDING_PATTERN = re.compile(
    r"(?:P2 Badge|badge/P2-|(?:^|\n)\s*(?:\*\*)?\[P2\]\s+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MonitorReport:
    status: str
    pr_number: str
    head_sha: str
    trigger_found: bool
    latest_review_url: str | None
    latest_review_sha: str | None
    blocking_findings: int
    advisory_findings: int
    message: str
    head_updated_at: str | None = None
    context_invalid_reviews: int = 0
    trigger_invalid: bool = False


def build_monitor_report(
    *,
    repo: str,
    pr_number: str,
    pr: Mapping[str, object],
    issue_comments: Sequence[Mapping[str, object]],
    reviews: Sequence[Mapping[str, object]],
    review_comments: Sequence[Mapping[str, object]],
    review_threads: Sequence[Mapping[str, object]] | None = None,
    changed_files: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
    head_created_at: str | None = None,
) -> MonitorReport:
    """Build a status summary for Codex reviews on the PR head."""

    head_sha = _head_sha(pr)
    pr_url = str(pr.get("html_url", "")) or f"https://github.com/{repo}/pull/{pr_number}"
    pr_body = str(pr.get("body", ""))
    skip_authorized = official_codex_review_skip_authorized(pr_body)
    contract_payload, contract_errors = _extract_contract_v1_evidence(pr_body)
    if contract_payload is not None or contract_errors:
        official_required, official_errors = _contract_v1_official_codex_requirement(
            pr_body,
            contract_errors=contract_errors,
            changed_files=changed_files,
            labels=labels,
        )
    else:
        official_required, official_errors = _official_codex_required(
            pr_body,
            changed_files=changed_files,
            labels=labels,
        )
    if not pr_body.strip() and changed_files is None and labels is None:
        official_errors = []
    official_review_required = official_required or bool(official_errors)
    trigger_time = _required_trigger_time(
        issue_comments,
        head_created_at=head_created_at,
        expected_pr_url=pr_url,
        expected_head_sha=head_sha,
    )
    trigger_found = trigger_time is not None
    current_head_reviews = _current_head_codex_reviews(reviews, head_sha=head_sha)
    post_trigger_reviews = _reviews_after_trigger(
        current_head_reviews, trigger_time=trigger_time
    )
    latest_review = _latest_codex_review(post_trigger_reviews) or _latest_codex_review(
        current_head_reviews
    )
    completion_comment = _latest_codex_completion_comment(
        issue_comments,
        head_created_at=head_created_at,
        trigger_time=trigger_time,
        expected_pr_url=pr_url,
        expected_head_sha=head_sha,
    )
    completion_time = (
        codex_completion_effective_time(
            completion_comment,
            expected_pr_url=pr_url,
            expected_head_sha=head_sha,
        )
        if completion_comment
        else ""
    )
    latest_review_time = _review_submitted_at(latest_review) if latest_review else ""
    completion_is_latest = completion_comment is not None and (
        latest_review is None or not latest_review_time or latest_review_time <= completion_time
    )
    if completion_comment is not None and completion_is_latest:
        latest_review_url = _issue_comment_url(
            repo=repo, pr_number=pr_number, comment=completion_comment
        )
        latest_review_sha = head_sha
        reviewed_until = completion_time
        context_invalid_cutoff = completion_time
    elif latest_review is not None:
        latest_review_url = _review_url(
            repo=repo, pr_number=pr_number, review=latest_review
        )
        latest_review_sha = str(latest_review.get("commit_id", ""))
        reviewed_until = _review_submitted_at(latest_review)
        context_invalid_cutoff = None
    else:
        latest_review_url = None
        latest_review_sha = None
        reviewed_until = None
        context_invalid_cutoff = None
    trigger_invalid = _has_context_hostile_trigger_comment(
        issue_comments,
        head_created_at=head_created_at,
        before_or_at=reviewed_until,
    )
    blocking_findings = _count_reviews_findings(
        current_head_reviews,
        review_comments=review_comments,
        pattern=BLOCKING_CODEX_FINDING_PATTERN,
    )
    blocking_findings += (
        unresolved_blocking_codex_thread_count(review_threads)
        if review_threads is not None
        else 0
    )
    context_invalid_reviews = codex_context_invalid_review_count(
        current_head_reviews,
        review_comments=review_comments,
        expected_head_sha=head_sha,
        submitted_after=context_invalid_cutoff,
    )
    advisory_findings = _count_reviews_findings(
        current_head_reviews,
        review_comments=review_comments,
        pattern=P2_FINDING_PATTERN,
    )

    if context_invalid_reviews:
        status = "context_invalid"
        message = (
            "Codex review context invalid: review did not receive a reliable "
            "current-head diff context. Treat this as a review workflow P1, not "
            "as a passable code review finding."
        )
    elif blocking_findings:
        status = "blocked"
        message = "Codex review 含阻断发现或未解决 thread，不能填写通过结论。"
    elif official_errors:
        status = "evidence_invalid"
        message = "PR review evidence invalid: " + "; ".join(official_errors)
    elif skip_authorized:
        status = "skipped"
        message = "官方 Codex review 已由用户授权跳过。"
    elif not official_review_required:
        status = "skipped"
        message = "官方 Codex review 按 PR 风险证据无需执行。"
    elif trigger_invalid:
        status = "trigger_invalid"
        message = (
            "Codex review trigger context invalid: trigger comments must not "
            "disable repository context or local command access."
        )
    elif not trigger_found:
        status = "waiting_for_trigger"
        message = "未发现符合规则的 `@codex review` 触发评论。"
    elif not post_trigger_reviews and completion_comment is None:
        status = "waiting_for_codex"
        message = "已发现触发评论，正在等待 Codex 针对当前 head 输出 review。"
    else:
        status = "passed"
        message = "当前 head 的 Codex review 未发现阻断项，可以更新 PR 证据结论。"

    return MonitorReport(
        status=status,
        pr_number=pr_number,
        head_sha=head_sha,
        trigger_found=trigger_found,
        latest_review_url=latest_review_url,
        latest_review_sha=latest_review_sha,
        blocking_findings=blocking_findings,
        advisory_findings=advisory_findings,
        message=message,
        head_updated_at=head_created_at,
        context_invalid_reviews=context_invalid_reviews,
        trigger_invalid=trigger_invalid,
    )


def _contract_v1_official_codex_requirement(
    body: str,
    *,
    contract_errors: Sequence[str],
    changed_files: Sequence[str] | None,
    labels: Sequence[str] | None,
) -> tuple[bool, list[str]]:
    errors = list(contract_errors)
    if errors:
        return True, errors
    required, body_errors = _official_codex_required(
        body,
        changed_files=changed_files,
        labels=labels,
    )
    missing_ai_review = f"PR body missing section: {AI_REVIEW_SECTION_HEADER}"
    if body_errors == [missing_ai_review]:
        return True, []
    body_errors = [
        error
        for error in body_errors
        if error != "local check evidence must include verify full command"
    ]
    return required, body_errors


def render_monitor_comment(report: MonitorReport) -> str:
    status_label = {
        "waiting_for_trigger": "等待触发",
        "waiting_for_codex": "等待 Codex review",
        "trigger_invalid": "trigger context invalid",
        "context_invalid": "context invalid",
        "evidence_invalid": "PR evidence invalid",
        "blocked": "阻断",
        "passed": "可更新通过证据",
        "skipped": "授权跳过",
    }.get(report.status, report.status)
    latest_review = report.latest_review_url or "未发现"
    latest_sha = (
        _short_sha(report.latest_review_sha) if report.latest_review_sha else "未发现"
    )
    return "\n".join(
        [
            MONITOR_MARKER,
            render_monitor_head_state(
                head_sha=report.head_sha, head_updated_at=report.head_updated_at
            ),
            "## Codex Review Monitor",
            "",
            f"- PR: `#{report.pr_number}`",
            f"- 当前 head: `{_short_sha(report.head_sha)}`",
            f"- 状态: **{status_label}**",
            f"- 合规触发评论: {'已发现' if report.trigger_found else '未发现'}",
            f"- 最新当前 head Codex review: {latest_review}",
            f"- review commit: `{latest_sha}`",
            f"- context invalid: `{report.context_invalid_reviews}`",
            f"- 阻断项/未 resolved thread: `{report.blocking_findings}`",
            f"- P2: `{report.advisory_findings}`",
            "",
            report.message,
        ]
    )


def sync_monitor_comment(
    *, repo: str, pr_number: str, token: str, report: MonitorReport
) -> None:
    body = render_monitor_comment(report)
    comments = _fetch_github_list(
        repo=repo, path=f"issues/{pr_number}/comments", token=token
    )
    existing_id = _find_monitor_comment_id(comments)
    if existing_id:
        _request_json(
            method="PATCH",
            url=f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}",
            token=token,
            payload={"body": body},
        )
    else:
        _request_json(
            method="POST",
            url=f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            token=token,
            payload={"body": body},
        )


def sync_commit_status(
    *, repo: str, pr: Mapping[str, object], token: str, report: MonitorReport
) -> None:
    state = {
        "waiting_for_trigger": "pending",
        "waiting_for_codex": "pending",
        "trigger_invalid": "failure",
        "context_invalid": "failure",
        "evidence_invalid": "failure",
        "blocked": "failure",
        "passed": "success",
        "skipped": "success",
    }.get(report.status, "error")
    pr_url = (
        str(pr.get("html_url", ""))
        or f"https://github.com/{repo}/pull/{report.pr_number}"
    )
    target_url = report.latest_review_url or pr_url
    description = {
        "waiting_for_trigger": "Waiting for required @codex review trigger",
        "waiting_for_codex": "Waiting for Codex review on current head",
        "trigger_invalid": "Codex review trigger disables required context",
        "context_invalid": "Codex review context is invalid for current head",
        "evidence_invalid": "PR review evidence invalid",
        "blocked": "Codex review has blockers",
        "passed": "Codex review has no blockers",
        "skipped": "Official Codex review not required or skipped",
    }.get(report.status, "Codex review monitor status unavailable")
    _request_json(
        method="POST",
        url=f"https://api.github.com/repos/{repo}/statuses/{report.head_sha}",
        token=token,
        payload={
            "state": state,
            "target_url": target_url,
            "description": description[:140],
            "context": _review_status_context(),
        },
    )


def _review_status_context() -> str:
    return pr_flow_contract.load_contract(Path(".")).required_checks[0]


def _has_required_trigger_comment(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
) -> bool:
    return (
        _required_trigger_time(issue_comments, head_created_at=head_created_at)
        is not None
    )


def _required_trigger_time(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> str | None:
    matched_times = [
        _comment_effective_time(comment)
        for comment in _required_trigger_comments(
            issue_comments,
            head_created_at=head_created_at,
            expected_pr_url=expected_pr_url,
            expected_head_sha=expected_head_sha,
        )
    ]
    return max(matched_times) if matched_times else None


def _required_trigger_comments(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> tuple[Mapping[str, object], ...]:
    matched: list[Mapping[str, object]] = []
    for comment in _trigger_candidate_comments(
        issue_comments, head_created_at=head_created_at
    ):
        if not _is_required_trigger_comment(
            comment,
            expected_pr_url=expected_pr_url,
            expected_head_sha=expected_head_sha,
        ):
            continue
        matched.append(comment)
    return tuple(matched)


def _trigger_candidate_comments(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> tuple[Mapping[str, object], ...]:
    matched: list[Mapping[str, object]] = []
    for comment in issue_comments:
        if not _is_trigger_candidate_comment(comment):
            continue
        effective_time = _comment_effective_time(comment)
        if not effective_time:
            if head_created_at:
                continue
        elif head_created_at and effective_time < head_created_at:
            continue
        if before_or_at and effective_time and before_or_at < effective_time:
            continue
        matched.append(comment)
    return tuple(matched)


def _has_context_hostile_trigger_comment(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> bool:
    latest = _latest_trigger_candidate_comment(
        issue_comments, head_created_at=head_created_at, before_or_at=before_or_at
    )
    return latest is not None and _is_context_hostile_trigger_comment(latest)


def _has_reused_official_evidence(body: str, *, head_sha: str) -> bool:
    if "复用状态: reused" not in body:
        return False
    required_tokens = (
        "触发方式: @codex review (reused)",
        "结论: 通过",
        "阻断问题: 无",
        "旧 head:",
        f"当前 head: {head_sha[:12]}",
        "复用原因:",
        "关键证据:",
    )
    return all(token in body for token in required_tokens)


def _latest_trigger_candidate_comment(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> Mapping[str, object] | None:
    latest: Mapping[str, object] | None = None
    latest_time = ""
    for comment in _trigger_candidate_comments(
        issue_comments, head_created_at=head_created_at, before_or_at=before_or_at
    ):
        effective_time = _comment_effective_time(comment)
        if latest is None or not effective_time or not latest_time or latest_time <= effective_time:
            latest = comment
            latest_time = effective_time
    return latest


def _is_trigger_candidate_comment(comment: Mapping[str, object]) -> bool:
    user = comment.get("user")
    login = user.get("login") if isinstance(user, Mapping) else ""
    if str(login) in CODEX_REVIEW_AUTHORS:
        return False
    body = str(comment.get("body", ""))
    return all(token in body for token in REQUIRED_TRIGGER_TOKENS)


def _is_context_hostile_trigger_comment(comment: Mapping[str, object]) -> bool:
    if not _is_trigger_candidate_comment(comment):
        return False
    body = str(comment.get("body", ""))
    return not is_codex_review_request(body) or bool(
        CONTEXT_HOSTILE_TRIGGER_PATTERN.search(body)
    )


def _is_required_trigger_comment(
    comment: Mapping[str, object],
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> bool:
    if not _is_trigger_candidate_comment(comment):
        return False
    return is_codex_review_request(
        str(comment.get("body", "")),
        expected_pr_url=expected_pr_url,
        expected_head_sha=expected_head_sha,
    )


def _latest_codex_completion_comment(
    issue_comments: Sequence[Mapping[str, object]],
    *,
    head_created_at: str | None = None,
    trigger_time: str | None = None,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> Mapping[str, object] | None:
    matched: list[Mapping[str, object]] = []
    for comment in issue_comments:
        comment_time = _comment_effective_time(comment)
        if head_created_at and comment_time and comment_time < head_created_at:
            continue
        if trigger_time and comment_time and comment_time < trigger_time:
            continue
        if _is_required_trigger_comment(
            comment,
            expected_pr_url=expected_pr_url,
            expected_head_sha=expected_head_sha,
        ) and has_codex_completion_reaction(comment):
            matched.append(comment)
            continue
        if is_codex_completion_comment(comment):
            matched.append(comment)
    if not matched:
        return None
    return sorted(
        matched,
        key=lambda comment: codex_completion_effective_time(
            comment,
            expected_pr_url=expected_pr_url,
            expected_head_sha=expected_head_sha,
        ),
    )[-1]


def _comment_effective_time(comment: Mapping[str, object]) -> str:
    created_at = str(comment.get("created_at", "") or "")
    updated_at = str(comment.get("updated_at", "") or "")
    if created_at and updated_at:
        return max(created_at, updated_at)
    return updated_at or created_at


def _current_head_codex_reviews(
    reviews: Sequence[Mapping[str, object]],
    *,
    head_sha: str,
) -> list[Mapping[str, object]]:
    return [
        review
        for review in reviews
        if str(review.get("commit_id", "")) == head_sha
        and is_effective_codex_review(review)
    ]


def _reviews_after_trigger(
    reviews: Sequence[Mapping[str, object]],
    *,
    trigger_time: str | None,
) -> list[Mapping[str, object]]:
    if trigger_time is None:
        return []
    return [
        review for review in reviews if _review_submitted_at(review) >= trigger_time
    ]


def _review_submitted_at(review: Mapping[str, object]) -> str:
    for key in ("submitted_at", "created_at", "updated_at"):
        value = review.get(key)
        if value:
            return str(value)
    return ""


def _latest_codex_review(
    reviews: Sequence[Mapping[str, object]],
) -> Mapping[str, object] | None:
    if not reviews:
        return None
    return sorted(reviews, key=_review_sort_key)[-1]


def _review_sort_key(review: Mapping[str, object]) -> str:
    for key in ("submitted_at", "created_at", "updated_at"):
        value = review.get(key)
        if value:
            return str(value)
    return str(review.get("id", ""))


def _review_url(*, repo: str, pr_number: str, review: Mapping[str, object]) -> str:
    return f"https://github.com/{repo}/pull/{pr_number}#pullrequestreview-{review.get('id')}"


def _issue_comment_url(
    *, repo: str, pr_number: str, comment: Mapping[str, object]
) -> str:
    return (
        str(comment.get("html_url", ""))
        or f"https://github.com/{repo}/pull/{pr_number}#issuecomment-{comment.get('id')}"
    )


def _count_review_findings(
    review: Mapping[str, object] | None,
    *,
    review_comments: Sequence[Mapping[str, object]],
    pattern: re.Pattern[str],
) -> int:
    if review is None:
        return 0
    review_id = str(review.get("id", ""))
    texts = [str(review.get("body", ""))]
    for comment in review_comments:
        if str(comment.get("pull_request_review_id", "")) == review_id:
            texts.append(str(comment.get("body", "")))
    if pattern is BLOCKING_CODEX_FINDING_PATTERN and any(
        CODEX_CONTEXT_INVALID_PATTERN.search(text) for text in texts
    ):
        return 0
    return sum(1 for text in texts if pattern.search(text))


def _count_reviews_findings(
    reviews: Sequence[Mapping[str, object]],
    *,
    review_comments: Sequence[Mapping[str, object]],
    pattern: re.Pattern[str],
) -> int:
    return sum(
        _count_review_findings(review, review_comments=review_comments, pattern=pattern)
        for review in reviews
    )


def _find_monitor_comment_id(comments: Sequence[object]) -> int | None:
    for comment in comments:
        if not isinstance(comment, Mapping):
            continue
        if MONITOR_MARKER in str(comment.get("body", "")):
            raw_id = comment.get("id")
            return int(raw_id) if raw_id is not None else None
    return None


def _head_sha(pr: Mapping[str, object]) -> str:
    head = pr.get("head")
    if isinstance(head, Mapping):
        return str(head.get("sha", ""))
    return ""


def _short_sha(value: str | None) -> str:
    return (value or "")[:7] or "unknown"


def _api_url(*, repo: str, path: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"https://api.github.com/repos/{repo}/{path}{separator}per_page=100"


def _request_json(
    *, method: str, url: str, token: str, payload: object | None = None
) -> tuple[object, str | None]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return parsed, _parse_next_link(response.headers.get("Link", ""))


def _fetch_github_json(*, repo: str, path: str, token: str) -> object:
    payload, _ = _request_json(
        method="GET", url=_api_url(repo=repo, path=path), token=token
    )
    return payload


def _fetch_github_list(*, repo: str, path: str, token: str) -> list[object]:
    items: list[object] = []
    url: str | None = _api_url(repo=repo, path=path)
    while url:
        payload, url = _request_json(method="GET", url=url, token=token)
        if not isinstance(payload, list):
            return items
        items.extend(payload)
    return items


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
        item["reaction_items"] = _as_mapping_list(
            _fetch_github_list(
                repo=repo, path=f"issues/comments/{comment_id}/reactions", token=token
            )
        )
        enriched.append(item)
    return enriched


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


def _read_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    return value if value else None


def _read_json_file(path: Path | None) -> object | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _as_mapping(payload: object | None) -> Mapping[str, object]:
    return payload if isinstance(payload, Mapping) else {}


def _as_mapping_list(payload: object | None) -> list[Mapping[str, object]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, Mapping)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-env", default="GITHUB_REPOSITORY")
    parser.add_argument("--pr-number-env", default="PR_NUMBER")
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN")
    parser.add_argument("--summary-file-env", default="GITHUB_STEP_SUMMARY")
    parser.add_argument("--sync-comment", action="store_true")
    parser.add_argument("--sync-status", action="store_true")
    parser.add_argument("--pr-file", type=Path)
    parser.add_argument("--comments-file", type=Path)
    parser.add_argument("--reviews-file", type=Path)
    parser.add_argument("--review-comments-file", type=Path)
    parser.add_argument("--review-threads-file", type=Path)
    parser.add_argument("--head-updated-at-env")
    parser.add_argument("--head-created-at-env", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    repo = _read_env(args.repo_env)
    pr_number = _read_env(args.pr_number_env)
    token = _read_env(args.github_token_env)
    if not repo or not pr_number:
        print("error: repo and PR number are required", file=sys.stderr)
        return 2

    pr = _as_mapping(_read_json_file(args.pr_file))
    issue_comments = _as_mapping_list(_read_json_file(args.comments_file))
    reviews = _as_mapping_list(_read_json_file(args.reviews_file))
    review_comments = _as_mapping_list(_read_json_file(args.review_comments_file))
    review_threads = _as_mapping_list(_read_json_file(args.review_threads_file))
    changed_files: Sequence[str] | None = None
    labels: Sequence[str] | None = None
    head_created_at = _read_env(args.head_updated_at_env) or _read_env(
        args.head_created_at_env
    )

    if token:
        if not pr:
            pr = _as_mapping(
                _fetch_github_json(repo=repo, path=f"pulls/{pr_number}", token=token)
            )
        if not issue_comments:
            issue_comments = _as_mapping_list(
                _fetch_github_list(
                    repo=repo, path=f"issues/{pr_number}/comments", token=token
                )
            )
        issue_comments = _enrich_required_trigger_reactions(
            issue_comments, repo=repo, token=token
        )
        if not reviews:
            reviews = _as_mapping_list(
                _fetch_github_list(
                    repo=repo, path=f"pulls/{pr_number}/reviews", token=token
                )
            )
        if not review_comments:
            review_comments = _as_mapping_list(
                _fetch_github_list(
                    repo=repo, path=f"pulls/{pr_number}/comments", token=token
                )
            )
        if not review_threads:
            review_threads = _fetch_pr_review_threads(
                repo=repo, pr_number=pr_number, token=token
            )
        changed_files = _fetch_pr_changed_files(
            repo=repo, pr_number=pr_number, token=token
        )
        labels = _issue_label_names(
            _fetch_issue_metadata(repo=repo, pr_number=pr_number, token=token)
        )
        if not head_created_at:
            head_created_at = head_updated_at_from_monitor_state(
                issue_comments,
                expected_head_sha=_head_sha(pr),
            )

    if not head_created_at:
        head_created_at = head_updated_at_from_monitor_state(
            issue_comments,
            expected_head_sha=_head_sha(pr),
        )

    report = build_monitor_report(
        repo=repo,
        pr_number=pr_number,
        pr=pr,
        issue_comments=issue_comments,
        reviews=reviews,
        review_comments=review_comments,
        review_threads=review_threads,
        changed_files=changed_files,
        labels=labels,
        head_created_at=head_created_at,
    )
    body = render_monitor_comment(report)
    print(body)

    summary_file = _read_env(args.summary_file_env)
    if summary_file:
        Path(summary_file).write_text(body + "\n", encoding="utf-8")

    if args.sync_status:
        if not token:
            print(
                "error: GITHUB_TOKEN is required when --sync-status is used",
                file=sys.stderr,
            )
            return 2
        sync_commit_status(repo=repo, pr=pr, token=token, report=report)
    if args.sync_comment:
        if not token:
            print(
                "error: GITHUB_TOKEN is required when --sync-comment is used",
                file=sys.stderr,
            )
            return 2
        try:
            sync_monitor_comment(
                repo=repo, pr_number=pr_number, token=token, report=report
            )
        except urllib.error.HTTPError as error:
            if error.code != 403:
                raise
            print(
                "warning: unable to sync monitor PR comment: HTTP 403", file=sys.stderr
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
