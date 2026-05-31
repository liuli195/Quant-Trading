from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.governance import pr_flow


@pytest.fixture(autouse=True)
def _isolate_current_diff_fingerprint(monkeypatch) -> None:
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: None,
    )


def _codex_review_trigger_body(head_sha: str = "1" * 40) -> str:
    return pr_flow.render_codex_review_request(
        pr_url="https://github.com/liuli195/Quant-Trading/pull/7",
        head_sha=head_sha,
        review_scope=("scripts/research/governance/pr_flow.py",),
    )


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
                ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full",
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


def _write_valid_v3_report(
    root: Path,
    *,
    changed_files: list[str],
    diff_files_hash: str,
) -> None:
    _write_valid_report(root, changed_files=changed_files)
    latest = root / ".local" / "ai-review" / "latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload.update(
        {
            "schema_version": 3,
            "diff_fingerprint": {
                "base_ref": "origin/main",
                "head_sha": "1" * 40,
                "diff_files_hash": diff_files_hash,
                "changed_files": changed_files,
            },
            "review_fragments": {
                "standards": {"status": "pass", "evidence": "standards review completed"},
                "spec": {"status": "pass", "evidence": "spec review completed"},
                "security": {"status": "pass", "evidence": "security review completed"},
            },
            "external_findings": [],
            "current_commit_evidence": {
                "head_sha": "1" * 40,
                "checks": payload["checks"],
            },
        }
    )
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_valid_v4_issue_report(root: Path, *, issue_number: int = 50) -> None:
    _write_valid_v3_report(
        root,
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )
    latest = root / ".local" / "ai-review" / "latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload = pr_flow.ai_review_gate.payload_as_schema_v4(
        payload,
        repo_root=root,
        changed_files=["docs/guides/example.md"],
    )
    payload["spec_ref"] = {
        "issues": [{"number": issue_number, "role": "closes"}],
        "design_docs": [],
        "adrs": [],
    }
    payload["issue_refs"] = [
        {
            "number": issue_number,
            "title": f"Issue {issue_number}",
            "acceptance_criteria": ["first AC"],
        }
    ]
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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
        self.thread_replies: list[dict[str, str]] = []

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
        if command == ["git", "rev-list", "--reverse", "origin/main..HEAD"]:
            return pr_flow.CommandResult(0, "", "")
        if command == ["git", "ls-remote", "--heads", "origin", "feature/pr-flow"]:
            return pr_flow.CommandResult(
                0,
                "1" * 40 + "\trefs/heads/feature/pr-flow\n",
                "",
            )
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
            query = _graphql_query(command)
            if "addPullRequestReviewThreadReply" in query:
                thread_id = _command_field(command, "threadId")
                body = _command_field(command, "body")
                self.thread_replies.append({"thread_id": thread_id, "body": body})
                return pr_flow.CommandResult(
                    0,
                    json.dumps(
                        {
                            "data": {
                                "addPullRequestReviewThreadReply": {
                                    "comment": {"id": f"reply-{thread_id}"}
                                }
                            }
                        }
                    ),
                    "",
                )
            if "resolveReviewThread" in query:
                thread_id = _command_field(command, "threadId")
                is_resolved = True
                for thread in self.api_review_threads:
                    if str(thread.get("id") or "") == thread_id:
                        thread["isResolved"] = True
                        is_resolved = bool(thread.get("isResolved"))
                        break
                return pr_flow.CommandResult(
                    0,
                    json.dumps(
                        {
                            "data": {
                                "resolveReviewThread": {
                                    "thread": {
                                        "id": thread_id,
                                        "isResolved": is_resolved,
                                    }
                                }
                            }
                        }
                    ),
                    "",
                )
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


def _graphql_query(command: list[str]) -> str:
    for item in command:
        if item.startswith("query="):
            return item.removeprefix("query=")
    return ""


def _command_field(command: list[str], name: str) -> str:
    prefix = f"{name}="
    for index, item in enumerate(command[:-1]):
        if item in {"-F", "-f"} and command[index + 1].startswith(prefix):
            return command[index + 1].removeprefix(prefix)
    return ""


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
        if command == [
            "gh",
            "pr",
            "view",
            "7",
            "--json",
            "url,baseRefName,isDraft,statusCheckRollup",
        ]:
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


class RollupFallbackChecksRunner:
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
            return pr_flow.CommandResult(1, "", "no required checks reported")
        if command == [
            "gh",
            "pr",
            "checks",
            "7",
            "--required",
            "--json",
            pr_flow.CHECKS_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(0, "[]", "")
        if command == [
            "gh",
            "pr",
            "view",
            "7",
            "--json",
            "url,baseRefName,isDraft,statusCheckRollup",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "url": "https://github.com/liuli195/Quant-Trading/pull/7",
                        "baseRefName": "main",
                        "isDraft": False,
                        "statusCheckRollup": [
                            {
                                "name": "governance",
                                "workflowName": "Research Governance",
                                "state": "SUCCESS",
                                "detailsUrl": "https://github.com/o/r/actions/runs/30/job/300",
                                "startedAt": "2026-05-28T10:00:00Z",
                                "completedAt": "2026-05-28T10:01:00Z",
                            }
                        ],
                    }
                ),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/rulesets?includes_parents=true":
            return pr_flow.CommandResult(
                0,
                json.dumps([{"id": 11, "name": "main rules"}]),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/rulesets/11":
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "id": 11,
                        "rules": [
                            {
                                "type": "required_status_checks",
                                "parameters": {
                                    "required_status_checks": [
                                        {"context": "Research Governance / governance"}
                                    ]
                                },
                            }
                        ],
                    }
                ),
                "",
            )
        if command == ["gh", "pr", "checks", "7", "--required"]:
            return pr_flow.CommandResult(1, "", "no required checks reported")
        raise AssertionError(f"unexpected command: {command}")


