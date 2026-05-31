from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research.governance import ai_review_gate, pr_flow, pr_review_evidence


class FakeIntentRunner:
    def __init__(
        self,
        *,
        staged_diff: str = "diff --git a/a.txt b/a.txt\n+hello\n",
        staged_files: str = "a.txt\n",
        issue_states: dict[int, str] | None = None,
        issue_bodies: dict[int, str] | None = None,
        branch: str = "feature/intent",
        head_sha: str = "1" * 40,
        branch_commits: tuple[str, ...] = (),
    ) -> None:
        self.calls: list[list[str]] = []
        self.staged_diff = staged_diff
        self.staged_files = staged_files
        self.issue_states = issue_states or {}
        self.issue_bodies = issue_bodies or {}
        self.branch = branch
        self.head_sha = head_sha
        self.branch_commits = branch_commits
        self.edited_issues: dict[int, str] = {}
        self.issue_comments: dict[int, list[str]] = {}

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
        if command == ["git", "branch", "--show-current"]:
            return pr_flow.CommandResult(0, f"{self.branch}\n", "")
        if command == ["git", "rev-parse", "HEAD"]:
            return pr_flow.CommandResult(0, f"{self.head_sha}\n", "")
        if command == ["git", "rev-list", "--reverse", "origin/main..HEAD"]:
            return pr_flow.CommandResult(0, "\n".join(self.branch_commits) + "\n", "")
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "--cached",
        ]:
            return pr_flow.CommandResult(0, self.staged_diff, "")
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-only",
            "--cached",
        ]:
            return pr_flow.CommandResult(0, self.staged_files, "")
        if command == ["git", "config", "user.email"]:
            return pr_flow.CommandResult(0, "agent@example.com\n", "")
        if command[:3] == ["gh", "issue", "view"]:
            number = int(command[3])
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "state": self.issue_states.get(number, "OPEN"),
                        "title": f"Issue {number}",
                        "body": self.issue_bodies.get(number, ""),
                    }
                ),
                "",
            )
        if command[:3] == ["gh", "issue", "edit"] and "--body-file" in command:
            number = int(command[3])
            body_file = Path(command[command.index("--body-file") + 1])
            self.edited_issues[number] = body_file.read_text(encoding="utf-8")
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "issue", "comment"] and "--body-file" in command:
            number = int(command[3])
            body_file = Path(command[command.index("--body-file") + 1])
            self.issue_comments.setdefault(number, []).append(
                body_file.read_text(encoding="utf-8")
            )
            return pr_flow.CommandResult(0, "", "")
        return pr_flow.CommandResult(1, "", f"unexpected command: {command}")


def test_intent_stage_records_multi_issue_pending_intent(tmp_path: Path) -> None:
    runner = FakeIntentRunner()

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        issue_bindings=("55:reference", "56:closes"),
        now="2026-06-01T08:00:00Z",
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    pending = json.loads(
        (tmp_path / ".local/pr-flow/pending-intent.json").read_text(encoding="utf-8")
    )
    assert pending["branch"] == "feature/intent"
    assert pending["issue_policy"] == "issues"
    assert pending["issues"] == [
        {"number": 55, "role": "reference", "title": "Issue 55"},
        {"number": 56, "role": "closes", "title": "Issue 56"},
    ]
    assert pending["created_by"] == "agent@example.com"
    assert pending["staged_diff_fingerprint"]["changed_files"] == ["a.txt"]
    assert pending["consumed"] is False


def test_intent_stage_records_user_required_ac_review_mode(tmp_path: Path) -> None:
    runner = FakeIntentRunner()

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        issue_bindings=("55:closes",),
        ac_review_mode="user_required",
        now="2026-06-01T08:00:00Z",
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    pending = json.loads(
        (tmp_path / ".local/pr-flow/pending-intent.json").read_text(encoding="utf-8")
    )
    assert pending["ac_review_mode"] == "user_required"


