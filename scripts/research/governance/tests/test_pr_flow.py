from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance import pr_flow


def _write_valid_report(
    root: Path,
    *,
    risk_level: str = "low",
    requires_official: bool = False,
    changed_files: list[str] | None = None,
    official_evidence: bool = False,
) -> None:
    local = root / ".local/ai-review"
    local.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "tool": "codex",
        "reviewers": ["spec-review-subagent", "quality-review-subagent"],
        "risk_level": risk_level,
        "requires_official_codex_review": requires_official,
        "security_review": {
            "tool": "codex-security",
            "evidence": "codex-security local security review completed",
        },
        "cross_review": {
            "delegated_to_subagents": True,
            "review_skills": [
                "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
                "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
            ],
            "evidence": "spec and quality reviewers completed",
        },
        "complete_review": {
            "evidence": "reviewers continued until no new findings",
            "iterations": [
                {
                    "reviewer": "spec-review-subagent",
                    "round": 1,
                    "new_findings": [],
                    "no_new_findings": True,
                },
                {
                    "reviewer": "quality-review-subagent",
                    "round": 1,
                    "new_findings": [],
                    "no_new_findings": True,
                },
            ],
        },
        "changed_files": changed_files or ["docs/guides/example.md"],
        "findings": [],
        "checks": {"pytest": "pass"},
    }
    if official_evidence:
        payload["official_codex_review"] = {
            "reviewer": "Codex",
            "trigger": "@codex review",
            "conclusion": "通过",
            "blocking_issues": "无",
            "evidence": [
                "https://github.com/liuli195/Quant-Trading/pull/7#pullrequestreview-1",
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate",
            ],
        }
    (local / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (local / "pr-body.md").write_text(
        "## AI Review 风险分级\n\n"
        "- 风险等级: low\n"
        "- 是否需要官方 Codex Review: 否\n"
        "- 本地 AI review 模式: complete\n"
        "- 本地 AI review: `.local/ai-review/latest.md`\n\n"
        "## P2 保留项\n\n- 无\n",
        encoding="utf-8",
    )
    (local / "codex-review-scope.md").write_text(
        "## Review Scope\n\n### 高风险文件\n- `scripts/research/governance/rules.py`\n",
        encoding="utf-8",
    )


class FakeRunner:
    def __init__(
        self,
        *,
        existing_pr: bool,
        pr_body: str = "",
        labels: list[str] | None = None,
    ) -> None:
        self.existing_pr = existing_pr
        self.pr_body = pr_body
        self.labels = labels or []
        self.calls: list[list[str]] = []
        self.edited_bodies: list[str] = []
        self.created_bodies: list[str] = []
        self.comments: list[str] = []

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
        if command == ["git", "branch", "--show-current"]:
            return pr_flow.CommandResult(0, "feature/pr-flow\n", "")
        if command == ["git", "rev-parse", "HEAD"]:
            return pr_flow.CommandResult(0, "1" * 40 + "\n", "")
        if command == ["gh", "pr", "view", "--json", "number,url,state,isDraft"]:
            if not self.existing_pr:
                return pr_flow.CommandResult(1, "", "no pull request")
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "number": 7,
                        "url": "https://github.com/liuli195/Quant-Trading/pull/7",
                        "state": "OPEN",
                        "isDraft": True,
                    }
                ),
                "",
            )
        if command == ["gh", "pr", "view", "--json", "body"]:
            return pr_flow.CommandResult(0, json.dumps({"body": self.pr_body}), "")
        if command == ["gh", "pr", "view", "--json", "labels"]:
            return pr_flow.CommandResult(
                0,
                json.dumps({"labels": [{"name": label} for label in self.labels]}),
                "",
            )
        if command[:3] == ["gh", "pr", "create"]:
            body_file = Path(command[command.index("--body-file") + 1])
            self.created_bodies.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(
                0,
                "https://github.com/liuli195/Quant-Trading/pull/8\n",
                "",
            )
        if command[:3] == ["gh", "pr", "edit"] and "--body-file" in command:
            body_file = Path(command[command.index("--body-file") + 1])
            self.edited_bodies.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "pr", "edit"] and "--add-label" in command:
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "pr", "edit"] and "--remove-label" in command:
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "pr", "comment"]:
            body_file = Path(command[command.index("--body-file") + 1])
            self.comments.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(0, "", "")
        if command == [
            "gh",
            "pr",
            "checks",
            "7",
            "--required",
            "--watch",
            "--interval",
            "10",
        ]:
            return pr_flow.CommandResult(0, "checks passed\n", "")
        raise AssertionError(f"unexpected command: {command}")


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
        return pr_flow.CommandResult(0, "", "")


