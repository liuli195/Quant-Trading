"""Plan scoped governance checks for changed repository files."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Sequence


ALL_CHECK_IDS = (
    "pathref.changed-files",
    "skill-ownership.scoped",
    "ruff.governance",
    "bandit.governance",
    "mypy.governance",
    "pytest.governance",
    "py_compile.strategy",
    "pytest.strategy",
    "pip-audit.dependencies",
)


@dataclass(frozen=True)
class ChangedFileSource:
    source: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    command: tuple[str, ...]
    inputs: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    scope: str = "scoped"
    full_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "command": list(self.command),
            "inputs": list(self.inputs),
            "subjects": list(self.subjects),
            "scope": self.scope,
            "full_required": self.full_required,
        }


@dataclass(frozen=True)
class AffectedPlan:
    changed_files: tuple[str, ...]
    checked: tuple[CheckSpec, ...]
    skipped: tuple[CheckSpec, ...]
    full_required: bool = False
    full_not_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_files": list(self.changed_files),
            "checked": [check.to_dict() for check in self.checked],
            "skipped": [check.to_dict() for check in self.skipped],
            "full_required": self.full_required,
            "full_not_run": self.full_not_run,
        }


def collect_changed_files(
    repo_root: str | Path,
    *,
    staged: bool = False,
    base: str | None = None,
    files: Sequence[str | Path] | None = None,
    ai_review_report: str | Path | None = None,
) -> ChangedFileSource:
    root = Path(repo_root).resolve()
    changed: list[str] = []
    source_parts: list[str] = []

    if files:
        changed.extend(_normalize_path(path) for path in files)
        source_parts.append("files")

    if base:
        changed.extend(_git_changed_files(root, [base, "HEAD"]))
        source_parts.append(f"base:{base}")

    if staged:
        changed.extend(_git_changed_files(root, ["--cached"]))
        source_parts.append("staged")

    if not files and not base and not staged:
        changed.extend(_git_changed_files(root, []))
        source_parts.append("worktree")

    report_path = Path(ai_review_report) if ai_review_report else None
    if report_path is None:
        report_path = root / ".local" / "ai-review" / "latest.json"
    if report_path.is_file():
        changed.extend(_changed_files_from_ai_review(report_path))
        source_parts.append("ai-review")

    normalized = tuple(sorted(dict.fromkeys(item for item in changed if item)))
    return ChangedFileSource(source="+".join(source_parts) or "none", files=normalized)


def plan_checks(changed_files: Sequence[str | Path]) -> AffectedPlan:
    normalized = tuple(sorted(dict.fromkeys(_normalize_path(path) for path in changed_files)))
    checked: list[CheckSpec] = []

    docs = tuple(path for path in normalized if path.startswith("docs/") and path.endswith(".md"))
    if docs:
        checked.append(
            CheckSpec(
                "pathref.changed-files",
                ("python", "-m", "scripts.tools.path_tools.refactor", "check", "--files", *docs),
                inputs=docs,
            )
        )

    skills = tuple(
        path
        for path in normalized
        if path.startswith(".codex/skills/") or path.startswith(".claude/skills/")
    )
    if skills:
        checked.append(
            CheckSpec(
                "skill-ownership.scoped",
                ("python", "-m", "scripts.research.governance.skill_ownership", "check"),
                inputs=skills,
                subjects=_skill_names(skills),
            )
        )

    requirements = tuple(
        path for path in normalized if path in {"requirements.txt", "requirements-dev.txt"}
    )
    if requirements:
        checked.append(
            CheckSpec(
                "pip-audit.dependencies",
                ("python", "-m", "pip_audit"),
                inputs=requirements,
            )
        )

    governance = tuple(
        path for path in normalized if path.startswith("scripts/research/governance/")
    )
    if governance:
        checked.extend(
            (
                CheckSpec(
                    "ruff.governance",
                    ("python", "-m", "ruff", "check", "scripts/research/governance"),
                    inputs=governance,
                ),
                CheckSpec(
                    "bandit.governance",
                    (
                        "python",
                        "-m",
                        "bandit",
                        "-q",
                        "-r",
                        "scripts/research/governance",
                        "-x",
                        "scripts/research/governance/tests",
                        "-s",
                        "B310,B404,B603,B607",
                    ),
                    inputs=governance,
                ),
                CheckSpec(
                    "mypy.governance",
                    (
                        "python",
                        "-m",
                        "mypy",
                        "--explicit-package-bases",
                        "--follow-imports=skip",
                        "--ignore-missing-imports",
                        "scripts/research/governance",
                    ),
                    inputs=governance,
                ),
                CheckSpec(
                    "pytest.governance",
                    ("python", "-m", "pytest", "scripts/research/governance/tests", "-q"),
                    inputs=governance,
                ),
            )
        )

    strategies = _strategy_names(normalized)
    for strategy in strategies:
        source = f"strategies/{strategy}/{strategy}.py"
        checked.append(
            CheckSpec(
                "py_compile.strategy",
                ("python", "-m", "py_compile", source),
                inputs=(source,),
            )
        )
        checked.append(
            CheckSpec(
                "pytest.strategy",
                ("python", "-m", "pytest", f"strategies/{strategy}/tests", "-q"),
                inputs=(f"strategies/{strategy}/tests",),
            )
        )

    checked_ids = {check.check_id for check in checked}
    skipped = tuple(_empty_check(check_id) for check_id in ALL_CHECK_IDS if check_id not in checked_ids)
    return AffectedPlan(
        changed_files=normalized,
        checked=tuple(checked),
        skipped=skipped,
        full_required=False,
        full_not_run=True,
    )


def _empty_check(check_id: str) -> CheckSpec:
    return CheckSpec(check_id=check_id, command=(), inputs=(), scope="skipped")


def _normalize_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _git_changed_files(root: Path, args: Sequence[str]) -> list[str]:
    command = ["git", "diff", "--name-only", *args]
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return []
    return [_normalize_path(line) for line in result.stdout.splitlines() if line.strip()]


def _changed_files_from_ai_review(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    files = payload.get("changed_files")
    if not isinstance(files, list):
        return []
    return [_normalize_path(item) for item in files if isinstance(item, str)]


def _strategy_names(paths: Sequence[str]) -> tuple[str, ...]:
    names: list[str] = []
    for path in paths:
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "strategies":
            names.append(parts[1])
    return tuple(sorted(dict.fromkeys(names)))


def _skill_names(paths: Sequence[str]) -> tuple[str, ...]:
    names: list[str] = []
    for path in paths:
        parts = path.split("/")
        if len(parts) >= 3 and parts[0] in {".codex", ".claude"} and parts[1] == "skills":
            names.append(parts[2])
    return tuple(sorted(dict.fromkeys(names)))