def test_intent_stage_records_no_issue_authorization(tmp_path: Path) -> None:
    runner = FakeIntentRunner()

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        no_issue_reason="mechanical docs index refresh",
        no_issue_authorized_by="liuli195",
        no_issue_evidence="user requested no issue",
        now="2026-06-01T08:00:00Z",
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    pending = json.loads(
        (tmp_path / ".local/pr-flow/pending-intent.json").read_text(encoding="utf-8")
    )
    assert pending["issue_policy"] == "no_issue"
    assert pending["no_issue_authorization"] == {
        "reason": "mechanical docs index refresh",
        "authorized_by": "liuli195",
        "evidence": "user requested no issue",
    }


def test_intent_stage_rejects_missing_staged_diff(tmp_path: Path) -> None:
    runner = FakeIntentRunner(staged_diff="")

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        issue_bindings=("55:reference",),
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "STAGED_DIFF_MISSING"


def test_intent_stage_rejects_invalid_issue_role(tmp_path: Path) -> None:
    runner = FakeIntentRunner()

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        issue_bindings=("55:mentions",),
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "COMMIT_INTENT_ISSUE_ROLE_INVALID"


def test_intent_stage_rejects_closes_for_closed_issue(tmp_path: Path) -> None:
    runner = FakeIntentRunner(issue_states={55: "CLOSED"})

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        issue_bindings=("55:closes",),
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "COMMIT_INTENT_CLOSED_ISSUE_CLOSE_REJECTED"


def test_intent_stage_allows_reference_for_closed_issue(tmp_path: Path) -> None:
    runner = FakeIntentRunner(issue_states={55: "CLOSED"})

    code = pr_flow.stage_commit_intent(
        repo_root=tmp_path,
        runner=runner,
        issue_bindings=("55:reference",),
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    pending = json.loads(
        (tmp_path / ".local/pr-flow/pending-intent.json").read_text(encoding="utf-8")
    )
    assert pending["issues"] == [
        {"number": 55, "role": "reference", "title": "Issue 55"}
    ]


def test_commit_intent_pre_commit_accepts_matching_pending_intent(
    tmp_path: Path,
) -> None:
    runner = FakeIntentRunner()
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:reference",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )

    code = pr_flow.validate_pending_commit_intent(
        repo_root=tmp_path,
        runner=runner,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE


def test_commit_intent_pre_commit_rejects_missing_pending_intent(
    tmp_path: Path,
) -> None:
    runner = FakeIntentRunner()

    code = pr_flow.validate_pending_commit_intent(
        repo_root=tmp_path,
        runner=runner,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "COMMIT_INTENT_MISSING"


def test_commit_intent_pre_commit_rejects_stale_fingerprint(
    tmp_path: Path,
) -> None:
    runner = FakeIntentRunner()
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:reference",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    runner.staged_diff = "diff --git a/a.txt b/a.txt\n+changed again\n"

    code = pr_flow.validate_pending_commit_intent(
        repo_root=tmp_path,
        runner=runner,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "COMMIT_INTENT_STALE"


def test_commit_intent_post_commit_merges_branch_intent_and_consumes_pending(
    tmp_path: Path,
) -> None:
    runner = FakeIntentRunner(head_sha="2" * 40)
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:reference",),
            now="2026-06-01T08:00:00Z",
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )

    code = pr_flow.record_committed_intent(
        repo_root=tmp_path,
        runner=runner,
        now="2026-06-01T08:01:00Z",
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    branch_intent = json.loads(
        (tmp_path / ".local/pr-flow/intents/feature/intent.json").read_text(
            encoding="utf-8"
        )
    )
    assert branch_intent["issues"] == [
        {"number": 55, "role": "reference", "title": "Issue 55"}
    ]
    assert branch_intent["commits"][0]["commit_sha"] == "2" * 40
    pending = json.loads(
        (tmp_path / ".local/pr-flow/pending-intent.json").read_text(encoding="utf-8")
    )
    assert pending["consumed"] is True
    assert pending["commit_sha"] == "2" * 40


def test_branch_intent_aggregates_closes_over_reference(tmp_path: Path) -> None:
    runner = FakeIntentRunner()
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:reference",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    runner.head_sha = "1" * 40
    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:closes",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    runner.head_sha = "2" * 40

    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )

    branch_intent = json.loads(
        (tmp_path / ".local/pr-flow/intents/feature/intent.json").read_text(
            encoding="utf-8"
        )
    )
    assert branch_intent["issues"] == [
        {"number": 55, "role": "closes", "title": "Issue 55"}
    ]


def test_branch_intent_explicit_correction_can_downgrade_closes_to_reference(
    tmp_path: Path,
) -> None:
    runner = FakeIntentRunner()
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:closes",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    runner.head_sha = "1" * 40
    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:reference",),
            correction_reason="follow-up is only background context",
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    runner.head_sha = "2" * 40

    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )

    branch_intent = json.loads(
        (tmp_path / ".local/pr-flow/intents/feature/intent.json").read_text(
            encoding="utf-8"
        )
    )
    assert branch_intent["issues"] == [
        {
            "number": 55,
            "role": "reference",
            "title": "Issue 55",
            "correction_reason": "follow-up is only background context",
        }
    ]


def test_branch_intent_preserves_no_issue_authorizations(tmp_path: Path) -> None:
    runner = FakeIntentRunner(head_sha="3" * 40)
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            no_issue_reason="format-only generated index",
            no_issue_authorized_by="liuli195",
            no_issue_evidence="maintenance authorization",
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )

    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )

    branch_intent = json.loads(
        (tmp_path / ".local/pr-flow/intents/feature/intent.json").read_text(
            encoding="utf-8"
        )
    )
    assert branch_intent["no_issue_authorizations"] == [
        {
            "reason": "format-only generated index",
            "authorized_by": "liuli195",
            "evidence": "maintenance authorization",
            "commit_sha": "3" * 40,
        }
    ]


