"""Fixed Codex review request contract."""

from __future__ import annotations


CODEX_REVIEW_REQUEST_TEMPLATE = "@codex review"


def render_codex_review_request() -> str:
    """Return the only accepted Codex review trigger body."""

    return CODEX_REVIEW_REQUEST_TEMPLATE


def is_codex_review_request(body: str) -> bool:
    """Return whether a comment body exactly matches the trigger template."""

    return body == CODEX_REVIEW_REQUEST_TEMPLATE