class DiagnoseRunner:
    def __init__(
        self,
        *,
        merge_state: str = "BLOCKED",
        check_bucket: str = "fail",
        check_state: str = "FAILURE",
        review_decision: str = "REVIEW_REQUIRED",
        required_approving_review_count: int = 0,
        require_code_owner_review: bool = False,
        require_last_push_approval: bool = False,
        local_head: str | None = None,
        issue_comments: list[dict[str, object]] | None = None,
        reviews: list[dict[str, object]] | None = None,
        review_threads: list[dict[str, object]] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.merge_state = merge_state
        self.check_bucket = check_bucket
        self.check_state = check_state
        self.review_decision = review_decision
        self.required_approving_review_count = required_approving_review_count
        self.require_code_owner_review = require_code_owner_review
        self.require_last_push_approval = require_last_push_approval
        self.local_head = local_head or "1" * 40
        self.issue_comments = issue_comments
        self.reviews = reviews
        self.review_threads = review_threads

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
            "view",
            "7",
            "--json",
            pr_flow.PR_DIAGNOSE_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "number": 7,
                        "url": "https://github.com/liuli195/Quant-Trading/pull/7",
                        "state": "OPEN",
                        "isDraft": False,
                        "headRefOid": "1" * 40,
                        "baseRefName": "main",
                        "mergeStateStatus": self.merge_state,
                        "reviewDecision": self.review_decision,
                        "body": (
                            f"{pr_flow.MANAGED_BLOCK_START}\n"
                            "## AI Review 风险分级\n"
                            f"{pr_flow.MANAGED_BLOCK_END}\n"
                        ),
                    }
                ),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/rulesets?includes_parents=true":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(
                    command,
                    [
                        {
                            "id": 11,
                            "name": "main rules",
                            "target": "branch",
                            "enforcement": "active",
                            "conditions": {
                                "ref_name": {
                                    "include": ["refs/heads/main"],
                                    "exclude": [],
                                }
                            },
                            "rules": None,
                        }
                    ],
                ),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/rulesets/11":
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "id": 11,
                        "name": "main rules",
                        "target": "branch",
                        "enforcement": "active",
                        "conditions": {
                            "ref_name": {
                                "include": ["refs/heads/main"],
                                "exclude": [],
                            }
                        },
                        "rules": [
                            {
                                "type": "pull_request",
                                "parameters": {
                                    "required_approving_review_count": self.required_approving_review_count,
                                    "require_code_owner_review": self.require_code_owner_review,
                                    "require_last_push_approval": self.require_last_push_approval,
                                    "required_review_thread_resolution": True,
                                },
                            }
                        ],
                    }
                ),
                "",
            )
        if command == ["git", "rev-parse", "HEAD"]:
            return pr_flow.CommandResult(0, self.local_head + "\n", "")
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
                            "name": "pr-review-evidence",
                            "state": self.check_state,
                            "bucket": self.check_bucket,
                            "workflow": "Research Governance",
                            "link": "https://github.com/o/r/actions/runs/20/job/200",
                        }
                    ]
                ),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/issues/7/comments?per_page=100":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(
                    command,
                    self.issue_comments
                    if self.issue_comments is not None
                    else [
                        {
                            "id": 1,
                            "user": {"login": "test-user"},
                            "body": _codex_review_trigger_body(),
                            "created_at": "2026-05-28T09:00:00Z",
                            "updated_at": "2026-05-28T09:00:00Z",
                        },
                        {
                            "id": 2,
                            "user": {"login": "chatgpt-codex-connector"},
                            "body": "Codex Review: Didn't find any major issues.",
                            "created_at": "2026-05-28T10:00:00Z",
                            "updated_at": "2026-05-28T10:00:00Z",
                        },
                    ],
                ),
                "",
            )
        if _gh_api_path(command) == "repos/liuli195/Quant-Trading/pulls/7/reviews?per_page=100":
            return pr_flow.CommandResult(
                0,
                _gh_api_json(command, self.reviews or []),
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
                                        "nodes": self.review_threads
                                        if self.review_threads is not None
                                        else [
                                            {
                                                "isResolved": False,
                                                "isOutdated": True,
                                                "comments": {
                                                    "nodes": [
                                                        {
                                                            "body": "P2: optional cleanup can wait.",
                                                            "author": {
                                                                "login": "chatgpt-codex-connector"
                                                            },
                                                        }
                                                    ]
                                                },
                                            }
                                        ],
                                        "pageInfo": {
                                            "hasNextPage": False,
                                            "endCursor": None,
                                        },
                                    }
                                }
                            }
                        }
                    }
                ),
                "",
            )
        raise AssertionError(f"unexpected command: {command}")


class MissingRemoteHeadRunner(FakeRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == ["git", "ls-remote", "--heads", "origin", "feature/pr-flow"]:
            self.calls.append(command)
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "pr", "create"]:
            self.calls.append(command)
            return pr_flow.CommandResult(
                1,
                "",
                "GraphQL: Head sha can't be blank, Base sha can't be blank",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class ReadyForReviewRunner:
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
        if command == ["gh", "pr", "ready", "7"]:
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


class MergeReadyRunner(DiagnoseRunner):
    def __init__(self) -> None:
        super().__init__(
            merge_state="CLEAN",
            check_bucket="pass",
            check_state="SUCCESS",
            review_decision="APPROVED",
            issue_comments=[
                {
                    "id": 1,
                    "user": {"login": "test-user"},
                    "body": _codex_review_trigger_body(),
                    "created_at": "2026-05-28T09:00:00Z",
                    "updated_at": "2026-05-28T09:00:00Z",
                }
            ],
            reviews=[
                {
                    "id": 10,
                    "user": {"login": "chatgpt-codex-connector"},
                    "state": "COMMENTED",
                    "commit_id": "1" * 40,
                    "submitted_at": "2026-05-28T10:00:00Z",
                    "body": "Codex Review: Didn't find any major issues.",
                }
            ],
            review_threads=[],
        )

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
            "merge",
            "7",
            "--merge",
            "--match-head-commit",
            "1" * 40,
        ]:
            self.calls.append(command)
            return pr_flow.CommandResult(
                0,
                "Merged pull request #7 (merge commit abc1234)\n",
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class CleanupRunner:
    def __init__(self, *, is_cross_repository: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.is_cross_repository = is_cross_repository

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
            "view",
            "7",
            "--json",
            "number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "number": 7,
                        "state": "MERGED",
                        "mergedAt": "2026-05-29T16:48:26Z",
                        "headRefName": "feature/pr-flow",
                        "baseRefName": "main",
                        "isCrossRepository": self.is_cross_repository,
                    }
                ),
                "",
            )
        if command in (
            ["git", "fetch", "--prune", "origin"],
            ["git", "switch", "main"],
            ["git", "merge", "--ff-only", "origin/main"],
            ["git", "branch", "-d", "feature/pr-flow"],
            ["git", "push", "origin", "--delete", "feature/pr-flow"],
            ["git", "rev-list", "--left-right", "--count", "main...origin/main"],
            ["git", "ls-remote", "--heads", "origin", "feature/pr-flow"],
        ):
            stdout = "0\t0\n" if command[1:3] == ["rev-list", "--left-right"] else ""
            return pr_flow.CommandResult(0, stdout, "")
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


