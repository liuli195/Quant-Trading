from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance import ai_review_gate
from scripts.research.governance.ai_review_gate import (
    render_markdown_report,
    validate_report_file,
)
from scripts.research.governance.pr_review_evidence import (
    AI_REVIEW_SECTION_HEADER,
    P2_SECTION_HEADER,
    SECTION_HEADER,
    validate_pr_body,
)

GOVERNANCE_GATE_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full"
)


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _cross_review() -> dict:
    return {
        "delegated_to_subagents": True,
        "review_skills": [
            "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
            "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
        ],
        "evidence": "spec reviewer and code quality reviewer subagents completed",
    }


def _complete_review(*reviewers: str) -> dict:
    reviewer_names = reviewers or ("spec-review-subagent", "quality-review-subagent")
    return {
        "evidence": "each reviewer continued searching until no new findings",
        "iterations": [
            {
                "reviewer": reviewer,
                "round": 1,
                "new_findings": [],
                "no_new_findings": True,
            }
            for reviewer in reviewer_names
        ],
    }


def _review_mode_authorization() -> dict:
    return {
        "authorized_by": "用户",
        "reason": "本次只做紧急小范围文档修订",
        "evidence": "当前对话中用户明确授权不完全 review 模式",
    }


def _official_skip_authorization() -> dict:
    return {
        "authorized_by": "用户",
        "reason": "当前 PR 官方 Codex review 成本高于风险",
        "evidence": "当前对话中用户明确授权跳过官方 Codex review",
    }


def _security_review(tool: str = "codex") -> dict:
    review_tool = {
        "codex": "codex-security",
        "claude": "security-guidance",
    }[tool]
    return {
        "tool": review_tool,
        "evidence": f"{review_tool} local security review completed",
    }


def _valid_complete_payload(
    *,
    changed_files: list[str] | None = None,
    risk_level: str = "low",
    requires_official: bool = False,
) -> dict:
    return {
        "schema_version": 2,
        "tool": "codex",
        "reviewers": ["spec-review-subagent", "quality-review-subagent"],
        "risk_level": risk_level,
        "requires_official_codex_review": requires_official,
        "security_review": _security_review(),
        "cross_review": _cross_review(),
        "complete_review": _complete_review(
            "spec-review-subagent", "quality-review-subagent"
        ),
        "changed_files": changed_files or ["docs/guides/example.md"],
        "findings": [],
        "checks": {"verify full": GOVERNANCE_GATE_COMMAND, "pytest": "pass"},
    }


def _diff_fingerprint(
    *,
    changed_files: list[str] | None = None,
    head_sha: str = "1" * 40,
    diff_files_hash: str = "diff-hash-1",
) -> dict:
    files = changed_files or ["docs/guides/example.md"]
    return {
        "base_ref": "origin/main",
        "head_sha": head_sha,
        "diff_files_hash": diff_files_hash,
        "changed_files": files,
    }


def _valid_v3_payload(
    *,
    changed_files: list[str] | None = None,
    diff_files_hash: str = "diff-hash-1",
    review_mode: str = "complete",
) -> dict:
    files = changed_files or ["docs/guides/example.md"]
    fingerprint = _diff_fingerprint(
        changed_files=files,
        diff_files_hash=diff_files_hash,
    )
    payload = _valid_complete_payload(changed_files=files)
    payload.update(
        {
            "schema_version": 3,
            "review_mode": review_mode,
            "diff_fingerprint": fingerprint,
            "review_fragments": {
                "standards": {
                    "status": "pass",
                    "evidence": "standards review completed",
                },
                "spec": {"status": "pass", "evidence": "spec review completed"},
                "security": {
                    "status": "pass",
                    "evidence": "security review completed",
                },
            },
            "external_findings": [],
            "current_commit_evidence": {
                "head_sha": fingerprint["head_sha"],
                "checks": payload["checks"],
            },
        }
    )
    return payload


