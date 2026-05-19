from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance.ai_review_gate import (
    render_markdown_report,
    validate_report_file,
)


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_open_p1_blocks_progress(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 1,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "changed_files": ["strategies/etf_factor_rotation/etf_factor_rotation.py"],
            "findings": [
                {
                    "id": "AIR-001",
                    "severity": "P1",
                    "title": "默认参数变更缺少回归验证",
                    "path": "strategies/etf_factor_rotation/etf_factor_rotation.py",
                    "status": "open",
                    "evidence": "diff changes default MA parameter",
                    "recommendation": "补充回归测试或云端确认证据",
                }
            ],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "P0/P1 finding AIR-001 is not closed" in result.errors


def test_p2_requires_defer_reason(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 1,
            "tool": "claude",
            "reviewers": ["pr-review-toolkit", "security-guidance"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "changed_files": ["docs/guides/example.md"],
            "findings": [
                {
                    "id": "AIR-002",
                    "severity": "P2",
                    "title": "说明不够完整",
                    "path": "docs/guides/example.md",
                    "status": "accepted",
                    "evidence": "review noted missing context",
                    "recommendation": "补充上下文",
                }
            ],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "P2 finding AIR-002 accepted without defer_reason" in result.errors


def test_high_risk_scope_mentions_changed_file(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 1,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "changed_files": ["scripts/research/governance/rules.py"],
            "findings": [],
            "checks": {"pytest": "pass", "governance_gate": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok
    assert "scripts/research/governance/rules.py" in result.review_scope
    assert "@codex review" in result.review_scope
    assert "只审以下高风险范围的 P0/P1 逻辑风险" in result.review_scope


def test_markdown_summary_lists_risk_and_findings() -> None:
    payload = {
        "schema_version": 1,
        "tool": "codex",
        "reviewers": ["superpowers", "codex-security"],
        "risk_level": "low",
        "requires_official_codex_review": False,
        "changed_files": ["docs/guides/example.md"],
        "findings": [
            {
                "id": "AIR-003",
                "severity": "P2",
                "title": "说明不够完整",
                "path": "docs/guides/example.md",
                "status": "accepted",
                "evidence": "review noted missing context",
                "recommendation": "补充上下文",
                "defer_reason": "文档后续统一补充",
                "risk_acceptance": "不影响代码行为",
            }
        ],
        "checks": {"pytest": "pass"},
    }

    text = render_markdown_report(payload)

    assert "# 本地 AI Review 报告" in text
    assert "- 风险等级: low" in text
    assert "AIR-003" in text
    assert "docs/guides/example.md" in text


def test_report_file_accepts_utf8_bom(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    payload = {
        "schema_version": 1,
        "tool": "codex",
        "reviewers": ["superpowers"],
        "risk_level": "low",
        "requires_official_codex_review": False,
        "changed_files": ["docs/guides/example.md"],
        "findings": [],
        "checks": {"pytest": "pass"},
    }
    report.write_bytes(
        ("\ufeff" + json.dumps(payload, ensure_ascii=False)).encode("utf-8")
    )

    result = validate_report_file(report)

    assert result.ok, result.errors
