"""Fixed Codex review request contract."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


CODEX_REVIEW_COMMAND = "@codex review"
CODEX_REVIEW_SCOPE_HEADER = "Review Scope："
CODEX_REVIEW_FOCUS_LINE = "审查重点：仅 P0/P1 合并阻断风险"


@dataclass(frozen=True)
class CodexReviewRequest:
    """Parsed fixed-template Codex review request."""

    pr_url: str
    head_sha: str
    review_scope: tuple[str, ...]


def render_codex_review_request(
    *,
    pr_url: str,
    head_sha: str,
    review_scope: Sequence[str] = (),
) -> str:
    """Return the only accepted Codex review trigger body."""

    lines = [
        CODEX_REVIEW_COMMAND,
        "",
        f"PR：{pr_url}",
        f"HEAD：{head_sha}",
        CODEX_REVIEW_SCOPE_HEADER,
    ]
    lines.extend(f"- {path}" for path in review_scope)
    lines.extend(["", CODEX_REVIEW_FOCUS_LINE])
    return "\n".join(lines)


def parse_codex_review_request(body: str) -> CodexReviewRequest | None:
    """Parse the fixed Codex review trigger template."""

    normalized_body = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_body.split("\n")
    if len(lines) < 7:
        return None
    if lines[0] != CODEX_REVIEW_COMMAND or lines[1] != "":
        return None
    if not lines[2].startswith("PR："):
        return None
    pr_url = lines[2].removeprefix("PR：")
    if not pr_url:
        return None
    if not lines[3].startswith("HEAD："):
        return None
    head_sha = lines[3].removeprefix("HEAD：")
    if not head_sha:
        return None
    if lines[4] != CODEX_REVIEW_SCOPE_HEADER:
        return None

    scope: list[str] = []
    index = 5
    while index < len(lines) and lines[index].startswith("- "):
        path = lines[index].removeprefix("- ")
        if not path:
            return None
        scope.append(path)
        index += 1

    if index >= len(lines) or lines[index] != "":
        return None
    index += 1
    if index != len(lines) - 1 or lines[index] != CODEX_REVIEW_FOCUS_LINE:
        return None
    return CodexReviewRequest(
        pr_url=pr_url,
        head_sha=head_sha,
        review_scope=tuple(scope),
    )


def is_codex_review_request(
    body: str,
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
) -> bool:
    """Return whether a comment body exactly matches the trigger template."""

    request = parse_codex_review_request(body)
    if request is None:
        return False
    if expected_pr_url and request.pr_url != expected_pr_url:
        return False
    if expected_head_sha and request.head_sha != expected_head_sha:
        return False
    return True
