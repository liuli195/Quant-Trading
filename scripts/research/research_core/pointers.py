"""Data-center pointer aware file readers."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any


def read_data_center_pointer(path: str | Path) -> dict[str, Any] | None:
    """Return the pointer payload when ``path`` is a data-center pointer file."""

    pointer_path = Path(path)
    if not pointer_path.is_file() or pointer_path.stat().st_size > 8192:
        return None
    try:
        payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and payload.get("kind") == "data_center_pointer":
        return payload
    return None


def resolve_data_center_pointer(path: str | Path) -> Path | None:
    """Resolve a data-center pointer to its stored raw file path."""

    pointer_path = Path(path)
    pointer = read_data_center_pointer(path)
    if pointer is None:
        return None
    snapshot = Path(str(pointer.get("dataset_snapshot", "")))
    dataset_file = str(pointer.get("dataset_file", ""))
    if not dataset_file:
        return None
    target = snapshot / dataset_file
    if target.is_file():
        return target
    if not snapshot.is_absolute():
        pointer_target = pointer_path.parent / snapshot / dataset_file
        if pointer_target.is_file():
            return pointer_target
        repo_root = _find_repo_root(pointer_path)
        if repo_root is not None:
            repo_target = repo_root / snapshot / dataset_file
            if repo_target.is_file():
                return repo_target
        cwd_target = Path.cwd() / snapshot / dataset_file
        if cwd_target.is_file():
            return cwd_target
    return target


def _find_repo_root(path: Path) -> Path | None:
    current = path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def read_logical_bytes(path: str | Path) -> bytes:
    """Read the original payload, following pointer files and gzip storage."""

    source_path = Path(path)
    target = resolve_data_center_pointer(source_path)
    if target is not None:
        return read_logical_bytes(target)
    raw = source_path.read_bytes()
    if source_path.suffix.lower() == ".gz":
        return gzip.decompress(raw)
    return raw


def read_text_file(path: str | Path) -> str:
    """Read a UTF-8 text payload after resolving pointers and gzip files."""

    return read_logical_bytes(path).decode("utf-8-sig")


def read_json_object(path: str | Path) -> dict[str, Any]:
    """Read a JSON object after resolving pointers and gzip files."""

    payload = json.loads(read_text_file(path))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload
