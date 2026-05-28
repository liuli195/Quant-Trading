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
        fail_body_view: bool = False,
        api_review_commit: str | None = None,
        api_review_body: str = "Codex Review: Didn't find any major issues.",
        api_review_comments: list[dict[str, object]] | None = None,
        api_issue_comments: list[dict[str, object]] | None = None,
        api_review_threads: list[dict[str, object]] | None = None,
        api_reactions: list[dict[str, object]] | None = None,
        pr_head_sha_after_wait: str | None = None,
        fail_api_paths: set[str] | None = None,
        fail_graphql: bool = False,
        trigger_comment_time: str = "2026-05-28T09:00:00Z",
    ) -> None:
        self.existing_pr = existing_pr
        self.pr_body = pr_body
        self.labels = labels or []
        self.fail_body_view = fail_body_view
        self.api_review_commit = api_review_commit or "1" * 40
        self.api_review_body = api_review_body
        self.api_review_comments = api_review_comments or []
        self.api_issue_comments = api_issue_comments or []
        self.api_review_threads = api_review_threads or []
        self.api_reactions = api_reactions or []
        self.pr_head_sha_after_wait = pr_head_sha_after_wait
        self.fail_api_paths = fail_api_paths or set()
        self.fail_graphql = fail_graphql
        self.trigger_comment_time = trigger_comment_time
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
            if self.fail_body_view:
                return pr_flow.CommandResult(1, "", "body read failed")
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
            body = body_file.read_text(encoding="utf-8")
            self.comments.append(body)
            self.api_issue_comments.append(
                {
                    "id": 1,
                    "user": {"login": "test-user"},
                    "body": body,
                    "created_at": self.trigger_comment_time,
                    "updated_at": self.trigger_comment_time,
                    "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-1",
                }
            )
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "api", "graphql"] and self.fail_graphql:
            return pr_flow.CommandResult(1, "", "GraphQL unavailable")
        if _gh_api_path(command) in self.fail_api_paths:
            return pr_flow.CommandResult(1, "", "GitHub API unavailable")
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/pulls/7/reviews?per_page=100":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(
                    command,
                    [
                        {
                            "id": 1,
                            "user": {"login": "chatgpt-codex-connector"},
                            "state": "COMMENTED",
                            "commit_id": self.api_review_commit,
                            "submitted_at": "2026-05-28T10:00:00Z",
                            "body": self.api_review_body,
                        }
                    ],
                ),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/pulls/7/comments?per_page=100":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(command, self.api_review_comments),
                "",
            )
        if command == ["gh", "pr", "view", "--json", "headRefOid"]:
            if not self.existing_pr:
                return pr_flow.CommandResult(1, "", "no pull request")
            return pr_flow.CommandResult(
                0,
                json.dumps({"headRefOid": self.pr_head_sha_after_wait or "1" * 40}),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/issues/7/comments?per_page=100":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(command, self.api_issue_comments),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/issues/comments/1/reactions?per_page=100":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(command, self.api_reactions),
                "",
            )
        if command[:3] == ["gh", "api", "graphql"]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": self.api_review_threads,
                                    }
                                }
                            }
                        }
                    }
                ),
                "",
            )
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


def _gh_api_path(command: list[str]) -> str:
    if len(command) >= 3 and command[0] == "gh" and command[1] == "api":
        return command[-1]
    return ""


def _gh_api_json(command: list[str], payload: object) -> str:
    return json.dumps([payload]) if "--slurp" in command else json.dumps(payload)


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


class DuplicateRequiredChecksRunner:
    def __init__(self, checks: list[dict[str, str]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.checks = checks or [
            {
                "name": "pr-review-evidence",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "Research Governance",
                "link": "https://github.com/o/r/actions/runs/20/job/200",
            },
            {
                "name": "pr-review-evidence",
                "state": "FAILURE",
                "bucket": "fail",
                "workflow": "Research Governance",
                "link": "https://github.com/o/r/actions/runs/10/job/100",
            },
            {
                "name": "Codex Review Monitor",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "",
                "link": "https://github.com/o/r/pull/7#issuecomment-1",
            },
        ]

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
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
            return pr_flow.CommandResult(1, "", "")
        if command == [
            "gh",
            "pr",
            "checks",
            "7",
            "--required",
            "--json",
            pr_flow.CHECKS_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(self.checks),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")


class UnavailableRequiredChecksRunner:
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command[:4] == ["gh", "pr", "checks", "7"]:
            return pr_flow.CommandResult(1, "", "authentication required")
        raise AssertionError(f"unexpected command: {command}")


class PendingRequiredChecksRunner:
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
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
            return pr_flow.CommandResult(1, "", "")
        if command == [
            "gh",
            "pr",
            "checks",
            "7",
            "--required",
            "--json",
            pr_flow.CHECKS_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "name": "governance",
                            "state": "PENDING",
                            "bucket": "pending",
                            "workflow": "Research Governance",
                            "link": "https://github.com/o/r/actions/runs/20/job/200",
                        }
                    ]
                ),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")


class SlurpedPagesRunner:
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/o/r/issues/1/comments?per_page=100",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps([[{"id": 1}], [{"id": 2}]]),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")


class PaginatedThreadsRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command[:3] != ["gh", "api", "graphql"]:
            raise AssertionError(f"unexpected command: {command}")
        self.calls += 1
        has_next = self.calls == 1
        end_cursor = "cursor-1" if has_next else None
        node = {
            "isResolved": False,
            "isOutdated": False,
            "comments": {
                "nodes": [
                    {
                        "body": f"P1 Badge page {self.calls}",
                        "author": {"login": "chatgpt-codex-connector"},
                    }
                ]
            },
        }
        return pr_flow.CommandResult(
            0,
            json.dumps(
                {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": [node],
                                    "pageInfo": {
                                        "hasNextPage": has_next,
                                        "endCursor": end_cursor,
                                    },
                                }
                            }
                        }
                    }
                }
            ),
            "",
        )