def test_discover_changed_files_merges_cached_and_worktree(
    monkeypatch,
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []

    class FakeResult:
        def __init__(self, stdout: str, returncode: int = 0) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_run(command: list[str], **kwargs: object) -> FakeResult:
        commands.append(tuple(command))
        assert kwargs["cwd"] == tmp_path
        if command == ["git", "-c", "core.quotePath=false", "diff", "--name-only", "--cached"]:
            return FakeResult("scripts\\research\\governance\\ai_review_gate.py\n")
        if command == ["git", "-c", "core.quotePath=false", "diff", "--name-only"]:
            return FakeResult(
                "docs/guides/example.md\nscripts/research/governance/ai_review_gate.py\n"
            )
        if command == ["git", "merge-base", "--fork-point", "origin/main", "HEAD"]:
            return FakeResult("abc123\n")
        if command == ["git", "-c", "core.quotePath=false", "diff", "--name-only", "abc123...HEAD"]:
            return FakeResult("scripts/research/governance/pr_flow.py\n")
        if command == ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"]:
            return FakeResult("docs/superpowers/plans/new-plan.md\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(ai_review_gate.subprocess, "run", fake_run)

    changed_files = ai_review_gate._discover_changed_files(tmp_path)

    assert commands == [
        ("git", "-c", "core.quotePath=false", "diff", "--name-only", "--cached"),
        ("git", "-c", "core.quotePath=false", "diff", "--name-only"),
        ("git", "merge-base", "--fork-point", "origin/main", "HEAD"),
        ("git", "-c", "core.quotePath=false", "diff", "--name-only", "abc123...HEAD"),
        ("git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"),
    ]
    assert changed_files == [
        "docs/guides/example.md",
        "docs/superpowers/plans/new-plan.md",
        "scripts/research/governance/ai_review_gate.py",
        "scripts/research/governance/pr_flow.py",
    ]


def test_discover_changed_files_uses_merge_base_fallback(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class FakeResult:
        def __init__(self, stdout: str = "", returncode: int = 0) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_run(command: list[str], **kwargs: object) -> FakeResult:
        assert kwargs["cwd"] == tmp_path
        if command in (
            ["git", "-c", "core.quotePath=false", "diff", "--name-only", "--cached"],
            ["git", "-c", "core.quotePath=false", "diff", "--name-only"],
            ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"],
        ):
            return FakeResult("")
        if command == ["git", "merge-base", "--fork-point", "origin/main", "HEAD"]:
            return FakeResult(returncode=1)
        if command == ["git", "merge-base", "origin/main", "HEAD"]:
            return FakeResult("base456\n")
        if command == ["git", "-c", "core.quotePath=false", "diff", "--name-only", "base456...HEAD"]:
            return FakeResult("docs/rules/pr-workflow.md\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(ai_review_gate.subprocess, "run", fake_run)

    assert ai_review_gate._discover_changed_files(tmp_path) == [
        "docs/rules/pr-workflow.md"
    ]


def test_discover_changed_files_returns_none_for_clean_branch_without_base(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class FakeResult:
        def __init__(self, stdout: str = "", returncode: int = 0) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_run(command: list[str], **kwargs: object) -> FakeResult:
        assert kwargs["cwd"] == tmp_path
        if command in (
            ["git", "-c", "core.quotePath=false", "diff", "--name-only", "--cached"],
            ["git", "-c", "core.quotePath=false", "diff", "--name-only"],
            ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"],
        ):
            return FakeResult("")
        if command[:2] == ["git", "merge-base"]:
            return FakeResult(returncode=1)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(ai_review_gate.subprocess, "run", fake_run)

    assert ai_review_gate._discover_changed_files(tmp_path) is None


def test_draft_command_writes_high_risk_defaults(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / ".local/ai-review/latest.draft.json"
    monkeypatch.setattr(
        ai_review_gate,
        "_discover_changed_files",
        lambda repo_root: ["scripts/research/governance/ai_review_gate.py"],
    )

    code = ai_review_gate.main(["draft", "--output", str(output)])

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert payload["tool"] == "codex"
    assert payload["review_mode"] == "complete"
    assert payload["risk_level"] == "high"
    assert payload["requires_official_codex_review"] is True
    assert payload["changed_files"] == ["scripts/research/governance/ai_review_gate.py"]
    assert payload["diff_fingerprint"]["changed_files"] == [
        "scripts/research/governance/ai_review_gate.py"
    ]
    assert payload["review_fragments"] == {}
    assert payload["external_findings"] == []
    assert payload["current_commit_evidence"]["head_sha"] == "unknown"
    assert payload["findings"] == []
    assert payload["checks"] == {}
    assert "security_review" not in payload
    assert "cross_review" not in payload
    assert "complete_review" not in payload


def test_draft_command_marks_docs_only_changes_low_risk(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "draft.json"
    monkeypatch.setattr(
        ai_review_gate,
        "_discover_changed_files",
        lambda repo_root: ["docs/guides/example.md"],
    )

    code = ai_review_gate.main(["draft", "--output", str(output)])

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["risk_level"] == "low"
    assert payload["requires_official_codex_review"] is False


def test_draft_command_marks_undetected_changes_unknown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "draft.json"
    monkeypatch.setattr(
        ai_review_gate,
        "_discover_changed_files",
        lambda repo_root: None,
    )

    code = ai_review_gate.main(["draft", "--output", str(output)])

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["risk_level"] == "unknown"
    assert payload["requires_official_codex_review"] is True
    assert payload["changed_files"] == []


def test_pr_body_command_renders_low_risk_body_accepted_by_validator(
    tmp_path: Path,
) -> None:
    report = tmp_path / ".local/ai-review/latest.json"
    output = tmp_path / ".local/ai-review/pr-body.md"
    payload = _valid_complete_payload()
    _write_report(report, payload)

    code = ai_review_gate.main(
        ["pr-body", "--report", str(report), "--output", str(output)]
    )

    assert code == 0
    body = output.read_text(encoding="utf-8")
    assert f"## {AI_REVIEW_SECTION_HEADER}" in body
    assert f"## {P2_SECTION_HEADER}" in body
    assert f"## {SECTION_HEADER}" not in body
    assert "## 已运行检查" in body
    assert GOVERNANCE_GATE_COMMAND in body
    evidence = validate_pr_body(
        body,
        changed_files=payload["changed_files"],
        labels=[],
    )
    assert evidence.ok, evidence.errors


def test_pr_body_renders_v3_head_and_diff_summary_without_full_diff() -> None:
    payload = _valid_v3_payload(
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )
    body = ai_review_gate.render_pr_body(payload)

    assert "Head SHA: 111111111111" in body
    assert "Diff hash: current-diff" in body
    assert "Changed files: 1" in body
    assert "Changed file paths:" in body
    assert "`docs/guides/example.md`" in body
    assert "diff --git" not in body


def test_current_diff_fingerprint_hashes_worktree_patch_content(
    monkeypatch,
    tmp_path: Path,
) -> None:
    unstaged_patch = {"text": "unstaged-v1"}

    monkeypatch.setattr(
        ai_review_gate,
        "_discover_changed_files",
        lambda _root: ["docs/guides/example.md"],
    )
    monkeypatch.setattr(
        ai_review_gate,
        "_discover_branch_diff_base",
        lambda _root: "origin/main",
    )

    def fake_git_stdout(_root: Path, command: list[str]) -> str | None:
        if command == ["git", "rev-parse", "HEAD"]:
            return "1" * 40
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "origin/main...HEAD",
        ]:
            return "base-diff"
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
        ]:
            return unstaged_patch["text"]
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "--cached",
        ]:
            return "staged-diff"
        return None

    monkeypatch.setattr(ai_review_gate, "_git_stdout", fake_git_stdout)
    monkeypatch.setattr(
        ai_review_gate,
        "_untracked_content_fingerprint",
        lambda _root: "untracked-v1",
    )

    first = ai_review_gate.current_diff_fingerprint(tmp_path)
    unstaged_patch["text"] = "unstaged-v2"
    second = ai_review_gate.current_diff_fingerprint(tmp_path)

    assert first is not None
    assert second is not None
    assert first["diff_files_hash"] != second["diff_files_hash"]


def test_current_diff_fingerprint_hashes_untracked_content(
    monkeypatch,
    tmp_path: Path,
) -> None:
    untracked_hash = {"text": "untracked-v1"}

    monkeypatch.setattr(
        ai_review_gate,
        "_discover_changed_files",
        lambda _root: ["docs/guides/new.md"],
    )
    monkeypatch.setattr(
        ai_review_gate,
        "_discover_branch_diff_base",
        lambda _root: "origin/main",
    )

    def fake_git_stdout(_root: Path, command: list[str]) -> str | None:
        if command == ["git", "rev-parse", "HEAD"]:
            return "1" * 40
        if command[:6] == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
        ]:
            return ""
        return None

    monkeypatch.setattr(ai_review_gate, "_git_stdout", fake_git_stdout)
    monkeypatch.setattr(
        ai_review_gate,
        "_untracked_content_fingerprint",
        lambda _root: untracked_hash["text"],
    )

    first = ai_review_gate.current_diff_fingerprint(tmp_path)
    untracked_hash["text"] = "untracked-v2"
    second = ai_review_gate.current_diff_fingerprint(tmp_path)

    assert first is not None
    assert second is not None
    assert first["diff_files_hash"] != second["diff_files_hash"]


def test_pr_body_command_renders_accepted_p2_details(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    output = tmp_path / "pr-body.md"
    payload = _valid_complete_payload()
    payload["findings"] = [
        {
            "id": "AIR-003",
            "severity": "P2",
            "title": "文档说明不足",
            "path": "docs/guides/example.md",
            "status": "accepted",
            "defer_reason": "统一随下一批文档补齐",
            "risk_acceptance": "不影响代码执行和治理门禁",
            "handling": "保留为后续文档任务",
        }
    ]
    _write_report(report, payload)

    code = ai_review_gate.main(
        ["pr-body", "--report", str(report), "--output", str(output)]
    )

    assert code == 0
    body = output.read_text(encoding="utf-8")
    assert "defer_reason: 统一随下一批文档补齐" in body
    assert "risk_acceptance: 不影响代码执行和治理门禁" in body
    assert "handling: 保留为后续文档任务" in body
    evidence = validate_pr_body(
        body,
        changed_files=payload["changed_files"],
        labels=[],
    )
    assert evidence.ok, evidence.errors


def test_pr_body_renders_accepted_external_p2_details() -> None:
    payload = _valid_v3_payload(changed_files=["docs/guides/example.md"])
    payload["external_findings"] = [
        {
            "id": "EXT-CODEX-THREAD-PRRT_p2",
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_p2",
            "severity": "P2",
            "title": "Official Codex advisory",
            "path": "https://github.com/liuli195/Quant-Trading/pull/7",
            "status": "accepted",
            "defer_reason": "official Codex P2 finding is not a merge blocker",
            "risk_acceptance": "accepted as retained P2 review advice",
            "handling": "fixed acceptance reply posted and thread resolved",
        }
    ]

    body = ai_review_gate.render_pr_body(payload)

    assert "EXT-CODEX-THREAD-PRRT_p2" in body
    assert "defer_reason: official Codex P2 finding is not a merge blocker" in body
    assert "risk_acceptance: accepted as retained P2 review advice" in body
    assert "handling: fixed acceptance reply posted and thread resolved" in body


def test_pr_body_renders_codex_section_only_when_evidence_is_present(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    output = tmp_path / "pr-body.md"
    payload = _valid_complete_payload(
        changed_files=["scripts/research/governance/ai_review_gate.py"],
        risk_level="high",
        requires_official=True,
    )
    _write_report(report, payload)

    code = ai_review_gate.main(
        ["pr-body", "--report", str(report), "--output", str(output)]
    )

    assert code == 0
    assert f"## {SECTION_HEADER}" not in output.read_text(encoding="utf-8")

    payload["official_codex_review"] = {
        "reviewer": "Codex",
        "trigger": "@codex review",
        "conclusion": "通过",
        "blocking_issues": "无",
        "evidence": [
            "Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
            "`.\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full`",
        ],
    }
    _write_report(report, payload)

    code = ai_review_gate.main(
        ["pr-body", "--report", str(report), "--output", str(output)]
    )

    assert code == 0
    body = output.read_text(encoding="utf-8")
    assert f"## {SECTION_HEADER}" in body
    evidence = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        changed_files=payload["changed_files"],
        labels=["ai-risk-review"],
    )
    assert evidence.ok, evidence.errors


def test_pr_body_prefixes_raw_codex_review_link_for_validator(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    output = tmp_path / "pr-body.md"
    payload = _valid_complete_payload(
        changed_files=["scripts/research/governance/ai_review_gate.py"],
        risk_level="high",
        requires_official=True,
    )
    payload["official_codex_review"] = {
        "reviewer": "Codex",
        "trigger": "@codex review",
        "conclusion": "通过",
        "blocking_issues": "无",
        "evidence": [
            "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
            GOVERNANCE_GATE_COMMAND,
        ],
    }
    _write_report(report, payload)

    code = ai_review_gate.main(
        ["pr-body", "--report", str(report), "--output", str(output)]
    )

    assert code == 0
    body = output.read_text(encoding="utf-8")
    assert (
        "Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5"
        "#pullrequestreview-4314779358"
    ) in body
    evidence = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        changed_files=payload["changed_files"],
        labels=["ai-risk-review"],
    )
    assert evidence.ok, evidence.errors


def test_pr_body_prefixes_raw_codex_completion_comment_link_for_validator(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    output = tmp_path / "pr-body.md"
    payload = _valid_complete_payload(
        changed_files=["scripts/research/governance/ai_review_gate.py"],
        risk_level="high",
        requires_official=True,
    )
    payload["official_codex_review"] = {
        "reviewer": "Codex",
        "trigger": "@codex review",
        "conclusion": "通过",
        "blocking_issues": "无",
        "evidence": [
            "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4557969190",
            GOVERNANCE_GATE_COMMAND,
        ],
    }
    _write_report(report, payload)

    code = ai_review_gate.main(
        ["pr-body", "--report", str(report), "--output", str(output)]
    )

    assert code == 0
    body = output.read_text(encoding="utf-8")
    assert "#issuecomment-4557969190" in body
    evidence = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        changed_files=payload["changed_files"],
        labels=["ai-risk-review"],
    )
    assert evidence.ok, evidence.errors


def test_codex_report_requires_codex_security_review(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "security_review.tool must be codex-security for codex local review"
        in result.errors
    )


def test_claude_report_requires_security_guidance_review(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "claude",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "security_review.tool must be security-guidance for claude local review"
        in result.errors
    )


def test_schema_v2_defaults_to_complete_review_mode(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok, result.errors


def test_schema_v3_accepts_matching_diff_fingerprint() -> None:
    payload = _valid_v3_payload(
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )
    current = _diff_fingerprint(
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )

    result = ai_review_gate.validate_report(
        payload,
        current_diff_fingerprint=current,
    )

    assert result.ok, result.errors


def test_schema_v3_rejects_changed_file_drift() -> None:
    payload = _valid_v3_payload(
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )
    current = _diff_fingerprint(
        changed_files=["docs/guides/example.md", "scripts/research/governance/pr_flow.py"],
        diff_files_hash="current-diff",
    )

    result = ai_review_gate.validate_report(
        payload,
        current_diff_fingerprint=current,
    )

    assert not result.ok
    assert "diff_fingerprint changed_files does not match current diff" in result.errors


def test_schema_v3_rejects_diff_hash_drift() -> None:
    payload = _valid_v3_payload(
        changed_files=["docs/guides/example.md"],
        diff_files_hash="old-diff",
    )
    current = _diff_fingerprint(
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )

    result = ai_review_gate.validate_report(
        payload,
        current_diff_fingerprint=current,
    )

    assert not result.ok
    assert "diff_fingerprint diff_files_hash does not match current diff" in result.errors


def test_schema_v3_accepts_incremental_review_covering_current_diff() -> None:
    payload = _valid_v3_payload(
        changed_files=[
            "docs/guides/example.md",
            "scripts/research/governance/pr_flow.py",
        ],
        diff_files_hash="current-diff",
        review_mode="incremental",
    )
    payload["risk_level"] = "high"
    payload["requires_official_codex_review"] = True
    payload["incremental_review"] = {
        "base_review": {
            "diff_files_hash": "base-diff",
            "covered_changed_files": ["docs/guides/example.md"],
        },
        "increments": [
            {
                "diff_files_hash": "current-diff",
                "covered_changed_files": ["scripts/research/governance/pr_flow.py"],
                "evidence": "incremental review covered new governance file",
            }
        ],
    }
    current = _diff_fingerprint(
        changed_files=[
            "docs/guides/example.md",
            "scripts/research/governance/pr_flow.py",
        ],
        diff_files_hash="current-diff",
    )

    result = ai_review_gate.validate_report(
        payload,
        current_diff_fingerprint=current,
    )

    assert result.ok, result.errors


def test_review_wrapper_builds_standards_spec_fragments_and_raw_summary() -> None:
    evidence = ai_review_gate.build_review_wrapper_evidence(
        standards_summary="Standards axis passed.",
        spec_summary="Spec axis matched issue #27.",
        standards_semantic_change=True,
        spec_semantic_change=True,
        parallel_attempted=True,
    )

    assert set(evidence["review_fragments"]) == {"standards", "spec"}
    assert evidence["review_fragments"]["standards"]["evidence"] == (
        "Standards axis passed."
    )
    assert evidence["review_fragments"]["spec"]["evidence"] == (
        "Spec axis matched issue #27."
    )
    assert evidence["raw_review_summary"]["standards"] == "Standards axis passed."
    assert evidence["raw_review_summary"]["spec"] == "Spec axis matched issue #27."
    assert evidence["raw_review_summary"]["parallel"]["attempted"] is True


def test_schema_v3_accepts_feature_pr_with_spec_ref() -> None:
    payload = _valid_v3_payload()
    payload["pr_class"] = "feature"
    payload["spec_ref"] = "https://github.com/liuli195/Quant-Trading/issues/27"

    result = ai_review_gate.validate_report(payload)

    assert result.ok, result.errors


def test_schema_v3_accepts_maintenance_without_spec_ref() -> None:
    payload = _valid_v3_payload()
    payload["pr_class"] = "maintenance"

    result = ai_review_gate.validate_report(payload)

    assert result.ok, result.errors


def test_schema_v3_accepts_governance_wording_without_semantic_change() -> None:
    payload = _valid_v3_payload(changed_files=["docs/rules/pr-workflow.md"])
    payload["risk_level"] = "high"
    payload["requires_official_codex_review"] = True
    payload["pr_class"] = "governance_wording"
    payload["review_fragments"]["standards"]["semantic_change"] = False
    payload["review_fragments"]["spec"]["semantic_change"] = False

    result = ai_review_gate.validate_report(payload)

    assert result.ok, result.errors


def test_schema_v3_rejects_governance_functional_without_spec_ref() -> None:
    payload = _valid_v3_payload(changed_files=["docs/rules/pr-workflow.md"])
    payload["risk_level"] = "high"
    payload["requires_official_codex_review"] = True
    payload["pr_class"] = "governance_functional"

    result = ai_review_gate.validate_report(payload)

    assert not result.ok
    assert "pr_class governance_functional requires issue_ref or spec_ref" in result.errors


def test_schema_v3_accepts_issue_spec_skip_authorization() -> None:
    payload = _valid_v3_payload(changed_files=["scripts/research/governance/pr_flow.py"])
    payload["risk_level"] = "high"
    payload["requires_official_codex_review"] = True
    payload["pr_class"] = "governance_functional"
    payload["issue_spec_skip_authorization"] = {
        "authorized_by": "用户",
        "reason": "当前 PR 是一次性流程修复",
        "evidence": "用户明确授权跳过 issue/spec 要求",
    }

    result = ai_review_gate.validate_report(payload)

    assert result.ok, result.errors


def test_risk_classifier_outputs_low_high_unknown_and_official_requirement() -> None:
    low = ai_review_gate.classify_risk(_valid_complete_payload(risk_level="low"))
    high = ai_review_gate.classify_risk(_valid_complete_payload(risk_level="high"))
    unknown = ai_review_gate.classify_risk(
        _valid_complete_payload(risk_level="unknown")
    )

    assert low.risk_level == "low"
    assert low.requires_official_codex_review is False
    assert high.risk_level == "high"
    assert high.requires_official_codex_review is True
    assert unknown.risk_level == "unknown"
    assert unknown.requires_official_codex_review is True


def test_risk_classifier_ignores_accepted_p2_p3_findings() -> None:
    payload = _valid_complete_payload(risk_level="low")
    payload["findings"] = [
        {
            "id": "AIR-002",
            "severity": "P2",
            "status": "accepted",
            "defer_reason": "后续统一处理",
            "risk_acceptance": "不影响合并安全",
            "handling": "保留为后续任务",
        },
        {"id": "AIR-003", "severity": "P3", "status": "accepted"},
    ]

    result = ai_review_gate.classify_risk(payload)

    assert result.risk_level == "low"
    assert result.requires_official_codex_review is False
    assert "accepted P2/P3 findings are non-blocking" in result.reasons


def test_risk_classifier_blocks_unclosed_p0_p1_findings() -> None:
    payload = _valid_complete_payload(risk_level="low")
    payload["findings"] = [
        {"id": "AIR-001", "severity": "P1", "status": "open"},
    ]

    result = ai_review_gate.classify_risk(payload)

    assert result.risk_level == "unknown"
    assert result.requires_official_codex_review is True
    assert "P0/P1 finding AIR-001 is not closed" in result.blocking_errors


def test_risk_classifier_allows_current_pr_downgrade_without_blockers() -> None:
    payload = _valid_complete_payload(risk_level="high")
    payload["risk_downgrade_authorization"] = {
        "authorized_by": "用户",
        "reason": "当前 PR 只调整注释",
        "evidence": "用户明确授权当前 PR 降级",
    }

    result = ai_review_gate.classify_risk(payload)

    assert result.risk_level == "low"
    assert result.requires_official_codex_review is False
    assert "risk downgrade authorized for current PR" in result.reasons


def test_risk_classifier_rejects_downgrade_when_coverage_incomplete() -> None:
    payload = _valid_complete_payload(risk_level="high")
    payload["risk_downgrade_authorization"] = {
        "authorized_by": "用户",
        "reason": "当前 PR 降级",
        "evidence": "用户明确授权",
    }

    result = ai_review_gate.classify_risk(payload, coverage_complete=False)

    assert result.risk_level == "unknown"
    assert result.requires_official_codex_review is True
    assert (
        "risk downgrade authorization cannot override incomplete coverage"
        in result.blocking_errors
    )


def test_official_review_decision_supports_all_actions() -> None:
    low = _valid_complete_payload(risk_level="low")
    high = _valid_complete_payload(risk_level="high")
    reusable = _valid_v3_payload(changed_files=["scripts/research/governance/pr_flow.py"])
    reusable["risk_level"] = "high"
    reusable["requires_official_codex_review"] = True
    reusable["review_fragments"]["standards"]["official_scope_impact"] = False
    reusable["review_fragments"]["spec"]["official_scope_impact"] = False
    reusable["review_fragments"]["security"]["security_impact"] = False
    reusable["official_codex_review_reuse"] = {
        "old_head_sha": "0" * 40,
        "current_head_sha": "1" * 40,
        "reason": "only docs wording changed after official review",
        "evidence": ["https://github.com/liuli195/Quant-Trading/pull/7#pullrequestreview-1"],
    }

    assert ai_review_gate.decide_official_review_action(low).action == "not_required"
    assert (
        ai_review_gate.decide_official_review_action(
            high,
            current_head_present=True,
        ).action
        == "current_head_present"
    )
    assert (
        ai_review_gate.decide_official_review_action(high, pending_trigger=True).action
        == "pending"
    )
    assert ai_review_gate.decide_official_review_action(high).action == "trigger_needed"
    assert ai_review_gate.decide_official_review_action(reusable).action == "reused"


def test_pr_body_renders_reused_official_review_evidence() -> None:
    payload = _valid_v3_payload(changed_files=["scripts/research/governance/pr_flow.py"])
    payload["risk_level"] = "high"
    payload["requires_official_codex_review"] = True
    payload["review_fragments"]["standards"]["official_scope_impact"] = False
    payload["review_fragments"]["spec"]["official_scope_impact"] = False
    payload["review_fragments"]["security"]["security_impact"] = False
    payload["official_codex_review_reuse"] = {
        "old_head_sha": "0" * 40,
        "current_head_sha": "1" * 40,
        "reason": "only docs wording changed after official review",
        "evidence": ["https://github.com/liuli195/Quant-Trading/pull/7#pullrequestreview-1"],
    }

    body = ai_review_gate.render_pr_body(payload)

    assert "复用状态: reused" in body
    assert "旧 head: 000000000000" in body
    assert "当前 head: 111111111111" in body
    assert "only docs wording changed after official review" in body


def test_complete_review_requires_each_reviewer_to_end_with_no_new_findings(
    tmp_path: Path,
) -> None:
    complete_review = _complete_review()
    complete_review["iterations"] = [
        {
            "reviewer": "spec-review-subagent",
            "round": 1,
            "new_findings": ["AIR-001"],
        },
        {
            "reviewer": "quality-review-subagent",
            "round": 1,
            "new_findings": [],
            "no_new_findings": True,
        },
    ]
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "complete_review": complete_review,
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "complete_review reviewer spec-review-subagent must end with a no-new-findings iteration"
        in result.errors
    )


def test_complete_review_requires_final_new_findings_to_be_explicitly_empty(
    tmp_path: Path,
) -> None:
    complete_review = _complete_review()
    complete_review["iterations"][0]["new_findings"] = [{"id": "P1"}]
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": complete_review,
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "complete_review reviewer spec-review-subagent final new_findings must be []"
        in result.errors
    )


def test_partial_review_mode_requires_user_authorization(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "review_mode": "partial",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "partial review mode requires user authorization" in result.errors


def test_partial_review_mode_accepts_user_authorization(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "review_mode": "partial",
            "review_mode_authorization": _review_mode_authorization(),
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok, result.errors


def test_partial_review_mode_rejects_placeholder_authorization_values(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "review_mode": "partial",
            "review_mode_authorization": {
                "authorized_by": "<授权人>",
                "reason": "<原因>",
                "evidence": "<授权证据>",
            },
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "partial review mode authorization invalid authorized_by" in result.errors
    assert "partial review mode authorization invalid reason" in result.errors
    assert "partial review mode authorization invalid evidence" in result.errors


def test_partial_review_mode_rejects_embedded_placeholder_authorization_values(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "review_mode": "partial",
            "review_mode_authorization": {
                "authorized_by": "user <template>",
                "reason": "approved because <template>",
                "evidence": "ticket <template>",
            },
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "partial review mode authorization invalid authorized_by" in result.errors
    assert "partial review mode authorization invalid reason" in result.errors
    assert "partial review mode authorization invalid evidence" in result.errors


def test_high_risk_report_requires_official_review_by_default(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "high",
            "requires_official_codex_review": False,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok, result.errors
    assert result.requires_official_codex_review


def test_high_risk_report_can_skip_official_review_with_user_authorization(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "high",
            "requires_official_codex_review": False,
            "skip_official_codex_review": True,
            "official_codex_review_skip_authorization": _official_skip_authorization(),
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok, result.errors
    assert not result.requires_official_codex_review


def test_skip_official_review_requires_user_authorization(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "high",
            "requires_official_codex_review": False,
            "skip_official_codex_review": True,
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "official Codex review skip requires user authorization" in result.errors


def test_skip_official_review_rejects_placeholder_authorization_values(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "high",
            "requires_official_codex_review": False,
            "skip_official_codex_review": True,
            "official_codex_review_skip_authorization": {
                "authorized_by": "<授权人>",
                "reason": "<原因>",
                "evidence": "<授权证据>",
            },
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "official Codex review skip authorization invalid authorized_by"
        in result.errors
    )
    assert "official Codex review skip authorization invalid reason" in result.errors
    assert "official Codex review skip authorization invalid evidence" in result.errors


def test_skip_official_review_rejects_embedded_placeholder_authorization_values(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "high",
            "requires_official_codex_review": False,
            "skip_official_codex_review": True,
            "official_codex_review_skip_authorization": {
                "authorized_by": "user <template>",
                "reason": "approved because <template>",
                "evidence": "ticket <template>",
            },
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "official Codex review skip authorization invalid authorized_by"
        in result.errors
    )
    assert "official Codex review skip authorization invalid reason" in result.errors
    assert "official Codex review skip authorization invalid evidence" in result.errors


def test_report_requires_two_distinct_reviewers_for_cross_review(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["superpowers"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "reviewers must include at least two distinct reviewers for cross-review"
        in result.errors
    )


def test_report_rejects_duplicate_reviewers_for_cross_review(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["superpowers", "superpowers"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "reviewers must include at least two distinct reviewers for cross-review"
        in result.errors
    )


def test_report_rejects_duplicate_reviewers_with_markup(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["alice", "`alice`"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "reviewers must include at least two distinct reviewers for cross-review"
        in result.errors
    )


def test_report_requires_delegated_cross_review_evidence(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "cross_review.delegated_to_subagents must be true" in result.errors


def test_report_requires_superpowers_review_skills(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": {
                "delegated_to_subagents": True,
                "review_skills": ["codex-security"],
                "evidence": "subagents completed",
            },
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "cross_review.review_skills must include superpowers:subagent-driven-development/spec-reviewer-prompt.md and superpowers:subagent-driven-development/code-quality-reviewer-prompt.md"
        in result.errors
    )


def test_report_trims_reviewers_before_distinct_check(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["spec-review-subagent", " spec-review-subagent "],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert (
        "reviewers must include at least two distinct reviewers for cross-review"
        in result.errors
    )


def test_report_rejects_non_string_reviewers(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": [None, "quality-review-subagent"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "reviewers must contain only strings" in result.errors


def test_report_rejects_placeholder_reviewers(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["<规格评审子agent>", "<代码质量评审子agent>"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "reviewers must not contain placeholder reviewer names" in result.errors


def test_report_rejects_implementer_or_controller_reviewers(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["主会话", "实现者"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
            "changed_files": ["docs/guides/example.md"],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "reviewers must not contain placeholder reviewer names" in result.errors


def test_open_p1_blocks_progress(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
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
            "schema_version": 2,
            "tool": "claude",
            "reviewers": ["pr-review-toolkit", "security-guidance"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "cross_review": _cross_review(),
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


def test_p2_requires_handling(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    payload = _valid_complete_payload()
    payload["findings"] = [
        {
            "id": "AIR-004",
            "severity": "P2",
            "title": "说明不够完整",
            "path": "docs/guides/example.md",
            "status": "accepted",
            "defer_reason": "后续文档批次统一补充",
            "risk_acceptance": "不影响代码执行",
        }
    ]
    _write_report(report, payload)

    result = validate_report_file(report)

    assert not result.ok
    assert "P2 finding AIR-004 accepted without handling" in result.errors


def test_high_risk_scope_mentions_changed_file(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review("superpowers", "codex-security"),
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


def test_high_risk_scope_excludes_generated_strategy_artifacts(
    tmp_path: Path,
) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 2,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "security_review": _security_review(),
            "cross_review": _cross_review(),
            "complete_review": _complete_review("superpowers", "codex-security"),
            "changed_files": [
                "strategies/etf_factor_rotation/backtest_runs/run/api_export.json",
                "strategies/etf_factor_rotation/etf_factor_rotation.py",
                "scripts/research/platform/datasets.py",
                ".github/pull_request_template.md",
            ],
            "findings": [],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok, result.errors
    assert "backtest_runs/run/api_export.json" not in result.review_scope
    assert (
        "strategies/etf_factor_rotation/etf_factor_rotation.py" in result.review_scope
    )
    assert "scripts/research/platform/datasets.py" in result.review_scope
    assert ".github/pull_request_template.md" in result.review_scope


def test_markdown_summary_lists_risk_and_findings() -> None:
    cross_review = _cross_review()
    cross_review["evidence"] = "line one\n## injected heading"
    payload = {
        "schema_version": 2,
        "tool": "codex",
        "reviewers": ["superpowers", "codex-security"],
        "risk_level": "low",
        "requires_official_codex_review": False,
        "security_review": _security_review(),
        "cross_review": cross_review,
        "complete_review": _complete_review("superpowers", "codex-security"),
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
    assert "## 子 agent 交叉评审" in text
    assert "superpowers:subagent-driven-development/spec-reviewer-prompt.md" in text
    assert (
        "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md"
        in text
    )
    assert "line one ## injected heading" in text


def test_report_file_accepts_utf8_bom(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    payload = {
        "schema_version": 2,
        "tool": "codex",
        "reviewers": ["superpowers", "codex-security"],
        "risk_level": "low",
        "requires_official_codex_review": False,
        "security_review": _security_review(),
        "cross_review": _cross_review(),
        "complete_review": _complete_review("superpowers", "codex-security"),
        "changed_files": ["docs/guides/example.md"],
        "findings": [],
        "checks": {"pytest": "pass"},
    }
    report.write_bytes(
        ("\ufeff" + json.dumps(payload, ensure_ascii=False)).encode("utf-8")
    )

    result = validate_report_file(report)

    assert result.ok, result.errors