def test_branch_intent_preserves_user_required_ac_review_mode(tmp_path: Path) -> None:
    runner = FakeIntentRunner(head_sha="3" * 40)
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:closes",),
            ac_review_mode="user_required",
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )

    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )

    branch_intent = json.loads(
        (tmp_path / ".local/pr-flow/intents/feature/intent.json").read_text(
            encoding="utf-8"
        )
    )
    assert branch_intent["ac_review_mode"] == "user_required"


def test_branch_intent_coverage_detects_missing_current_commit(
    tmp_path: Path,
) -> None:
    recorded = "1" * 40
    missing = "2" * 40
    runner = FakeIntentRunner(branch_commits=(recorded, missing))
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:reference",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    runner.head_sha = recorded
    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )

    code = pr_flow.check_branch_intent_coverage(
        repo_root=tmp_path,
        runner=runner,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "BRANCH_INTENT_COVERAGE_MISSING"
    assert missing in status["blocking_items"]


def test_branch_intent_coverage_rejects_stale_commit(
    tmp_path: Path,
) -> None:
    current = "1" * 40
    stale = "2" * 40
    runner = FakeIntentRunner(branch_commits=(current,))
    path = tmp_path / ".local/pr-flow/intents/feature/intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "branch": "feature/intent",
                "commits": [
                    {
                        "commit_sha": current,
                        "issue_policy": "issues",
                        "issues": [{"number": 55, "role": "closes"}],
                    },
                    {
                        "commit_sha": stale,
                        "issue_policy": "issues",
                        "issues": [{"number": 99, "role": "closes"}],
                    },
                ],
                "issues": [
                    {"number": 55, "role": "closes"},
                    {"number": 99, "role": "closes"},
                ],
                "no_issue_authorizations": [],
            }
        ),
        encoding="utf-8",
    )

    code = pr_flow.check_branch_intent_coverage(repo_root=tmp_path, runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "BRANCH_INTENT_STALE_COMMITS"
    assert stale in status["blocking_items"]


def _valid_issue_intent_payload() -> dict[str, Any]:
    head_sha = "a" * 40
    return {
        "schema_version": 4,
        "tool": "codex",
        "review_mode": "complete",
        "risk_level": "low",
        "requires_official_codex_review": False,
        "reviewers": ["standards-reviewer", "spec-reviewer"],
        "security_review": {
            "tool": "codex-security",
            "evidence": "security review completed",
        },
        "cross_review": {
            "delegated_to_subagents": True,
            "review_skills": [
                "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
                "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
            ],
            "evidence": "standards and spec reviews completed",
        },
        "complete_review": {
            "evidence": "complete review finished",
            "iterations": [
                {
                    "reviewer": "standards-reviewer",
                    "round": 1,
                    "new_findings": [],
                    "no_new_findings": True,
                },
                {
                    "reviewer": "spec-reviewer",
                    "round": 1,
                    "new_findings": [],
                    "no_new_findings": True,
                },
            ],
        },
        "changed_files": ["docs/guides/example.md"],
        "diff_fingerprint": {
            "base_ref": "origin/main",
            "head_sha": head_sha,
            "diff_files_hash": "diff-hash",
            "changed_files": ["docs/guides/example.md"],
        },
        "review_fragments": {
            "standards": {"status": "pass", "evidence": "standards pass"},
            "spec": {"status": "pass", "evidence": "spec pass"},
            "security": {"status": "pass", "evidence": "security pass"},
        },
        "external_findings": [],
        "current_commit_evidence": {"head_sha": head_sha, "checks": {}},
        "spec_ref": {
            "issues": [
                {"number": 54, "role": "reference"},
                {"number": 55, "role": "closes"},
            ],
            "design_docs": [],
            "adrs": [],
        },
        "issue_refs": [
            {
                "number": 55,
                "title": "Intent stage",
                "acceptance_criteria": ["AC is met"],
            }
        ],
        "issue_intent": {
            "schema_version": 1,
            "head_sha": head_sha,
            "commits": [
                {
                    "commit_sha": "1" * 40,
                    "issue_policy": "issues",
                    "issues": [{"number": 55, "role": "closes"}],
                },
                {
                    "commit_sha": "2" * 40,
                    "issue_policy": "no_issue",
                    "no_issue_authorization": {
                        "reason": "format-only",
                        "authorized_by": "liuli195",
                        "evidence": "maintenance authorization",
                    },
                },
            ],
            "issues": [
                {"number": 54, "role": "reference", "title": "Parent"},
                {"number": 55, "role": "closes", "title": "Intent stage"},
            ],
            "no_issue_authorizations": [
                {
                    "commit_sha": "2" * 40,
                    "reason": "format-only",
                    "authorized_by": "liuli195",
                    "evidence": "maintenance authorization",
                }
            ],
        },
        "findings": [],
        "checks": {
            "verify full": ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full; passed"
        },
    }


def test_pr_body_renders_issue_intent_summary_and_machine_block() -> None:
    body = ai_review_gate.render_pr_body(_valid_issue_intent_payload())

    assert "## Issue 绑定审计" in body
    assert "References #54" in body
    assert "Closes #55" in body
    assert "No-Issue commits: 1" in body
    assert body.count("<details>") == 1
    assert '"commit_sha": "1111111111111111111111111111111111111111"' in body
    assert '"head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"' in body


def test_pr_review_evidence_validates_issue_intent_machine_block() -> None:
    body = ai_review_gate.render_pr_body(_valid_issue_intent_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert report.ok


def test_pr_review_evidence_rejects_stale_issue_intent_head() -> None:
    body = ai_review_gate.render_pr_body(_valid_issue_intent_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="b" * 40,
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert not report.ok
    assert "issue intent machine data head_sha does not match current PR head" in report.errors


def test_review_payload_derives_spec_ref_from_branch_intent(tmp_path: Path) -> None:
    runner = FakeIntentRunner(head_sha="4" * 40)
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:closes",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )
    payload = _valid_issue_intent_payload()
    payload["spec_ref"] = {
        "issues": [{"number": 99, "role": "reference"}],
        "design_docs": ["docs/design/kept.md"],
        "adrs": ["docs/adr/0007-pr-flow-closed-loop-review-evidence.md"],
    }

    updated = pr_flow.payload_with_branch_intent(
        payload,
        repo_root=tmp_path,
        runner=runner,
    )

    assert updated["spec_ref"] == {
        "issues": [{"number": 55, "role": "closes"}],
        "design_docs": ["docs/design/kept.md"],
        "adrs": ["docs/adr/0007-pr-flow-closed-loop-review-evidence.md"],
    }
    assert updated["issue_intent"]["head_sha"] == "4" * 40
    assert updated["issue_intent"]["commits"][0]["commit_sha"] == "4" * 40


def test_review_payload_filters_stale_branch_intent_commits(tmp_path: Path) -> None:
    current = "4" * 40
    stale = "5" * 40
    runner = FakeIntentRunner(head_sha=current, branch_commits=(current,))
    path = tmp_path / ".local/pr-flow/intents/feature/intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "branch": "feature/intent",
                "commits": [
                    {
                        "commit_sha": current,
                        "issue_policy": "issues",
                        "issues": [{"number": 55, "role": "closes"}],
                    },
                    {
                        "commit_sha": stale,
                        "issue_policy": "issues",
                        "issues": [{"number": 99, "role": "closes"}],
                    },
                ],
                "issues": [
                    {"number": 55, "role": "closes"},
                    {"number": 99, "role": "closes"},
                ],
                "no_issue_authorizations": [],
            }
        ),
        encoding="utf-8",
    )

    updated = pr_flow.payload_with_branch_intent(
        _valid_issue_intent_payload(),
        repo_root=tmp_path,
        runner=runner,
    )

    assert updated["spec_ref"]["issues"] == [{"number": 55, "role": "closes"}]
    assert [item["commit_sha"] for item in updated["issue_intent"]["commits"]] == [
        current
    ]