def test_select_local_checks_for_changed_files() -> None:
    cases = [
        (["docs/guides/a.md"], ["governance-fast", "pathref"]),
        (
            ["scripts/research/governance/rules.py"],
            [
                "ruff-governance",
                "bandit-governance",
                "mypy-governance",
                "pytest-governance",
                "governance-full",
            ],
        ),
        (
            ["strategies/demo/demo.py"],
            ["py-compile-strategy", "pytest-strategy-if-present", "governance-full"],
        ),
        (["requirements.txt"], ["pip-audit", "governance-full"]),
        (
            ["requirements.txt", "scripts/research/governance/pr_flow.py"],
            [
                "pip-audit",
                "ruff-governance",
                "bandit-governance",
                "mypy-governance",
                "pytest-governance",
                "governance-full",
            ],
        ),
        (
            ["requirements-dev.txt", "strategies/demo/demo.py"],
            [
                "pip-audit",
                "py-compile-strategy",
                "pytest-strategy-if-present",
                "governance-full",
            ],
        ),
    ]

    for changed_files, expected in cases:
        assert pr_flow.select_local_checks(changed_files) == expected


def test_prepare_selects_checks_from_latest_report_when_diff_is_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 0
    modules = [
        call[call.index("-m") + 1]
        for call in runner.calls
        if "-m" in call
    ]
    assert "ruff" in modules
    assert "bandit" in modules
    assert "mypy" in modules
    assert "pytest" in modules
    mypy_call = next(call for call in runner.calls if "mypy" in call)
    assert "--explicit-package-bases" in mypy_call
    assert "--follow-imports=skip" in mypy_call
    assert "--ignore-missing-imports" in mypy_call
    assert "scripts.research.governance" in modules
    bandit_call = next(call for call in runner.calls if "bandit" in call)
    assert "-x" in bandit_call
    assert "scripts/research/governance/tests" in bandit_call
    assert "-s" in bandit_call
    assert "B310,B404,B603,B607" in bandit_call
    assert not any(
        call[call.index("-m") + 1] == "scripts.research.governance"
        and "--fast" in call
        for call in runner.calls
        if "-m" in call
    )


def test_prepare_uses_report_files_for_strategy_checks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["strategies/demo/demo.py"],
    )
    (tmp_path / "strategies/demo/tests").mkdir(parents=True)
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 0
    assert any(
        "-m" in call
        and call[call.index("-m") + 1] == "py_compile"
        and "strategies/demo/demo.py" in call
        for call in runner.calls
    )
    assert any("strategies/demo/tests" in call for call in runner.calls)