class FlakyGitHubApiRunner:
    def __init__(self, failures: list[pr_flow.CommandResult]) -> None:
        self.calls: list[list[str]] = []
        self.failures = failures

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
        if self.failures:
            return self.failures.pop(0)
        return pr_flow.CommandResult(0, json.dumps([{"id": 1}]), "")


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


class ResolveThreadsRunner:
    def __init__(
        self,
        *,
        is_resolved: bool = True,
        returncode: int = 0,
    ) -> None:
        self.calls: list[list[str]] = []
        self.is_resolved = is_resolved
        self.returncode = returncode

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
        if command[:3] != ["gh", "api", "graphql"]:
            raise AssertionError(f"unexpected command: {command}")
        if self.returncode != 0:
            return pr_flow.CommandResult(self.returncode, "", "graphql failed")
        thread_id = command[-1].removeprefix("threadId=")
        return pr_flow.CommandResult(
            0,
            json.dumps(
                {
                    "data": {
                        "resolveReviewThread": {
                            "thread": {
                                "id": thread_id,
                                "isResolved": self.is_resolved,
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


def test_resolve_review_threads_resolves_each_thread(tmp_path: Path, capsys) -> None:
    runner = ResolveThreadsRunner()

    code = pr_flow.resolve_review_threads(
        repo_root=tmp_path,
        thread_ids=("PRRT_one", "PRRT_two"),
        runner=runner,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "resolved review thread: PRRT_one" in captured.out
    assert "resolved review thread: PRRT_two" in captured.out
    assert len(runner.calls) == 2
    assert all(call[:3] == ["gh", "api", "graphql"] for call in runner.calls)
    assert ["-F", "threadId=PRRT_one"] in [
        runner.calls[0][index : index + 2]
        for index in range(len(runner.calls[0]) - 1)
    ]


def test_resolve_review_threads_fails_closed_on_graphql_error(
    tmp_path: Path,
    capsys,
) -> None:
    runner = ResolveThreadsRunner(returncode=1)

    code = pr_flow.resolve_review_threads(
        repo_root=tmp_path,
        thread_ids=("PRRT_one",),
        runner=runner,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "gh api graphql resolveReviewThread" in captured.err


def test_resolve_review_threads_fails_closed_when_thread_remains_unresolved(
    tmp_path: Path,
    capsys,
) -> None:
    runner = ResolveThreadsRunner(is_resolved=False)

    code = pr_flow.resolve_review_threads(
        repo_root=tmp_path,
        thread_ids=("PRRT_one",),
        runner=runner,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "review thread was not resolved" in captured.err


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


def test_wait_falls_back_to_status_check_rollup_when_required_checks_empty(
    tmp_path: Path,
    capsys,
) -> None:
    runner = RollupFallbackChecksRunner()

    code = pr_flow.wait(repo_root=tmp_path, pr="7", runner=runner)

    assert code == 0
    assert "required checks passed" in capsys.readouterr().out
    assert [
        "gh",
        "pr",
        "view",
        "7",
        "--json",
        "url,baseRefName,isDraft,statusCheckRollup",
    ] in runner.calls


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


def test_wait_writes_structured_last_status_for_pending_checks(
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
    assert "reason_code: REQUIRED_CHECKS_PENDING" in captured.err
    assert "phase: wait_required_checks" in captured.err
    assert "retryable: true" in captured.err

    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["state"] == "EXCEPTION_REQUIRED"
    assert status["reason_code"] == "REQUIRED_CHECKS_PENDING"
    assert status["phase"] == "wait_required_checks"
    assert status["retryable"] is True
    assert status["dispatch_target"] == "github"
    assert status["blocking_items"] == ["Research Governance / governance"]
    assert status["next_actions"] == ["wait for pending required checks"]


def test_diagnose_reports_required_checks_and_unresolved_threads(
    tmp_path: Path,
    capsys,
) -> None:
    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=DiagnoseRunner())

    captured = capsys.readouterr()
    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "PR_DIAGNOSE: #7 OPEN head=111111111111" in captured.out
    assert "mergeStateStatus: BLOCKED" in captured.out
    assert "pr body evidence: present" in captured.out
    assert "required checks: failing" in captured.out
    assert "Research Governance / pr-review-evidence" in captured.out
    assert "review threads: unresolved=1" in captured.out
    assert "next: resolve unresolved review threads" in captured.out


def test_diagnose_falls_back_to_status_check_rollup_when_required_checks_empty(
    tmp_path: Path,
    capsys,
) -> None:
    class DiagnoseRollupRunner(DiagnoseRunner):
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
                "--json",
                pr_flow.CHECKS_JSON_FIELDS,
            ]:
                self.calls.append(command)
                return pr_flow.CommandResult(0, "[]", "")
            if command == [
                "gh",
                "pr",
                "view",
                "7",
                "--json",
                "url,baseRefName,isDraft,statusCheckRollup",
            ]:
                self.calls.append(command)
                return pr_flow.CommandResult(
                    0,
                    json.dumps(
                        {
                            "url": "https://github.com/liuli195/Quant-Trading/pull/7",
                            "baseRefName": "main",
                            "isDraft": False,
                            "statusCheckRollup": [
                                {
                                    "name": "governance",
                                    "workflowName": "Research Governance",
                                    "state": "SUCCESS",
                                    "detailsUrl": "https://github.com/o/r/actions/runs/30/job/300",
                                }
                            ],
                        }
                    ),
                    "",
                )
            return super().run(command, cwd=cwd, input_text=input_text)

    code = pr_flow.diagnose(
        repo_root=tmp_path,
        pr="7",
        runner=DiagnoseRollupRunner(
            merge_state="CLEAN",
            check_bucket="pass",
            check_state="SUCCESS",
            review_decision="APPROVED",
            review_threads=[],
        ),
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "required checks: passed" in captured.out


def test_diagnose_writes_structured_last_status_for_unresolved_threads(
    tmp_path: Path,
    capsys,
) -> None:
    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=DiagnoseRunner())

    captured = capsys.readouterr()
    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "reason_code: REVIEW_THREADS_UNRESOLVED" in captured.out
    assert "phase: diagnose" in captured.out

    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["state"] == "REPLY_OR_FIX_REQUIRED"
    assert status["reason_code"] == "REVIEW_THREADS_UNRESOLVED"
    assert status["phase"] == "diagnose"
    assert status["retryable"] is False
    assert status["dispatch_target"] == "author"
    assert status["blocking_items"] == [
        "unresolved review thread P2: optional cleanup can wait."
    ]
    assert status["next_actions"] == ["resolve unresolved review threads"]


def test_diagnose_reports_current_head_review_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DiagnoseRunner(
        merge_state="CLEAN",
        check_bucket="pass",
        check_state="SUCCESS",
        review_decision="APPROVED",
        issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 10,
                "user": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit_id": "1" * 40,
                "submitted_at": "2026-05-28T10:00:00Z",
                "body": "Codex Review: Didn't find any major issues.",
            }
        ],
        review_threads=[],
    )

    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "codex review evidence: present" in captured.out
    assert "codex blockers: 0" in captured.out
    assert "next: PR automation state is merge-ready" in captured.out


def test_diagnose_blocks_merge_ready_without_approved_review(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DiagnoseRunner(
        merge_state="CLEAN",
        check_bucket="pass",
        check_state="SUCCESS",
        review_decision="REVIEW_REQUIRED",
        required_approving_review_count=1,
        issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 10,
                "user": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit_id": "1" * 40,
                "submitted_at": "2026-05-28T10:00:00Z",
                "body": "Codex Review: Didn't find any major issues.",
            }
        ],
        review_threads=[],
    )

    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "reviewDecision: REVIEW_REQUIRED" in captured.out
    assert "next: wait for approved review required by remote rules" in captured.out
    assert "next: PR automation state is merge-ready" not in captured.out


def test_diagnose_allows_merge_ready_without_remote_approval_requirement(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DiagnoseRunner(
        merge_state="CLEAN",
        check_bucket="pass",
        check_state="SUCCESS",
        review_decision="REVIEW_REQUIRED",
        issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 10,
                "user": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit_id": "1" * 40,
                "submitted_at": "2026-05-28T10:00:00Z",
                "body": "Codex Review: Didn't find any major issues.",
            }
        ],
        review_threads=[],
    )

    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "reviewDecision: REVIEW_REQUIRED" in captured.out
    assert "next: wait for approved review required by remote rules" not in captured.out
    assert "next: PR automation state is merge-ready" in captured.out


def test_diagnose_waits_for_pending_checks_before_ruleset_attention(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DiagnoseRunner(
        merge_state="BLOCKED",
        check_bucket="pending",
        check_state="IN_PROGRESS",
        issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 10,
                "user": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit_id": "1" * 40,
                "submitted_at": "2026-05-28T10:00:00Z",
                "body": "Codex Review: Didn't find any major issues.",
            }
        ],
        review_threads=[],
    )

    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "required checks: pending" in captured.out
    assert "next: wait for pending required checks" in captured.out
    assert "next: inspect branch protection or ruleset blockers" not in captured.out


def test_diagnose_stops_on_current_head_review_blocker(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DiagnoseRunner(
        merge_state="CLEAN",
        check_bucket="pass",
        check_state="SUCCESS",
        issue_comments=[
            {
                "id": 1,
                "user": {"login": "test-user"},
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 10,
                "user": {"login": "chatgpt-codex-connector"},
                "state": "COMMENTED",
                "commit_id": "1" * 40,
                "submitted_at": "2026-05-28T10:00:00Z",
                "body": "P1 Badge: review evidence can be bypassed.",
            }
        ],
        review_threads=[],
    )

    code = pr_flow.diagnose(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "codex blockers: 1" in captured.out
    assert "P1 Badge" in captured.out
    assert "next: reply to or fix Codex blockers" in captured.out


def test_gh_api_list_flattens_slurped_paginated_pages(tmp_path: Path) -> None:
    items = pr_flow._gh_api_list(
        tmp_path,
        SlurpedPagesRunner(),
        "repos/o/r/issues/1/comments?per_page=100",
    )

    assert [item["id"] for item in items] == [1, 2]


def test_gh_api_list_retries_transient_errors(tmp_path: Path) -> None:
    runner = FlakyGitHubApiRunner(
        [
            pr_flow.CommandResult(1, "", "EOF"),
            pr_flow.CommandResult(1, "", "connection reset by peer"),
        ]
    )

    items = pr_flow._gh_api_list(
        tmp_path,
        runner,
        "repos/o/r/issues/1/comments?per_page=100",
    )

    assert items == [{"id": 1}]
    assert len(runner.calls) == 3


def test_gh_api_list_does_not_retry_auth_errors(tmp_path: Path) -> None:
    runner = FlakyGitHubApiRunner(
        [pr_flow.CommandResult(1, "", "authentication required")]
    )

    try:
        pr_flow._gh_api_list(
            tmp_path,
            runner,
            "repos/o/r/issues/1/comments?per_page=100",
        )
    except pr_flow.GitHubDataUnavailable as exc:
        assert exc.retryable is False
    else:
        raise AssertionError("expected GitHubDataUnavailable")
    assert len(runner.calls) == 1


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


def test_select_local_checks_for_changed_files(tmp_path: Path) -> None:
    (tmp_path / "docs/guides").mkdir(parents=True)
    (tmp_path / "docs/guides/a.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "scripts/research/governance").mkdir(parents=True)
    (tmp_path / "scripts/research/governance/rules.py").write_text(
        "# rules\n",
        encoding="utf-8",
    )
    (tmp_path / "strategies/demo").mkdir(parents=True)
    (tmp_path / "strategies/demo/demo.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")
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
        assert pr_flow.select_local_checks(changed_files, repo_root=tmp_path) == expected


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


def test_prepare_records_verify_full_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
    )
    monkeypatch.setattr(
        pr_flow.sys,
        "executable",
        str(tmp_path / ".venv" / "Scripts" / "python.exe"),
    )
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 0
    payload = json.loads(
        (tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8")
    )
    gate_evidence = payload["checks"]["verify full"]
    assert ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full" in gate_evidence
    body = (tmp_path / ".local/ai-review/pr-body.md").read_text(encoding="utf-8")
    assert gate_evidence in body


def test_prepare_migrates_latest_report_to_schema_v4(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
    )
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 0
    payload = json.loads(
        (tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == 4
    assert payload["diff_fingerprint"]["diff_files_hash"] == "current-diff"
    assert set(payload["review_fragments"]) == {"standards", "spec", "security"}
    assert payload["external_findings"] == []
    assert payload["current_commit_evidence"]["head_sha"] == "1" * 40
    assert payload["spec_ref"] == {"issues": [], "design_docs": [], "adrs": []}
    assert payload["issue_refs"] == []


def test_prepare_populates_issue_refs_from_closing_spec_issues(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_v3_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )
    latest = tmp_path / ".local" / "ai-review" / "latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload = pr_flow.ai_review_gate.payload_as_schema_v4(
        payload,
        repo_root=tmp_path,
        changed_files=["docs/guides/example.md"],
    )
    payload["spec_ref"] = {
        "issues": [
            {"number": 50, "role": "closes"},
            {"number": 27, "role": "reference"},
        ],
        "design_docs": [],
        "adrs": [],
    }
    payload["issue_refs"] = []
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])

    class IssueRunner(RecordingRunner):
        def run(
            self,
            command: list[str],
            *,
            cwd: Path | None = None,
            input_text: str | None = None,
        ) -> pr_flow.CommandResult:
            self.calls.append(command)
            if command == ["gh", "issue", "view", "50", "--json", "title,body"]:
                return pr_flow.CommandResult(
                    0,
                    json.dumps(
                        {
                            "title": "PR Flow v2：集成 Issue 状态处理",
                            "body": "- [ ] first AC\n- [x] second AC\n",
                        }
                    ),
                    "",
                )
            return pr_flow.CommandResult(0, "", "")

    code = pr_flow.prepare(repo_root=tmp_path, runner=IssueRunner())

    assert code == 0
    updated = json.loads(latest.read_text(encoding="utf-8"))
    assert updated["schema_version"] == 4
    assert updated["issue_refs"] == [
        {
            "number": 50,
            "title": "PR Flow v2：集成 Issue 状态处理",
            "acceptance_criteria": ["first AC", "second AC"],
        }
    ]


def test_prepare_keeps_matching_issue_refs_without_refetching(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_v3_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
        diff_files_hash="current-diff",
    )
    latest = tmp_path / ".local" / "ai-review" / "latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload = pr_flow.ai_review_gate.payload_as_schema_v4(
        payload,
        repo_root=tmp_path,
        changed_files=["docs/guides/example.md"],
    )
    payload["spec_ref"] = {
        "issues": [{"number": 50, "role": "closes"}],
        "design_docs": [],
        "adrs": [],
    }
    payload["issue_refs"] = [
        {
            "number": 50,
            "title": "Already cached",
            "acceptance_criteria": ["cached AC"],
        }
    ]
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pr_flow.ai_review_gate, "_discover_changed_files", lambda _root: [])
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 0
    assert ["gh", "issue", "view", "50", "--json", "title,body"] not in runner.calls
    updated = json.loads(latest.read_text(encoding="utf-8"))
    assert updated["issue_refs"][0]["title"] == "Already cached"


def test_prepare_rejects_stale_schema_v3_diff_fingerprint(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_v3_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
        diff_files_hash="old-diff",
    )
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "_discover_changed_files",
        lambda _root: ["docs/guides/example.md"],
    )
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )
    runner = RecordingRunner()

    code = pr_flow.prepare(repo_root=tmp_path, runner=runner)

    assert code == 1
    assert "diff_fingerprint diff_files_hash does not match current diff" in capsys.readouterr().err
    payload = json.loads(
        (tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8")
    )
    assert payload["diff_fingerprint"]["diff_files_hash"] == "old-diff"


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
    (tmp_path / "strategies/demo/demo.py").write_text("pass\n", encoding="utf-8")
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


def test_sync_rejects_stale_schema_v3_diff_fingerprint(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_v3_report(
        tmp_path,
        changed_files=["docs/guides/example.md"],
        diff_files_hash="old-diff",
    )
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="PR 流程自动化", runner=runner)

    assert code == 1
    assert "diff_fingerprint diff_files_hash does not match current diff" in capsys.readouterr().err
    assert not any(call[:3] == ["gh", "pr", "edit"] for call in runner.calls)


def test_sync_stops_after_pr_body_update_when_issue_ac_is_unchecked(
    tmp_path: Path,
) -> None:
    _write_valid_v4_issue_report(tmp_path, issue_number=50)

    class IssueAcRunner(FakeRunner):
        def run(
            self,
            command: list[str],
            *,
            cwd: Path | None = None,
            input_text: str | None = None,
        ) -> pr_flow.CommandResult:
            if command == ["gh", "issue", "view", "50", "--json", "title,body"]:
                self.calls.append(command)
                return pr_flow.CommandResult(
                    0,
                    json.dumps({"title": "Issue 50", "body": "- [ ] first AC\n"}),
                    "",
                )
            return super().run(command, cwd=cwd, input_text=input_text)

    runner = IssueAcRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="PR Flow issue gate", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert "Closes #50" in runner.edited_bodies[-1]
    status = json.loads(
        (tmp_path / ".local" / "pr-flow" / "last-status.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["state"] == "DISPATCH_REQUIRED"
    assert status["reason_code"] == "ISSUE_ACCEPTANCE_CRITERIA_INCOMPLETE"
    assert status["blocking_items"] == ["#50 Issue 50: - [ ] first AC"]


def test_sync_continues_when_linked_issue_ac_is_checked(
    tmp_path: Path,
) -> None:
    _write_valid_v4_issue_report(tmp_path, issue_number=50)

    class IssueAcRunner(FakeRunner):
        def run(
            self,
            command: list[str],
            *,
            cwd: Path | None = None,
            input_text: str | None = None,
        ) -> pr_flow.CommandResult:
            if command == ["gh", "issue", "view", "50", "--json", "title,body"]:
                self.calls.append(command)
                return pr_flow.CommandResult(
                    0,
                    json.dumps({"title": "Issue 50", "body": "- [x] first AC\n"}),
                    "",
                )
            return super().run(command, cwd=cwd, input_text=input_text)

    runner = IssueAcRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="PR Flow issue gate", runner=runner)

    assert code == 0
    assert "Closes #50" in runner.edited_bodies[-1]


def test_sync_migrates_legacy_report_to_schema_v4_before_rendering(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="low",
        requires_official=False,
        changed_files=["docs/guides/example.md"],
    )
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="PR 流程自动化", runner=runner)

    assert code == 0
    payload = json.loads(
        (tmp_path / ".local" / "ai-review" / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["schema_version"] == 4
    assert payload["diff_fingerprint"]["diff_files_hash"] == "current-diff"
    assert payload["spec_ref"] == {"issues": [], "design_docs": [], "adrs": []}
    assert payload["issue_refs"] == []
    assert "## 当前提交与差异摘要" in runner.edited_bodies[-1]


def test_sync_migrates_legacy_report_with_current_diff_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="low",
        requires_official=False,
        changed_files=["docs/guides/stale.md"],
    )
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/current.md"],
        },
    )
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="PR 流程自动化", runner=runner)

    assert code == 0
    payload = json.loads(
        (tmp_path / ".local" / "ai-review" / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["changed_files"] == ["docs/guides/current.md"]
    assert payload["diff_fingerprint"]["changed_files"] == ["docs/guides/current.md"]


def test_sync_uses_migrated_review_scope_for_codex_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/rules.py"],
    )
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["scripts/research/governance/pr_flow.py"],
        },
    )
    runner = FakeRunner(existing_pr=True)

    code = pr_flow.sync(repo_root=tmp_path, title="PR 流程自动化", runner=runner)

    assert code == 0
    assert runner.comments
    assert "scripts/research/governance/pr_flow.py" in runner.comments[-1]
    assert "scripts/research/governance/rules.py" not in runner.comments[-1]


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
    payload["checks"]["verify full"] = (
        ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full; passed"
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
    assert ".\\.venv\\Scripts\\python.exe" in edited


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


def test_sync_stops_with_push_required_when_remote_head_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(tmp_path)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/pull_request_template.md").write_text(
        "<!-- pr-flow:start -->\nold\n<!-- pr-flow:end -->\n",
        encoding="utf-8",
    )
    runner = MissingRemoteHeadRunner(existing_pr=False)

    code = pr_flow.sync(repo_root=tmp_path, title="文档更新", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "PUSH_REQUIRED" in captured.err
    assert "git push -u origin feature/pr-flow" in captured.err
    assert not any(call[:3] == ["gh", "pr", "create"] for call in runner.calls)


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
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

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


def test_ready_writes_structured_last_status_when_review_evidence_missing(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 1)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert "reason_code: LOCAL_AI_REVIEW_MISSING" in captured.err
    assert "phase: local_review" in captured.err

    status = json.loads(
        (tmp_path / ".local/pr-flow/last-status.json").read_text(encoding="utf-8")
    )
    assert status["state"] == "DISPATCH_REQUIRED"
    assert status["reason_code"] == "LOCAL_AI_REVIEW_MISSING"
    assert status["phase"] == "local_review"
    assert status["dispatch_target"] == "review-agent"
    assert status["next_actions"] == ["produce .local/ai-review/latest.json"]


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


def test_ready_stops_with_dispatch_required_when_review_fingerprint_drifts(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(tmp_path, changed_files=["docs/guides/example.md"])
    latest = tmp_path / ".local/ai-review/latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload.update(
        {
            "schema_version": 3,
            "diff_fingerprint": {
                "base_ref": "origin/main",
                "head_sha": "1" * 40,
                "diff_files_hash": "old-diff",
                "changed_files": ["docs/guides/example.md"],
            },
            "review_fragments": {
                "standards": {"evidence": "standards review completed"},
                "spec": {"evidence": "spec review completed"},
                "security": {"evidence": "security review completed"},
            },
            "external_findings": [],
            "current_commit_evidence": {"head_sha": "1" * 40, "checks": {}},
        }
    )
    latest.write_text(json.dumps(payload), encoding="utf-8")
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": [
                "docs/guides/example.md",
                "scripts/research/governance/pr_flow.py",
            ],
        },
        raising=False,
    )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert "DISPATCH_REQUIRED" in captured.err
    assert "LOCAL_AI_REVIEW_INVALID" in captured.err
    assert "diff_fingerprint changed_files does not match current diff" in captured.err
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