def test_branch_context_applies_intent_before_spec_policy_validation(
    tmp_path: Path,
) -> None:
    head_sha = "a" * 40
    runner = FakeIntentRunner(
        head_sha=head_sha,
        branch_commits=(head_sha,),
        issue_bodies={55: "- [ ] AC is met\n"},
    )
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:closes",),
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )
    payload = _valid_issue_intent_payload()
    payload["pr_class"] = "governance_functional"
    payload["spec_ref"] = {"issues": [], "design_docs": [], "adrs": []}
    payload["issue_refs"] = []

    updated = pr_flow._payload_with_current_branch_context(
        payload,
        root=tmp_path,
        runner=runner,
        current_diff_fingerprint=payload["diff_fingerprint"],
    )
    result = ai_review_gate.validate_report(
        updated,
        current_diff_fingerprint=payload["diff_fingerprint"],
    )

    assert result.ok, result.errors
    assert updated["spec_ref"]["issues"] == [{"number": 55, "role": "closes"}]
    assert updated["issue_refs"] == [
        {
            "number": 55,
            "title": "Issue 55",
            "acceptance_criteria": ["AC is met"],
        }
    ]


def test_review_payload_carries_ac_review_mode_from_branch_intent(tmp_path: Path) -> None:
    runner = FakeIntentRunner(head_sha="4" * 40)
    assert (
        pr_flow.stage_commit_intent(
            repo_root=tmp_path,
            runner=runner,
            issue_bindings=("55:closes",),
            ac_review_mode="user_required",
        )
        == pr_flow.SUCCESS_EXIT_CODE
    )
    assert (
        pr_flow.record_committed_intent(repo_root=tmp_path, runner=runner)
        == pr_flow.SUCCESS_EXIT_CODE
    )

    updated = pr_flow.payload_with_branch_intent(
        _valid_issue_intent_payload(),
        repo_root=tmp_path,
        runner=runner,
    )

    assert updated["issue_intent"]["ac_review_mode"] == "user_required"


