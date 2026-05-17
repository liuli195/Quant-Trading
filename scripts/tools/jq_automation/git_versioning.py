from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .paths import automation_tmp_dir, repo_root

SAFE_LABEL_RE = re.compile(r"[^a-zA-Z0-9._-]")


class GitVersionError(RuntimeError):
    """Raised when a Git ref cannot be resolved or a file cannot be read."""


def resolve_git_ref(ref: str, root: Path | None = None) -> str:
    """Convert a branch, tag, or short SHA into a full commit SHA."""
    root = root or repo_root()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=str(root),
            capture_output=True,
            text=True, encoding="utf-8",
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GitVersionError(f"Failed to resolve git ref '{ref}': {exc.stderr.strip()}") from exc
    sha = result.stdout.strip()
    if not sha:
        raise GitVersionError(f"Git ref '{ref}' resolved to empty string")
    return sha


def assert_file_at_commit(commit: str, path: str, root: Path | None = None) -> str:
    """Verify that *path* exists in *commit* and return the canonical commit SHA."""
    root = root or repo_root()
    resolved = resolve_git_ref(commit, root=root)
    result = subprocess.run(
        ["git", "ls-tree", resolved, "--", path],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise GitVersionError(
            f"File '{path}' not found in commit {resolved[:12]}"
        )
    return resolved


def read_file_at_commit(commit: str, path: str, root: Path | None = None) -> str:
    """Read the content of *path* from *commit* without checking it out.

    Returns the file content as a UTF-8 string.
    """
    root = root or repo_root()
    resolved = assert_file_at_commit(commit, path, root=root)
    try:
        result = subprocess.run(
            ["git", "show", f"{resolved}:{path}"],
            cwd=str(root),
            capture_output=True,
            text=True, encoding="utf-8",
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GitVersionError(
            f"Failed to read '{path}' at commit {resolved[:12]}: {exc.stderr.strip()}"
        ) from exc
    return result.stdout


def materialize_strategy_source(
    commit: str, path: str, experiment_id: str, label: str, root: Path | None = None
) -> Path:
    """Write the strategy source from *commit* to a temporary file for upload.

    Returns the path to the written file.
    """
    content = read_file_at_commit(commit, path, root=root)
    safe_label = SAFE_LABEL_RE.sub("-", label).strip("-") or "variant"
    out_dir = automation_tmp_dir(root) / "ab" / _sanitize_label(experiment_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_label}_source.py"
    out_path.write_text(content, encoding="utf-8")
    return out_path


def git_code_fingerprint(commit: str, path: str, root: Path | None = None) -> str:
    """Return a short fingerprint: ``<commit[:12]>:<blob_sha[:8]>``."""
    root = root or repo_root()
    resolved = resolve_git_ref(commit, root=root)
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{resolved}:{path}"],
            cwd=str(root),
            capture_output=True,
            text=True, encoding="utf-8",
            check=True,
        )
        blob_sha = result.stdout.strip()
    except subprocess.CalledProcessError:
        # Fall back to content hash if git rev-parse on the path fails
        content = read_file_at_commit(resolved, path, root=root)
        blob_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    return f"{resolved[:12]}:{blob_sha[:8]}"


def compute_uploaded_code_sha256(file_path: str | Path) -> str:
    """Compute SHA-256 of the final upload .py file."""
    content = Path(file_path).read_text(encoding="utf-8")
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _sanitize_label(label: str) -> str:
    """Replace characters unsafe for file/directory names."""
    safe = SAFE_LABEL_RE.sub("-", label)
    safe = safe.strip("-")
    return safe or "unnamed"
