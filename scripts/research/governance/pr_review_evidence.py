"""Validate required PR review evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


REQUIRED_REVIEWER = "Codex"
SECTION_HEADER = "Codex Code Review 结论"
AI_REVIEW_SECTION_HEADER = "AI Review 风险分级"
P2_SECTION_HEADER = "P2 保留项"
AI_REVIEW_MODE_FIELD = "本地 AI review 模式"
PARTIAL_REVIEW_AUTH_FIELD = "不完全 Review 模式授权"
OFFICIAL_SKIP_FIELD = "官方 Codex Review 跳过授权"
SECURITY_REVIEW_FIELD = "本地安全 review"
REQUIRED_CROSS_REVIEW_TOKENS = (
    "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
    "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
)
REQUIRED_SECURITY_REVIEW_TOOLS = {
    "codex": "codex-security",
    "claude": "security-guidance",
}
SECURITY_REVIEW_PROVIDER_PATTERN = re.compile(
    r"(?:provider|工具|提供方)\s*[=:：]\s*(?P<provider>codex|claude)",
    re.IGNORECASE,
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
REVIEWER_NAMES_PATTERN = re.compile(
    r"reviewers?\s*[:：]\s*(?P<names>[^；;\n]+)", re.IGNORECASE
)
CODEX_REVIEW_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<number>\d+)#pullrequestreview-(?P<review_id>\d+)"
)
CODEX_COMPLETION_COMMENT_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/(?:pull|issues)/(?P<number>\d+)#issuecomment-(?P<comment_id>\d+)"
)
CODEX_REVIEW_AUTHORS = {"chatgpt-codex-connector", "chatgpt-codex-connector[bot]"}
DISQUALIFIED_CODEX_REVIEW_STATES = {"DISMISSED", "PENDING"}
MONITOR_STATE_PATTERN = re.compile(
    r"<!--\s*codex-review-monitor-state\s+(?P<payload>\{.*?\})\s*-->", re.DOTALL
)
BLOCKING_CODEX_FINDING_PATTERN = re.compile(
    r"(?:P[01] Badge|badge/P[01]-|(?:^|\n)\s*(?:\*\*)?\[P[01]\]\s+)",
    re.IGNORECASE,
)
CODEX_CONTEXT_INVALID_PATTERN = re.compile(
    r"(?:(?:cannot|can't|can\s*not|unable\s+to|could\s+not)\s+"
    r".*?(?:review|complete|read|access).*?(?:diff|code\s+diff|unified\s+diff)|"
    r"conversation\s+did\s+not\s+include.*diff|"
    r"cannot\s+complete.*static\s+review.*diff|"
    r"could\s+not\s+read.*diff|"
    r"(?:provide|paste)\s+(?:the\s+)?(?:unified\s+)?diff\s+"
    r"(?:to|before|for)\s+(?:complete|perform|review)|"
    r"无法.*?(?:审查|完成|读取|获取).*?(?:diff|差异|统一\s*diff)|"
    r"(?:缺少|未包含).*?(?:diff|差异|统一\s*diff))",
    re.IGNORECASE | re.DOTALL,
)
CODEX_NO_MAJOR_ISSUES_PATTERN = re.compile(
    r"Codex Review:\s*(?:Didn['’]t|Did not) find any major issues",
    re.IGNORECASE,
)
CONTEXT_HOSTILE_TRIGGER_PATTERN = re.compile(
    r"(?:do\s+not\s+(?:execute|run)\s+(?:any\s+)?(?:local\s+)?"
    r"(?:commands?|checks?|tests?|wrapper)|"
    r"only\s+do\s+a\s+static\s+diff\s+review|"
    r"(?:不要|不)(?:执行|运行).*?(?:本地命令|wrapper|检查|测试)|"
    r"只做静态\s*diff\s*review)",
    re.IGNORECASE,
)
CONTEXT_INVALID_REVIEW_ERROR = "Codex review context is invalid for the current head"
CONTEXT_HOSTILE_TRIGGER_ERROR = (
    "required @codex review trigger must not disable repository context"
)
REQUIRED_TRIGGER_TOKENS = ("@codex review",)
REQUIRED_GOVERNANCE_GATE_COMMANDS = (
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate",
    "sh .githooks/run-python.sh -m scripts.research.governance gate",
    ".githooks/run-python.sh -m scripts.research.governance gate",
)


@dataclass(frozen=True)
class EvidenceReport:
    ok: bool
    errors: tuple[str, ...]


def validate_pr_body(
    body: str,
    *,
    expected_pr_url: str | None = None,
    expected_head_sha: str | None = None,
    expected_head_created_at: str | None = None,
    comments: Sequence[object] | None = None,
    reviews: Sequence[Mapping[str, object]] | None = None,
    review_comments: Sequence[Mapping[str, object]] | None = None,
    review_threads: Sequence[Mapping[str, object]] | None = None,
    changed_files: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> EvidenceReport:
    """Return whether a PR body contains merge-blocking review evidence."""

    official_codex_required, errors = _official_codex_required(
        body, changed_files=changed_files, labels=labels
    )
    if (
        review_threads is not None
        and unresolved_blocking_codex_thread_count(review_threads) > 0
    ):
        errors.append(
            "Codex review must not have unresolved non-outdated P0/P1 threads"
        )
    if not official_codex_required:
        return EvidenceReport(not errors, tuple(errors))

    section = _extract_section(body)
    if section is None:
        errors.append(f"PR body missing section: {SECTION_HEADER}")
        return EvidenceReport(False, tuple(errors))

    reviewer = _read_field(section, "Reviewer")
    trigger = _read_field(section, "触发方式")
    conclusion = _read_field(section, "结论")
    blockers = _read_field(section, "阻断问题")

    if _normalize_value(reviewer) != REQUIRED_REVIEWER:
        errors.append(f"Reviewer must be {REQUIRED_REVIEWER}")
    normalized_trigger = _normalize_value(trigger)
    if not normalized_trigger:
        errors.append("触发方式 must be filled")
    else:
        if "@codex review" not in normalized_trigger:
            errors.append("触发方式 must include @codex review")
    if _normalize_value(conclusion) != "通过":
        errors.append("结论 must be 通过")
    if _normalize_value(blockers) != "无":
        errors.append("阻断问题 must be 无")
    reviewed_until: str | None = None
    if "关键证据" not in section:
        errors.append("review evidence must include 关键证据")
    elif not _has_nonempty_evidence(section):
        errors.append("review evidence must include at least one evidence item")
    else:
        review_link = _find_codex_evidence_link(
            section, expected_pr_url=expected_pr_url
        )
        if review_link is None:
            errors.append(
                "review evidence must include a real Codex review link for this PR"
            )
        elif reviews is not None:
            reviewed_until = _codex_evidence_reviewed_until(
                review_link, reviews=reviews, comments=comments
            )
            errors.extend(
                _codex_review_errors(
                    review_link,
                    reviews=reviews,
                    review_comments=review_comments,
                    expected_head_sha=expected_head_sha,
                    expected_head_created_at=expected_head_created_at,
                    comments=comments,
                )
            )
    if comments is not None:
        if _has_context_hostile_trigger_comment(
            comments,
            expected_head_created_at=expected_head_created_at,
            before_or_at=reviewed_until,
        ):
            errors.append(CONTEXT_HOSTILE_TRIGGER_ERROR)
        if not _required_trigger_comments(comments, before_or_at=reviewed_until):
            errors.append("PR comments must include the required @codex review trigger")
    if not _has_governance_gate_wrapper_command(section):
        errors.append("review evidence must include governance gate wrapper command")

    return EvidenceReport(not errors, tuple(errors))


def _extract_section(body: str) -> str | None:
    return _extract_named_section(body, SECTION_HEADER)


def _has_governance_gate_wrapper_command(section: str) -> bool:
    normalized_section = " ".join(section.replace("`", "").split()).casefold()
    return any(
        command.casefold() in normalized_section
        for command in REQUIRED_GOVERNANCE_GATE_COMMANDS
    )


def _extract_named_section(body: str, header: str) -> str | None:
    lines = body.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if re.match(rf"^\s*##+\s+{re.escape(header)}\s*$", line):
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


def _official_codex_required(
    body: str,
    *,
    changed_files: Sequence[str] | None,
    labels: Sequence[str] | None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    section = _extract_named_section(body, AI_REVIEW_SECTION_HEADER)
    if section is None:
        return True, [f"PR body missing section: {AI_REVIEW_SECTION_HEADER}"]
    risk = _normalize_value(_read_field(section, "风险等级"))
    requires = _normalize_value(_read_field(section, "是否需要官方 Codex Review"))
    review_mode = _read_field(section, AI_REVIEW_MODE_FIELD)
    partial_review_authorization = _read_field(section, PARTIAL_REVIEW_AUTH_FIELD)
    skip_authorization = _read_field(section, OFFICIAL_SKIP_FIELD)
    local_review = _normalize_value(_read_field(section, "本地 AI review"))
    security_review = _read_field(section, SECURITY_REVIEW_FIELD)
    cross_review = _normalize_value(_read_field(section, "子 agent 交叉评审"))
    task_dispatch = _normalize_value(_read_field(section, "任务分发说明"))
    blockers = _normalize_value(_read_field(section, "P0/P1 未关闭项"))
    if risk not in {"low", "high", "unknown"}:
        errors.append("风险等级 must be low, high, or unknown")
        return True, errors
    if _is_unfilled_ai_review_field(local_review):
        errors.append("本地 AI review must be filled")
    elif ".local/ai-review/latest.md" not in local_review:
        errors.append("本地 AI review must reference .local/ai-review/latest.md")
    errors.extend(_security_review_field_errors(security_review))
    errors.extend(_cross_review_field_errors(cross_review))
    errors.extend(_task_dispatch_errors(task_dispatch))
    errors.extend(
        _ai_review_mode_errors(
            review_mode,
            partial_review_authorization=partial_review_authorization,
        )
    )
    errors.extend(_p2_section_errors(body))
    if blockers != "无":
        errors.append("P0/P1 未关闭项 must be 无")
    high_risk_files = _high_risk_changed_files(changed_files)
    if high_risk_files:
        if risk == "low":
            errors.append("high-risk changed files require official Codex Review")
        if requires in {"否", "不需要", "false", "False"}:
            skip_errors = _official_codex_skip_authorization_errors(skip_authorization)
            if skip_errors:
                errors.extend(skip_errors)
            elif risk != "low":
                return False, errors
        return True, errors
    if _has_ai_risk_review_label(labels):
        if risk == "low":
            errors.append("ai-risk-review label requires official Codex Review")
        if requires in {"否", "不需要", "false", "False"}:
            skip_errors = _official_codex_skip_authorization_errors(skip_authorization)
            if skip_errors:
                errors.extend(skip_errors)
            elif risk != "low":
                return False, errors
        return True, errors
    if risk in {"high", "unknown"}:
        if requires in {"否", "不需要", "false", "False"}:
            skip_errors = _official_codex_skip_authorization_errors(skip_authorization)
            if skip_errors:
                errors.extend(skip_errors)
                return True, errors
            return False, errors
        return True, errors
    if requires in {"是", "需要", "true", "True"}:
        return True, errors
    if requires in {"否", "不需要", "false", "False"}:
        if _official_skip_authorization_present(skip_authorization):
            errors.extend(_official_codex_skip_authorization_errors(skip_authorization))
        return False, errors
    errors.append("低风险 PR must mark 是否需要官方 Codex Review as 是 or 否")
    return True, errors


def official_codex_review_skip_authorized(body: str) -> bool:
    section = _extract_named_section(body, AI_REVIEW_SECTION_HEADER)
    if section is None:
        return False
    value = _read_field(section, OFFICIAL_SKIP_FIELD)
    return _official_skip_authorization_present(
        value
    ) and not _official_codex_skip_authorization_errors(value)


def _official_skip_authorization_present(value: str) -> bool:
    normalized = _normalize_value(value)
    if not normalized:
        return False
    return normalized.casefold() not in {
        "无",
        "否",
        "不跳过",
        "未授权",
        "none",
        "n/a",
        "na",
    }


def _official_codex_skip_authorization_errors(value: str) -> list[str]:
    if not _official_skip_authorization_present(value):
        return [f"{OFFICIAL_SKIP_FIELD} must be filled"]
    return _authorization_field_errors(value, OFFICIAL_SKIP_FIELD)


def _ai_review_mode_errors(
    value: str, *, partial_review_authorization: str
) -> list[str]:
    mode = _normalize_value(value) or "complete"
    if mode not in {"complete", "partial"}:
        return [f"{AI_REVIEW_MODE_FIELD} must be complete or partial"]
    if mode == "partial":
        return _authorization_field_errors(
            partial_review_authorization,
            PARTIAL_REVIEW_AUTH_FIELD,
        )
    return []


def _authorization_field_errors(value: str, field: str) -> list[str]:
    normalized = _normalize_value(value)
    if not normalized or normalized.casefold() in {"无", "否", "none", "n/a", "na"}:
        return [f"{field} must be filled"]
    placeholder_error = _placeholder_field_error(value, field)
    if placeholder_error:
        return [placeholder_error]
    errors: list[str] = []
    required_groups = (
        ("authorized_by", ("authorized_by", "授权人", "批准人")),
        ("reason", ("reason", "原因", "理由")),
        ("evidence", ("evidence", "证据")),
    )
    for label, aliases in required_groups:
        assignment_values = [
            text
            for alias in aliases
            if (text := _assignment_value(value, alias)) is not None
        ]
        if assignment_values:
            if not any(_has_real_field_value(text) for text in assignment_values):
                errors.append(f"{field} {label} must be filled")
        elif any(alias in value for alias in aliases):
            errors.append(f"{field} {label} must be filled")
        elif not any(alias in value for alias in aliases):
            errors.append(f"{field} must include " + "/".join(aliases))
    return errors


def _is_unfilled_ai_review_field(value: str) -> bool:
    if not value:
        return True
    placeholders = ("填写", "已分发 / 未分发")
    return any(token in value for token in placeholders)


def _placeholder_field_error(value: str, field: str) -> str | None:
    if re.search(r"<[^>]+>", value) or " / " in value:
        return f"{field} must not contain placeholder text"
    return None


def _assignment_value(value: str, key: str) -> str | None:
    pattern = re.compile(rf"{re.escape(key)}\s*[=:：]\s*([^；;\n]*)")
    match = pattern.search(value)
    return match.group(1).strip() if match else None


def _has_real_field_value(value: str) -> bool:
    normalized = _normalize_value(value)
    return bool(normalized) and normalized.casefold() not in {
        "无",
        "否",
        "none",
        "n/a",
        "na",
    }


def _cross_review_field_errors(value: str) -> list[str]:
    if _is_unfilled_ai_review_field(value):
        return ["子 agent 交叉评审 must be filled"]
    errors: list[str] = []
    missing = [token for token in REQUIRED_CROSS_REVIEW_TOKENS if token not in value]
    if missing:
        errors.append(
            "子 agent 交叉评审 must include "
            + " and ".join(REQUIRED_CROSS_REVIEW_TOKENS)
        )
    reviewer_names = _cross_review_reviewer_names(value)
    if any(_is_placeholder_reviewer_name(name) for name in reviewer_names):
        errors.append("子 agent 交叉评审 must not include invalid reviewer names")
    if _cross_review_reviewer_count(reviewer_names) < 2:
        errors.append("子 agent 交叉评审 must include two reviewer names")
    return errors


def _security_review_field_errors(value: str) -> list[str]:
    if _is_unfilled_ai_review_field(_normalize_value(value)):
        return [f"{SECURITY_REVIEW_FIELD} must be filled"]
    placeholder_error = _placeholder_field_error(value, SECURITY_REVIEW_FIELD)
    if placeholder_error:
        return [placeholder_error]
    errors: list[str] = []
    normalized = value.casefold()
    match = SECURITY_REVIEW_PROVIDER_PATTERN.search(value)
    provider = match.group("provider").casefold() if match else ""
    if provider not in REQUIRED_SECURITY_REVIEW_TOOLS:
        errors.append(
            f"{SECURITY_REVIEW_FIELD} must include provider=codex or provider=claude"
        )
        return errors
    required_tool = REQUIRED_SECURITY_REVIEW_TOOLS[provider]
    tool_value = _assignment_value(value, "tool")
    if tool_value is None or tool_value.casefold() != required_tool:
        errors.append(
            f"{SECURITY_REVIEW_FIELD} must include tool={required_tool} for provider={provider}"
        )
    evidence_values = (
        _assignment_value(value, "evidence"),
        _assignment_value(value, "证据"),
    )
    has_evidence_assignment = any(item is not None for item in evidence_values)
    if any(
        item is not None and not _has_real_field_value(item) for item in evidence_values
    ):
        errors.append(f"{SECURITY_REVIEW_FIELD} evidence must be filled")
    if not has_evidence_assignment:
        if "evidence" in normalized or "证据" in value:
            errors.append(f"{SECURITY_REVIEW_FIELD} evidence must be filled")
        else:
            errors.append(f"{SECURITY_REVIEW_FIELD} must include evidence")
    return errors


def _task_dispatch_errors(value: str) -> list[str]:
    if _is_unfilled_ai_review_field(value):
        return ["任务分发说明 must be filled"]
    if "已分发" in value:
        if not _has_meaningful_dispatched_detail(value):
            return ["任务分发说明 must include dispatched task detail"]
        return []
    if "未分发" in value:
        if not _task_dispatch_has_reason(value):
            return ["任务分发说明 must include reason when 未分发"]
        return []
    return ["任务分发说明 must state 已分发 or 未分发"]


def _has_meaningful_dispatched_detail(value: str) -> bool:
    normalized = value.replace("无未分发项", "")
    normalized = normalized.replace("已分发", "")
    normalized = normalized.replace("给", "")
    normalized = normalized.strip().strip("`\"'。.!！；;:：,，- ")
    return len(normalized) >= 3


def _task_dispatch_has_reason(value: str) -> bool:
    if "未分发" not in value:
        return True
    match = re.search(r"(?:原因|理由)\s*[:：]\s*(?P<reason>.*)$", value)
    if not match:
        match = re.search(r"未分发\s*[,，;；:：-]+\s*(?P<reason>.*)$", value)
    if not match:
        return False
    return _has_meaningful_dispatch_reason(match.group("reason"))


def _has_meaningful_dispatch_reason(value: str) -> bool:
    normalized = value.strip().strip("`\"'。.!！；;:：,，- ")
    if not normalized:
        return False
    return normalized.casefold() not in {"无", "none", "n/a", "na", "null"}


def _p2_section_errors(body: str) -> list[str]:
    section = _extract_named_section(body, P2_SECTION_HEADER)
    if section is None:
        return [f"PR body missing section: {P2_SECTION_HEADER}"]
    normalized = section.strip()
    if not normalized:
        return ["P2 保留项 must be filled"]
    if _p2_section_declares_none_only(section):
        return []
    errors: list[str] = []
    if not _section_contains_any(section, ("defer_reason", "不修原因")):
        errors.append("P2 保留项 must include defer_reason or 不修原因")
    if not _section_contains_any(section, ("risk_acceptance", "风险接受理由")):
        errors.append("P2 保留项 must include risk_acceptance or 风险接受理由")
    if not _section_contains_any(section, ("handling", "处理方式")):
        errors.append("P2 保留项 must include handling or 处理方式")
    return errors


def _section_contains_any(section: str, tokens: Sequence[str]) -> bool:
    return any(token in section for token in tokens)


def _p2_section_declares_none_only(section: str) -> bool:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    return lines == ["- 无"] or lines == ["* 无"]


def _high_risk_changed_files(changed_files: Sequence[str] | None) -> tuple[str, ...]:
    if changed_files is None:
        return ()
    return tuple(path for path in changed_files if _is_high_risk_path(path))


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


def _has_ai_risk_review_label(labels: Sequence[str] | None) -> bool:
    if labels is None:
        return False
    return any(str(label).casefold() == "ai-risk-review" for label in labels)


def _cross_review_reviewer_names(value: str) -> tuple[str, ...]:
    match = REVIEWER_NAMES_PATTERN.search(value)
    if not match:
        return ()
    return tuple(
        name.strip()
        for name in re.split(r"[,，、+/]+", match.group("names"))
        if name.strip()
    )


def _cross_review_reviewer_count(names: Sequence[str]) -> int:
    names = [name for name in names if not _is_placeholder_reviewer_name(name)]
    return len({_normalize_reviewer_identity(name) for name in names})


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


def _read_field(section: str, field: str) -> str:
    pattern = re.compile(
        rf"^\s*[-*]\s*{re.escape(field)}\s*[:：]\s*(.+?)\s*$", re.MULTILINE
    )
    match = pattern.search(section)
    return match.group(1) if match else ""


def _normalize_value(value: str) -> str:
    return value.strip().strip("`").strip()


def _has_nonempty_evidence(section: str) -> bool:
    evidence_start = section.find("关键证据")
    if evidence_start < 0:
        return False
    evidence = section[evidence_start:].splitlines()[1:]
    for line in evidence:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^[-*]\s*\S+", stripped):
            return True
    return False


def _find_codex_evidence_link(
    section: str, *, expected_pr_url: str | None = None
) -> str | None:
    expected = _normalize_pr_url(expected_pr_url)
    expected_issue_url = expected.replace("/pull/", "/issues/") if expected else None
    evidence_start = section.find("关键证据")
    if evidence_start < 0:
        return None
    evidence = section[evidence_start:].splitlines()[1:]
    for line in evidence:
        if "Codex review 链接" not in line:
            continue
        match = CODEX_REVIEW_URL_PATTERN.search(
            line
        ) or CODEX_COMPLETION_COMMENT_URL_PATTERN.search(line)
        if not match:
            continue
        url = match.group(0)
        if expected and not (
            url.startswith(f"{expected}#pullrequestreview-")
            or url.startswith(f"{expected}#issuecomment-")
            or url.startswith(f"{expected_issue_url}#issuecomment-")
        ):
            continue
        return url
    return None


def _codex_review_errors(
    review_link: str,
    *,
    reviews: Sequence[Mapping[str, object]],
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
    expected_head_created_at: str | None,
    comments: Sequence[object] | None,
) -> tuple[str, ...]:
    match = CODEX_REVIEW_URL_PATTERN.fullmatch(review_link)
    if match is None:
        comment_match = CODEX_COMPLETION_COMMENT_URL_PATTERN.fullmatch(review_link)
        if comment_match is not None and comments is not None:
            return _codex_completion_comment_errors(
                comment_match.group("comment_id"),
                comments=comments,
                reviews=reviews,
                review_comments=review_comments,
                expected_head_sha=expected_head_sha,
                expected_head_created_at=expected_head_created_at,
            )
        return ("Codex review link must match a Codex review on the current head",)
    review_id = match.group("review_id")
    matched_review: Mapping[str, object] | None = None
    for review in reviews:
        if str(review.get("id", "")) != review_id:
            continue
        matched_review = review
        if not is_effective_codex_review(review):
            return ("Codex review link must match a Codex review on the current head",)
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            return ("Codex review link must match a Codex review on the current head",)
        break
    if matched_review is None:
        return ("Codex review link must match a Codex review on the current head",)
    errors: list[str] = []
    if _review_has_context_invalid_findings(
        matched_review,
        review_id=review_id,
        review_comments=review_comments,
    ):
        errors.append(CONTEXT_INVALID_REVIEW_ERROR)
    trigger_comments = (
        _required_trigger_comments(comments) if comments is not None else None
    )
    if trigger_comments is not None:
        if not _has_required_trigger_after_current_head(
            trigger_comments, expected_head_created_at
        ):
            errors.append(
                "required @codex review trigger must be submitted after the current head"
            )
        if not _review_is_after_required_trigger(
            matched_review,
            trigger_comments,
            expected_head_created_at=expected_head_created_at,
        ):
            errors.append(
                "Codex review must be submitted after the required @codex review trigger"
            )
    if codex_context_invalid_review_count(
        reviews,
        review_comments=review_comments,
        expected_head_sha=expected_head_sha,
    ):
        if CONTEXT_INVALID_REVIEW_ERROR not in errors:
            errors.append(CONTEXT_INVALID_REVIEW_ERROR)
    elif _current_head_has_blocking_codex_review(
        reviews,
        review_comments=review_comments,
        expected_head_sha=expected_head_sha,
    ):
        errors.append(
            "Codex review must not contain P0/P1 findings on the current head"
        )
    return tuple(errors)


def _codex_evidence_reviewed_until(
    review_link: str,
    *,
    reviews: Sequence[Mapping[str, object]],
    comments: Sequence[object] | None,
) -> str | None:
    review_match = CODEX_REVIEW_URL_PATTERN.fullmatch(review_link)
    if review_match is not None:
        review_id = review_match.group("review_id")
        for review in reviews:
            if str(review.get("id", "")) == review_id:
                return _review_submitted_time(review)
        return None

    comment_match = CODEX_COMPLETION_COMMENT_URL_PATTERN.fullmatch(review_link)
    if comment_match is None or comments is None:
        return None
    comment = _find_comment_by_id(comments, comment_match.group("comment_id"))
    if comment is None:
        return None
    return _comment_effective_time(comment)


def _codex_completion_comment_errors(
    comment_id: str,
    *,
    comments: Sequence[object],
    reviews: Sequence[Mapping[str, object]],
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
    expected_head_created_at: str | None,
) -> tuple[str, ...]:
    comment = _find_comment_by_id(comments, comment_id)
    if comment is None:
        return ("Codex review link must match a Codex review on the current head",)

    errors: list[str] = []
    trigger_comments = _required_trigger_comments(comments)
    if not _has_required_trigger_after_current_head(
        trigger_comments, expected_head_created_at
    ):
        errors.append(
            "required @codex review trigger must be submitted after the current head"
        )
    latest_trigger_time = _latest_required_trigger_time(
        trigger_comments,
        expected_head_created_at=expected_head_created_at,
    )
    comment_time = _comment_effective_time(comment)
    if latest_trigger_time and comment_time and comment_time < latest_trigger_time:
        errors.append(
            "Codex completion comment must match the latest required @codex review trigger"
        )
    if _is_required_trigger_comment(comment):
        if not has_codex_completion_reaction(comment):
            errors.append(
                "Codex completion comment must include a Codex thumbs-up reaction"
            )
    elif not is_codex_completion_comment(comment):
        return ("Codex review link must match a Codex review on the current head",)
    if codex_context_invalid_review_count(
        reviews,
        review_comments=review_comments,
        expected_head_sha=expected_head_sha,
    ):
        errors.append(CONTEXT_INVALID_REVIEW_ERROR)
    elif _current_head_has_blocking_codex_review(
        reviews,
        review_comments=review_comments,
        expected_head_sha=expected_head_sha,
    ):
        errors.append(
            "Codex review must not contain P0/P1 findings on the current head"
        )
    return tuple(errors)


def unresolved_blocking_codex_thread_count(
    review_threads: Sequence[Mapping[str, object]],
) -> int:
    """Count unresolved, non-outdated Codex review threads with P0/P1 findings."""

    count = 0
    for thread in review_threads:
        if _thread_is_resolved(thread) or _thread_is_outdated(thread):
            continue
        if _thread_has_blocking_codex_comment(thread):
            count += 1
    return count


def _thread_is_resolved(thread: Mapping[str, object]) -> bool:
    return bool(_first_thread_value(thread, "isResolved", "is_resolved"))


def _thread_is_outdated(thread: Mapping[str, object]) -> bool:
    return bool(_first_thread_value(thread, "isOutdated", "is_outdated"))


def _first_thread_value(thread: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in thread:
            return thread[key]
    return False


def _thread_has_blocking_codex_comment(thread: Mapping[str, object]) -> bool:
    for comment in _thread_comments(thread):
        author = comment.get("author")
        if not isinstance(author, Mapping):
            author = comment.get("user")
        login = author.get("login") if isinstance(author, Mapping) else ""
        if str(login) not in CODEX_REVIEW_AUTHORS:
            continue
        if BLOCKING_CODEX_FINDING_PATTERN.search(str(comment.get("body", ""))):
            return True
    return False


def _thread_comments(thread: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    comments = thread.get("comments")
    if isinstance(comments, list):
        return tuple(item for item in comments if isinstance(item, Mapping))
    if isinstance(comments, Mapping):
        nodes = comments.get("nodes")
        if isinstance(nodes, list):
            return tuple(item for item in nodes if isinstance(item, Mapping))
        edges = comments.get("edges")
        if isinstance(edges, list):
            extracted: list[Mapping[str, object]] = []
            for edge in edges:
                if not isinstance(edge, Mapping):
                    continue
                node = edge.get("node")
                if isinstance(node, Mapping):
                    extracted.append(node)
            return tuple(extracted)
    return ()


def _review_texts(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> tuple[str, ...]:
    texts = [str(review.get("body", ""))]
    if review_comments is not None:
        for comment in review_comments:
            if str(comment.get("pull_request_review_id", "")) == review_id:
                texts.append(str(comment.get("body", "")))
    return tuple(texts)


def _review_has_context_invalid_findings(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> bool:
    return any(
        CODEX_CONTEXT_INVALID_PATTERN.search(text)
        for text in _review_texts(
            review, review_id=review_id, review_comments=review_comments
        )
    )


def codex_context_invalid_review_count(
    reviews: Sequence[Mapping[str, object]],
    *,
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
) -> int:
    latest_review = _latest_effective_codex_review(
        reviews, expected_head_sha=expected_head_sha
    )
    if latest_review is None:
        return 0
    return int(
        _review_has_context_invalid_findings(
            latest_review,
            review_id=str(latest_review.get("id", "")),
            review_comments=review_comments,
        )
    )


def _latest_effective_codex_review(
    reviews: Sequence[Mapping[str, object]], *, expected_head_sha: str | None
) -> Mapping[str, object] | None:
    matched = []
    for review in reviews:
        if not is_effective_codex_review(review):
            continue
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            continue
        matched.append(review)
    if not matched:
        return None
    return sorted(matched, key=_review_sort_key)[-1]


def _review_sort_key(review: Mapping[str, object]) -> str:
    return _review_submitted_time(review) or str(review.get("id", ""))


def _review_submitted_time(review: Mapping[str, object]) -> str:
    return _first_value(review, "submitted_at", "created_at", "updated_at")


def _review_has_blocking_findings(
    review: Mapping[str, object],
    *,
    review_id: str,
    review_comments: Sequence[Mapping[str, object]] | None,
) -> bool:
    if _review_has_context_invalid_findings(
        review, review_id=review_id, review_comments=review_comments
    ):
        return False
    return any(
        BLOCKING_CODEX_FINDING_PATTERN.search(text)
        for text in _review_texts(
            review, review_id=review_id, review_comments=review_comments
        )
    )


def _current_head_has_blocking_codex_review(
    reviews: Sequence[Mapping[str, object]],
    *,
    review_comments: Sequence[Mapping[str, object]] | None,
    expected_head_sha: str | None,
) -> bool:
    for review in reviews:
        if not is_effective_codex_review(review):
            continue
        if expected_head_sha and str(review.get("commit_id", "")) != expected_head_sha:
            continue
        if _review_has_blocking_findings(
            review, review_id=str(review.get("id", "")), review_comments=review_comments
        ):
            return True
    return False


def is_effective_codex_review(review: Mapping[str, object]) -> bool:
    if not is_codex_review(review):
        return False
    return _review_state(review) not in DISQUALIFIED_CODEX_REVIEW_STATES


def is_codex_review(review: Mapping[str, object]) -> bool:
    author = review.get("user")
    login = author.get("login") if isinstance(author, Mapping) else ""
    return str(login) in CODEX_REVIEW_AUTHORS


def _review_state(review: Mapping[str, object]) -> str:
    return str(review.get("state", "") or "").upper()


def _required_trigger_comments(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> tuple[object, ...]:
    matched: list[object] = []
    for comment in _trigger_candidate_comments(
        comments,
        expected_head_created_at=expected_head_created_at,
        before_or_at=before_or_at,
    ):
        if _is_required_trigger_comment(comment):
            matched.append(comment)
    return tuple(matched)


def _trigger_candidate_comments(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> tuple[object, ...]:
    matched: list[object] = []
    for comment in comments:
        if not _is_trigger_candidate_comment(comment):
            continue
        if isinstance(comment, Mapping):
            comment_time = _comment_effective_time(comment)
            if (
                expected_head_created_at
                and comment_time
                and comment_time < expected_head_created_at
            ):
                continue
            if before_or_at and comment_time and before_or_at < comment_time:
                continue
        matched.append(comment)
    return tuple(matched)


def _has_context_hostile_trigger_comment(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> bool:
    latest = _latest_trigger_candidate_comment(
        comments,
        expected_head_created_at=expected_head_created_at,
        before_or_at=before_or_at,
    )
    return latest is not None and _is_context_hostile_trigger_comment(latest)


def _latest_trigger_candidate_comment(
    comments: Sequence[object],
    *,
    expected_head_created_at: str | None = None,
    before_or_at: str | None = None,
) -> object | None:
    latest: object | None = None
    latest_time = ""
    for comment in _trigger_candidate_comments(
        comments,
        expected_head_created_at=expected_head_created_at,
        before_or_at=before_or_at,
    ):
        comment_time = (
            _comment_effective_time(comment) if isinstance(comment, Mapping) else ""
        )
        if (
            latest is None
            or not comment_time
            or not latest_time
            or latest_time <= comment_time
        ):
            latest = comment
            latest_time = comment_time
    return latest


def _is_trigger_candidate_comment(comment: object) -> bool:
    if isinstance(comment, Mapping):
        user = comment.get("user")
        login = user.get("login") if isinstance(user, Mapping) else ""
        if str(login) in CODEX_REVIEW_AUTHORS:
            return False
    body = _comment_body(comment)
    return all(token in body for token in REQUIRED_TRIGGER_TOKENS)


def _is_context_hostile_trigger_comment(comment: object) -> bool:
    return _is_trigger_candidate_comment(comment) and bool(
        CONTEXT_HOSTILE_TRIGGER_PATTERN.search(_comment_body(comment))
    )


def _is_required_trigger_comment(comment: object) -> bool:
    if not _is_trigger_candidate_comment(comment):
        return False
    if CONTEXT_HOSTILE_TRIGGER_PATTERN.search(_comment_body(comment)):
        return False
    return True


def _comment_body(comment: object) -> str:
    if isinstance(comment, str):
        return comment
    if isinstance(comment, Mapping):
        return str(comment.get("body", ""))
    return ""


def _find_comment_by_id(
    comments: Sequence[object], comment_id: str
) -> Mapping[str, object] | None:
    for comment in comments:
        if not isinstance(comment, Mapping):
            continue
        if str(comment.get("id", "")) == comment_id:
            return comment
    return None


def has_codex_completion_reaction(comment: Mapping[str, object]) -> bool:
    comment_time = _comment_effective_time(comment)
    for reaction in _comment_reaction_items(comment):
        if str(reaction.get("content", "")) != "+1":
            continue
        user = reaction.get("user")
        login = user.get("login") if isinstance(user, Mapping) else ""
        if str(login) not in CODEX_REVIEW_AUTHORS:
            continue
        reaction_time = _first_value(reaction, "created_at")
        if reaction_time and comment_time and reaction_time < comment_time:
            continue
        return True
    return False


def is_codex_completion_comment(comment: Mapping[str, object]) -> bool:
    user = comment.get("user")
    login = user.get("login") if isinstance(user, Mapping) else ""
    if str(login) not in CODEX_REVIEW_AUTHORS:
        return False
    body = str(comment.get("body", ""))
    if not CODEX_NO_MAJOR_ISSUES_PATTERN.search(body):
        return False
    return not BLOCKING_CODEX_FINDING_PATTERN.search(body)


def _comment_reaction_items(
    comment: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    for key in ("reactions_detail", "reaction_items"):
        value = comment.get(key)
        if isinstance(value, list):
            return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def render_monitor_head_state(*, head_sha: str, head_updated_at: str | None) -> str:
    payload = {
        "head_sha": head_sha,
        "head_updated_at": head_updated_at or "",
    }
    return f"<!-- codex-review-monitor-state {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))} -->"


def head_updated_at_from_monitor_state(
    comments: Sequence[object] | None,
    *,
    expected_head_sha: str | None,
) -> str | None:
    if comments is None or not expected_head_sha:
        return None
    matched: list[str] = []
    for comment in comments:
        for payload in MONITOR_STATE_PATTERN.findall(_comment_body(comment)):
            try:
                state = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(state, Mapping):
                continue
            if str(state.get("head_sha", "")) != expected_head_sha:
                continue
            head_updated_at = str(state.get("head_updated_at", "") or "")
            if head_updated_at:
                matched.append(head_updated_at)
    return max(matched) if matched else None


def _review_is_after_required_trigger(
    review: Mapping[str, object],
    trigger_comments: Sequence[object],
    *,
    expected_head_created_at: str | None,
) -> bool:
    review_time = _review_submitted_time(review)
    trigger_time = _latest_required_trigger_time(
        trigger_comments,
        expected_head_created_at=expected_head_created_at,
    )
    if not review_time or not trigger_time:
        return True
    return trigger_time <= review_time


def _has_required_trigger_after_current_head(
    trigger_comments: Sequence[object],
    expected_head_created_at: str | None,
) -> bool:
    if not expected_head_created_at:
        return True
    return (
        _latest_required_trigger_time(
            trigger_comments,
            expected_head_created_at=expected_head_created_at,
        )
        is not None
    )


def _latest_required_trigger_time(
    trigger_comments: Sequence[object],
    *,
    expected_head_created_at: str | None,
) -> str | None:
    trigger_times = [
        _comment_effective_time(comment)
        for comment in trigger_comments
        if isinstance(comment, Mapping)
    ]
    trigger_times = [value for value in trigger_times if value]
    if expected_head_created_at:
        trigger_times = [
            value for value in trigger_times if expected_head_created_at <= value
        ]
    return max(trigger_times) if trigger_times else None


def _comment_effective_time(comment: Mapping[str, object]) -> str:
    created_at = _first_value(comment, "created_at")
    updated_at = _first_value(comment, "updated_at")
    if created_at and updated_at:
        return max(created_at, updated_at)
    return updated_at or created_at


def _first_value(item: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _normalize_pr_url(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().rstrip("/") or None


def _github_api_url(*, repo: str, path: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"https://api.github.com/repos/{repo}/{path}{separator}per_page=100"


def _fetch_github_json_url(*, url: str, token: str) -> tuple[object, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
        next_url = _parse_next_link(response.headers.get("Link", ""))
        return payload, next_url


def _fetch_github_json(*, repo: str, path: str, token: str) -> object:
    payload, _ = _fetch_github_json_url(
        url=_github_api_url(repo=repo, path=path), token=token
    )
    return payload


def _fetch_github_graphql(
    *, query: str, variables: Mapping[str, object], token: str
) -> Mapping[str, object]:
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": dict(variables)}).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, Mapping) else {}


def _fetch_github_list(*, repo: str, path: str, token: str) -> list[object]:
    items: list[object] = []
    url: str | None = _github_api_url(repo=repo, path=path)
    while url:
        payload, url = _fetch_github_json_url(url=url, token=token)
        if not isinstance(payload, list):
            return items
        items.extend(payload)
    return items


def _parse_next_link(header: str) -> str | None:
    for part in header.split(","):
        pieces = part.split(";")
        if len(pieces) < 2:
            continue
        if not any(piece.strip() == 'rel="next"' for piece in pieces[1:]):
            continue
        url = pieces[0].strip()
        if url.startswith("<") and url.endswith(">"):
            return url[1:-1]
    return None


def _fetch_pr_metadata(
    *, repo: str, pr_number: str, token: str
) -> Mapping[str, object] | None:
    payload = _fetch_github_json(repo=repo, path=f"pulls/{pr_number}", token=token)
    return payload if isinstance(payload, Mapping) else None


def _fetch_pr_comments(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"issues/{pr_number}/comments", token=token
    )
    return _enrich_required_trigger_reactions(
        [item for item in payload if isinstance(item, Mapping)],
        repo=repo,
        token=token,
    )


def _enrich_required_trigger_reactions(
    comments: Sequence[Mapping[str, object]],
    *,
    repo: str,
    token: str,
) -> list[Mapping[str, object]]:
    enriched: list[Mapping[str, object]] = []
    for comment in comments:
        if not _is_required_trigger_comment(comment):
            enriched.append(comment)
            continue
        comment_id = comment.get("id")
        if comment_id is None:
            enriched.append(comment)
            continue
        item = dict(comment)
        item["reaction_items"] = _fetch_issue_comment_reactions(
            repo=repo, comment_id=str(comment_id), token=token
        )
        enriched.append(item)
    return enriched


def _fetch_issue_comment_reactions(
    *, repo: str, comment_id: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"issues/comments/{comment_id}/reactions", token=token
    )
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_reviews(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/reviews", token=token
    )
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_review_comments(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/comments", token=token
    )
    return [item for item in payload if isinstance(item, Mapping)]


def _fetch_pr_changed_files(
    *, repo: str, pr_number: str, token: str
) -> tuple[str, ...]:
    payload = _fetch_github_list(
        repo=repo, path=f"pulls/{pr_number}/files", token=token
    )
    return tuple(
        str(item.get("filename", ""))
        for item in payload
        if isinstance(item, Mapping) and str(item.get("filename", "")).strip()
    )


def _fetch_issue_metadata(
    *, repo: str, pr_number: str, token: str
) -> Mapping[str, object]:
    payload = _fetch_github_json(repo=repo, path=f"issues/{pr_number}", token=token)
    return payload if isinstance(payload, Mapping) else {}


def _issue_label_names(issue: Mapping[str, object]) -> tuple[str, ...]:
    labels = issue.get("labels")
    if not isinstance(labels, list):
        return ()
    names: list[str] = []
    for label in labels:
        if isinstance(label, Mapping):
            name = str(label.get("name", "")).strip()
        else:
            name = str(label).strip()
        if name:
            names.append(name)
    return tuple(names)


def _fetch_pr_review_threads(
    *, repo: str, pr_number: str, token: str
) -> list[Mapping[str, object]]:
    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          reviewThreads(first: 100, after: $cursor) {
            nodes {
              isResolved
              isOutdated
              comments(first: 50) {
                nodes {
                  body
                  author {
                    login
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      }
    }
    """
    threads: list[Mapping[str, object]] = []
    cursor: str | None = None
    while True:
        payload = _fetch_github_graphql(
            query=query,
            variables={
                "owner": owner,
                "name": name,
                "number": int(pr_number),
                "cursor": cursor,
            },
            token=token,
        )
        connection = _graphql_review_threads_connection(payload)
        nodes = connection.get("nodes")
        if isinstance(nodes, list):
            threads.extend(item for item in nodes if isinstance(item, Mapping))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, Mapping) or not bool(page_info.get("hasNextPage")):
            break
        cursor = str(page_info.get("endCursor", "") or "")
        if not cursor:
            break
    return threads