def test_review_pipeline_skips_security_when_standards_has_open_p1() -> None:
    payload = _valid_issue_intent_payload()
    payload["review_fragments"]["standards"]["findings"] = [
        {"id": "STD-1", "severity": "P1", "status": "open"}
    ]

    decision = pr_flow.evaluate_review_pipeline(payload)

    assert decision["status"] == "security_skipped"
    assert decision["blocking_findings"] == ["STD-1"]


def test_review_pipeline_requires_spec_ac_evidence_for_closes_issue() -> None:
    payload = _valid_issue_intent_payload()
    payload["review_fragments"]["spec"]["ac_evidence"] = [
        {
            "issue": 55,
            "criteria": "AC is met",
            "met": True,
            "evidence": ["focused pytest"],
            "reviewer": "spec-reviewer",
        }
    ]

    decision = pr_flow.evaluate_review_pipeline(payload)

    assert decision["status"] == "security_ready"
    assert decision["ac_evidence"][0]["criteria"] == "AC is met"


def test_review_pipeline_blocks_missing_ac_evidence() -> None:
    payload = _valid_issue_intent_payload()

    decision = pr_flow.evaluate_review_pipeline(payload)

    assert decision["status"] == "blocked"
    assert "missing AC evidence for #55: AC is met" in decision["blocking_findings"]


