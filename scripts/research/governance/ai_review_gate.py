"""Validate local AI review reports and generate Codex review scope."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BLOCKING_SEVERITIES = {"P0", "P1"}
VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}
VALID_STATUSES = {"open", "fixed", "false_positive", "accepted"}
REQUIRED_CROSS_REVIEW_SKILLS = (
    "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
    "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
)
HIGH_RISK_PREFIXES = (
    "strategies/",
    "scripts/research/platform/",
    "scripts/research/governance/",
    ".github/",
    ".githooks/",
    "docs/rules/",
    "docs/adr/",
)


@dataclass(frozen=True)
class AiReviewValidation:
    ok: bool
    risk_level: str
    requires_official_codex_review: bool
    errors: tuple[str, ...]
    review_scope: str


def validate_report_file(path: Path) -> AiReviewValidation:
    if not path.is_file():
        return AiReviewValidation(
            False, "unknown", True, (f"AI review report missing: {path}",), ""
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return AiReviewValidation(
            False, "unknown", True, (f"AI review report invalid JSON: {exc}",), ""
        )
    return validate_report(payload)


def validate_report(payload: dict[str, Any]) -> AiReviewValidation:
    errors: list[str] = []
    risk_level = str(payload.get("risk_level") or "unknown")
    changed_files = _string_list(payload.get("changed_files"))
    findings = payload.get("findings")
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if str(payload.get("tool") or "") not in {"codex", "claude"}:
        errors.append("tool must be codex or claude")
    raw_reviewers = payload.get("reviewers")
    reviewers = _string_list(raw_reviewers)
    distinct_reviewers = {
        _normalize_reviewer_identity(reviewer) for reviewer in reviewers
    }
    if isinstance(raw_reviewers, list) and any(
        not isinstance(item, str) for item in raw_reviewers
    ):
        errors.append("reviewers must contain only strings")
    if not reviewers:
        errors.append("reviewers must not be empty")
    elif len(distinct_reviewers) < 2:
        errors.append(
            "reviewers must include at least two distinct reviewers for cross-review"
        )
    if any(_is_placeholder_reviewer_name(reviewer) for reviewer in reviewers):
        errors.append("reviewers must not contain placeholder reviewer names")
    errors.extend(_cross_review_errors(payload.get("cross_review")))
    if risk_level not in {"low", "high", "unknown"}:
        errors.append("risk_level must be low, high, or unknown")
        risk_level = "unknown"
    if not changed_files:
        errors.append("changed_files must not be empty")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        findings = []

    for item in findings:
        if not isinstance(item, dict):
            errors.append("each finding must be an object")
            continue
        finding_id = str(item.get("id") or "<missing-id>")
        severity = str(item.get("severity") or "")
        status = str(item.get("status") or "")
        if severity not in VALID_SEVERITIES:
            errors.append(f"finding {finding_id} has invalid severity")
        if status not in VALID_STATUSES:
            errors.append(f"finding {finding_id} has invalid status")
        if severity in BLOCKING_SEVERITIES and status not in {
            "fixed",
            "false_positive",
        }:
            errors.append(f"P0/P1 finding {finding_id} is not closed")
        if status == "false_positive" and not str(item.get("evidence") or "").strip():
            errors.append(f"false_positive finding {finding_id} missing evidence")
        if severity == "P2" and status == "accepted":
            if not str(item.get("defer_reason") or "").strip():
                errors.append(f"P2 finding {finding_id} accepted without defer_reason")
            if not str(item.get("risk_acceptance") or "").strip():
                errors.append(
                    f"P2 finding {finding_id} accepted without risk_acceptance"
                )

    high_risk_by_path = any(_is_high_risk_path(path) for path in changed_files)
    requires_official = (
        bool(payload.get("requires_official_codex_review"))
        or risk_level != "low"
        or high_risk_by_path
    )
    if high_risk_by_path and risk_level == "low":
        errors.append("high-risk changed files cannot be risk_level low")
        risk_level = "high"
        requires_official = True
    review_scope = build_codex_review_scope(
        payload, requires_official=requires_official
    )
    return AiReviewValidation(
        not errors, risk_level, requires_official, tuple(errors), review_scope
    )


def build_codex_review_scope(
    payload: dict[str, Any], *, requires_official: bool
) -> str:
    changed_files = _string_list(payload.get("changed_files"))
    high_risk_files = [path for path in changed_files if _is_high_risk_path(path)]
    risk_files = high_risk_files or changed_files
    finding_lines = []
    for item in payload.get("findings") or []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "")
        if severity in {"P0", "P1", "P2"}:
            finding_lines.append(
                f"- {item.get('id')}: {severity} {item.get('title')} ({item.get('path')}) status={item.get('status')}"
            )
    scope_files = "\n".join(f"- `{path}`" for path in risk_files)
    findings_text = (
        "\n".join(finding_lines)
        if finding_lines
        else "- 无未关闭 P0/P1；无必须交给官方复核的本地发现。"
    )
    if not requires_official:
        return "本 PR 当前不要求官方 Codex Review。"
    return (
        "@codex review\n\n"
        "请只审以下高风险范围的 P0/P1 逻辑风险，不做全量风格审查。\n\n"
        "## Review Scope\n\n"
        "### 高风险文件\n"
        f"{scope_files}\n\n"
        "### 本地 AI Review 结果\n"
        f"{findings_text}\n\n"
        "### 审查重点\n"
        "- 交易逻辑、治理门禁、安全边界、数据解释是否存在 P0/P1 风险。\n"
        "- 不需要重复给出 P2/P3 风格建议。\n"
    )


def render_markdown_report(payload: dict[str, Any]) -> str:
    result = validate_report(payload)
    changed_files = _string_list(payload.get("changed_files"))
    findings = [
        item for item in payload.get("findings") or [] if isinstance(item, dict)
    ]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}

    lines = [
        "# 本地 AI Review 报告",
        "",
        f"- 工具: {payload.get('tool', '')}",
        f"- Reviewers: {', '.join(_string_list(payload.get('reviewers')))}",
        f"- 风险等级: {result.risk_level}",
        f"- 是否需要官方 Codex Review: {'是' if result.requires_official_codex_review else '否'}",
        f"- 校验结果: {'通过' if result.ok else '失败'}",
    ]
    lines.extend(_render_cross_review(payload.get("cross_review")))
    lines.extend(["", "## 变更文件", ""])
    lines.extend(f"- `{path}`" for path in changed_files)
    if not changed_files:
        lines.append("- 无")

    lines.extend(["", "## 问题清单", ""])
    if findings:
        for item in findings:
            lines.append(
                f"- {item.get('id')}: {item.get('severity')} {item.get('title')} "
                f"(`{item.get('path')}`) status={item.get('status')}"
            )
            if item.get("defer_reason"):
                lines.append(f"  - defer_reason: {item.get('defer_reason')}")
            if item.get("risk_acceptance"):
                lines.append(f"  - risk_acceptance: {item.get('risk_acceptance')}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 检查结果", ""])
    if checks:
        lines.extend(f"- {name}: {status}" for name, status in checks.items())
    else:
        lines.append("- 无")

    if result.errors:
        lines.extend(["", "## 校验错误", ""])
        lines.extend(f"- {error}" for error in result.errors)

    return "\n".join(lines) + "\n"


def _is_high_risk_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if _is_generated_strategy_artifact(normalized):
        return False
    return any(normalized.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)


def _is_generated_strategy_artifact(path: str) -> bool:
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "strategies" and parts[2] == "backtest_runs"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if isinstance(item, str) and (text := item.strip())]


def _is_placeholder_reviewer_name(value: str) -> bool:
    normalized = value.strip().strip("`\"'")
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    compact = _normalize_reviewer_identity(normalized.strip("<>"))
    return compact in {
        "a",
        "b",
        "reviewera",
        "reviewerb",
        "controller",
        "coordinator",
        "implementer",
        "mainagent",
        "mainsession",
        "主会话",
        "实现者",
        "规格评审子agent",
        "代码质量评审子agent",
    }


def _normalize_reviewer_identity(value: str) -> str:
    return "".join(value.strip().strip("`\"'").split()).casefold()


def _cross_review_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["cross_review.delegated_to_subagents must be true"]
    errors: list[str] = []
    if value.get("delegated_to_subagents") is not True:
        errors.append("cross_review.delegated_to_subagents must be true")
    skills = {skill.casefold() for skill in _string_list(value.get("review_skills"))}
    required_skills = {skill.casefold() for skill in REQUIRED_CROSS_REVIEW_SKILLS}
    if not required_skills.issubset(skills):
        errors.append(
            "cross_review.review_skills must include superpowers:subagent-driven-development/spec-reviewer-prompt.md and superpowers:subagent-driven-development/code-quality-reviewer-prompt.md"
        )
    if not str(value.get("evidence") or "").strip():
        errors.append("cross_review.evidence must be filled")
    return errors


def _render_cross_review(value: Any) -> list[str]:
    lines = ["", "## 子 agent 交叉评审", ""]
    if not isinstance(value, dict):
        lines.append("- 未记录")
        return lines
    delegated = "是" if value.get("delegated_to_subagents") is True else "否"
    lines.append(f"- 已委派子 agent: {delegated}")
    skills = _string_list(value.get("review_skills"))
    if skills:
        lines.append("- Superpowers 评审技能:")
        lines.extend(f"  - `{skill}`" for skill in skills)
    else:
        lines.append("- Superpowers 评审技能: 未记录")
    evidence = _single_line_text(value.get("evidence"))
    lines.append(f"- 证据: {evidence or '未记录'}")
    return lines


def _single_line_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "risk", "scope", "markdown"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--report", type=Path, required=True)
        if name in {"scope", "markdown"}:
            subparser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_report_file(args.report)
    if args.command == "scope":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.review_scope, encoding="utf-8")
    if args.command == "markdown":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = json.loads(args.report.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        args.output.write_text(render_markdown_report(payload), encoding="utf-8")
    if args.command == "risk":
        print(result.risk_level)
    if args.command == "validate":
        print("AI review report ok" if result.ok else "AI review report failed")
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
