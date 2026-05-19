"""Validate required PR review evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


REQUIRED_REVIEWER = "Codex"
SECTION_HEADER = "Codex Code Review 结论"
CODEX_REVIEW_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)#pullrequestreview-(?P<review_id>\d+)"
)
CODEX_COMPLETION_COMMENT_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)#issuecomment-(?P<comment_id>\d+)"
)
CODEX_REVIEW_AUTHORS = {"chatgpt-codex-connector", "chatgpt-codex-connector[bot]"}
DISQUALIFIED_CODEX_REVIEW_STATES = {"DISMISSED", "PENDING"}
MONITOR_STATE_PATTERN = re.compile(r"<!--\s*codex-review-monitor-state\s+(?P<payload>\{.*?\})\s*-->", re.DOTALL)
BLOCKING_CODEX_FINDING_PATTERN = re.compile(
    r"(?:P[01] Badge|badge/P[01]-|(?:^|\n)\s*(?:\*\*)?\[P[01]\]\s+)",
    re.IGNORECASE,
)
REQUIRED_TRIGGER_TOKENS = ("@codex review", "AGENTS.md", "docs/rules/review-guidelines.md", "docs/rules/*.md")


@dataclass(frozen=True)
class EvidenceReport:
    ok: bool
    errors: tuple[str, ...]


def validate_pr_body(
    body: str,
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
    expected_head_created_at: str | None = None,
    comments: Sequence[object] | None = None,
    reviews: Sequence[Mapping[str, object]] | None = None,
    review_comments: Sequence[Mapping[str, object]] | None = None,
) -> EvidenceReport:
    """Return whether a PR body contains merge-blocking review evidence."""

    errors: list[str] = []
    section = _extract_section(body)
    if section is None:
        return EvidenceReport(False, (f"PR body missing section: {SECTION_HEADER}",))

    reviewer = _read_field(section, "Reviewer")
    trigger = _read_field(section, "触发方式")
    conclusion = _read_field(section, "结论")
    blockers = _read_field(section, "阻断问题")

    if _normalize_value(reviewer) != REQUIRED_REVIEWER:
        errors.append(f"Reviewer must be {REQUIRED_REVIEWER}")
    normalized_trigger = _normalize_value(trigger)
    if not normalized_trigger:
        errors.append("触发方式 must be filled")
    else:
        if "@codex review" not in normalized_trigger:
            errors.append("触发方式 must include @codex review")
        if "AGENTS.md" not in normalized_trigger:
            errors.append("触发方式 must include AGENTS.md")
        if "docs/rules/review-guidelines.md" not in normalized_trigger:
            errors.append("触发方式 must include docs/rules/review-guidelines.md")
        if "docs/rules/*.md" not in normalized_trigger:
            errors.append("触发方式 must include docs/rules/*.md")
    if _normalize_value(conclusion) != "通过":
        errors.append("结论 must be 通过")
    if _normalize_value(blockers) != "无":
        errors.append("阻断问题 must be 无")
    if "关键证据" not in section:
        errors.append("review evidence must include 关键证据")
    elif not _has_nonempty_evidence(section):
        errors.append("review evidence must include at least one evidence item")
    else:
        review_link = _find_codex_evidence_link(section, expected_pr_url=expected_pr_url)
        if review_link is None:
            errors.append("review evidence must include a real Codex review link for this PR")
        elif reviews is not None:
            errors.extend(
                _codex_review_errors(
                    review_link,
                    reviews=reviews,
                    review_comments=review_comments,
                    expected_head_sha=expected_head_sha,
                    expected_head_created_at=expected_head_created_at,
                    comments=comments,
                )
            )
    if comments is not None and not _required_trigger_comments(comments):
        errors.append("PR comments must include the required @codex review trigger")
    if "scripts.research.governance gate" not in section:
        errors.append("review evidence must include governance gate command")

    return EvidenceReport(not errors, tuple(errors))


def _extract_section(body: str) -> str | None:
    lines = body.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if re.match(rf"^\s*##+\s+{re.escape(SECTION_HEADER)}\s*$", line):
            start = index + 1
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^\s*##+\s+\S+", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def _read_field(section: str, field: str) -> str:
    pattern = re.compile(rf"^\s*[-*]\s*{re.escape(field)}\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(section)
    return match.group(1) if match else ""


def _normalize_value(value: str) -> str:
    return value.strip().strip("`").strip()


def _has_nonempty_evidence(section: str) -> bool:
    evidence_start = section.find("关键证据")
    if evidence_start < 0:
        return False
    evidence = section[evidence_start:].splitlines()[1:]
    for line in evidence:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^[-*]\s*\S+", stripped):
            return True
    return False


def _find_codex_evidence_link(section: str, *, expected_pr_url: str | None = None) -> str | None:
    expected = _normalize_pr_url(expected_pr_url)
    evidence_start = section.find("关键证据")
    if evidence_start < 0:
        return None
    evidence = section[evidence_start:].splitlines()[1:]
    for line in evidence:
        if "Codex review 链接" not in line:
            continue
        match = CODEX_REVIEW_URL_PATTERN.search(line) or CODEX_COMPLETION_COMMENT_URL_PATTERN.search(line)
        if not match:
            continue
        url = match.group(0)
        if expected and not (
            url.startswith(f"{expected}#pullrequestreview-") or url.startswith(f"{expected}#issuecomment-")
        ):
            continue
        return url
    return None


def _codex_review_errors(
    review_link: str,
    *,
    reviews: Sequence[Mapping[str, object]],
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
    expected_head_created_at: str | None,
    comments: Sequence[object] | None,
) -> tuple[str, ...]:
    match = CODEX_REVIEW_URL_PATTERN.fullmatch(review_link)
    if match is None:
        comment_match = CODEX_COMPLETION_COMMENT_URL_PATTERN.fullmatch(review_link)
        if comment_match is not None and comments is not None:
            return _codex_completion_comment_errors(
                comment_match.group("comment_id"),
                comments=comments,
                reviews=reviews,
                review_comments=review_comments,
                expected_head_sha=expected_head_sha,
                expected_head_created_at=expected_head_created_at,
            )
        return ("Codex review link must match a Codex review on the current head",)
    review_id = match.group("review_id")
    matched_review: Mapping[str, object] | None = None
    for review in reviews:
        if str(review.get("id", "")) != review_id:
            continue
        matched_review = review
        if not is_effective_codex_review(review):
            return ("Codex review link must match a Codex review on the current head",)
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            return ("Codex review link must match a Codex review on the current head",)
        break
    if matched_review is None:
        return ("Codex review link must match a Codex review on the current head",)
    errors: list[str] = []
    trigger_comments = _required_trigger_comments(comments) if comments is not None else None
    if trigger_comments is not None:
        if not _has_required_trigger_after_current_head(trigger_comments, expected_head_created_at):
            errors.append("required @codex review trigger must be submitted after the current head")
        if not _review_is_after_required_trigger(
            matched_review,
            trigger_comments,
            expected_head_created_at=expected_head_created_at,
        ):
            errors.append("Codex review must be submitted after the required @codex review trigger")
    if _current_head_has_blocking_codex_review(
        reviews,
        review_comments=review_comments,
        expected_head_sha=expected_head_sha,
    ):
        errors.append("Codex review must not contain P0/P1 findings on the current head")
    return tuple(errors)


def _codex_completion_comment_errors(
    comment_id: str,
    *,
    comments: Sequence[object],
    reviews: Sequence[Mapping[str, object]],
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
    expected_head_created_at: str | None,
) -> tuple[str, ...]:
    comment = _find_comment_by_id(comments, comment_id)
    if comment is None or not _is_required_trigger_comment(comment):
        return ("Codex review link must match a Codex review on the current head",)

    errors: list[str] = []
    if not _has_required_trigger_after_current_head((comment,), expected_head_created_at):
        errors.append("required @codex review trigger must be submitted after the current head")
    if not has_codex_completion_reaction(comment):
        errors.append("Codex completion comment must include a Codex thumbs-up reaction")
    if _current_head_has_blocking_codex_review(
        reviews,
        review_comments=review_comments,
        expected_head_sha=expected_head_sha,
    ):
        errors.append("Codex review must not contain P0/P1 findings on the current head")
    return tuple(errors)


def _review_has_blocking_findings(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> bool:
    texts = [str(review.get("body", ""))]
    if review_comments is not None:
        for comment in review_comments:
            if str(comment.get("pull_request_review_id", "")) == review_id:
                texts.append(str(comment.get("body", "")))
    return any(BLOCKING_CODEX_FINDING_PATTERN.search(text) for text in texts)


def _current_head_has_blocking_codex_review(
    reviews: Sequence[Mapping[str, object]],
    *,
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
) -> bool:
    for review in reviews:
        if not is_effective_codex_review(review):
            continue
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            continue
        if _review_has_blocking_findings(review, review_id=str(review.get("id", "")), review_comments=review_comments):
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


def _required_trigger_comments(comments: Sequence[object]) -> tuple[object, ...]:
    matched: list[object] = []
    for comment in comments:
        if _is_required_trigger_comment(comment):
            matched.append(comment)
    return tuple(matched)


def _is_required_trigger_comment(comment: object) -> bool:
    body = _comment_body(comment)
    return all(token in body for token in REQUIRED_TRIGGER_TOKENS)


def _comment_body(comment: object) -> str:
    if isinstance(comment, str):
        return comment
    if isinstance(comment, Mapping):
        return str(comment.get("body", ""))
    return ""


def _find_comment_by_id(comments: Sequence[object], comment_id: str) -> Mapping[str, object] | None:
    for comment in comments:
        if not isinstance(comment, Mapping):
            continue
        if str(comment.get("id", "")) == comment_id:
            return comment
    return None


def has_codex_completion_reaction(comment: Mapping[str, object]) -> bool:
    comment_time = _comment_effective_time(comment)
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
        return True
    return False


def _comment_reaction_items(comment: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
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
    review_time = _first_value(review, "submitted_at", "created_at")
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
    return _latest_required_trigger_time(
        trigger_comments,
        expected_head_created_at=expected_head_created_at,
    ) is not None


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
        trigger_times = [value for value in trigger_times if expected_head_created_at <= value]
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
    payload, _ = _fetch_github_json_url(url=_github_api_url(repo=repo, path=path), token=token)
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


def _fetch_pr_metadata(*, repo: str, pr_number: str, token: str) -> Mapping[str, object] | None:
    payload = _fetch_github_json(repo=repo, path=f"pulls/{pr_number}", token=token)
    return payload if isinstance(payload, Mapping) else None


def _fetch_pr_comments(*, repo: str, pr_number: str, token: str) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(repo=repo, path=f"issues/{pr_number}/comments", token=token)
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
        item["reaction_items"] = _fetch_issue_comment_reactions(repo=repo, comment_id=str(comment_id), token=token)
        enriched.append(item)
    return enriched


def _fetch_issue_comment_reactions(*, repo: str, comment_id: str, token: str) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(repo=repo, path=f"issues/comments/{comment_id}/reactions", token=token)
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_reviews(*, repo: str, pr_number: str, token: str) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(repo=repo, path=f"pulls/{pr_number}/reviews", token=token)
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_review_comments(*, repo: str, pr_number: str, token: str) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(repo=repo, path=f"pulls/{pr_number}/comments", token=token)
    return [item for item in payload if isinstance(item, Mapping)]


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
    expected_pr_url = _read_env(args.pr_url_env)
    expected_head_sha = _read_env(args.head_sha_env)
    expected_head_created_at = _read_env(args.head_updated_at_env) or _read_env(args.head_created_at_env)

    repo = _read_env(args.repo_env)
    pr_number = _read_env(args.pr_number_env)
    token = _read_env(args.github_token_env)
    if repo and pr_number and token:
        pr_metadata: Mapping[str, object] | None = None
        if not body or not expected_pr_url or not expected_head_sha or not expected_head_created_at:
            pr_metadata = _fetch_pr_metadata(repo=repo, pr_number=pr_number, token=token)
            if pr_metadata is not None:
                if not body:
                    body = str(pr_metadata.get("body", ""))
                if not expected_pr_url:
                    expected_pr_url = str(pr_metadata.get("html_url", ""))
                head = pr_metadata.get("head")
                if not expected_head_sha and isinstance(head, Mapping):
                    expected_head_sha = str(head.get("sha", ""))
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
            review_comments = _fetch_pr_review_comments(repo=repo, pr_number=pr_number, token=token)

    if not expected_head_created_at:
        expected_head_created_at = head_updated_at_from_monitor_state(
            comments,
            expected_head_sha=expected_head_sha,
        )

    report = validate_pr_body(
        body,
        expected_pr_url=expected_pr_url,
        expected_head_sha=expected_head_sha,
        expected_head_created_at=expected_head_created_at,
        comments=comments,
        reviews=reviews,
        review_comments=review_comments,
    )
    if report.ok:
        print("PR review evidence ok")
        return 0
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