def test_sync_updates_existing_pr_block_label_and_codex_comment(
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/rules.py"],
    )
    existing_body = "\n".join(
        [
            "Intro",
            "",
            "<!-- pr-flow:start -->",
            "old managed content",
            "<!-- pr-flow:end -->",
            "",
            "Tail",
        ]
    )
    runner = FakeRunner(existing_pr=True, pr_body=existing_body)

    code = pr_flow.sync(repo_root=tmp_path, title="PR 流程自动化", runner=runner)

    assert code == 0
    assert ["gh", "pr", "view", "--json", "number,url,state,isDraft"] in runner.calls
    assert any(
        call[:3] == ["gh", "pr", "edit"] and "--body-file" in call
        for call in runner.calls
    )
    assert ["gh", "pr", "edit", "7", "--add-label", "ai-risk-review"] in runner.calls
    assert any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert len(runner.edited_bodies) == 1
    edited = runner.edited_bodies[0]
    assert "Intro" in edited
    assert "Tail" in edited
    assert "old managed content" not in edited
    assert "<!-- pr-flow:start -->" in edited
    assert "## AI Review 风险分级" in edited
    assert runner.comments[0].startswith("@codex review\n\n")
    assert "scripts/research/governance/rules.py" in runner.comments[0]


def test_sync_generates_missing_codex_review_scope_from_validation(
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/rules.py"],
    )
    scope_path = tmp_path / ".local/ai-review/codex-review-scope.md"
    scope_path.unlink()
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="治理改造", runner=runner)

    assert code == 0
    assert scope_path.is_file()
    assert any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert "scripts/research/governance/rules.py" in runner.comments[0]


def test_sync_creates_missing_draft_pr_without_label_or_codex_comment(
    tmp_path: Path,
) -> None:
    _write_valid_report(tmp_path)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/pull_request_template.md").write_text(
        "## 改动目标\n\n-\n\n"
        "<!-- pr-flow:start -->\nold\n<!-- pr-flow:end -->\n\n"
        "## 人工补充\n\n- 额外证据链接：\n- waiver：\n",
        encoding="utf-8",
    )
    runner = FakeRunner(existing_pr=False)

    code = pr_flow.sync(repo_root=tmp_path, title="文档更新", runner=runner)

    assert code == 0
    create_calls = [
        call for call in runner.calls if call[:3] == ["gh", "pr", "create"]
    ]
    assert len(create_calls) == 1
    create_call = create_calls[0]
    assert "--draft" in create_call
    assert ["--head", "feature/pr-flow"] == create_call[
        create_call.index("--head") : create_call.index("--head") + 2
    ]
    assert "## 人工补充" in runner.created_bodies[0]
    assert "old" not in runner.created_bodies[0]
    assert "## AI Review 风险分级" in runner.created_bodies[0]
    assert not any("--add-label" in call for call in runner.calls)
    assert not runner.comments


def test_sync_removes_stale_ai_risk_review_label_for_low_risk(
    tmp_path: Path,
) -> None:
    _write_valid_report(tmp_path, risk_level="low", requires_official=False)
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(
        repo_root=tmp_path,
        title="低风险文档更新",
        runner=runner,
        existing_labels=["ai-risk-review"],
    )

    assert code == 0
    assert ["gh", "pr", "edit", "7", "--remove-label", "ai-risk-review"] in runner.calls


def test_sync_rerenders_pr_body_from_latest_report(
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        changed_files=["docs/guides/current.md"],
        risk_level="low",
        requires_official=False,
    )
    local = tmp_path / ".local/ai-review"
    (local / "pr-body.md").write_text("STALE BODY", encoding="utf-8")
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="文档更新", runner=runner)

    assert code == 0
    assert "STALE BODY" not in runner.edited_bodies[0]
    assert "## AI Review 风险分级" in runner.edited_bodies[0]


def test_ready_stops_after_requesting_required_codex_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/rules.py"],
    )
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(repo_root=tmp_path, title="治理改造", runner=runner)

    assert code == pr_flow.CODEX_REVIEW_PENDING_EXIT_CODE
    assert any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert not any(call[:4] == ["gh", "pr", "checks", "7"] for call in runner.calls)


def test_ready_does_not_retrigger_codex_review_when_evidence_exists(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/rules.py"],
        official_evidence=True,
    )
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(repo_root=tmp_path, title="治理改造", runner=runner)

    assert code == 0
    assert not any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert [
        "gh",
        "pr",
        "checks",
        "7",
        "--required",
        "--watch",
        "--interval",
        "10",
    ] in runner.calls