def _graphql_review_threads_connection(
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return {}
    repository = data.get("repository")
    if not isinstance(repository, Mapping):
        return {}
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, Mapping):
        return {}
    review_threads = pull_request.get("reviewThreads")
    return review_threads if isinstance(review_threads, Mapping) else {}


def _read_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    return value if value else None


def _read_optional_file(path: Path | None) -> object | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_comments(payload: object | None) -> Sequence[object] | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        return ()
    comments: list[object] = []
    for item in payload:
        if isinstance(item, str):
            comments.append(item)
        elif isinstance(item, Mapping):
            comments.append(item)
    return comments


def _coerce_reviews(payload: object | None) -> Sequence[Mapping[str, object]] | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        return ()
    return [item for item in payload if isinstance(item, Mapping)]


def _coerce_review_threads(
    payload: object | None,
) -> Sequence[Mapping[str, object]] | None:
    return _coerce_reviews(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file", type=Path)
    source.add_argument("--body-env")
    parser.add_argument("--pr-url-env")
    parser.add_argument("--repo-env")
    parser.add_argument("--pr-number-env")
    parser.add_argument("--head-sha-env")
    parser.add_argument("--head-updated-at-env")
    parser.add_argument("--head-created-at-env", help=argparse.SUPPRESS)
    parser.add_argument("--github-token-env")
    parser.add_argument("--comments-file", type=Path)
    parser.add_argument("--reviews-file", type=Path)
    parser.add_argument("--review-comments-file", type=Path)
    parser.add_argument("--review-threads-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8", errors="replace")
    else:
        body = os.environ.get(args.body_env, "")

    comments = _coerce_comments(_read_optional_file(args.comments_file))
    reviews = _coerce_reviews(_read_optional_file(args.reviews_file))
    review_comments = _coerce_reviews(_read_optional_file(args.review_comments_file))
    review_threads = _coerce_review_threads(
        _read_optional_file(args.review_threads_file)
    )
    changed_files: Sequence[str] | None = None
    labels: Sequence[str] | None = None
    expected_pr_url = _read_env(args.pr_url_env)
    expected_head_sha = _read_env(args.head_sha_env)
    expected_head_created_at = _read_env(args.head_updated_at_env) or _read_env(
        args.head_created_at_env
    )

    repo = _read_env(args.repo_env)
    pr_number = _read_env(args.pr_number_env)
    token = _read_env(args.github_token_env)
    if repo and pr_number and token:
        pr_metadata: Mapping[str, object] | None = None
        if (
            not body
            or not expected_pr_url
            or not expected_head_sha
            or not expected_head_created_at
        ):
            pr_metadata = _fetch_pr_metadata(
                repo=repo, pr_number=pr_number, token=token
            )
            if pr_metadata is not None:
                if not body:
                    body = str(pr_metadata.get("body", ""))
                if not expected_pr_url:
                    expected_pr_url = str(pr_metadata.get("html_url", ""))
                head = pr_metadata.get("head")
                if not expected_head_sha and isinstance(head, Mapping):
                    expected_head_sha = str(head.get("sha", ""))
        if comments is None:
            comments = _fetch_pr_comments(repo=repo, pr_number=pr_number, token=token)
        if not expected_head_created_at:
            expected_head_created_at = head_updated_at_from_monitor_state(
                comments,
                expected_head_sha=expected_head_sha,
            )
        if reviews is None:
            reviews = _fetch_pr_reviews(repo=repo, pr_number=pr_number, token=token)
        if review_comments is None:
            review_comments = _fetch_pr_review_comments(
                repo=repo, pr_number=pr_number, token=token
            )
        if review_threads is None:
            review_threads = _fetch_pr_review_threads(
                repo=repo, pr_number=pr_number, token=token
            )
        changed_files = _fetch_pr_changed_files(
            repo=repo, pr_number=pr_number, token=token
        )
        labels = _issue_label_names(
            _fetch_issue_metadata(repo=repo, pr_number=pr_number, token=token)
        )

    if not expected_head_created_at:
        expected_head_created_at = head_updated_at_from_monitor_state(
            comments,
            expected_head_sha=expected_head_sha,
        )

    report = validate_pr_body(
        body,
        expected_pr_url=expected_pr_url,
        expected_head_sha=expected_head_sha,
        expected_head_created_at=expected_head_created_at,
        comments=comments,
        reviews=reviews,
        review_comments=review_comments,
        review_threads=review_threads,
        changed_files=changed_files,
        labels=labels,
    )
    if report.ok:
        print("PR review evidence ok")
        return 0
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
