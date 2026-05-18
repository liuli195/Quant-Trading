"""Validate required PR review evidence."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_AGENT = "pr-governance-review"
SECTION_HEADER = "评审治理 Agent 结论"


@dataclass(frozen=True)
class EvidenceReport:
    ok: bool
    errors: tuple[str, ...]


def validate_pr_body(body: str) -> EvidenceReport:
    """Return whether a PR body contains merge-blocking review evidence."""

    errors: list[str] = []
    section = _extract_section(body)
    if section is None:
        return EvidenceReport(False, (f"PR body missing section: {SECTION_HEADER}",))

    agent = _read_field(section, "Agent")
    conclusion = _read_field(section, "结论")
    blockers = _read_field(section, "阻断问题")

    if _normalize_value(agent) != REQUIRED_AGENT:
        errors.append(f"Agent must be {REQUIRED_AGENT}")
    if _normalize_value(conclusion) != "通过":
        errors.append("结论 must be 通过")
    if _normalize_value(blockers) != "无":
        errors.append("阻断问题 must be 无")
    if "关键证据" not in section:
        errors.append("review evidence must include 关键证据")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file", type=Path)
    source.add_argument("--body-env")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8", errors="replace")
    else:
        body = os.environ.get(args.body_env, "")

    report = validate_pr_body(body)
    if report.ok:
        print("PR review evidence ok")
        return 0
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
