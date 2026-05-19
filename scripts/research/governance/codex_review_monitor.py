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

from scripts.research.governance.pr_review_evidence import (
    BLOCKING_CODEX_FINDING_PATTERN,
    CODEX_REVIEW_AUTHORS,
)


MONITOR_MARKER = "<!-- codex-review-monitor -->"
REQUIRED_TRIGGER_TOKENS = ("@codex review", "AGENTS.md", "docs/rules/review-guidelines.md", "docs/rules/*.md")
P2_FINDING_PATTERN = re.compile(r"(?:P2 Badge|badge/P2-)", re.IGNORECASE)


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


def build_monitor_report(
    *,
    repo: str,
    pr_number: str,
    pr: Mapping[str, object],
    issue_comments: Sequence[Mapping[str, object]],
    reviews: Sequence[Mapping[str, object]],
    review_comments: Sequence[Mapping[str, object]],
) -> MonitorReport:
    """Build a status summary for Codex reviews on the PR head."""

    head_sha = _head_sha(pr)
    trigger_found = _has_required_trigger_comment(issue_comments)
    current_head_reviews = _current_head_codex_reviews(reviews, head_sha=head_sha)
    latest_review = _latest_codex_review(current_head_reviews)
    latest_review_url = _review_url(repo=repo, pr_number=pr_number, review=latest_review) if latest_review else None
    latest_review_sha = str(latest_review.get("commit_id", "")) if latest_review else None
    blocking_findings = _count_reviews_findings(
        current_head_reviews,
        review_comments=review_comments,
        pattern=BLOCKING_CODEX_FINDING_PATTERN,
    )
    advisory_findings = _count_reviews_findings(
        current_head_reviews,
        review_comments=review_comments,
        pattern=P2_FINDING_PATTERN,
    )

    if not trigger_found:
        status = "waiting_for_trigger"
        message = "未发现符合规则的 `@codex review` 触发评论。"
    elif latest_review is None:
        status = "waiting_for_codex"
        message = "已发现触发评论，正在等待 Codex 针对当前 head 输出 review。"
    elif blocking_findings:
        status = "blocked"
        message = "Codex review 含 P0/P1 阻断发现，不能填写通过结论。"
    else:
        status = "passed"
        message = "当前 head 的 Codex review 未发现 P0/P1，可以更新 PR 证据结论。"

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
    )


def render_monitor_comment(report: MonitorReport) -> str:
    status_label = {
        "waiting_for_trigger": "等待触发",
        "waiting_for_codex": "等待 Codex review",
        "blocked": "阻断",
        "passed": "可更新通过证据",
    }.get(report.status, report.status)
    latest_review = report.latest_review_url or "未发现"
    latest_sha = _short_sha(report.latest_review_sha) if report.latest_review_sha else "未发现"
    return "\n".join(
        [
            MONITOR_MARKER,
            "## Codex Review Monitor",
            "",
            f"- PR: `#{report.pr_number}`",
            f"- 当前 head: `{_short_sha(report.head_sha)}`",
            f"- 状态: **{status_label}**",
            f"- 合规触发评论: {'已发现' if report.trigger_found else '未发现'}",
            f"- 最新当前 head Codex review: {latest_review}",
            f"- review commit: `{latest_sha}`",
            f"- P0/P1: `{report.blocking_findings}`",
            f"- P2: `{report.advisory_findings}`",
            "",
            report.message,
        ]
    )


def sync_monitor_comment(*, repo: str, pr_number: str, token: str, report: MonitorReport) -> None:
    body = render_monitor_comment(report)
    comments = _fetch_github_list(repo=repo, path=f"issues/{pr_number}/comments", token=token)
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