def test_wait_uses_latest_duplicate_required_check_result(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DuplicateRequiredChecksRunner()

    code = pr_flow.wait(repo_root=tmp_path, pr="7", runner=runner)

    assert code == 0
    assert "required checks passed" in capsys.readouterr().out


def test_wait_blocks_latest_duplicate_required_check_failure(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DuplicateRequiredChecksRunner(
        [
            {
                "name": "pr-review-evidence",
                "state": "FAILURE",
                "bucket": "fail",
                "workflow": "Research Governance",
                "link": "https://github.com/o/r/actions/runs/20/job/200",
            },
            {
                "name": "pr-review-evidence",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "Research Governance",
                "link": "https://github.com/o/r/actions/runs/10/job/100",
            },
        ]
    )

    code = pr_flow.wait(repo_root=tmp_path, pr="7", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "Research Governance / pr-review-evidence" in capsys.readouterr().err


def test_wait_uses_latest_duplicate_non_actions_required_check_timestamp(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DuplicateRequiredChecksRunner(
        [
            {
                "name": "external-policy",
                "state": "FAILURE",
                "bucket": "fail",
                "workflow": "External Policy",
                "link": "https://checks.example/policy/old",
                "completedAt": "2026-05-28T09:00:00Z",
            },
            {
                "name": "external-policy",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "External Policy",
                "link": "https://checks.example/policy/new",
                "completedAt": "2026-05-28T10:00:00Z",
            },
        ]
    )

    code = pr_flow.wait(repo_root=tmp_path, pr="7", runner=runner)

    assert code == 0
    assert "required checks passed" in capsys.readouterr().out


def test_wait_reports_exception_when_required_checks_unavailable(
    tmp_path: Path,
    capsys,
) -> None:
    code = pr_flow.wait(
        repo_root=tmp_path,
        pr="7",
        runner=UnavailableRequiredChecksRunner(),
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in capsys.readouterr().err


def test_wait_reports_exception_when_required_checks_are_pending(
    tmp_path: Path,
    capsys,
) -> None:
    code = pr_flow.wait(
        repo_root=tmp_path,
        pr="7",
        runner=PendingRequiredChecksRunner(),
    )

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in captured.err
    assert "Research Governance / governance" in captured.err


def test_gh_api_list_flattens_slurped_paginated_pages(tmp_path: Path) -> None:
    items = pr_flow._gh_api_list(
        tmp_path,
        SlurpedPagesRunner(),
        "repos/o/r/issues/1/comments?per_page=100",
    )

    assert [item["id"] for item in items] == [1, 2]


def test_current_pr_review_threads_reads_all_graphql_pages(tmp_path: Path) -> None:
    runner = PaginatedThreadsRunner()

    threads = pr_flow._current_pr_review_threads(
        root=tmp_path,
        runner=runner,
        repo="o/r",
        pr_number="1",
    )

    assert runner.calls == 2
    assert len(threads) == 2


def test_select_local_checks_for_changed_files() -> None:
    cases = [
        (["docs/guides/a.md"], ["governance-full"]),
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


def test_prepare_records_full_governance_gate_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
    )
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 0
    payload = json.loads(
        (tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8")
    )
    gate_evidence = payload["checks"]["governance gate"]
    assert ".githooks/run-python.sh -m scripts.research.governance gate" in gate_evidence
    body = (tmp_path / ".local/ai-review/pr-body.md").read_text(encoding="utf-8")
    assert gate_evidence in body


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


def test_sync_replaces_existing_pr_block_with_windows_path_evidence(
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/rules.py"],
    )
    report_path = tmp_path / ".local/ai-review/latest.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["checks"]["governance gate"] = (
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
        ".\\.githooks\\run-python.ps1 -m scripts.research.governance gate; passed"
    )
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
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
    edited = runner.edited_bodies[0]
    assert "old managed content" not in edited
    assert ".\\.githooks\\run-python.ps1" in edited


def test_sync_stops_when_existing_pr_body_cannot_be_read(
    tmp_path: Path,
) -> None:
    _write_valid_report(tmp_path)
    runner = FakeRunner(existing_pr=True, fail_body_view=True)

    code = pr_flow.sync(repo_root=tmp_path, title="文档更新", runner=runner)

    assert code == 1
    assert not runner.edited_bodies


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


def test_sync_refreshes_stale_codex_review_scope_before_commenting(
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    scope_path = tmp_path / ".local/ai-review/codex-review-scope.md"
    scope_path.write_text(
        "## Review Scope\n\n### 高风险文件\n- `docs/old.md`\n",
        encoding="utf-8",
    )
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="治理改造", runner=runner)

    assert code == 0
    assert "docs/old.md" not in runner.comments[0]
    assert "scripts/research/governance/pr_flow.py" in runner.comments[0]
    assert "docs/old.md" not in scope_path.read_text(encoding="utf-8")


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


def test_ready_stops_with_dispatch_required_when_review_evidence_missing(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert "DISPATCH_REQUIRED" in capsys.readouterr().err
    assert not any(call[:3] == ["gh", "pr", "edit"] for call in runner.calls)


def test_ready_stops_with_dispatch_required_when_review_evidence_incomplete(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(tmp_path)
    latest = tmp_path / ".local/ai-review/latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload.pop("security_review")
    latest.write_text(json.dumps(payload), encoding="utf-8")
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert "DISPATCH_REQUIRED" in capsys.readouterr().err
    assert not any(call[:3] == ["gh", "pr", "edit"] for call in runner.calls)


def test_ready_reports_exception_when_prepare_fails_for_non_evidence_reason(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(tmp_path)
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 2)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in capsys.readouterr().err


def test_ready_reports_exception_when_sync_fails(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(tmp_path)
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(pr_flow, "sync", lambda **_kwargs: 2)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in capsys.readouterr().err


def test_ready_waits_after_requesting_required_codex_review(
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

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理改造",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == 0
    assert any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert "pullrequestreview-1" in runner.edited_bodies[-1]
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


def test_ready_auto_records_current_head_codex_completion_comment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True, api_review_commit="2" * 40)
    runner.api_issue_comments.append(
        {
            "id": 99,
            "user": {"login": "chatgpt-codex-connector"},
            "body": "Codex Review: Didn't find any major issues.",
            "created_at": "2026-05-28T10:00:00Z",
            "updated_at": "2026-05-28T10:00:00Z",
            "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-99",
        }
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == 0
    payload = json.loads((tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8"))
    assert payload["official_codex_review"]["evidence"][0].endswith("#issuecomment-99")
    assert "## Codex Code Review" in runner.edited_bodies[-1]


def test_ready_uses_existing_trigger_result_without_retriggering(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_commit="2" * 40,
        trigger_comment_time="2026-05-28T11:00:00Z",
        api_issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": f"@codex review https://github.com/liuli195/Quant-Trading/pull/7 {'1' * 40}",
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-1",
            },
            {
                "id": 99,
                "user": {"login": "chatgpt-codex-connector"},
                "body": "Codex Review: Didn't find any major issues.",
                "created_at": "2026-05-28T10:00:00Z",
                "updated_at": "2026-05-28T10:00:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-99",
            },
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == 0
    assert not any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    payload = json.loads((tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8"))
    assert payload["official_codex_review"]["evidence"][0].endswith("#issuecomment-99")


def test_ready_reports_exception_when_review_api_unavailable(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": f"@codex review https://github.com/liuli195/Quant-Trading/pull/7 {'1' * 40}",
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        fail_api_paths={"repos/liuli195/Quant-Trading/pulls/7/reviews?per_page=100"},
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in capsys.readouterr().err
    payload = json.loads((tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8"))
    assert "official_codex_review" not in payload


def test_ready_reports_exception_when_review_threads_unavailable(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": f"@codex review https://github.com/liuli195/Quant-Trading/pull/7 {'1' * 40}",
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        fail_graphql=True,
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in capsys.readouterr().err
    payload = json.loads((tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8"))
    assert "official_codex_review" not in payload


def test_ready_stops_when_codex_reports_blocking_finding(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True, api_review_commit="2" * 40)
    runner.api_issue_comments.append(
        {
            "id": 100,
            "user": {"login": "chatgpt-codex-connector"},
            "body": "P1 Badge: required check can be bypassed.",
            "created_at": "2026-05-28T10:00:00Z",
            "updated_at": "2026-05-28T10:00:00Z",
            "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-100",
        }
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "REPLY_OR_FIX_REQUIRED" in capsys.readouterr().err


def test_ready_does_not_let_completion_comment_supersede_blocking_finding(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_commit="2" * 40,
        api_issue_comments=[
            {
                "id": 100,
                "user": {"login": "chatgpt-codex-connector"},
                "body": f"P1 Badge: required check can be bypassed on {'1' * 40}.",
                "created_at": "2026-05-28T09:30:00Z",
                "updated_at": "2026-05-28T09:30:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-100",
            },
            {
                "id": 101,
                "user": {"login": "chatgpt-codex-connector"},
                "body": "Codex Review: Didn't find any major issues.",
                "created_at": "2026-05-28T10:00:00Z",
                "updated_at": "2026-05-28T10:00:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-101",
            },
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    stderr = capsys.readouterr().err
    assert "REPLY_OR_FIX_REQUIRED" in stderr
    assert "P1 Badge" in stderr


def test_ready_stops_when_blocking_finding_appears_after_valid_evidence(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
        official_evidence=True,
    )
    runner = FakeRunner(existing_pr=True)
    runner.api_issue_comments.append(
        {
            "id": 101,
            "user": {"login": "chatgpt-codex-connector"},
            "body": f"P1 Badge: required check can be bypassed on {'1' * 40}.",
            "created_at": "2026-05-28T10:00:00Z",
            "updated_at": "2026-05-28T10:00:00Z",
            "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-101",
        }
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "REPLY_OR_FIX_REQUIRED" in capsys.readouterr().err


def test_ready_stops_when_blocking_finding_appears_during_codex_wait(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True, api_review_commit="2" * 40)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    def add_blocking_comment(_seconds: float) -> None:
        runner.api_issue_comments.append(
            {
                "id": 102,
                "user": {"login": "chatgpt-codex-connector"},
                "body": "P1 Badge: required check can be bypassed.",
                "created_at": "2026-05-28T10:00:00Z",
                "updated_at": "2026-05-28T10:00:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-102",
            }
        )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0.01,
        codex_review_poll_seconds=0.01,
        sleeper=add_blocking_comment,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "REPLY_OR_FIX_REQUIRED" in capsys.readouterr().err


def test_current_head_codex_review_evidence_requires_current_trigger(
    tmp_path: Path,
) -> None:
    runner = FakeRunner(existing_pr=True)

    evidence = pr_flow._current_head_codex_review_evidence(
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha="1" * 40,
        root=tmp_path,
        runner=runner,
    )

    assert evidence is None


def test_existing_codex_review_evidence_requires_current_trigger(
    tmp_path: Path,
) -> None:
    _write_valid_report(tmp_path, official_evidence=True)
    payload = json.loads(
        (tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8")
    )
    runner = FakeRunner(existing_pr=True)

    valid = pr_flow._official_codex_review_evidence_valid_for_current_pr(
        payload,
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha="1" * 40,
        root=tmp_path,
        runner=runner,
    )

    assert not valid


def test_completion_reaction_must_be_after_trigger_comment_update(
    tmp_path: Path,
) -> None:
    _write_valid_report(tmp_path, official_evidence=True)
    latest = tmp_path / ".local/ai-review/latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload["official_codex_review"]["evidence"][0] = (
        "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-1"
    )
    runner = FakeRunner(
        existing_pr=True,
        api_issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": f"@codex review https://github.com/liuli195/Quant-Trading/pull/7 {'1' * 40}",
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T10:00:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-1",
            }
        ],
        api_reactions=[
            {
                "content": "+1",
                "user": {"login": "chatgpt-codex-connector"},
                "created_at": "2026-05-28T09:30:00Z",
            }
        ],
    )

    valid = pr_flow._official_codex_review_evidence_valid_for_current_pr(
        payload,
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha="1" * 40,
        root=tmp_path,
        runner=runner,
    )

    assert not valid


def test_ready_stops_when_codex_review_body_has_blocking_finding(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
        official_evidence=True,
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_body="P1 Badge: required check can be bypassed.",
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "REPLY_OR_FIX_REQUIRED" in capsys.readouterr().err


def test_ready_stops_when_codex_review_context_is_invalid(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
        official_evidence=True,
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_body="I couldn't access the PR diff.",
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    stderr = capsys.readouterr().err
    assert "REPLY_OR_FIX_REQUIRED" in stderr
    assert "context invalid" in stderr


def test_ready_stops_when_completion_comment_context_is_invalid(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_commit="2" * 40,
        api_issue_comments=[
            {
                "id": 101,
                "user": {"login": "chatgpt-codex-connector"},
                "body": "Codex Review: Didn't find any major issues. I couldn't access the PR diff.",
                "created_at": "2026-05-28T10:00:00Z",
                "updated_at": "2026-05-28T10:00:00Z",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-101",
            },
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    stderr = capsys.readouterr().err
    assert "REPLY_OR_FIX_REQUIRED" in stderr
    assert "context invalid" in stderr


def test_ready_stops_when_codex_review_thread_is_unresolved(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_threads=[
            {
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "body": "P1 Badge: required check can be bypassed.",
                            "author": {"login": "chatgpt-codex-connector"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "unresolved" in capsys.readouterr().err


def test_ready_stops_on_unresolved_codex_thread_even_when_official_review_not_required(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="low",
        requires_official=False,
        changed_files=["docs/guides/example.md"],
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_threads=[
            {
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "body": "P1 Badge: required check can be bypassed.",
                            "author": {"login": "chatgpt-codex-connector"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "unresolved" in capsys.readouterr().err


def test_ready_ignores_resolved_codex_review_thread(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
        official_evidence=True,
    )
    runner = FakeRunner(
        existing_pr=True,
        api_review_comments=[
            {
                "pull_request_review_id": 1,
                "user": {"login": "chatgpt-codex-connector"},
                "commit_id": "1" * 40,
                "body": "P1 Badge: fixed by follow-up.",
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#discussion_r1",
            }
        ],
        api_review_threads=[
            {
                "isResolved": True,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "body": "P1 Badge: fixed by follow-up.",
                            "author": {"login": "chatgpt-codex-connector"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == 0


def test_ready_stops_when_pr_head_changes_during_codex_wait(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True, pr_head_sha_after_wait="2" * 40)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "head changed" in capsys.readouterr().err


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
    runner = FakeRunner(
        existing_pr=True,
        api_issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": f"@codex review https://github.com/liuli195/Quant-Trading/pull/7 {'1' * 40}",
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
    )
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


def test_ready_retriggers_codex_review_when_evidence_is_for_old_head(
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
    runner = FakeRunner(existing_pr=True, api_review_commit="2" * 40)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="governance update",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.CODEX_REVIEW_PENDING_EXIT_CODE
    assert any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert not any(call[:4] == ["gh", "pr", "checks", "7"] for call in runner.calls)
