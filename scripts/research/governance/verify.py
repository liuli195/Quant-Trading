"""Affected governance verification entrypoints."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .affected import (
    AffectedPlan,
    ChangedFileCollectionError,
    ChangedFileSource,
    CheckSpec,
    collect_changed_files,
    plan_checks,
)
from . import verify_cache


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    command: tuple[str, ...]
    ok: bool
    returncode: int
    subjects: tuple[str, ...] = ()
    scope: str = "scoped"
    skipped: bool = False
    stdout: str = ""
    stderr: str = ""
    cache_hit: bool = False
    cache_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "command": list(self.command),
            "ok": self.ok,
            "returncode": self.returncode,
            "subjects": list(self.subjects),
            "scope": self.scope,
            "skipped": self.skipped,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "cache_hit": self.cache_hit,
            "cache_key": self.cache_key,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            command=tuple(str(item) for item in payload.get("command", [])),
            ok=bool(payload["ok"]),
            returncode=int(payload["returncode"]),
            subjects=tuple(str(item) for item in payload.get("subjects", [])),
            scope=str(payload.get("scope", "scoped")),
            skipped=bool(payload.get("skipped", False)),
            stdout=str(payload.get("stdout", "")),
            stderr=str(payload.get("stderr", "")),
            cache_hit=True,
            cache_key=str(payload.get("cache_key", "")),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    explain = subparsers.add_parser("explain", help="explain affected checks")
    _add_affected_arguments(explain)
    explain.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format",
    )
    explain.set_defaults(func=_cmd_explain)

    fast = subparsers.add_parser("fast", help="run affected fast checks")
    _add_affected_arguments(fast)
    fast.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format",
    )
    fast.set_defaults(func=_cmd_fast)

    full = subparsers.add_parser("full", help="run full governance verification")
    full.add_argument("--repo-root", default=".")
    full.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format",
    )
    full.set_defaults(func=_cmd_full)

    return parser


def _add_affected_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--base")
    parser.add_argument("--files", nargs="+", default=None)
    parser.add_argument("--ai-review-report")


def _cmd_explain(args: argparse.Namespace) -> int:
    try:
        source = _collect_source(args)
    except ChangedFileCollectionError as exc:
        return _render_collection_error(args, str(exc))
    plan = plan_checks(source.files, repo_root=args.repo_root)
    if args.format == "json":
        print(json.dumps(_explain_payload(plan, Path(args.repo_root)), ensure_ascii=False, indent=2))
    else:
        print(render_text(plan))
    return 0


def _cmd_fast(args: argparse.Namespace) -> int:
    try:
        source = _collect_source(args)
    except ChangedFileCollectionError as exc:
        return _render_collection_error(args, str(exc))
    plan = plan_checks(source.files, repo_root=args.repo_root)
    results = [_run_check(check, repo_root=Path(args.repo_root)) for check in plan.checked]
    ok = all(result.ok for result in results)
    payload = {
        "ok": ok,
        "checked": [result.to_dict() for result in results],
        "skipped": [check.to_dict() for check in plan.skipped],
        "full_not_run": plan.full_not_run,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_fast_text(payload))
    return 0 if ok else 1


def _collect_source(args: argparse.Namespace) -> ChangedFileSource:
    return collect_changed_files(
        args.repo_root,
        staged=args.staged,
        base=args.base,
        files=args.files,
        ai_review_report=args.ai_review_report,
    )


def _render_collection_error(args: argparse.Namespace, message: str) -> int:
    payload = {
        "ok": False,
        "error": message,
        "changed_files": [],
        "checked": [],
        "skipped": [],
        "full_required": False,
        "full_not_run": True,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"error: {message}", file=sys.stderr)
    return 1


def _cmd_full(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    results = [_run_full_command(command, root) for command in _full_commands()]
    ok = all(result.ok for result in results)
    payload = {
        "ok": ok,
        "checked": [result.to_dict() for result in results],
        "skipped": [],
        "full_not_run": False,
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_fast_text(payload))
    return 0 if ok else 1


def _full_commands() -> tuple[CheckSpec, ...]:
    return (
        CheckSpec(
            "ruff.governance",
            ("python", "-m", "ruff", "check", "scripts/research/governance"),
            scope="full",
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
            scope="full",
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
            scope="full",
        ),
        CheckSpec("pip-audit.dependencies", ("python", "-m", "pip_audit"), scope="full"),
        CheckSpec(
            "pytest.governance",
            (
                "python",
                "-m",
                "pytest",
                "scripts/research/governance/tests",
                "-q",
                "--basetemp",
                ".local/pytest-tmp/verify-full",
                "-p",
                "no:cacheprovider",
            ),
            scope="full",
        ),
        CheckSpec(
            "pathref.full",
            ("python", "-m", "scripts.tools.path_tools.refactor", "check"),
            scope="full",
        ),
        CheckSpec(
            "governance.full",
            ("python", "-m", "scripts.research.governance", "gate"),
            scope="full",
        ),
    )


def _run_full_command(check: CheckSpec, root: Path) -> CheckResult:
    command = _python_command(check.command)
    result = _run_command(command, root)
    return CheckResult(
        check_id=check.check_id,
        command=command,
        ok=result.returncode == 0,
        returncode=result.returncode,
        scope=check.scope,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )


def _run_check(check: CheckSpec, *, repo_root: Path) -> CheckResult:
    root = repo_root.resolve()
    if check.check_id in {
        "pathref.changed-files",
        "skill-ownership.scoped",
        "ruff.governance",
        "bandit.governance",
        "mypy.governance",
        "pytest.governance",
        "py_compile.strategy",
        "pip-audit.dependencies",
    }:
        command = _python_command(check.command)
        key, key_summary = verify_cache.cache_key(root, check, command)
        cached = verify_cache.load(root, key)
        if cached is not None:
            cached["cache_key"] = key_summary
            return CheckResult.from_dict(cached)
        result = _run_command(command, root)
        check_result = CheckResult(
            check_id=check.check_id,
            command=command,
            ok=result.returncode == 0,
            returncode=result.returncode,
            subjects=check.subjects,
            scope=check.scope,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            cache_key=key_summary,
        )
        if check_result.ok:
            verify_cache.store(root, key, check_result.to_dict())
        return check_result
    if check.check_id in {"pathref.full", "governance.full"}:
        command = _python_command(check.command)
        result = _run_command(command, root)
        return CheckResult(
            check_id=check.check_id,
            command=command,
            ok=result.returncode == 0,
            returncode=result.returncode,
            subjects=check.subjects,
            scope=check.scope,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    if check.check_id == "pytest.strategy":
        test_dir = root / check.inputs[0] if check.inputs else root / "__missing__"
        command = _python_command(check.command)
        if not test_dir.is_dir():
            return CheckResult(
                check_id=check.check_id,
                command=command,
                ok=True,
                returncode=0,
                subjects=check.subjects,
                scope=check.scope,
                skipped=True,
                stdout=f"skipped: missing test directory {check.inputs[0]}",
            )
        key, key_summary = verify_cache.cache_key(root, check, command)
        cached = verify_cache.load(root, key)
        if cached is not None:
            cached["cache_key"] = key_summary
            return CheckResult.from_dict(cached)
        result = _run_command(command, root)
        check_result = CheckResult(
            check_id=check.check_id,
            command=command,
            ok=result.returncode == 0,
            returncode=result.returncode,
            subjects=check.subjects,
            scope=check.scope,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            cache_key=key_summary,
        )
        if check_result.ok:
            verify_cache.store(root, key, check_result.to_dict())
        return check_result
    return CheckResult(
        check_id=check.check_id,
        command=check.command,
        ok=True,
        returncode=0,
        subjects=check.subjects,
        scope=check.scope,
        skipped=True,
        stdout="skipped: runner not implemented",
    )


def _python_command(command: tuple[str, ...]) -> tuple[str, ...]:
    if command and command[0] == "python":
        return (sys.executable, *command[1:])
    return command


def _run_command(command: tuple[str, ...], root: Path) -> subprocess.CompletedProcess[str]:
    _prepare_command_paths(command, root)
    return subprocess.run(
        list(command),
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _prepare_command_paths(command: tuple[str, ...], root: Path) -> None:
    for index, item in enumerate(command):
        if item == "--basetemp" and index + 1 < len(command):
            (root / command[index + 1]).parent.mkdir(parents=True, exist_ok=True)


def render_text(plan: AffectedPlan) -> str:
    lines = ["checked:"]
    if plan.checked:
        for check in plan.checked:
            subjects = f" ({', '.join(check.subjects)})" if check.subjects else ""
            lines.append(f"  - {check.check_id}{subjects}")
    else:
        lines.append("  - none")
    lines.append("skipped:")
    if plan.skipped:
        lines.extend(f"  - {check.check_id}" for check in plan.skipped)
    else:
        lines.append("  - none")
    lines.append(f"full-not-run: {str(plan.full_not_run).lower()}")
    return "\n".join(lines)


def _explain_payload(plan: AffectedPlan, root: Path) -> dict[str, Any]:
    payload = plan.to_dict()
    for check_payload, check in zip(payload["checked"], plan.checked, strict=True):
        command = _python_command(check.command)
        _, key_summary = verify_cache.cache_key(root.resolve(), check, command)
        check_payload["cache_key"] = key_summary
    return payload


def render_fast_text(payload: dict[str, Any]) -> str:
    lines = [f"ok: {str(payload['ok']).lower()}", "checked:"]
    checked = payload.get("checked") or []
    if checked:
        for item in checked:
            status = "skipped" if item.get("skipped") else ("passed" if item.get("ok") else "failed")
            subjects = item.get("subjects") or []
            suffix = f" ({', '.join(subjects)})" if subjects else ""
            scope = f" [{item.get('scope')}]" if item.get("scope") else ""
            lines.append(f"  - {item.get('check_id')}{suffix}{scope}: {status}")
    else:
        lines.append("  - none")
    lines.append("skipped:")
    skipped = payload.get("skipped") or []
    if skipped:
        lines.extend(f"  - {item.get('check_id')}" for item in skipped)
    else:
        lines.append("  - none")
    lines.append(f"full-not-run: {str(payload['full_not_run']).lower()}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
