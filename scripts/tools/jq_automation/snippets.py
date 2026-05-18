from __future__ import annotations

from pathlib import Path

from .paths import repo_root


class SnippetError(RuntimeError):
    """Raised when a browser-side contract snippet cannot be found."""


def read_snippet(name: str, root: Path | None = None) -> str:
    base = root or repo_root()
    candidates = [
        base / "scripts" / "tools" / "jq_automation" / "snippets" / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise SnippetError(f"Could not find browser snippet: {name}")