def test_auto_mark_acceptance_criteria_marks_met_closes_issue_and_comments(
    tmp_path: Path,
) -> None:
    payload = _valid_issue_intent_payload()
    payload["review_fragments"]["spec"]["ac_evidence"] = [
        {
            "issue": 55,
            "criteria": "AC is met",
            "met": True,
            "evidence": ["focused pytest"],
            "reviewer": "spec-reviewer",
        }
    ]
    runner = FakeIntentRunner(issue_bodies={55: "- [ ] AC is met\n- [ ] Other AC\n"})

    code = pr_flow.auto_mark_acceptance_criteria(
        repo_root=tmp_path,
        runner=runner,
        payload=payload,
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha="a" * 40,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "- [x] AC is met" in runner.edited_issues[55]
    assert "- [ ] Other AC" in runner.edited_issues[55]
    assert "https://github.com/liuli195/Quant-Trading/pull/7" in runner.issue_comments[55][0]
    assert "AC is met" in runner.issue_comments[55][0]


def test_auto_mark_acceptance_criteria_stops_for_user_required_mode(
    tmp_path: Path,
) -> None:
    payload = _valid_issue_intent_payload()
    payload["issue_intent"]["ac_review_mode"] = "user_required"
    runner = FakeIntentRunner(issue_bodies={55: "- [ ] AC is met\n"})

    code = pr_flow.auto_mark_acceptance_criteria(
        repo_root=tmp_path,
        runner=runner,
        payload=payload,
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha="a" * 40,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert runner.edited_issues == {}
    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["reason_code"] == "AC_REVIEW_USER_REQUIRED"


def test_auto_mark_acceptance_criteria_skips_reference_issue(tmp_path: Path) -> None:
    payload = _valid_issue_intent_payload()
    payload["issue_intent"]["issues"] = [
        {"number": 55, "role": "reference", "title": "Intent stage"}
    ]
    payload["spec_ref"]["issues"] = [{"number": 55, "role": "reference"}]
    runner = FakeIntentRunner(issue_bodies={55: "- [ ] AC is met\n"})

    code = pr_flow.auto_mark_acceptance_criteria(
        repo_root=tmp_path,
        runner=runner,
        payload=payload,
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha="a" * 40,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.edited_issues == {}


def test_intent_cli_parser_accepts_stage_command() -> None:
    args = pr_flow.build_parser().parse_args(
        [
            "intent",
            "stage",
            "--issue",
            "55:closes",
            "--correction-reason",
            "fix role",
            "--ac-review-mode",
            "user_required",
        ]
    )

    assert args.command == "intent"
    assert args.intent_command == "stage"
    assert args.issue == ["55:closes"]
    assert args.correction_reason == "fix role"
    assert args.ac_review_mode == "user_required"


def test_git_hooks_call_commit_intent_gate() -> None:
    pre_commit = Path(".githooks/pre-commit").read_text(encoding="utf-8")
    post_commit = Path(".githooks/post-commit").read_text(encoding="utf-8")

    assert "scripts.research.governance.pr_flow intent pre-commit" in pre_commit
    assert "scripts.research.governance.pr_flow intent post-commit" in post_commit
