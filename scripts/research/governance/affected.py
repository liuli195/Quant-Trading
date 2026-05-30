"""Plan scoped governance checks for changed repository files."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALL_CHECK_IDS = (
    "pathref.changed-files",
    "pathref.full",
    "skill-ownership.scoped",
    "ruff.governance",
    "bandit.governance",
    "mypy.governance",
    "pytest.governance",
    "governance.full",
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
class StrategyChange:
    name: str
    source_files: tuple[str, ...]
    run_pytest: bool = False


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


class ChangedFileCollectionError(RuntimeError):
    """Raised when changed-file discovery cannot safely determine scope."""


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
        staged_files = _git_changed_files(root, ["--cached"])
        changed.extend(staged_files)
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


def plan_checks(changed_files: Sequence[str | Path], *, repo_root: str | Path = ".") -> AffectedPlan:
    root = Path(repo_root).resolve()
    normalized = tuple(sorted(dict.fromkeys(_normalize_path(path) for path in changed_files)))
    checked: list[CheckSpec] = []

    markdown = tuple(
        path for path in normalized if path.endswith(".md") and _path_exists(root, path)
    )
    deleted_markdown = tuple(
        path for path in normalized if path.endswith(".md") and not _path_exists(root, path)
    )
    if markdown:
        checked.append(
            CheckSpec(
                "pathref.changed-files",
                ("python", "-m", "scripts.tools.path_tools.refactor", "check", "--files", *markdown),
                inputs=markdown,
            )
        )

    if deleted_markdown or _requires_full_pathref(normalized):
        checked.append(
            CheckSpec(
                "pathref.full",
                ("python", "-m", "scripts.tools.path_tools.refactor", "check"),
                inputs=("scripts/tools/path_tools", "path_aliases.json"),
                scope="full",
                full_required=True,
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
                inputs=(".codex/skills", ".claude/skills", "docs/rules/skills.md"),
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
                    inputs=("scripts/research/governance",),
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
                    inputs=("scripts/research/governance",),
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
                    inputs=("scripts/research/governance",),
                ),
                CheckSpec(
                    "pytest.governance",
                    (
                        "python",
                        "-m",
                        "pytest",
                        "scripts/research/governance/tests",
                        "-q",
                        "--basetemp",
                        ".local/pytest-tmp/governance-fast",
                        "-p",
                        "no:cacheprovider",
                    ),
                    inputs=("scripts/research/governance",),
                ),
            )
        )

    if _requires_full_governance(normalized):
        checked.append(
            CheckSpec(
                "governance.full",
                ("python", "-m", "scripts.research.governance", "gate"),
                inputs=_full_governance_inputs(),
                scope="full",
                full_required=True,
            )
        )

    for strategy_change in _strategy_changes(normalized, root):
        for source in strategy_change.source_files:
            checked.append(
                CheckSpec(
                    "py_compile.strategy",
                    ("python", "-m", "py_compile", source),
                    inputs=(source,),
                    subjects=(strategy_change.name,),
                )
            )
        if strategy_change.run_pytest:
            test_dir = f"strategies/{strategy_change.name}/tests"
            checked.append(
                CheckSpec(
                    "pytest.strategy",
                    (
                        "python",
                        "-m",
                        "pytest",
                        test_dir,
                        "-q",
                        "--basetemp",
                        f".local/pytest-tmp/strategy-{strategy_change.name}-fast",
                        "-p",
                        "no:cacheprovider",
                    ),
                    inputs=(test_dir, *strategy_change.source_files),
                    subjects=(strategy_change.name,),
                )
            )

    checked = _dedupe_checks(checked)
    checked_ids = {check.check_id for check in checked}
    skipped = tuple(_empty_check(check_id) for check_id in ALL_CHECK_IDS if check_id not in checked_ids)
    return AffectedPlan(
        changed_files=normalized,
        checked=tuple(checked),
        skipped=skipped,
        full_required=any(check.full_required for check in checked),
        full_not_run=True,
    )


def _empty_check(check_id: str) -> CheckSpec:
    return CheckSpec(check_id=check_id, command=(), inputs=(), scope="skipped")


def _normalize_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _path_exists(root: Path, path: str) -> bool:
    return (root / path).exists()


def _git_changed_files(root: Path, args: Sequence[str]) -> list[str]:
    command = ["git", "-c", "core.quotePath=false", "diff", "--name-only", *args]
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
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        raise ChangedFileCollectionError(f"git diff failed: {detail}")
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


def _strategy_changes(paths: Sequence[str], root: Path) -> tuple[StrategyChange, ...]:
    changes: dict[str, dict[str, object]] = {}
    for path in paths:
        parts = path.split("/")
        if len(parts) < 2 or parts[0] != "strategies":
            continue
        strategy = parts[1]
        record = changes.setdefault(strategy, {"source_files": set(), "run_pytest": False})
        exists = _path_exists(root, path)
        is_test_path = len(parts) >= 3 and parts[2] == "tests"
        if is_test_path and exists:
            record["run_pytest"] = True
        elif path.endswith(".py") and exists:
            source_files = record["source_files"]
            if isinstance(source_files, set):
                source_files.add(path)
            record["run_pytest"] = True

    strategy_changes: list[StrategyChange] = []
    for strategy in sorted(changes):
        record = changes[strategy]
        source_files = record["source_files"]
        sources = tuple(sorted(source_files)) if isinstance(source_files, set) else ()
        run_pytest = bool(record["run_pytest"])
        if sources or run_pytest:
            strategy_changes.append(
                StrategyChange(name=strategy, source_files=sources, run_pytest=run_pytest)
            )
    return tuple(strategy_changes)


def _skill_names(paths: Sequence[str]) -> tuple[str, ...]:
    names: list[str] = []
    for path in paths:
        parts = path.split("/")
        if len(parts) >= 3 and parts[0] in {".codex", ".claude"} and parts[1] == "skills":
            names.append(parts[2])
    return tuple(sorted(dict.fromkeys(names)))


def _requires_full_pathref(paths: Sequence[str]) -> bool:
    return any(
        path.startswith("scripts/tools/path_tools/")
        or path == "path_aliases.json"
        for path in paths
    )


def _requires_full_governance(paths: Sequence[str]) -> bool:
    exact = {"AGENTS.md", "CLAUDE.md", "indexes.md", "Makefile", "path_aliases.json"}
    prefixes = (
        ".githooks/",
        ".github/workflows/",
        ".codex/skills/",
        ".claude/skills/",
        "docs/adr/",
        "docs/rules/",
        "scripts/research/governance/",
        "scripts/research/registry/",
        "scripts/research/layers/",
        "scripts/tools/path_tools/",
    )
    return any(path in exact or path.startswith(prefixes) for path in paths)


def _full_governance_inputs() -> tuple[str, ...]:
    return (
        "AGENTS.md",
        "CLAUDE.md",
        "indexes.md",
        "docs/rules",
        "docs/adr",
        ".codex/skills",
        ".claude/skills",
        ".githooks",
        ".github/workflows",
        "scripts/research/governance",
        "scripts/research/registry",
        "scripts/research/layers",
        "scripts/tools/path_tools",
        "path_aliases.json",
        "Makefile",
    )


def _dedupe_checks(checks: Sequence[CheckSpec]) -> list[CheckSpec]:
    deduped: list[CheckSpec] = []
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str]] = set()
    for check in checks:
        key = (check.check_id, check.command, check.inputs, check.subjects, check.scope)
        if key in seen:
            continue
        deduped.append(check)
        seen.add(key)
    return deduped
