"""Validate local AI review reports and generate Codex review scope."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .pr_review_evidence import (
    AI_REVIEW_SECTION_HEADER,
    P2_SECTION_HEADER,
    SECTION_HEADER,
)


BLOCKING_SEVERITIES = {"P0", "P1"}
CURRENT_SCHEMA_VERSION = 2
VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}
VALID_STATUSES = {"open", "fixed", "false_positive", "accepted"}
VALID_REVIEW_MODES = {"complete", "partial"}
REQUIRED_CROSS_REVIEW_SKILLS = (
    "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
    "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
)
REQUIRED_SECURITY_REVIEW_TOOLS = {
    "codex": "codex-security",
    "claude": "security-guidance",
}
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
    official_codex_review_skipped: bool = False
    review_mode: str = "complete"


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
    schema_version = payload.get("schema_version")
    risk_level = str(payload.get("risk_level") or "unknown")
    changed_files = _string_list(payload.get("changed_files"))
    findings = payload.get("findings")
    if schema_version != CURRENT_SCHEMA_VERSION:
        errors.append("schema_version must be 2")
    tool = str(payload.get("tool") or "")
    if tool not in {"codex", "claude"}:
        errors.append("tool must be codex or claude")
    errors.extend(_security_review_errors(payload.get("security_review"), tool))
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

    review_mode = _review_mode(payload)
    if review_mode not in VALID_REVIEW_MODES:
        errors.append("review_mode must be complete or partial")
    elif review_mode == "complete":
        errors.extend(
            _complete_review_errors(payload.get("complete_review"), reviewers)
        )
    elif review_mode == "partial":
        errors.extend(
            _authorization_errors(
                payload.get("review_mode_authorization"),
                "partial review mode",
            )
        )

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
    natural_requires_official = (
        bool(payload.get("requires_official_codex_review"))
        or risk_level != "low"
        or high_risk_by_path
    )
    skip_official = bool(payload.get("skip_official_codex_review"))
    skip_auth_errors: list[str] = []
    if skip_official:
        skip_auth_errors = _authorization_errors(
            payload.get("official_codex_review_skip_authorization"),
            "official Codex review skip",
        )
        errors.extend(skip_auth_errors)
    official_skip_authorized = skip_official and not skip_auth_errors
    requires_official = natural_requires_official and not official_skip_authorized
    if high_risk_by_path and risk_level == "low":
        errors.append("high-risk changed files cannot be risk_level low")
        risk_level = "high"
        requires_official = not official_skip_authorized
    review_scope = build_codex_review_scope(
        payload,
        requires_official=requires_official,
        official_skip_authorized=official_skip_authorized,
    )
    return AiReviewValidation(
        not errors,
        risk_level,
        requires_official,
        tuple(errors),
        review_scope,
        official_codex_review_skipped=official_skip_authorized,
        review_mode=review_mode,
    )


def build_codex_review_scope(
    payload: dict[str, Any],
    *,
    requires_official: bool,
    official_skip_authorized: bool = False,
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
    if official_skip_authorized:
        authorization = payload.get("official_codex_review_skip_authorization")
        reason = ""
        if isinstance(authorization, dict):
            reason = _single_line_text(authorization.get("reason"))
        return f"官方 Codex Review 已由用户授权跳过。原因: {reason or '未记录'}"
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
        f"- Review 模式: {result.review_mode}",
        f"- 校验结果: {'通过' if result.ok else '失败'}",
    ]
    lines.extend(_render_security_review(payload.get("security_review")))
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


def render_pr_body(payload: dict[str, Any]) -> str:
    result = validate_report(payload)
    review_mode = result.review_mode
    findings = [
        item for item in payload.get("findings") or [] if isinstance(item, dict)
    ]
    requires = "是" if result.requires_official_codex_review else "否"
    lines = [
        f"## {AI_REVIEW_SECTION_HEADER}",
        "",
        f"- 风险等级: {result.risk_level}",
        f"- 是否需要官方 Codex Review: {requires}",
        f"- 本地 AI review 模式: {review_mode}",
        f"- 不完全 Review 模式授权: {_format_authorization(payload.get('review_mode_authorization')) if review_mode == 'partial' else '无'}",
        f"- 官方 Codex Review 跳过授权: {_format_authorization(payload.get('official_codex_review_skip_authorization')) if result.official_codex_review_skipped else '无'}",
        "- 本地 AI review: `.local/ai-review/latest.md`",
        f"- 本地安全 review: {_format_security_review_field(payload)}",
        f"- 子 agent 交叉评审: {_format_cross_review_field(payload)}",
        f"- 任务分发说明: {_format_task_dispatch_field(payload)}",
        f"- P0/P1 未关闭项: {_blocking_findings_summary(findings)}",
        "",
        "## 已运行检查",
        "",
    ]
    lines.extend(_render_pr_body_check_lines(payload))
    lines.extend(
        [
            "",
        f"## {P2_SECTION_HEADER}",
        "",
        ]
    )
    p2_lines = _render_p2_body_lines(findings)
    lines.extend(p2_lines)
    official_lines = _render_official_codex_review_lines(payload)
    if result.requires_official_codex_review and official_lines:
        lines.extend(["", f"## {SECTION_HEADER}", ""])
        lines.extend(official_lines)
    return "\n".join(lines) + "\n"


def draft_review_payload(changed_files: Sequence[str] | None) -> dict[str, Any]:
    files = sorted({_normalize_repo_path(path) for path in changed_files or [] if path})
    if changed_files is None:
        risk_level = "unknown"
    elif any(_is_high_risk_path(path) for path in files):
        risk_level = "high"
    else:
        risk_level = "low"
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "tool": "codex",
        "review_mode": "complete",
        "risk_level": risk_level,
        "requires_official_codex_review": risk_level != "low",
        "changed_files": files,
        "findings": [],
        "checks": {},
    }


def _discover_changed_files(repo_root: str | Path = ".") -> list[str] | None:
    root = Path(repo_root)
    discovered: list[str] = []
    for command in (
        ["git", "diff", "--name-only", "--cached"],
        ["git", "diff", "--name-only"],
    ):
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
            return None
        discovered.extend(result.stdout.splitlines())
    base = _discover_branch_diff_base(root)
    if base:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return None
        discovered.extend(result.stdout.splitlines())
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if untracked.returncode != 0:
        return None
    discovered.extend(untracked.stdout.splitlines())
    if not discovered and base is None:
        return None
    return sorted(
        {
            normalized
            for path in discovered
            if (normalized := _normalize_repo_path(path))
        }
    )


def _discover_branch_diff_base(root: Path) -> str | None:
    for command in (
        ["git", "merge-base", "--fork-point", "origin/main", "HEAD"],
        ["git", "merge-base", "origin/main", "HEAD"],
        ["git", "merge-base", "origin/master", "HEAD"],
        ["git", "merge-base", "main", "HEAD"],
        ["git", "merge-base", "master", "HEAD"],
    ):
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        base = result.stdout.strip()
        if result.returncode == 0 and base:
            return base
    return None


def _is_high_risk_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    if _is_generated_strategy_artifact(normalized):
        return False
    return any(normalized.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)


def _normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


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


def _security_review_errors(value: Any, tool: str) -> list[str]:
    required_tool = REQUIRED_SECURITY_REVIEW_TOOLS.get(tool)
    if required_tool is None:
        return []
    if not isinstance(value, dict):
        return [f"security_review.tool must be {required_tool} for {tool} local review"]
    errors: list[str] = []
    if str(value.get("tool") or "").strip().casefold() != required_tool:
        errors.append(
            f"security_review.tool must be {required_tool} for {tool} local review"
        )
    if not str(value.get("evidence") or "").strip():
        errors.append("security_review.evidence must be filled")
    return errors


def _review_mode(payload: dict[str, Any]) -> str:
    value = str(payload.get("review_mode") or "").strip()
    if value:
        return value
    return "complete"


def _complete_review_errors(value: Any, reviewers: list[str]) -> list[str]:
    if not isinstance(value, dict):
        return ["complete_review must be filled for complete review mode"]
    errors: list[str] = []
    if not str(value.get("evidence") or "").strip():
        errors.append("complete_review.evidence must be filled")
    iterations = value.get("iterations")
    if not isinstance(iterations, list) or not iterations:
        return errors + ["complete_review.iterations must not be empty"]

    valid_iterations = [item for item in iterations if isinstance(item, dict)]
    if len(valid_iterations) != len(iterations):
        errors.append("complete_review.iterations must contain only objects")
    for reviewer in reviewers:
        normalized = _normalize_reviewer_identity(reviewer)
        reviewer_iterations = [
            item
            for item in valid_iterations
            if _normalize_reviewer_identity(str(item.get("reviewer") or ""))
            == normalized
        ]
        reviewer_iterations.sort(key=_iteration_round)
        final_iteration = reviewer_iterations[-1] if reviewer_iterations else None
        if (
            final_iteration is None
            or final_iteration.get("no_new_findings") is not True
        ):
            errors.append(
                f"complete_review reviewer {reviewer} must end with a no-new-findings iteration"
            )
            continue
        if final_iteration.get("new_findings") != []:
            errors.append(
                f"complete_review reviewer {reviewer} final new_findings must be []"
            )
    return errors


def _iteration_round(value: dict[str, Any]) -> int:
    try:
        return int(value.get("round") or 0)
    except (TypeError, ValueError):
        return 0


def _authorization_errors(value: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} requires user authorization"]
    errors: list[str] = []
    for field in ("authorized_by", "reason", "evidence"):
        field_value = _single_line_text(value.get(field))
        if not field_value:
            errors.append(f"{label} authorization missing {field}")
        elif _is_placeholder_authorization_value(field_value):
            errors.append(f"{label} authorization invalid {field}")
    return errors


def _is_placeholder_authorization_value(value: str) -> bool:
    normalized = value.strip().strip("`\"'")
    return bool(re.search(r"<[^>]+>", normalized))


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


def _render_security_review(value: Any) -> list[str]:
    lines = ["", "## 本地安全 Review", ""]
    if not isinstance(value, dict):
        lines.append("- 未记录")
        return lines
    tool = _single_line_text(value.get("tool"))
    evidence = _single_line_text(value.get("evidence"))
    lines.append(f"- 工具: {tool or '未记录'}")
    lines.append(f"- 证据: {evidence or '未记录'}")
    return lines


def _single_line_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _format_authorization(value: Any) -> str:
    if not isinstance(value, dict):
        return "无"
    return (
        f"authorized_by={_single_line_text(value.get('authorized_by'))}; "
        f"reason={_single_line_text(value.get('reason'))}; "
        f"evidence={_single_line_text(value.get('evidence'))}"
    )


def _format_security_review_field(payload: dict[str, Any]) -> str:
    value = payload.get("security_review")
    provider = _single_line_text(payload.get("tool"))
    if not isinstance(value, dict):
        return f"provider={provider}; tool=; evidence="
    return (
        f"provider={provider}; "
        f"tool={_single_line_text(value.get('tool'))}; "
        f"evidence={_single_line_text(value.get('evidence'))}"
    )


def _format_cross_review_field(payload: dict[str, Any]) -> str:
    value = payload.get("cross_review")
    reviewers = _string_list(payload.get("reviewers"))
    if not isinstance(value, dict):
        return f"已分发； reviewers: {', '.join(reviewers)}"
    skills = _string_list(value.get("review_skills"))
    skill_text = ", ".join(f"`{skill}`" for skill in skills)
    evidence = _single_line_text(value.get("evidence"))
    return (
        f"已分发； reviewers: {', '.join(reviewers)}； "
        f"skills: {skill_text}； evidence={evidence}"
    )


def _format_task_dispatch_field(payload: dict[str, Any]) -> str:
    reviewers = _string_list(payload.get("reviewers"))
    value = payload.get("cross_review")
    evidence = ""
    if isinstance(value, dict):
        evidence = _single_line_text(value.get("evidence"))
    return f"已分发给 {', '.join(reviewers)}； evidence={evidence or '见子 agent 交叉评审'}"


def _blocking_findings_summary(findings: Sequence[dict[str, Any]]) -> str:
    open_blockers = []
    for item in findings:
        severity = str(item.get("severity") or "")
        status = str(item.get("status") or "")
        if severity in BLOCKING_SEVERITIES and status not in {
            "fixed",
            "false_positive",
        }:
            open_blockers.append(str(item.get("id") or "<missing-id>"))
    return "无" if not open_blockers else ", ".join(open_blockers)


def _render_p2_body_lines(findings: Sequence[dict[str, Any]]) -> list[str]:
    accepted = [
        item
        for item in findings
        if str(item.get("severity") or "") == "P2"
        and str(item.get("status") or "") == "accepted"
    ]
    if not accepted:
        return ["- 无"]
    lines: list[str] = []
    for item in accepted:
        lines.append(f"- {item.get('id')}: {item.get('title')} (`{item.get('path')}`)")
        lines.append(
            f"  - defer_reason: {_single_line_text(item.get('defer_reason')) or '未记录'}"
        )
        lines.append(
            f"  - risk_acceptance: {_single_line_text(item.get('risk_acceptance')) or '未记录'}"
        )
        lines.append(
            f"  - handling: {_single_line_text(item.get('handling')) or '未记录'}"
        )
    return lines


def _render_pr_body_check_lines(payload: dict[str, Any]) -> list[str]:
    checks = payload.get("checks")
    if not isinstance(checks, dict) or not checks:
        return ["- 未记录"]
    lines: list[str] = []
    for name, status in checks.items():
        lines.append(f"- {_single_line_text(name)}: {_single_line_text(status)}")
    return lines


def _render_official_codex_review_lines(payload: dict[str, Any]) -> list[str]:
    value = payload.get("official_codex_review")
    if not isinstance(value, dict):
        return []
    evidence = _string_or_list(value.get("evidence"))
    if not evidence:
        return []
    lines = [
        f"- Reviewer: {_single_line_text(value.get('reviewer')) or 'Codex'}",
        f"- 触发方式: {_single_line_text(value.get('trigger'))}",
        f"- 结论: {_single_line_text(value.get('conclusion'))}",
        f"- 阻断问题: {_single_line_text(value.get('blocking_issues'))}",
        "- 关键证据:",
    ]
    lines.extend(f"  - {item}" for item in evidence)
    return lines


def _string_or_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := _single_line_text(item))]
    text = _single_line_text(value)
    return [text] if text else []


def _read_report_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    draft = subparsers.add_parser("draft")
    draft.add_argument("--repo-root", type=Path, default=Path("."))
    draft.add_argument("--output", type=Path, required=True)
    for name in ("validate", "risk", "scope", "markdown", "pr-body"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--report", type=Path, required=True)
        if name in {"scope", "markdown", "pr-body"}:
            subparser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "draft":
        draft_payload = draft_review_payload(_discover_changed_files(args.repo_root))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(draft_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 0

    result = validate_report_file(args.report)
    if args.command == "pr-body":
        report_payload = _read_report_payload(args.report)
        if report_payload is None:
            print(
                f"error: AI review report invalid JSON: {args.report}", file=sys.stderr
            )
            return 1
        if not result.ok:
            for error in result.errors:
                print(f"error: {error}", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_pr_body(report_payload), encoding="utf-8")
        return 0

    if args.command == "scope":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.review_scope, encoding="utf-8")
    if args.command == "markdown":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = _read_report_payload(args.report) or {}
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
