"""Validate local AI review reports and generate Codex review scope."""

from __future__ import annotations

import argparse
import hashlib
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
LEGACY_SCHEMA_VERSION = 2
CURRENT_SCHEMA_VERSION = 3
VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}
VALID_STATUSES = {"open", "fixed", "false_positive", "accepted"}
VALID_REVIEW_MODES = {"complete", "partial", "incremental"}
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
CODEX_REVIEW_LINK_PATTERN = re.compile(
    r"https://github\.com/[^\s`]+/[^\s`]+/pull/\d+#pullrequestreview-\d+"
)
CODEX_COMPLETION_COMMENT_LINK_PATTERN = re.compile(
    r"https://github\.com/[^\s`]+/[^\s`]+/(?:pull|issues)/\d+#issuecomment-\d+"
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


@dataclass(frozen=True)
class RiskClassification:
    risk_level: str
    requires_official_codex_review: bool
    reasons: tuple[str, ...]
    blocking_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class OfficialReviewDecision:
    action: str
    reason: str


def validate_report_file(
    path: Path,
    *,
    current_diff_fingerprint: dict[str, Any] | None = None,
) -> AiReviewValidation:
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
    return validate_report(
        payload,
        current_diff_fingerprint=current_diff_fingerprint,
    )


def validate_report(
    payload: dict[str, Any],
    *,
    current_diff_fingerprint: dict[str, Any] | None = None,
) -> AiReviewValidation:
    errors: list[str] = []
    schema_version = payload.get("schema_version")
    risk_level = str(payload.get("risk_level") or "unknown")
    changed_files = _string_list(payload.get("changed_files"))
    findings = payload.get("findings")
    if schema_version not in {LEGACY_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION}:
        errors.append("schema_version must be 2 or 3")
    if schema_version == CURRENT_SCHEMA_VERSION:
        errors.extend(
            _schema_v3_errors(
                payload,
                changed_files=changed_files,
                current_diff_fingerprint=current_diff_fingerprint,
            )
        )
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
        errors.append("review_mode must be complete, partial, or incremental")
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
    elif review_mode == "incremental":
        errors.extend(
            _incremental_review_errors(
                payload.get("incremental_review"),
                changed_files=changed_files,
                current_diff_fingerprint=current_diff_fingerprint,
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
            if not str(item.get("handling") or "").strip():
                errors.append(f"P2 finding {finding_id} accepted without handling")

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


def classify_risk(
    payload: dict[str, Any],
    *,
    coverage_complete: bool = True,
    unresolved_threads: Sequence[str] = (),
    failing_checks: Sequence[str] = (),
) -> RiskClassification:
    reasons: list[str] = []
    blocking_errors: list[str] = []
    risk_level = str(payload.get("risk_level") or "unknown")
    if risk_level not in {"low", "high", "unknown"}:
        risk_level = "unknown"
        reasons.append("risk level is invalid")

    changed_files = _string_list(payload.get("changed_files"))
    if any(_is_high_risk_path(path) for path in changed_files) and risk_level == "low":
        risk_level = "high"
        reasons.append("high-risk changed files require high risk")

    if not coverage_complete:
        risk_level = "unknown"
        blocking_errors.append("risk downgrade authorization cannot override incomplete coverage")

    accepted_non_blocking = False
    for item in payload.get("findings") or []:
        if not isinstance(item, dict):
            continue
        finding_id = str(item.get("id") or "<missing-id>")
        severity = str(item.get("severity") or "")
        status = str(item.get("status") or "")
        if severity in BLOCKING_SEVERITIES and status not in {
            "fixed",
            "false_positive",
        }:
            risk_level = "unknown"
            blocking_errors.append(f"P0/P1 finding {finding_id} is not closed")
        elif severity in {"P2", "P3"} and status == "accepted":
            accepted_non_blocking = True
    if accepted_non_blocking:
        reasons.append("accepted P2/P3 findings are non-blocking")

    if unresolved_threads:
        risk_level = "unknown"
        blocking_errors.extend(
            f"unresolved review thread: {item}" for item in unresolved_threads
        )
    if failing_checks:
        risk_level = "unknown"
        blocking_errors.extend(f"failing required check: {item}" for item in failing_checks)

    authorization = payload.get("risk_downgrade_authorization")
    if isinstance(authorization, dict):
        auth_errors = _authorization_errors(authorization, "risk downgrade")
        if auth_errors:
            blocking_errors.extend(auth_errors)
        elif blocking_errors:
            if coverage_complete:
                blocking_errors.append(
                    "risk downgrade authorization cannot override blockers"
                )
        elif risk_level in {"high", "unknown"}:
            risk_level = "low"
            reasons.append("risk downgrade authorized for current PR")

    return RiskClassification(
        risk_level=risk_level,
        requires_official_codex_review=risk_level in {"high", "unknown"},
        reasons=tuple(dict.fromkeys(reasons)),
        blocking_errors=tuple(dict.fromkeys(blocking_errors)),
    )


def decide_official_review_action(
    payload: dict[str, Any],
    *,
    current_head_present: bool = False,
    pending_trigger: bool = False,
    github_blockers: Sequence[str] = (),
) -> OfficialReviewDecision:
    validation = validate_report(payload)
    if not validation.requires_official_codex_review:
        return OfficialReviewDecision("not_required", "low-risk PR does not require official review")
    if github_blockers:
        return OfficialReviewDecision("blocked", "GitHub state has review blockers")
    if current_head_present:
        return OfficialReviewDecision("current_head_present", "current head already has official review evidence")
    if pending_trigger:
        return OfficialReviewDecision("pending", "current head already has pending @codex review trigger")
    if _official_review_reuse_allowed(payload):
        return OfficialReviewDecision("reused", "approved reused official Codex review evidence")
    return OfficialReviewDecision("trigger_needed", "official Codex review must be triggered")


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
    external_findings = [
        item
        for item in payload.get("external_findings") or []
        if isinstance(item, dict)
    ]
    all_findings = [*findings, *external_findings]
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
        f"- P0/P1 未关闭项: {_blocking_findings_summary(all_findings)}",
        "",
    ]
    diff_summary = _render_diff_fingerprint_summary(payload)
    if diff_summary:
        lines.extend(["## 当前提交与差异摘要", ""])
        lines.extend(diff_summary)
        lines.append("")
    lines.extend(["## 已运行检查", ""])
    lines.extend(_render_pr_body_check_lines(payload))
    lines.extend(
        [
            "",
            f"## {P2_SECTION_HEADER}",
            "",
        ]
    )
    p2_lines = _render_p2_body_lines(all_findings)
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
    fingerprint = _placeholder_diff_fingerprint(files)
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "tool": "codex",
        "review_mode": "complete",
        "risk_level": risk_level,
        "requires_official_codex_review": risk_level != "low",
        "changed_files": files,
        "diff_fingerprint": fingerprint,
        "review_fragments": {},
        "external_findings": [],
        "current_commit_evidence": {"head_sha": fingerprint["head_sha"], "checks": {}},
        "findings": [],
        "checks": {},
    }


def payload_as_schema_v3(
    payload: dict[str, Any],
    *,
    repo_root: str | Path,
    changed_files: Sequence[str] | None = None,
) -> dict[str, Any]:
    updated = dict(payload)
    files = (
        sorted({_normalize_repo_path(path) for path in changed_files if path})
        if changed_files is not None
        else _string_list(payload.get("changed_files"))
    )
    fingerprint = current_diff_fingerprint(repo_root) or _placeholder_diff_fingerprint(files)
    if files:
        fingerprint = dict(fingerprint)
        fingerprint["changed_files"] = files
    updated["schema_version"] = CURRENT_SCHEMA_VERSION
    updated["changed_files"] = files
    updated["diff_fingerprint"] = fingerprint
    updated["review_fragments"] = _review_fragments_from_payload(payload)
    raw_external_findings = payload.get("external_findings")
    updated["external_findings"] = (
        list(raw_external_findings) if isinstance(raw_external_findings, list) else []
    )
    checks = updated.get("checks") if isinstance(updated.get("checks"), dict) else {}
    updated["current_commit_evidence"] = {
        "head_sha": _single_line_text(fingerprint.get("head_sha")),
        "checks": checks,
    }
    return updated


def build_review_wrapper_evidence(
    *,
    standards_summary: str,
    spec_summary: str,
    standards_semantic_change: bool,
    spec_semantic_change: bool,
    parallel_attempted: bool,
    parallel_blocked_reason: str = "",
) -> dict[str, Any]:
    parallel = {
        "attempted": parallel_attempted,
        "blocked_reason": _single_line_text(parallel_blocked_reason),
    }
    standards = _single_line_text(standards_summary)
    spec = _single_line_text(spec_summary)
    return {
        "review_fragments": {
            "standards": {
                "status": "pass",
                "evidence": standards,
                "semantic_change": standards_semantic_change,
                "axis": "standards",
            },
            "spec": {
                "status": "pass",
                "evidence": spec,
                "semantic_change": spec_semantic_change,
                "axis": "spec",
            },
        },
        "raw_review_summary": {
            "standards": standards,
            "spec": spec,
            "parallel": parallel,
        },
    }


def _discover_changed_files(repo_root: str | Path = ".") -> list[str] | None:
    root = Path(repo_root)
    discovered: list[str] = []
    for command in (
        ["git", "-c", "core.quotePath=false", "diff", "--name-only", "--cached"],
        ["git", "-c", "core.quotePath=false", "diff", "--name-only"],
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
            ["git", "-c", "core.quotePath=false", "diff", "--name-only", f"{base}...HEAD"],
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
        ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"],
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


def current_diff_fingerprint(repo_root: str | Path = ".") -> dict[str, Any] | None:
    root = Path(repo_root)
    changed_files = _discover_changed_files(root)
    if changed_files is None:
        return None
    base_ref = _discover_branch_diff_base(root) or "unknown"
    head_sha = _git_stdout(root, ["git", "rev-parse", "HEAD"]) or "unknown"
    diff_text = ""
    if base_ref != "unknown":
        discovered_diff_text = _git_stdout(
            root,
            [
                "git",
                "-c",
                "core.quotePath=false",
                "diff",
                "--binary",
                "--no-ext-diff",
                f"{base_ref}...HEAD",
            ],
        )
        if discovered_diff_text is None:
            return None
        diff_text = discovered_diff_text
    unstaged_diff_text = _git_stdout(
        root,
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
        ],
    )
    staged_diff_text = _git_stdout(
        root,
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "--cached",
        ],
    )
    untracked_content = _untracked_content_fingerprint(root)
    if (
        unstaged_diff_text is None
        or staged_diff_text is None
        or untracked_content is None
    ):
        return None
    hash_source = json.dumps(
        {
            "changed_files": changed_files,
            "base_diff": diff_text or "",
            "staged_diff": staged_diff_text,
            "unstaged_diff": unstaged_diff_text,
            "untracked_content": untracked_content,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "base_ref": base_ref,
        "head_sha": head_sha,
        "diff_files_hash": hashlib.sha256(hash_source.encode("utf-8")).hexdigest(),
        "changed_files": changed_files,
    }


def _untracked_content_fingerprint(root: Path) -> str | None:
    output = _git_stdout(
        root,
        ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"],
    )
    if output is None:
        return None
    root_resolved = root.resolve()
    entries: list[str] = []
    for raw_path in output.splitlines():
        path = _normalize_repo_path(raw_path)
        if not path:
            continue
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            return None
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_bytes()
        except OSError:
            return None
        digest = hashlib.sha256(content).hexdigest()
        entries.append(f"{path}\0{len(content)}\0{digest}")
    return "\n".join(sorted(entries))


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


def _git_stdout(root: Path, command: list[str]) -> str | None:
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
    return result.stdout.strip()


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


def _placeholder_diff_fingerprint(changed_files: Sequence[str]) -> dict[str, Any]:
    files = sorted({_normalize_repo_path(path) for path in changed_files if path})
    return {
        "base_ref": "unknown",
        "head_sha": "unknown",
        "diff_files_hash": "uncomputed",
        "changed_files": files,
    }


def _review_fragments_from_payload(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    existing = payload.get("review_fragments")
    if isinstance(existing, dict):
        return {
            key: dict(value)
            for key, value in existing.items()
            if isinstance(key, str) and isinstance(value, dict)
        }
    security_review = payload.get("security_review")
    cross_review = payload.get("cross_review")
    complete_review = payload.get("complete_review")
    return {
        "standards": {
            "status": "pass",
            "evidence": _fragment_evidence(cross_review, "cross review completed"),
        },
        "spec": {
            "status": "pass",
            "evidence": _fragment_evidence(complete_review, "complete review recorded"),
        },
        "security": {
            "status": "pass",
            "evidence": _fragment_evidence(security_review, "security review completed"),
        },
    }


def _fragment_evidence(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        return _single_line_text(value.get("evidence")) or fallback
    return fallback


def _is_generated_strategy_artifact(path: str) -> bool:
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == "strategies" and parts[2] == "backtest_runs"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if isinstance(item, str) and (text := item.strip())]


def _schema_v3_errors(
    payload: dict[str, Any],
    *,
    changed_files: Sequence[str],
    current_diff_fingerprint: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    fingerprint = payload.get("diff_fingerprint")
    if not isinstance(fingerprint, dict):
        return ["diff_fingerprint must be an object for schema v3"]

    errors.extend(_issue_spec_policy_errors(payload))

    fingerprint_files = _normalized_string_list(fingerprint.get("changed_files"))
    if fingerprint_files != sorted({_normalize_repo_path(path) for path in changed_files}):
        errors.append("diff_fingerprint changed_files must match changed_files")
    if not _single_line_text(fingerprint.get("base_ref")):
        errors.append("diff_fingerprint base_ref must not be empty")
    if not _single_line_text(fingerprint.get("head_sha")):
        errors.append("diff_fingerprint head_sha must not be empty")
    if not _single_line_text(fingerprint.get("diff_files_hash")):
        errors.append("diff_fingerprint diff_files_hash must not be empty")

    review_fragments = payload.get("review_fragments")
    if not isinstance(review_fragments, dict):
        errors.append("review_fragments must be an object for schema v3")
    else:
        for name in ("standards", "spec", "security"):
            fragment = review_fragments.get(name)
            if not isinstance(fragment, dict) or not str(fragment.get("evidence") or "").strip():
                errors.append(f"review_fragments.{name} evidence must not be empty")

    if not isinstance(payload.get("external_findings"), list):
        errors.append("external_findings must be a list for schema v3")

    current_commit = payload.get("current_commit_evidence")
    if not isinstance(current_commit, dict):
        errors.append("current_commit_evidence must be an object for schema v3")
    elif (
        _single_line_text(current_commit.get("head_sha"))
        != _single_line_text(fingerprint.get("head_sha"))
    ):
        errors.append("current_commit_evidence head_sha must match diff_fingerprint")

    if current_diff_fingerprint is not None:
        errors.extend(_diff_fingerprint_drift_errors(fingerprint, current_diff_fingerprint))
    return errors


def _diff_fingerprint_drift_errors(
    recorded: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    recorded_files = _normalized_string_list(recorded.get("changed_files"))
    current_files = _normalized_string_list(current.get("changed_files"))
    if recorded_files != current_files:
        errors.append("diff_fingerprint changed_files does not match current diff")
    if (
        _single_line_text(recorded.get("head_sha"))
        and _single_line_text(current.get("head_sha"))
        and _single_line_text(recorded.get("head_sha"))
        != _single_line_text(current.get("head_sha"))
    ):
        errors.append("diff_fingerprint head_sha does not match current diff")
    if _single_line_text(recorded.get("diff_files_hash")) != _single_line_text(
        current.get("diff_files_hash")
    ):
        errors.append("diff_fingerprint diff_files_hash does not match current diff")
    return errors


def _issue_spec_policy_errors(payload: dict[str, Any]) -> list[str]:
    pr_class = _single_line_text(payload.get("pr_class")) or "maintenance"
    if pr_class not in {
        "feature",
        "governance_functional",
        "governance_wording",
        "maintenance",
    }:
        return ["pr_class must be feature, governance_functional, governance_wording, or maintenance"]

    has_issue_or_spec = bool(
        _single_line_text(payload.get("issue_ref"))
        or _single_line_text(payload.get("spec_ref"))
    )
    authorization = payload.get("issue_spec_skip_authorization")
    has_authorization = isinstance(authorization, dict)
    authorization_errors = (
        _authorization_errors(authorization, "issue/spec skip")
        if has_authorization
        else []
    )
    if authorization_errors:
        return authorization_errors
    if has_issue_or_spec or has_authorization or pr_class == "maintenance":
        return []

    if pr_class in {"feature", "governance_functional"}:
        return [f"pr_class {pr_class} requires issue_ref or spec_ref"]

    fragments = payload.get("review_fragments")
    if pr_class == "governance_wording" and isinstance(fragments, dict):
        standards = fragments.get("standards")
        spec = fragments.get("spec")
        if (
            isinstance(standards, dict)
            and isinstance(spec, dict)
            and standards.get("semantic_change") is False
            and spec.get("semantic_change") is False
        ):
            return []
    return [
        "governance_wording without issue_ref/spec_ref requires both review axes to confirm no semantic change"
    ]


def _official_review_reuse_allowed(payload: dict[str, Any]) -> bool:
    reuse = payload.get("official_codex_review_reuse")
    fragments = payload.get("review_fragments")
    if not isinstance(reuse, dict) or not isinstance(fragments, dict):
        return False
    standards = fragments.get("standards")
    spec = fragments.get("spec")
    security = fragments.get("security")
    if not (
        isinstance(standards, dict)
        and isinstance(spec, dict)
        and isinstance(security, dict)
    ):
        return False
    if standards.get("official_scope_impact") is not False:
        return False
    if spec.get("official_scope_impact") is not False:
        return False
    if security.get("security_impact") is not False:
        return False
    return bool(
        _single_line_text(reuse.get("old_head_sha"))
        and _single_line_text(reuse.get("current_head_sha"))
        and _single_line_text(reuse.get("reason"))
        and _string_or_list(reuse.get("evidence"))
    )


def _incremental_review_errors(
    value: Any,
    *,
    changed_files: Sequence[str],
    current_diff_fingerprint: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(value, dict):
        return ["incremental_review must be an object"]
    base_review = value.get("base_review")
    increments = value.get("increments")
    errors: list[str] = []
    if not isinstance(base_review, dict):
        errors.append("incremental_review.base_review must be an object")
        base_files: list[str] = []
    else:
        base_files = _normalized_string_list(base_review.get("covered_changed_files"))
        if not _single_line_text(base_review.get("diff_files_hash")):
            errors.append("incremental_review.base_review diff_files_hash must not be empty")
    if not isinstance(increments, list) or not increments:
        errors.append("incremental_review.increments must not be empty")
        increment_files: list[str] = []
    else:
        increment_files = []
        has_current_increment = current_diff_fingerprint is None
        current_hash = (
            _single_line_text(current_diff_fingerprint.get("diff_files_hash"))
            if current_diff_fingerprint is not None
            else ""
        )
        for index, item in enumerate(increments):
            if not isinstance(item, dict):
                errors.append(f"incremental_review.increments[{index}] must be an object")
                continue
            increment_files.extend(
                _normalized_string_list(item.get("covered_changed_files"))
            )
            if not _single_line_text(item.get("evidence")):
                errors.append(
                    f"incremental_review.increments[{index}] evidence must not be empty"
                )
            if _single_line_text(item.get("diff_files_hash")) == current_hash:
                has_current_increment = True
        if not has_current_increment:
            errors.append("incremental_review must include an increment for current diff")
    covered = sorted({*base_files, *increment_files})
    expected = sorted({_normalize_repo_path(path) for path in changed_files})
    if covered != expected:
        errors.append("incremental_review covered_changed_files must cover current diff")
    return errors


def _normalized_string_list(value: Any) -> list[str]:
    return sorted({_normalize_repo_path(path) for path in _string_list(value)})


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


def _render_diff_fingerprint_summary(payload: dict[str, Any]) -> list[str]:
    fingerprint = payload.get("diff_fingerprint")
    if not isinstance(fingerprint, dict):
        return []
    changed_files = _normalized_string_list(fingerprint.get("changed_files"))
    head_sha = _single_line_text(fingerprint.get("head_sha"))
    diff_hash = _single_line_text(fingerprint.get("diff_files_hash"))
    base_ref = _single_line_text(fingerprint.get("base_ref"))
    if not head_sha and not diff_hash and not base_ref:
        return []
    return [
        f"- Base: {base_ref or 'unknown'}",
        f"- Head SHA: {_short_sha(head_sha)}",
        f"- Diff hash: {diff_hash or 'unknown'}",
        f"- Changed files: {len(changed_files)}",
        "- Changed file paths:",
        *(f"  - `{path}`" for path in changed_files),
    ]


def _short_sha(value: str) -> str:
    return value[:12] if value else "unknown"


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
    reuse = payload.get("official_codex_review_reuse")
    if isinstance(reuse, dict):
        evidence = _string_or_list(reuse.get("evidence"))
        if evidence:
            lines = [
                "- Reviewer: Codex",
                "- 触发方式: @codex review (reused)",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 复用状态: reused",
                f"- 旧 head: {_short_sha(_single_line_text(reuse.get('old_head_sha')))}",
                f"- 当前 head: {_short_sha(_single_line_text(reuse.get('current_head_sha')))}",
                f"- 复用原因: {_single_line_text(reuse.get('reason'))}",
                "- 关键证据:",
            ]
            lines.extend(f"  - {item}" for item in evidence)
            return lines
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
    lines.extend(
        f"  - {_format_official_codex_review_evidence(item)}" for item in evidence
    )
    return lines


def _format_official_codex_review_evidence(item: str) -> str:
    text = _single_line_text(item)
    if "Codex review 链接" in text:
        return text
    unquoted = text.strip("`")
    if CODEX_REVIEW_LINK_PATTERN.search(
        unquoted
    ) or CODEX_COMPLETION_COMMENT_LINK_PATTERN.search(unquoted):
        return f"Codex review 链接：{unquoted}"
    return text


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
