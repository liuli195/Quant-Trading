"""Local cache for passed affected governance checks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .affected import CheckSpec


CACHE_VERSION = "1"
CACHE_DIR = Path(".local") / "governance-cache"
CONFIG_INPUTS = (
    "path_aliases.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Makefile",
    "scripts/research/governance",
    "scripts/tools/path_tools",
)


def cache_key(root: Path, check: CheckSpec, command: tuple[str, ...]) -> tuple[str, str]:
    payload = {
        "cache_version": CACHE_VERSION,
        "check_id": check.check_id,
        "command": list(command),
        "inputs": {item: _hash_path(root / item) for item in check.inputs},
        "config": {item: _hash_path(root / item) for item in CONFIG_INPUTS if (root / item).exists()},
        "python_version": sys.version,
        "tool_version": CACHE_VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return digest, digest[:12]


def load(root: Path, key: str) -> dict[str, Any] | None:
    path = root / CACHE_DIR / f"{key}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def store(root: Path, key: str, payload: dict[str, Any]) -> None:
    cache_dir = root / CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _hash_path(path: Path) -> str:
    if path.is_file():
        return _hash_bytes(path.read_bytes())
    if path.is_dir():
        items: list[tuple[str, str]] = []
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            items.append((child.relative_to(path).as_posix(), _hash_bytes(child.read_bytes())))
        return _hash_bytes(json.dumps(items, sort_keys=True).encode("utf-8"))
    return "missing"


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