def sync_commit_status(*, repo: str, pr: Mapping[str, object], token: str, report: MonitorReport) -> None:
    state = {
        "waiting_for_trigger": "failure",
        "waiting_for_codex": "pending",
        "blocked": "failure",
        "passed": "success",
    }.get(report.status, "error")
    pr_url = str(pr.get("html_url", "")) or f"https://github.com/{repo}/pull/{report.pr_number}"
    target_url = report.latest_review_url or pr_url
    description = {
        "waiting_for_trigger": "Waiting for required @codex review trigger",
        "waiting_for_codex": "Waiting for Codex review on current head",
        "blocked": "Codex review has P0/P1 findings",
        "passed": "Codex review has no P0/P1 findings",
    }.get(report.status, "Codex review monitor status unavailable")
    _request_json(
        method="POST",
        url=f"https://api.github.com/repos/{repo}/statuses/{report.head_sha}",
        token=token,
        payload={
            "state": state,
            "target_url": target_url,
            "description": description[:140],
            "context": "Codex Review Monitor",
        },
    )


def _has_required_trigger_comment(issue_comments: Sequence[Mapping[str, object]]) -> bool:
    for comment in issue_comments:
        body = str(comment.get("body", ""))
        if all(token in body for token in REQUIRED_TRIGGER_TOKENS):
            return True
    return False


def _current_head_codex_reviews(
    reviews: Sequence[Mapping[str, object]],
    *,
    head_sha: str,
) -> list[Mapping[str, object]]:
    return [
        review
        for review in reviews
        if str(review.get("commit_id", "")) == head_sha and _is_codex_author(review.get("user"))
    ]


def _latest_codex_review(reviews: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    if not reviews:
        return None
    return sorted(reviews, key=_review_sort_key)[-1]


def _is_codex_author(user: object) -> bool:
    login = user.get("login") if isinstance(user, Mapping) else ""
    return str(login) in CODEX_REVIEW_AUTHORS


def _review_sort_key(review: Mapping[str, object]) -> str:
    for key in ("submitted_at", "created_at", "updated_at"):
        value = review.get(key)
        if value:
            return str(value)
    return str(review.get("id", ""))


def _review_url(*, repo: str, pr_number: str, review: Mapping[str, object]) -> str:
    return f"https://github.com/{repo}/pull/{pr_number}#pullrequestreview-{review.get('id')}"


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


def _request_json(*, method: str, url: str, token: str, payload: object | None = None) -> tuple[object, str | None]:
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
    payload, _ = _request_json(method="GET", url=_api_url(repo=repo, path=path), token=token)
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

    if token:
        if not pr:
            pr = _as_mapping(_fetch_github_json(repo=repo, path=f"pulls/{pr_number}", token=token))
        if not issue_comments:
            issue_comments = _as_mapping_list(
                _fetch_github_list(repo=repo, path=f"issues/{pr_number}/comments", token=token)
            )
        if not reviews:
            reviews = _as_mapping_list(_fetch_github_list(repo=repo, path=f"pulls/{pr_number}/reviews", token=token))
        if not review_comments:
            review_comments = _as_mapping_list(
                _fetch_github_list(repo=repo, path=f"pulls/{pr_number}/comments", token=token)
            )

    report = build_monitor_report(
        repo=repo,
        pr_number=pr_number,
        pr=pr,
        issue_comments=issue_comments,
        reviews=reviews,
        review_comments=review_comments,
    )
    body = render_monitor_comment(report)
    print(body)

    summary_file = _read_env(args.summary_file_env)
    if summary_file:
        Path(summary_file).write_text(body + "\n", encoding="utf-8")

    if args.sync_status:
        if not token:
            print("error: GITHUB_TOKEN is required when --sync-status is used", file=sys.stderr)
            return 2
        sync_commit_status(repo=repo, pr=pr, token=token, report=report)
    if args.sync_comment:
        if not token:
            print("error: GITHUB_TOKEN is required when --sync-comment is used", file=sys.stderr)
            return 2
        try:
            sync_monitor_comment(repo=repo, pr_number=pr_number, token=token, report=report)
        except urllib.error.HTTPError as error:
            if error.code != 403:
                raise
            print("warning: unable to sync monitor PR comment: HTTP 403", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