def test_ready_writes_ordered_merge_ready_state_without_merging(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="low",
        requires_official=False,
        changed_files=["docs/guides/example.md"],
    )
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="governance automation",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    state = json.loads(
        (tmp_path / ".local" / "pr-flow" / "state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["state"] == "merge-ready"
    assert state["completed_phases"] == [
        "preflight",
        "freeze_diff",
        "local_review",
        "security_review",
        "build_evidence",
        "official_codex",
        "threads",
        "sync_pr_body",
        "wait_latest_checks",
    ]
    assert state["next_action"] == "pr-complete"
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in runner.calls)


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
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

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
                "body": _codex_review_trigger_body(),
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
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

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


def test_ready_retriggers_when_existing_current_head_trigger_is_not_contract(
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
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == 0
    assert any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)


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
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
        fail_api_paths={"repos/liuli195/Quant-Trading/pulls/7/reviews?per_page=100"},
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

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
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["scripts/research/governance/pr_flow.py"],
        },
    )

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
    assert payload["official_codex_review"]["evidence"][0].endswith(
        "#pullrequestreview-1"
    )


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


def test_ready_auto_accepts_official_p2_thread_and_syncs_pr_body(
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
                "id": "PRRT_p2",
                "isResolved": False,
                "isOutdated": True,
                "comments": {
                    "nodes": [
                        {
                            "body": "P2: optional cleanup can wait.",
                            "author": {"login": "chatgpt-codex-connector"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="governance automation",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    captured = capsys.readouterr()
    assert "accepted official Codex review thread: PRRT_p2" in captured.out
    assert any(
        call[:3] == ["gh", "api", "graphql"]
        and any("addPullRequestReviewThreadReply" in item for item in call)
        for call in runner.calls
    )
    assert any(
        call[:3] == ["gh", "api", "graphql"]
        and any("resolveReviewThread" in item for item in call)
        and ["-F", "threadId=PRRT_p2"] in [
            call[index : index + 2] for index in range(len(call) - 1)
        ]
        for call in runner.calls
    )
    payload = json.loads(
        (tmp_path / ".local" / "ai-review" / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["external_findings"][0]["thread_id"] == "PRRT_p2"
    assert payload["external_findings"][0]["status"] == "accepted"
    assert len(runner.edited_bodies) >= 2
    assert "EXT-CODEX-THREAD-PRRT_p2" in runner.edited_bodies[-1]


def test_ready_blocks_official_thread_without_severity(
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
                "id": "PRRT_no_severity",
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "body": "This thread needs human classification.",
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
        title="governance automation",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "unresolved review thread" in capsys.readouterr().err
    assert not runner.thread_replies


def test_ready_blocks_human_unresolved_thread(
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
                "id": "PRRT_human",
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "body": "P2: human reviewer asks for a change.",
                            "author": {"login": "human-reviewer"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="governance automation",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "unresolved review thread" in capsys.readouterr().err
    assert not runner.thread_replies


def test_ready_auto_closes_outdated_p1_thread_with_structured_evidence(
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
    latest = tmp_path / ".local" / "ai-review" / "latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload["external_findings"] = [
        {
            "id": "EXT-CODEX-THREAD-PRRT_p1",
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_p1",
            "severity": "P1",
            "title": "Outdated blocker",
            "path": "scripts/research/governance/pr_flow.py",
            "status": "fixed",
            "evidence": "fixed by current diff and verified locally",
            "handling": "outdated finding fixed; close stale thread",
        }
    ]
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    runner = FakeRunner(
        existing_pr=True,
        api_review_threads=[
            {
                "id": "PRRT_p1",
                "isResolved": False,
                "isOutdated": True,
                "comments": {
                    "nodes": [
                        {
                            "body": "P1 Badge: stale blocker from old diff.",
                            "author": {"login": "chatgpt-codex-connector"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="governance automation",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "closed official Codex review thread: PRRT_p1" in capsys.readouterr().out
    assert runner.thread_replies
    assert "status: `fixed`" in runner.thread_replies[-1]["body"]


def test_ready_auto_closes_current_p1_thread_with_structured_evidence(
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
    latest = tmp_path / ".local" / "ai-review" / "latest.json"
    payload = json.loads(latest.read_text(encoding="utf-8"))
    payload["external_findings"] = [
        {
            "id": "EXT-CODEX-THREAD-PRRT_p1",
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_p1",
            "severity": "P1",
            "title": "Current blocker",
            "path": "scripts/research/governance/pr_flow.py",
            "status": "fixed",
            "evidence": "fixed by current head and verified locally",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
        }
    ]
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    runner = FakeRunner(
        existing_pr=True,
        api_review_threads=[
            {
                "id": "PRRT_p1",
                "isResolved": False,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "body": "P1 Badge: current blocker fixed by follow-up.",
                            "author": {"login": "chatgpt-codex-connector"},
                        }
                    ]
                },
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["docs/guides/example.md"],
        },
    )

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="governance automation",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "closed official Codex review thread: PRRT_p1" in capsys.readouterr().out
    assert runner.thread_replies
    assert "status: `fixed`" in runner.thread_replies[-1]["body"]


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
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["scripts/research/governance/pr_flow.py"],
        },
    )

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
                "body": _codex_review_trigger_body(),
                "created_at": "2026-05-28T09:00:00Z",
                "updated_at": "2026-05-28T09:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)
    monkeypatch.setattr(
        pr_flow.ai_review_gate,
        "current_diff_fingerprint",
        lambda _root: {
            "base_ref": "origin/main",
            "head_sha": "1" * 40,
            "diff_files_hash": "current-diff",
            "changed_files": ["scripts/research/governance/rules.py"],
        },
    )

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


def test_ready_for_review_marks_pr_ready_and_waits(tmp_path: Path) -> None:
    runner = ReadyForReviewRunner()

    code = pr_flow.ready_for_review(repo_root=tmp_path, pr="7", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["gh", "pr", "ready", "7"] in runner.calls
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


def test_merge_pr_uses_diagnose_and_match_head_commit(
    tmp_path: Path,
    capsys,
) -> None:
    runner = MergeReadyRunner()

    code = pr_flow.merge_pr(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert [
        "gh",
        "pr",
        "merge",
        "7",
        "--merge",
        "--match-head-commit",
        "1" * 40,
    ] in runner.calls
    assert "merge: PR #7 merged with head lock 111111111111" in captured.out
    assert "merge commit abc1234" in captured.out


def test_merge_pr_allows_unapproved_review_when_remote_does_not_require_approval(
    tmp_path: Path,
) -> None:
    runner = MergeReadyRunner()
    runner.review_decision = "REVIEW_REQUIRED"

    code = pr_flow.merge_pr(repo_root=tmp_path, pr="7", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert [
        "gh",
        "pr",
        "merge",
        "7",
        "--merge",
        "--match-head-commit",
        "1" * 40,
    ] in runner.calls


def test_merge_pr_blocks_when_local_head_differs_from_pr_head(
    tmp_path: Path,
    capsys,
) -> None:
    runner = MergeReadyRunner()
    runner.local_head = "2" * 40

    code = pr_flow.merge_pr(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "local HEAD does not match PR head" in captured.err
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in runner.calls)


def test_merge_pr_blocks_without_approved_review_decision(
    tmp_path: Path,
    capsys,
) -> None:
    runner = MergeReadyRunner()
    runner.review_decision = "REVIEW_REQUIRED"
    runner.required_approving_review_count = 1

    code = pr_flow.merge_pr(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "next: wait for approved review required by remote rules" in captured.out
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in runner.calls)


def test_cleanup_pr_syncs_main_and_deletes_merged_branch(
    tmp_path: Path,
    capsys,
) -> None:
    runner = CleanupRunner()

    code = pr_flow.cleanup_pr(repo_root=tmp_path, pr="7", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["git", "fetch", "--prune", "origin"] in runner.calls
    assert ["git", "switch", "main"] in runner.calls
    assert ["git", "merge", "--ff-only", "origin/main"] in runner.calls
    assert ["git", "branch", "-d", "feature/pr-flow"] in runner.calls
    assert ["git", "push", "origin", "--delete", "feature/pr-flow"] in runner.calls
    assert ["git", "ls-remote", "--heads", "origin", "feature/pr-flow"] in runner.calls
    assert "cleanup: PR #7 merged at 2026-05-29T16:48:26Z" in captured.out
    assert "cleanup: base main synced with origin/main" in captured.out
    assert "cleanup: local branch deleted: feature/pr-flow" in captured.out
    assert "cleanup: remote branch deleted: feature/pr-flow" in captured.out
    assert "cleanup: final base sync verified: main...origin/main = 0 0" in captured.out


def test_cleanup_pr_skips_head_branch_delete_for_fork_pr(tmp_path: Path) -> None:
    runner = CleanupRunner(is_cross_repository=True)

    code = pr_flow.cleanup_pr(repo_root=tmp_path, pr="7", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["git", "fetch", "--prune", "origin"] in runner.calls
    assert ["git", "switch", "main"] in runner.calls
    assert ["git", "merge", "--ff-only", "origin/main"] in runner.calls
    assert ["git", "branch", "-d", "feature/pr-flow"] not in runner.calls
    assert ["git", "push", "origin", "--delete", "feature/pr-flow"] not in runner.calls
    assert ["git", "ls-remote", "--heads", "origin", "feature/pr-flow"] not in runner.calls


def test_complete_pr_runs_ready_review_merge_and_cleanup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_ready(**kwargs: object) -> int:
        resolve_threads = kwargs.get("resolve_threads")
        assert isinstance(resolve_threads, tuple)
        calls.append(("ready", str(kwargs.get("title")), resolve_threads))
        return pr_flow.SUCCESS_EXIT_CODE

    def fake_ready_for_review(**kwargs: object) -> int:
        calls.append(("ready-for-review", str(kwargs.get("pr"))))
        return pr_flow.SUCCESS_EXIT_CODE

    def fake_merge_pr(**kwargs: object) -> int:
        calls.append(("merge", str(kwargs.get("pr"))))
        return pr_flow.SUCCESS_EXIT_CODE

    def fake_cleanup_pr(**kwargs: object) -> int:
        calls.append(("cleanup", str(kwargs.get("pr"))))
        return pr_flow.SUCCESS_EXIT_CODE

    monkeypatch.setattr(pr_flow, "ready", fake_ready)
    monkeypatch.setattr(pr_flow, "ready_for_review", fake_ready_for_review)
    monkeypatch.setattr(pr_flow, "merge_pr", fake_merge_pr)
    monkeypatch.setattr(pr_flow, "cleanup_pr", fake_cleanup_pr)
    monkeypatch.setattr(pr_flow, "_current_pr_number", lambda _root, _runner: "7")

    code = pr_flow.complete_pr(
        repo_root=tmp_path,
        title="PR 自动化",
        pr="7",
        resolve_threads=("PRRT_one",),
        runner=RecordingRunner(),
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert calls == [
        ("ready", "PR 自动化", ("PRRT_one",)),
        ("ready-for-review", "7"),
        ("merge", "7"),
        ("cleanup", "7"),
    ]
    assert "pr-complete: PR #7 complete" in captured.out


def test_complete_pr_rejects_explicit_pr_mismatch(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    ready_called = False

    def fake_ready(**_kwargs: object) -> int:
        nonlocal ready_called
        ready_called = True
        return pr_flow.SUCCESS_EXIT_CODE

    monkeypatch.setattr(pr_flow, "ready", fake_ready)
    monkeypatch.setattr(pr_flow, "_current_pr_number", lambda _root, _runner: "8")

    code = pr_flow.complete_pr(
        repo_root=tmp_path,
        title="PR 自动化",
        pr="7",
        runner=RecordingRunner(),
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "explicit PR does not match current branch PR" in captured.err
    assert not ready_called


def test_ready_resolves_threads_after_sync_before_wait(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_valid_report(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: pr_flow.SUCCESS_EXIT_CODE)
    monkeypatch.setattr(pr_flow, "sync", lambda **_kwargs: pr_flow.SUCCESS_EXIT_CODE)
    monkeypatch.setattr(
        pr_flow,
        "_current_pr_metadata",
        lambda _root, _runner, required: {
            "url": "https://github.com/liuli195/Quant-Trading/pull/7"
        },
    )
    def fake_blockers(**_kwargs: object) -> tuple[str, ...]:
        calls.append("blockers")
        return ()

    def fake_resolve(**_kwargs: object) -> int:
        calls.append("resolve")
        return pr_flow.SUCCESS_EXIT_CODE

    def fake_wait(**_kwargs: object) -> int:
        calls.append("wait")
        return pr_flow.SUCCESS_EXIT_CODE

    monkeypatch.setattr(pr_flow, "_current_head_codex_blocking_findings", fake_blockers)
    monkeypatch.setattr(pr_flow, "_current_pr_review_threads", lambda **_kwargs: [])
    monkeypatch.setattr(pr_flow, "resolve_review_threads", fake_resolve)
    monkeypatch.setattr(pr_flow, "wait", fake_wait)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="PR 自动化",
        runner=RecordingRunner(),
        resolve_threads=("PRRT_one",),
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert calls == ["resolve", "blockers", "wait"]
