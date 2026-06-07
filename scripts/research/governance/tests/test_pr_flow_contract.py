from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import pytest

from scripts.research.governance import (
    codex_review_monitor,
    pr_flow,
    pr_flow_contract,
    pr_review_evidence,
)


DEFAULT_DIFF_TEXT = "diff --git a/a.txt b/a.txt\n+hello\n"
DEFAULT_DIFF_HASH = hashlib.sha256(DEFAULT_DIFF_TEXT.encode("utf-8")).hexdigest()
DEFAULT_DELEGATION_ATTEMPT = {
    "required": True,
    "authorization_basis": "AGENTS.md + ADR 0009",
    "tool": "spawn_agent",
    "result": "spawned",
}
FIXED_CHECKPOINT_NAMES = {
    "official_codex_review",
    "required_checks",
    "pr_evidence",
    "review_threads",
    "local_review_fragments",
}


def test_submit_default_wait_timeout_is_ten_minutes() -> None:
    assert pr_flow.CODEX_REVIEW_WAIT_TIMEOUT_SECONDS == 10 * 60


def test_submit_default_codex_review_ack_timeout_is_three_minutes() -> None:
    assert pr_flow.CODEX_REVIEW_ACK_TIMEOUT_SECONDS == 3 * 60


def _submit_status(root: Path) -> dict[str, Any]:
    status = json.loads(
        (root / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert "schema" not in status
    assert "head" not in status
    assert "failures" not in status
    assert status["schema_version"] == 3
    return status


def _submit_status_path(root: Path) -> Path:
    return root / ".local/pr-flow/status.json"


def _blocking_signals(status: dict[str, Any]) -> list[dict[str, Any]]:
    signals = status.get("blocking_signals")
    assert isinstance(signals, list)
    return [signal for signal in signals if isinstance(signal, dict)]


def _blocking_as_legacy_failures(
    status: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "check": signal["source_context"],
            "source": signal["evidence_location"],
            "detail": signal["summary"],
        }
        for signal in _blocking_signals(status)
    ]


def _diagnostic_signals(status: dict[str, Any]) -> list[dict[str, Any]]:
    signals = status.get("diagnostic_signals")
    assert isinstance(signals, list)
    return [signal for signal in signals if isinstance(signal, dict)]


def _checkpoint_statuses(status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checkpoints = status.get("checkpoint_statuses")
    assert isinstance(checkpoints, list)
    parsed = {
        str(checkpoint["checkpoint_name"]): checkpoint
        for checkpoint in checkpoints
        if isinstance(checkpoint, dict) and "checkpoint_name" in checkpoint
    }
    assert set(parsed) == FIXED_CHECKPOINT_NAMES
    return parsed


def _evidence_artifacts(status: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = status.get("evidence_artifacts")
    assert isinstance(artifacts, list)
    return [artifact for artifact in artifacts if isinstance(artifact, dict)]


class SubmitPreflightRunner:
    def __init__(self, *, valid_contract: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.valid_contract = valid_contract

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.calls.append(command)
        if command == ["git", "rev-parse", "HEAD"]:
            return pr_flow.CommandResult(0, "1" * 40 + "\n", "")
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "origin/main...HEAD",
        ]:
            return pr_flow.CommandResult(0, DEFAULT_DIFF_TEXT, "")
        if command == ["git", "branch", "--show-current"]:
            return pr_flow.CommandResult(0, "feature/contract\n", "")
        if command == ["git", "rev-list", "--reverse", "origin/main..HEAD"]:
            return pr_flow.CommandResult(0, "", "")
        if command[:4] == ["git", "show", "-s", "--format=%P%n%s"]:
            return pr_flow.CommandResult(0, "0" * 40 + "\nregular commit\n", "")
        if command == ["gh", "pr", "view", "--json", "number,url,state,isDraft"]:
            return pr_flow.CommandResult(1, "", "no pull request")
        if command == ["gh", "repo", "view", "--json", "nameWithOwner"]:
            return pr_flow.CommandResult(
                0,
                json.dumps({"nameWithOwner": "liuli195/Quant-Trading"}),
                "",
            )
        if command == ["gh", "api", "repos/liuli195/Quant-Trading"]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "allow_auto_merge": self.valid_contract,
                        "delete_branch_on_merge": True,
                    }
                ),
                "",
            )
        if command == [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/liuli195/Quant-Trading/rulesets?includes_parents=true",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        [
                            {
                                "id": 1,
                                "target": "branch",
                                "enforcement": "active",
                                "conditions": {
                                    "ref_name": {"include": ["main"], "exclude": []}
                                },
                                "rules": [
                                    {
                                        "type": "required_status_checks",
                                        "parameters": {
                                            "required_status_checks": [
                                                {"context": "PR Flow / review-status"},
                                                *(
                                                    [
                                                        {
                                                            "context": "Research Governance / verify-full"
                                                        },
                                                        {"context": "PR Flow / evidence"},
                                                    ]
                                                    if self.valid_contract
                                                    else []
                                                ),
                                            ]
                                        },
                                    }
                                ],
                            }
                        ]
                    ]
                ),
                "",
            )
        if command == [
            "gh",
            "api",
            "repos/liuli195/Quant-Trading/branches/main/protection/required_status_checks",
        ]:
            return pr_flow.CommandResult(1, "", "404 Not Found")
        raise AssertionError(f"unexpected command: {command}")


class SubmitCreatePrRunner(SubmitPreflightRunner):
    def __init__(
        self,
        *,
        diff_text: str,
        checks_bucket: str = "pass",
        checks_returncode: int = 0,
        existing_pr: bool = False,
        existing_state: str = "OPEN",
        existing_body: str = "",
        preexisting_comments: list[dict[str, object]] | None = None,
        merge_returncode: int = 0,
        merge_stdout: str = "auto-merge enabled\n",
        merge_stderr: str = "",
        changed_files_output: str = "docs/guides/example.md\n",
        main_worktree_path: str | None = None,
        cleanup_status_output: str = "# branch.oid 1111111111111111111111111111111111111111\n# branch.head main\n",
        comment_reactions_by_id: dict[str, list[dict[str, object]]] | None = None,
        ack_generated_comments: bool = True,
    ) -> None:
        super().__init__(valid_contract=True)
        self.diff_text = diff_text
        self.checks_bucket = checks_bucket
        self.checks_returncode = checks_returncode
        self.existing_pr = existing_pr
        self.existing_state = existing_state
        self.existing_body = existing_body
        self.preexisting_comments = preexisting_comments or []
        self.merge_returncode = merge_returncode
        self.merge_stdout = merge_stdout
        self.merge_stderr = merge_stderr
        self.changed_files_output = changed_files_output
        self.main_worktree_path = main_worktree_path
        self.cleanup_status_output = cleanup_status_output
        self.comment_reactions_by_id = comment_reactions_by_id or {}
        self.ack_generated_comments = ack_generated_comments
        self.auto_merge_requested = existing_state.upper() == "MERGED"
        self.created_bodies: list[str] = []
        self.edited_bodies: list[str] = []
        self.body_file_names: list[str] = []
        self.comments: list[str] = []
        self.lifecycle_calls: list[list[str]] = []
        self.cwd_calls: list[tuple[list[str], Path | None]] = []
        self.ordered_calls: list[list[str]] = []

    def _status_rollup_command(self) -> list[str]:
        return [
            "gh",
            "pr",
            "view",
            "88",
            "--json",
            pr_flow.STATUS_CHECK_ROLLUP_JSON_FIELDS,
        ]

    def _status_rollup_result(
        self,
        items: list[dict[str, object]],
    ) -> pr_flow.CommandResult:
        return pr_flow.CommandResult(
            0,
            json.dumps(
                {
                    "url": "https://github.com/liuli195/Quant-Trading/pull/88",
                    "baseRefName": "main",
                    "isDraft": False,
                    "headRefOid": "1" * 40,
                    "statusCheckRollup": items,
                }
            ),
            "",
        )

    def _status_rollup_item(
        self,
        *,
        name: str,
        workflow: str = "",
        state: str = "SUCCESS",
        link: str = "",
        head_sha: str = "1" * 40,
    ) -> dict[str, object]:
        return {
            "name": name,
            "workflowName": workflow,
            "state": state,
            "detailsUrl": link,
            "startedAt": "2026-06-01T00:02:00Z",
            "completedAt": "2026-06-01T00:03:00Z" if state == "SUCCESS" else "",
            "headSha": head_sha,
        }

    def _default_status_rollup_items(self) -> list[dict[str, object]]:
        review_state = {
            "pass": "SUCCESS",
            "pending": "PENDING",
            "fail": "FAILURE",
        }.get(self.checks_bucket, self.checks_bucket.upper())
        return [
            self._status_rollup_item(
                name="review-status",
                workflow="PR Flow",
                state=review_state,
            ),
            self._status_rollup_item(
                name="verify-full",
                workflow="Research Governance",
                link="https://github.com/runs/1",
            ),
            self._status_rollup_item(
                name="evidence",
                workflow="PR Flow",
                link="https://github.com/runs/2",
            ),
        ]

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        self.ordered_calls.append(command)
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--binary",
            "--no-ext-diff",
            "origin/main...HEAD",
        ]:
            return pr_flow.CommandResult(0, self.diff_text, "")
        if command == [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-only",
            "origin/main...HEAD",
        ]:
            return pr_flow.CommandResult(0, self.changed_files_output, "")
        if command == ["git", "branch", "--show-current"]:
            return pr_flow.CommandResult(0, "feature/contract\n", "")
        if command == ["git", "rev-list", "--reverse", "origin/main..HEAD"]:
            return pr_flow.CommandResult(0, "1" * 40 + "\n" + "2" * 40 + "\n", "")
        if command[:3] == ["gh", "issue", "view"]:
            return pr_flow.CommandResult(
                0,
                json.dumps({"title": f"Issue {command[3]}", "body": "- [x] done\n"}),
                "",
            )
        if command in (
            ["gh", "pr", "view", "--json", "number,url,state,isDraft"],
            ["gh", "pr", "view", "88", "--json", "number,url,state,isDraft"],
        ):
            if not self.existing_pr:
                return pr_flow.CommandResult(1, "", "no pull request")
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "number": 88,
                        "url": "https://github.com/liuli195/Quant-Trading/pull/88",
                        "state": self.existing_state,
                        "isDraft": self.existing_state.upper() != "MERGED",
                    }
                ),
                "",
            )
        if command in (
            ["gh", "pr", "view", "--json", "body"],
            ["gh", "pr", "view", "88", "--json", "body"],
        ):
            body = (
                self.edited_bodies[-1]
                if self.edited_bodies
                else self.created_bodies[-1]
                if self.created_bodies
                else self.existing_body
            )
            return pr_flow.CommandResult(0, json.dumps({"body": body}), "")
        if command in (
            ["gh", "pr", "view", "--json", "headRefOid"],
            ["gh", "pr", "view", "88", "--json", "headRefOid"],
        ):
            return pr_flow.CommandResult(0, json.dumps({"headRefOid": "1" * 40}), "")
        if command == [
            "gh",
            "pr",
            "view",
            "88",
            "--json",
            pr_flow.STATUS_CHECK_ROLLUP_JSON_FIELDS,
        ]:
            return self._status_rollup_result(self._default_status_rollup_items())
        if command[:4] == ["gh", "pr", "edit", "88"]:
            body_file = Path(command[command.index("--body-file") + 1])
            self.body_file_names.append(body_file.name)
            self.edited_bodies.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(0, "", "")
        if command == [
            "git",
            "ls-remote",
            "--heads",
            "origin",
            "feature/contract",
        ]:
            return pr_flow.CommandResult(
                0,
                "1" * 40 + "\trefs/heads/feature/contract\n",
                "",
            )
        if command[:3] == ["gh", "pr", "create"]:
            body_file = Path(command[command.index("--body-file") + 1])
            self.body_file_names.append(body_file.name)
            self.created_bodies.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(
                0,
                "https://github.com/liuli195/Quant-Trading/pull/88\n",
                "",
            )
        if command[:3] == ["gh", "pr", "comment"]:
            body_file = Path(command[command.index("--body-file") + 1])
            body = body_file.read_text(encoding="utf-8")
            self.comments.append(body)
            comment_id = str(1000 + len(self.comments))
            self.preexisting_comments.append(
                {
                    "id": int(comment_id),
                    "body": body,
                    "created_at": "2026-06-01T10:05:00Z",
                    "updated_at": "2026-06-01T10:05:00Z",
                    "user": {"login": "liuli195"},
                }
            )
            if self.ack_generated_comments:
                self.comment_reactions_by_id.setdefault(
                    comment_id,
                    [
                        _codex_eyes_reaction(
                            created_at="2026-06-01T10:05:01Z",
                        )
                    ],
                )
            return pr_flow.CommandResult(0, "", "")
        if command[:3] == ["gh", "api", "graphql"]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [],
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
        if command == [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/liuli195/Quant-Trading/issues/88/comments?per_page=100",
        ]:
            return pr_flow.CommandResult(0, json.dumps([self.preexisting_comments]), "")
        if command == [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/liuli195/Quant-Trading/pulls/88/reviews?per_page=100",
        ]:
            return pr_flow.CommandResult(0, json.dumps([[]]), "")
        if (
            command[:4] == ["gh", "api", "--paginate", "--slurp"]
            and command[4].startswith(
                "repos/liuli195/Quant-Trading/issues/comments/"
            )
            and command[4].endswith("/reactions?per_page=100")
        ):
            comment_id = command[4].split("/issues/comments/", 1)[1].split("/", 1)[0]
            return pr_flow.CommandResult(
                0,
                json.dumps([self.comment_reactions_by_id.get(comment_id, [])]),
                "",
            )
        if command == ["gh", "pr", "ready", "88"]:
            self.lifecycle_calls.append(command)
            return pr_flow.CommandResult(0, "", "")
        if command == [
            "gh",
            "pr",
            "merge",
            "88",
            "--merge",
            "--auto",
            "--match-head-commit",
            "1" * 40,
        ]:
            self.lifecycle_calls.append(command)
            self.auto_merge_requested = True
            return pr_flow.CommandResult(
                self.merge_returncode,
                self.merge_stdout,
                self.merge_stderr,
            )
        if command == [
            "gh",
            "pr",
            "view",
            "88",
            "--json",
            "number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
        ]:
            self.lifecycle_calls.append(command)
            state = "MERGED" if self.auto_merge_requested else "OPEN"
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "number": 88,
                        "state": state,
                        "mergedAt": "2026-06-01T10:00:00Z"
                        if state == "MERGED"
                        else None,
                        "headRefName": "feature/contract",
                        "baseRefName": "main",
                        "isCrossRepository": False,
                    }
                ),
                "",
            )
        if command in (
            ["git", "fetch", "--prune", "origin"],
            ["git", "worktree", "list", "--porcelain"],
            ["git", "switch", "main"],
            ["git", "switch", "--detach", "origin/main"],
            ["git", "merge", "--ff-only", "origin/main"],
            ["git", "branch", "-d", "feature/contract"],
            ["git", "rev-list", "--left-right", "--count", "main...origin/main"],
            ["git", "status", "--porcelain=v2", "--branch"],
        ):
            if command == ["git", "worktree", "list", "--porcelain"]:
                if self.main_worktree_path is not None:
                    return pr_flow.CommandResult(
                        0,
                        "worktree /repo\n"
                        "branch refs/heads/feature/contract\n\n"
                        f"worktree {self.main_worktree_path}\n"
                        "branch refs/heads/main\n",
                        "",
                    )
                return pr_flow.CommandResult(
                    0,
                        "worktree /repo\nbranch refs/heads/feature/contract\n",
                        "",
                    )
            if command == ["git", "status", "--porcelain=v2", "--branch"]:
                self.lifecycle_calls.append(command)
                self.cwd_calls.append((command, cwd))
                return pr_flow.CommandResult(0, self.cleanup_status_output, "")
            self.lifecycle_calls.append(command)
            self.cwd_calls.append((command, cwd))
            if command == [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                "main...origin/main",
            ]:
                return pr_flow.CommandResult(0, "0\t0\n", "")
            return pr_flow.CommandResult(0, "", "")
        return super().run(command, cwd=cwd, input_text=input_text)


class MissingSubmitRemoteHeadRunner(SubmitCreatePrRunner):
    def __init__(self, *, diff_text: str, push_returncode: int = 0) -> None:
        super().__init__(diff_text=diff_text)
        self.push_returncode = push_returncode
        self.pushed_remote = False

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == [
            "git",
            "ls-remote",
            "--heads",
            "origin",
            "feature/contract",
        ]:
            if self.pushed_remote:
                return pr_flow.CommandResult(
                    0,
                    "1" * 40 + "\trefs/heads/feature/contract\n",
                    "",
                )
            return pr_flow.CommandResult(0, "", "")
        if command == ["git", "push", "-u", "origin", "HEAD:feature/contract"]:
            self.lifecycle_calls.append(command)
            if self.push_returncode != 0:
                return pr_flow.CommandResult(
                    self.push_returncode,
                    "",
                    "remote rejected feature/contract",
                )
            self.pushed_remote = True
            return pr_flow.CommandResult(0, "", "")
        return super().run(command, cwd=cwd, input_text=input_text)


class MismatchedAutoPushRemoteHeadRunner(MissingSubmitRemoteHeadRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if (
            self.pushed_remote
            and command
            == ["git", "ls-remote", "--heads", "origin", "feature/contract"]
        ):
            return pr_flow.CommandResult(
                0,
                "2" * 40 + "\trefs/heads/feature/contract\n",
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class MainBranchMissingSubmitRemoteHeadRunner(MissingSubmitRemoteHeadRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == ["git", "branch", "--show-current"]:
            return pr_flow.CommandResult(0, "main\n", "")
        if command == ["git", "ls-remote", "--heads", "origin", "main"]:
            return pr_flow.CommandResult(0, "", "")
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitUpdateBranchMergeRunner(SubmitCreatePrRunner):
    update_branch_sha = "3" * 40
    parents = "1" * 40 + " " + "9" * 40

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == ["git", "rev-list", "--reverse", "origin/main..HEAD"]:
            return pr_flow.CommandResult(
                0,
                "1" * 40 + "\n" + "2" * 40 + "\n" + self.update_branch_sha + "\n",
                "",
            )
        if command == [
            "git",
            "show",
            "-s",
            "--format=%P%n%s",
            self.update_branch_sha,
        ]:
            return pr_flow.CommandResult(
                0,
                self.parents + "\nMerge branch 'main' into feature/contract\n",
                "",
            )
        if command == [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            "repos/liuli195/Quant-Trading/pulls/88/commits?per_page=100",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        [
                            {
                                "sha": self.update_branch_sha,
                                "author": {"login": "web-flow"},
                                "committer": {"login": "web-flow"},
                                "commit": {
                                    "author": {
                                        "name": "GitHub",
                                        "email": "noreply@github.com",
                                    },
                                    "committer": {
                                        "name": "GitHub",
                                        "email": "noreply@github.com",
                                    },
                                },
                            }
                        ]
                    ]
                ),
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitUpdateBranchSubjectOnlyRunner(SubmitUpdateBranchMergeRunner):
    parents = "1" * 40


class SubmitForgedUpdateBranchMergeRunner(SubmitUpdateBranchMergeRunner):
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
            "repos/liuli195/Quant-Trading/pulls/88/commits?per_page=100",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        [
                            {
                                "sha": self.update_branch_sha,
                                "author": {"login": "liuli195"},
                                "committer": {"login": "liuli195"},
                                "commit": {
                                    "author": {
                                        "name": "liuli195",
                                        "email": "liuli195@example.invalid",
                                    },
                                    "committer": {
                                        "name": "liuli195",
                                        "email": "liuli195@example.invalid",
                                    },
                                },
                            }
                        ]
                    ]
                ),
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitForgedRawGithubUpdateBranchMergeRunner(SubmitUpdateBranchMergeRunner):
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
            "repos/liuli195/Quant-Trading/pulls/88/commits?per_page=100",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        [
                            {
                                "sha": self.update_branch_sha,
                                "author": {"login": "liuli195"},
                                "committer": {"login": "liuli195"},
                                "commit": {
                                    "author": {
                                        "name": "GitHub",
                                        "email": "noreply@github.com",
                                    },
                                    "committer": {
                                        "name": "GitHub",
                                        "email": "github@users.noreply.github.com",
                                    },
                                },
                            }
                        ]
                    ]
                ),
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitFailingChecksRunner(SubmitCreatePrRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == self._status_rollup_command():
            return self._status_rollup_result(
                [
                    self._status_rollup_item(
                        name="evidence",
                        workflow="PR Flow",
                        state="FAILURE",
                        link="https://github.com/runs/evidence",
                    ),
                    self._status_rollup_item(
                        name="verify-full",
                        workflow="Research Governance",
                        state="FAILURE",
                        link="https://github.com/runs/verify",
                    ),
                    self._status_rollup_item(
                        name="review-status",
                        workflow="PR Flow",
                        state="FAILURE",
                        link="https://github.com/runs/review",
                    ),
                ]
            )
        if command[:3] == ["gh", "api", "graphql"] and any(
            "reviewThreads" in part for part in command
        ):
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [],
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
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitEmptyRequiredChecksWindowRunner(SubmitCreatePrRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == self._status_rollup_command():
            return self._status_rollup_result([])
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitRawStatusRollupRequiredNamesRunner(SubmitCreatePrRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == self._status_rollup_command():
            return self._status_rollup_result(
                [
                    self._status_rollup_item(name="review-status"),
                    self._status_rollup_item(name="verify-full"),
                    self._status_rollup_item(name="evidence"),
                ]
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitUnavailableStatusRollupRunner(SubmitCreatePrRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == self._status_rollup_command():
            return pr_flow.CommandResult(1, "", "status rollup unavailable")
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitCurrentHeadCodexOutputRunner(SubmitCreatePrRunner):
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
            "repos/liuli195/Quant-Trading/pulls/88/reviews?per_page=100",
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        [
                            {
                                "id": 4314779358,
                                "commit_id": "1" * 40,
                                "submitted_at": "2026-06-01T10:06:00Z",
                                "body": "### Codex Review\n\nNo blocking findings.",
                                "user": {
                                    "login": "chatgpt-codex-connector[bot]",
                                },
                            }
                        ]
                    ]
                ),
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitDraftStatusRollupRunner(SubmitCreatePrRunner):
    def _status_rollup_result(
        self,
        items: list[dict[str, object]],
    ) -> pr_flow.CommandResult:
        result = super()._status_rollup_result(items)
        payload = json.loads(result.stdout)
        payload["isDraft"] = True
        return pr_flow.CommandResult(0, json.dumps(payload), "")


class SubmitMismatchedHeadRunner(SubmitEmptyRequiredChecksWindowRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command in (
            ["gh", "pr", "view", "--json", "headRefOid"],
            ["gh", "pr", "view", "88", "--json", "headRefOid"],
        ):
            return pr_flow.CommandResult(0, json.dumps({"headRefOid": "0" * 40}), "")
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitMixedFailingPendingChecksRunner(SubmitCreatePrRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == self._status_rollup_command():
            return self._status_rollup_result(
                [
                    self._status_rollup_item(
                        name="review-status",
                        workflow="PR Flow",
                        link="https://github.com/runs/review",
                    ),
                    self._status_rollup_item(
                        name="verify-full",
                        workflow="Research Governance",
                        state="FAILURE",
                        link="https://github.com/runs/verify",
                    ),
                    self._status_rollup_item(
                        name="evidence",
                        workflow="PR Flow",
                        state="PENDING",
                        link="https://github.com/runs/evidence",
                    ),
                ]
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitLocalStablePendingRunner(SubmitCreatePrRunner):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        if command == self._status_rollup_command():
            return self._status_rollup_result(
                [
                    self._status_rollup_item(
                        name="review-status",
                        workflow="PR Flow",
                    ),
                    self._status_rollup_item(
                        name="verify-full",
                        workflow="Research Governance",
                        state="PENDING",
                        link="https://github.com/runs/verify",
                    ),
                    self._status_rollup_item(
                        name="evidence",
                        workflow="PR Flow",
                        state="PENDING",
                        link="https://github.com/runs/evidence",
                    ),
                ]
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitStaleRequiredCheckRunner(SubmitCreatePrRunner):
    def __init__(
        self,
        *,
        diff_text: str,
        current_review_bucket: str,
        current_review_state: str,
        verify_bucket: str = "pass",
        verify_state: str = "SUCCESS",
    ) -> None:
        super().__init__(diff_text=diff_text)
        self.current_review_bucket = current_review_bucket
        self.current_review_state = current_review_state
        self.verify_bucket = verify_bucket
        self.verify_state = verify_state

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
            "view",
            "88",
            "--json",
            pr_flow.STATUS_CHECK_ROLLUP_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "url": "https://github.com/liuli195/Quant-Trading/pull/88",
                        "baseRefName": "main",
                        "isDraft": False,
                        "headRefOid": "1" * 40,
                        "statusCheckRollup": [
                            {
                                "name": "PR Flow / review-status",
                                "state": "FAILURE",
                                "detailsUrl": "https://github.com/runs/review-old",
                                "startedAt": "2026-06-01T00:00:00Z",
                                "completedAt": "2026-06-01T00:01:00Z",
                                "headSha": "0" * 40,
                            },
                            {
                                "name": "PR Flow / review-status",
                                "state": self.current_review_state,
                                "detailsUrl": "https://github.com/runs/review-current",
                                "startedAt": "2026-06-01T00:02:00Z",
                                "completedAt": "2026-06-01T00:03:00Z"
                                if self.current_review_bucket == "pass"
                                else "",
                                "headSha": "1" * 40,
                            },
                            {
                                "name": "verify-full",
                                "workflowName": "Research Governance",
                                "state": self.verify_state,
                                "detailsUrl": "https://github.com/runs/verify",
                                "startedAt": "2026-06-01T00:02:00Z",
                                "completedAt": "2026-06-01T00:03:00Z",
                                "headSha": "1" * 40,
                            },
                            {
                                "name": "evidence",
                                "workflowName": "PR Flow",
                                "state": "SUCCESS",
                                "detailsUrl": "https://github.com/runs/evidence",
                                "startedAt": "2026-06-01T00:02:00Z",
                                "completedAt": "2026-06-01T00:03:00Z",
                                "headSha": "1" * 40,
                            },
                        ],
                    }
                ),
                "",
            )
        return super().run(command, cwd=cwd, input_text=input_text)


class SubmitOfficialCodexRetainedRunner(SubmitCreatePrRunner):
    def __init__(
        self,
        *,
        diff_text: str,
        thread_author: str = "chatgpt-codex-connector[bot]",
        thread_body: str = "**P2** retain as follow-up",
    ) -> None:
        super().__init__(diff_text=diff_text)
        self.checks_calls = 0
        self.thread_id = "PRRT_official_p2"
        self.thread_author = thread_author
        self.thread_body = thread_body
        self.replies: list[str] = []
        self.resolved_threads: list[str] = []

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        joined = "\n".join(command)
        if command == self._status_rollup_command():
            self.checks_calls += 1
            # If thread was already resolved by pre-CI auto-processing,
            # return success on the first call. Otherwise fail and retry.
            already_resolved = bool(self.resolved_threads)
            review_state = (
                "FAILURE" if (self.checks_calls == 1 and not already_resolved) else "SUCCESS"
            )
            return self._status_rollup_result(
                [
                    self._status_rollup_item(
                        name="review-status",
                        workflow="PR Flow",
                        state=review_state,
                        link="https://github.com/checks/review",
                    ),
                    self._status_rollup_item(
                        name="verify-full",
                        workflow="Research Governance",
                        link="https://github.com/runs/1",
                    ),
                    self._status_rollup_item(
                        name="evidence",
                        workflow="PR Flow",
                        link="https://github.com/runs/2",
                    ),
                ]
            )
        if "addPullRequestReviewThreadReply" in joined:
            body = next(
                (item.removeprefix("body=") for item in command if item.startswith("body=")),
                "",
            )
            self.replies.append(body)
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "addPullRequestReviewThreadReply": {
                                "comment": {"id": "comment-id"}
                            }
                        }
                    }
                ),
                "",
            )
        if "resolveReviewThread" in joined:
            thread_id = next(
                (
                    item.removeprefix("threadId=")
                    for item in command
                    if item.startswith("threadId=")
                ),
                "",
            )
            self.resolved_threads.append(thread_id)
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "resolveReviewThread": {
                                "thread": {"id": thread_id, "isResolved": True}
                            }
                        }
                    }
                ),
                "",
            )
        if "node(id:$threadId)" in joined:
            thread_id = next(
                (
                    item.removeprefix("threadId=")
                    for item in command
                    if item.startswith("threadId=")
                ),
                "",
            )
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "node": {"id": thread_id, "isResolved": True}
                        }
                    }
                ),
                "",
            )
        if "reviewThreads" in joined:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [
                                            {
                                                "id": self.thread_id,
                                                "isResolved": False,
                                                "isOutdated": False,
                                                "comments": {
                                                    "nodes": [
                                                        {
                                                            "body": self.thread_body,
                                                            "author": {
                                                                "login": self.thread_author
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
        return super().run(command, cwd=cwd, input_text=input_text)


def test_contract_loads_required_checks_and_writes_submit_status_snapshot_v3(
    tmp_path: Path,
) -> None:
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.required_checks == (
        "PR Flow / review-status",
        "Research Governance / verify-full",
        "PR Flow / evidence",
    )
    assert contract.pr_evidence_fields == (
        "schema",
        "head",
        "diff",
        "reviews",
        "official_review",
        "issues",
        "retained",
    )
    assert contract.submit_status_fields == (
        "schema_version",
        "snapshot_subject",
        "pr_submit_stop",
        "checkpoint_statuses",
        "blocking_signals",
        "diagnostic_signals",
        "suggested_next_actions",
        "evidence_artifacts",
    )

    status_path = pr_flow_contract.write_submit_status(
        tmp_path,
        contract,
        head="1" * 40,
        repository="liuli195/Quant-Trading",
        pr_number="88",
        head_branch="feature/contract",
        stop_state="EXCEPTION_REQUIRED",
        reason_code="REQUIRED_CHECKS_FAILED",
        phase="submit_wait_checks",
        retryable=True,
        failures=[
            pr_flow_contract.SubmitFailure(
                check="PR Flow / evidence",
                source="https://github.com/liuli195/Quant-Trading/actions/runs/1",
                detail="line one\nline two " + ("x" * 260),
            )
        ],
    )

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert list(payload) == [
        "schema_version",
        "snapshot_subject",
        "pr_submit_stop",
        "checkpoint_statuses",
        "blocking_signals",
        "diagnostic_signals",
        "suggested_next_actions",
        "evidence_artifacts",
    ]
    assert "schema" not in payload
    assert "head" not in payload
    assert "failures" not in payload
    assert payload["schema_version"] == 3
    assert payload["snapshot_subject"] == {
        "repository": "liuli195/Quant-Trading",
        "pr_number": "88",
        "head_sha": "1" * 40,
        "head_branch": "feature/contract",
    }
    expected_detail = pr_flow_contract.normalize_detail(
        "line one\nline two " + ("x" * 260),
        max_chars=contract.detail_max_chars,
    )
    expected_summary = pr_flow_contract.normalize_detail(
        f"PR Flow / evidence: {expected_detail}",
        max_chars=contract.detail_max_chars,
    )
    assert payload["pr_submit_stop"] == {
        "state": "EXCEPTION_REQUIRED",
        "reason_code": "REQUIRED_CHECKS_FAILED",
        "phase": "submit_wait_checks",
        "is_retryable": True,
        "summary": expected_summary,
    }
    assert {
        checkpoint["checkpoint_name"]
        for checkpoint in payload["checkpoint_statuses"]
    } == FIXED_CHECKPOINT_NAMES
    assert payload["blocking_signals"] == [
        {
            "signal_type": "required_check_failed",
            "summary": expected_detail,
            "source_context": "PR Flow / evidence",
            "evidence_location": "https://github.com/liuli195/Quant-Trading/actions/runs/1",
            "currentness": "current",
            "is_retryable": True,
        }
    ]
    assert payload["diagnostic_signals"] == []
    assert payload["suggested_next_actions"]
    assert payload["evidence_artifacts"] == []


def test_contract_rejects_legacy_submit_status_fields(tmp_path: Path) -> None:
    source = Path("docs/rules/pr-flow-interface-contract.yaml").read_text(
        encoding="utf-8"
    )
    legacy = source.replace(
        "  fields:\n"
        "    - schema_version\n"
        "    - snapshot_subject\n"
        "    - pr_submit_stop\n"
        "    - checkpoint_statuses\n"
        "    - blocking_signals\n"
        "    - diagnostic_signals\n"
        "    - suggested_next_actions\n"
        "    - evidence_artifacts\n",
        "  fields:\n"
        "    - schema\n"
        "    - head\n"
        "    - failures\n",
    )
    path = tmp_path / "docs" / "rules" / "pr-flow-interface-contract.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(legacy, encoding="utf-8")

    with pytest.raises(ValueError, match="legacy submit_status fields"):
        pr_flow_contract.load_contract(tmp_path)


def test_auto_review_thread_action_requires_codex_root_comment() -> None:
    thread = {
        "id": "PRRT_human_root",
        "isResolved": False,
        "isOutdated": False,
        "comments": {
            "nodes": [
                {
                    "body": "human reviewer opened this thread",
                    "author": {"login": "liuli195"},
                },
                {
                    "body": "**P2** official Codex later replied",
                    "author": {"login": "chatgpt-codex-connector"},
                },
            ]
        },
    }

    assert pr_flow._thread_is_official_codex(thread) is False
    assert pr_flow._auto_review_thread_action(thread, {}) == ""


def test_auto_review_thread_action_rejects_stale_closure_evidence() -> None:
    thread = {
        "id": "PRRT_codex_p1",
        "isResolved": False,
        "isOutdated": False,
        "comments": {
            "nodes": [
                {
                    "body": "**P1** current head blocker",
                    "author": {"login": "chatgpt-codex-connector"},
                }
            ]
        },
    }
    payload = {
        "diff_fingerprint": {
            "head_sha": "1" * 40,
            "diff_files_hash": "old-diff",
        },
        "external_findings": [
            {
                "source": "official_codex_review_thread",
                "thread_id": "PRRT_codex_p1",
                "severity": "P1",
                "status": "fixed",
                "evidence": "fixed in old head",
                "head_sha": "1" * 40,
                "diff_files_hash": "old-diff",
                "fix_commit": "1" * 40,
                "verification_command": "pytest old",
            }
        ],
    }

    assert (
        pr_flow._closed_external_finding_for_thread(
            payload,
            thread,
            current_head_sha="2" * 40,
            current_diff_hash="new-diff",
        )
        is None
    )
    assert (
        pr_flow._auto_review_thread_action(
            thread,
            payload,
            current_head_sha="2" * 40,
            current_diff_hash="new-diff",
        )
        == ""
    )


def test_submit_fails_fast_when_github_contract_preflight_is_missing(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner()

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert status["snapshot_subject"]["head_sha"] == "1" * 40
    assert status["pr_submit_stop"]["state"] == "EXCEPTION_REQUIRED"
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "github-settings",
            "source": "repos/liuli195/Quant-Trading",
            "detail": "allow_auto_merge must be enabled",
        },
        {
            "check": "required-checks",
            "source": "main",
            "detail": "missing required checks: Research Governance / verify-full, PR Flow / evidence",
        },
    ]


def test_submit_writes_submit_status_on_non_zero_exit(
    tmp_path: Path,
) -> None:
    """Non-zero pr-submit exits write the v3 handoff snapshot."""
    runner = SubmitPreflightRunner(valid_contract=True)
    # missing fragments should cause DISPATCH_REQUIRED
    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert status["snapshot_subject"]["head_sha"] == "1" * 40
    assert status["pr_submit_stop"]["state"] == "DISPATCH_REQUIRED"
    assert _blocking_signals(status)
    assert set(_blocking_signals(status)[0]) == {
        "signal_type",
        "summary",
        "source_context",
        "evidence_location",
        "currentness",
        "is_retryable",
    }


def test_submit_writes_submit_status_when_auto_merge_fails(tmp_path: Path) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        merge_returncode=1,
        merge_stdout="",
        merge_stderr="GraphQL: merge blocked by ruleset",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "pr-lifecycle",
            "source": "gh pr merge --auto",
            "detail": "gh pr merge --auto failed: GraphQL: merge blocked by ruleset",
        }
    ]


def test_submit_writes_submit_status_when_codex_request_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    monkeypatch.setattr(
        pr_flow,
        "_submit_request_codex_review",
        lambda **_kwargs: pr_flow.EXCEPTION_REQUIRED_EXIT_CODE,
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "official-codex-review",
            "source": "https://github.com/liuli195/Quant-Trading/pull/88",
            "detail": "official Codex review request failed",
        }
    ]


def test_submit_writes_submit_status_when_retained_thread_retry_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitFailingChecksRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    monkeypatch.setattr(
        pr_flow,
        "_submit_accept_official_codex_retained_threads",
        lambda **_kwargs: (pr_flow.EXCEPTION_REQUIRED_EXIT_CODE, False),
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "official-codex-review-thread",
            "source": "https://github.com/liuli195/Quant-Trading/pull/88",
            "detail": "official Codex retained thread auto-processing failed",
        }
    ]
    assert status["snapshot_subject"] == {
        "repository": "liuli195/Quant-Trading",
        "pr_number": "88",
        "head_sha": "1" * 40,
        "head_branch": "feature/contract",
    }


def test_submit_writes_submit_status_when_retained_thread_read_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitFailingChecksRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    def fail_review_threads(**_kwargs):
        raise pr_flow.GitHubDataUnavailable("GitHub review threads unavailable")

    monkeypatch.setattr(pr_flow, "_current_pr_review_threads", fail_review_threads)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "official-codex-review-thread",
            "source": "https://github.com/liuli195/Quant-Trading/pull/88",
            "detail": (
                "official Codex review thread read failed: "
                "GitHub review threads unavailable"
            ),
        }
    ]


def test_submit_writes_submit_status_when_merge_wait_times_out(
    tmp_path: Path,
    monkeypatch,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    monkeypatch.setattr(pr_flow, "_submit_wait_for_merged_pr", lambda **_kwargs: None)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "pr-lifecycle",
            "source": "PR #88",
            "detail": "PR merge timed out",
        }
    ]


def test_submit_writes_submit_status_when_cleanup_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_state="MERGED",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    monkeypatch.setattr(
        pr_flow,
        "_cleanup_merged_pr_metadata",
        lambda **_kwargs: pr_flow.EXCEPTION_REQUIRED_EXIT_CODE,
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "pr-lifecycle",
            "source": "PR #88",
            "detail": "post-merge cleanup failed",
        }
    ]


def test_submit_reports_missing_first_stage_review_fragments(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards fragment is missing",
        },
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/spec.json",
            "detail": "spec fragment is missing",
        },
    ]


def test_review_fragment_builder_writes_pass_verdict_current_fragment(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.build_review_fragment_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "standards",
            "verdict": "pass",
            "reviewed_head": "1" * 40,
            "reviewed_diff": DEFAULT_DIFF_HASH,
            "reviewer": "standards-reviewer",
            "delegation_attempt": DEFAULT_DELEGATION_ATTEMPT,
        },
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    fragment_path = tmp_path / ".local/ai-review/fragments/standards.json"
    assert json.loads(fragment_path.read_text(encoding="utf-8")) == {
        "schema": 2,
        "head": "1" * 40,
        "diff": DEFAULT_DIFF_HASH,
        "findings": [],
        "delegation_attempt": DEFAULT_DELEGATION_ATTEMPT,
    }


def test_submit_writes_review_fragments_handoff_for_missing_fragments(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _evidence_artifacts(status) == [
        {
            "artifact_type": "review_fragments_handoff",
            "artifact_path": ".local/pr-flow/review-fragments-handoff.json",
            "artifact_summary": "2 local review fragments require agent mapping",
        }
    ]
    handoff = json.loads(
        (tmp_path / ".local/pr-flow/review-fragments-handoff.json").read_text(
            encoding="utf-8"
        )
    )
    assert handoff["schema_version"] == 1
    assert handoff["head_sha"] == "1" * 40
    assert handoff["diff_hash"] == DEFAULT_DIFF_HASH
    assert [item["role"] for item in handoff["fragments"]] == ["standards", "spec"]
    assert handoff["fragments"][0]["builder_input_template"] == {
        "source": "standards",
        "verdict": "pass",
        "reviewed_head": "1" * 40,
        "reviewed_diff": DEFAULT_DIFF_HASH,
        "reviewer": "",
        "findings": [],
        "delegation_attempt": {
            "required": True,
            "authorization_basis": "AGENTS.md + ADR 0009",
            "tool": "spawn_agent",
            "result": "",
            "reason": "",
        },
    }


def test_review_fragment_builder_rejects_standards_without_delegation_attempt(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.build_review_fragment_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "standards",
            "verdict": "pass",
            "reviewed_head": "1" * 40,
            "reviewed_diff": DEFAULT_DIFF_HASH,
            "reviewer": "standards-reviewer",
        },
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert not (tmp_path / ".local/ai-review/fragments/standards.json").exists()


@pytest.mark.parametrize(
    "reason",
    [
        "user_not_authorized",
        "user not authorized",
        "Permission-Not-Allowed",
        "explicit authorization missing",
        "policy disallowed",
    ],
)
def test_review_fragment_builder_rejects_authorization_missing_delegation_reason(
    tmp_path: Path,
    reason: str,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.build_review_fragment_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "spec",
            "verdict": "pass",
            "reviewed_head": "1" * 40,
            "reviewed_diff": DEFAULT_DIFF_HASH,
            "reviewer": "spec-reviewer",
            "delegation_attempt": {
                "required": True,
                "authorization_basis": "AGENTS.md + ADR 0009",
                "tool": "spawn_agent",
                "result": "tool_unavailable",
                "reason": reason,
            },
        },
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert not (tmp_path / ".local/ai-review/fragments/spec.json").exists()


def test_submit_rejects_standards_fragment_without_delegation_attempt(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[],
        delegation_attempt=None,
    )
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards fragment delegation_attempt is required",
        }
    ]


def test_review_fragment_builder_rejects_security_without_fallback_reason(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.build_review_fragment_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "security",
            "verdict": "pass",
            "reviewed_head": "1" * 40,
            "reviewed_diff": DEFAULT_DIFF_HASH,
            "reviewer": "security-reviewer",
            "security_review": {"tool": "manual-security-review"},
        },
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert not (tmp_path / ".local/ai-review/fragments/security.json").exists()


def test_review_fragment_builder_preserves_fixed_blocking_finding(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.build_review_fragment_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "spec",
            "verdict": "findings",
            "reviewed_head": "1" * 40,
            "reviewed_diff": DEFAULT_DIFF_HASH,
            "reviewer": "spec-reviewer",
            "delegation_attempt": DEFAULT_DELEGATION_ATTEMPT,
            "findings": [
                {
                    "severity": "P1",
                    "status": "fixed",
                    "detail": "AC was incomplete",
                    "evidence": "current test covers the AC",
                }
            ],
        },
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    fragment = json.loads(
        (tmp_path / ".local/ai-review/fragments/spec.json").read_text(
            encoding="utf-8"
        )
    )
    assert fragment["delegation_attempt"] == DEFAULT_DELEGATION_ATTEMPT
    assert fragment["findings"] == [
        {
            "severity": "P1",
            "status": "fixed",
            "detail": "AC was incomplete",
            "evidence": "current test covers the AC",
            "reviewer": "spec-reviewer",
        }
    ]


def test_review_fragment_builder_subcommand_is_agent_only() -> None:
    parser = pr_flow.build_parser()

    args = parser.parse_args(
        ["build-review-fragment", "--payload-file", "verdict.json"]
    )

    assert args.command == "build-review-fragment"
    assert "build-review-fragment" not in parser.format_help()


def test_submit_requires_security_only_after_first_stage_passes(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[])
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/security.json",
            "detail": "security fragment is missing",
        }
    ]


def test_submit_rejects_stale_first_stage_fragment_before_security(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[], diff="stale-diff")
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards fragment diff is stale",
        }
    ]


def test_pre_push_review_fragment_freshness_warns_stale_diff_without_blocking(
    tmp_path: Path,
    capsys,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[], diff="stale-diff")
    original = (
        tmp_path / ".local" / "ai-review" / "fragments" / "standards.json"
    ).read_text(encoding="utf-8")

    code = pr_flow.warn_review_fragment_freshness(
        repo_root=tmp_path,
        runner=runner,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "local review fragments freshness" in captured.err
    assert "current head: " + "1" * 40 in captured.err
    assert f"current diff: {DEFAULT_DIFF_HASH}" in captured.err
    assert "standards: stale diff" in captured.err
    assert "rerun local review and remap fragments before pr-submit" in captured.err
    assert (
        tmp_path / ".local" / "ai-review" / "fragments" / "standards.json"
    ).read_text(encoding="utf-8") == original


def test_pre_push_review_fragment_freshness_is_silent_without_fragments(
    tmp_path: Path,
    capsys,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.warn_review_fragment_freshness(
        repo_root=tmp_path,
        runner=runner,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert captured.err == ""


def test_pre_push_review_fragment_freshness_warns_head_refreshable(
    tmp_path: Path,
    capsys,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[], head="0" * 40)

    code = pr_flow.warn_review_fragment_freshness(
        repo_root=tmp_path,
        runner=runner,
    )

    captured = capsys.readouterr()
    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert "standards: head refreshable" in captured.err
    assert "pr-submit can refresh same-diff fragment heads" in captured.err


def test_submit_reports_stale_diff_old_blockers_without_reply_or_fix(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[{"severity": "P1", "detail": "old blocker"}],
        diff="stale-diff",
    )
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards fragment diff is stale",
        },
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards finding 0 status is required for P0/P1",
        }
    ]


def test_submit_aggregates_first_stage_blockers_before_security(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[{"severity": "P1", "status": "open", "detail": "rules drift"}],
    )
    _write_fragment(
        tmp_path,
        "spec",
        findings=[{"severity": "P0", "status": "open", "detail": "AC not implemented"}],
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards P1: rules drift",
        },
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/spec.json",
            "detail": "spec P0: AC not implemented",
        },
    ]


def test_submit_accepts_fixed_blocking_fragment_finding_with_evidence(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[
            {
                "severity": "P1",
                "status": "fixed",
                "detail": "rules drift",
                "evidence": "verify fast passed on current head",
            }
        ],
        diff=diff_hash,
    )
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    payload = _payload_from_managed_body(runner.created_bodies[-1])
    assert payload["retained"] == []


def test_submit_rejects_fixed_blocking_fragment_finding_without_evidence(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[
            {
                "severity": "P1",
                "status": "fixed",
                "detail": "rules drift",
            }
        ],
    )
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards finding 0 fixed evidence is required",
        }
    ]


def test_submit_accepts_false_positive_blocking_fragment_finding_with_rationale(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[
            {
                "severity": "P1",
                "status": "false_positive",
                "detail": "old rule conflict",
                "rationale": "target spec wins for issue #108",
            }
        ],
        diff=diff_hash,
    )
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE


def test_submit_rejects_false_positive_blocking_fragment_without_rationale(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[
            {
                "severity": "P1",
                "status": "false_positive",
                "detail": "old rule conflict",
            }
        ],
    )
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards finding 0 false_positive rationale is required",
        }
    ]


def test_submit_rejects_blocking_fragment_finding_without_status(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[{"severity": "P1", "detail": "legacy blocker"}],
    )
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards finding 0 status is required for P0/P1",
        }
    ]


def test_submit_rejects_security_fragment_without_security_review(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[])
    _write_fragment(tmp_path, "spec", findings=[])
    _write_fragment_without_security_review(tmp_path, findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/security.json",
            "detail": "security fragment security_review is required",
        }
    ]
    handoff = json.loads(
        (tmp_path / ".local/pr-flow/review-fragments-handoff.json").read_text(
            encoding="utf-8"
        )
    )
    assert handoff["fragments"] == [
        {
            "role": "security",
            "state": "invalid",
            "detail": "security fragment security_review is required",
            "target_fragment_path": ".local/ai-review/fragments/security.json",
            "builder_input_template": {
                "source": "security",
                "verdict": "pass",
                "reviewed_head": "1" * 40,
                "reviewed_diff": DEFAULT_DIFF_HASH,
                "reviewer": "",
                "findings": [],
                "security_review": {"tool": "codex-security"},
            },
        }
    ]


def test_submit_requires_security_fallback_reason_for_non_codex_security_tool(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[])
    _write_fragment(tmp_path, "spec", findings=[])
    _write_fragment(
        tmp_path,
        "security",
        findings=[],
        security_review={"tool": "manual-security-review"},
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/security.json",
            "detail": (
                "security fragment fallback_reason is required when tool is "
                "not codex-security"
            ),
        }
    ]


def test_submit_accepts_security_fallback_reason_for_non_codex_security_tool(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(
        tmp_path,
        "security",
        findings=[],
        diff=diff_hash,
        security_review={
            "tool": "manual-security-review",
            "fallback_reason": "codex-security tool was unavailable",
        },
    )
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE


def test_security_fallback_reason_does_not_bypass_open_blocking_finding(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[])
    _write_fragment(tmp_path, "spec", findings=[])
    _write_fragment(
        tmp_path,
        "security",
        findings=[
            {
                "severity": "P1",
                "status": "open",
                "detail": "unsafe credential handling",
            }
        ],
        security_review={
            "tool": "manual-security-review",
            "fallback_reason": "codex-security tool was unavailable",
        },
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/security.json",
            "detail": "security P1: unsafe credential handling",
        }
    ]


def test_pr_review_evidence_accepts_contract_v1_managed_json() -> None:
    body = _managed_evidence_body(_contract_evidence_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert report.ok, report.errors


def test_pr_review_evidence_rejects_contract_without_official_review() -> (
    None
):
    payload = _contract_evidence_payload()
    payload["schema"] = 1
    payload.pop("official_review")
    body = _managed_evidence_body(payload)

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert not report.ok
    assert "PR Evidence JSON schema must be 2" in report.errors
    assert "PR Evidence official_review must be an object" in report.errors


def test_pr_review_evidence_rejects_invalid_official_review_shape() -> None:
    payload = _contract_evidence_payload()
    payload["official_review"] = {"decision": "required", "evidence": "extra"}
    body = _managed_evidence_body(payload)

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert not report.ok
    assert "PR Evidence official_review.required must only contain decision" in report.errors

    payload = _contract_evidence_payload()
    payload["official_review"] = {
        "decision": "skip_user_authorized",
        "authorized_by": "liuli195",
    }
    body = _managed_evidence_body(payload)

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert not report.ok
    assert "PR Evidence official_review.skip_user_authorized missing evidence" in report.errors


def test_pr_review_evidence_rejects_contract_v1_low_risk_skip_for_high_risk_files() -> (
    None
):
    payload = _contract_evidence_payload()
    payload["official_review"] = {"decision": "skip_risk_low"}
    body = _managed_evidence_body(payload)

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
        changed_files=("scripts/research/governance/pr_flow.py",),
        labels=(),
    )

    assert not report.ok
    assert (
        "PR Evidence official_review.skip_risk_low is invalid for high-risk changed files"
        in report.errors
    )


def test_pr_review_evidence_rejects_contract_v1_diff_mismatch() -> None:
    body = _managed_evidence_body(_contract_evidence_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="current-diff",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert not report.ok
    assert "PR Evidence JSON diff does not match current PR diff" in report.errors


def test_pr_review_evidence_ignores_threads_for_contract_v1_evidence() -> None:
    body = _managed_evidence_body(_contract_evidence_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
        review_threads=[{"isResolved": False}],
    )

    assert report.ok
    assert "Codex review must not have unresolved review threads" not in report.errors


def test_submit_creates_draft_pr_with_contract_evidence_json(tmp_path: Path) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(
        tmp_path,
        "security",
        findings=[{"severity": "P2", "detail": "accepted follow-up"}],
        diff=diff_hash,
    )
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.created_bodies
    assert runner.body_file_names == ["pr-evidence-body.md"]
    body = runner.created_bodies[-1]
    assert "## AI Review 风险分级" not in body
    payload = _payload_from_managed_body(body)
    assert list(payload) == [
        "schema",
        "head",
        "diff",
        "reviews",
        "official_review",
        "issues",
        "retained",
    ]
    assert payload["head"] == "1" * 40
    assert payload["diff"] == diff_hash
    assert payload["reviews"] == {
        "standards": {"head": "1" * 40, "diff": diff_hash},
        "spec": {"head": "1" * 40, "diff": diff_hash},
        "security": {"head": "1" * 40, "diff": diff_hash},
    }
    assert payload["official_review"] == {"decision": "required"}
    issues = payload["issues"]
    assert isinstance(issues, dict)
    assert issues["commits"] == [
        {"sha": "1" * 40, "issues": [{"number": 66, "role": "closes"}]},
        {"sha": "2" * 40, "no_issue": True},
    ]
    assert issues["refs"] == [
        {"number": 66, "role": "closes"},
    ]
    assert "<!-- github-native-links:start -->" in body
    assert "Closes #66" in body
    assert "#65" not in body.split("<!-- github-native-links:start -->", 1)[1]
    assert payload["retained"] == [
        {"severity": "P2", "source": "security", "detail": "accepted follow-up"}
    ]
    assert runner.comments
    assert "@codex review" in runner.comments[-1]
    assert "https://github.com/liuli195/Quant-Trading/pull/88" in runner.comments[-1]
    assert "1" * 40 in runner.comments[-1]


def test_submit_reissues_current_head_codex_request_without_eyes_ack(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        preexisting_comments=[_current_head_trigger_comment()],
        comment_reactions_by_id={"1": []},
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        codex_review_ack_timeout_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert len(runner.comments) == 1
    assert "@codex review" in runner.comments[-1]
    assert "1" * 40 in runner.comments[-1]


def test_submit_reissues_new_codex_request_when_eyes_ack_times_out(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        ack_generated_comments=False,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        codex_review_ack_timeout_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert len(runner.comments) == 2
    assert all("@codex review" in comment for comment in runner.comments)


def test_submit_blocks_when_reissued_codex_request_lacks_eyes_ack(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        preexisting_comments=[_current_head_trigger_comment()],
        comment_reactions_by_id={"1": []},
        ack_generated_comments=False,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        codex_review_ack_timeout_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert len(runner.comments) == 1


def test_submit_reissues_when_eyes_ack_is_after_three_minute_window(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        preexisting_comments=[_current_head_trigger_comment()],
        comment_reactions_by_id={
            "1": [_codex_eyes_reaction(created_at="2026-06-01T10:04:01Z")]
        },
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert len(runner.comments) == 1


def test_submit_reuses_current_head_codex_request_with_eyes_ack(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        preexisting_comments=[_current_head_trigger_comment()],
        comment_reactions_by_id={
            "1": [_codex_eyes_reaction(created_at="2026-06-01T10:01:00Z")]
        },
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.comments == []


def test_submit_reuses_current_head_codex_output_without_eyes_ack(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCurrentHeadCodexOutputRunner(
        diff_text=diff_text,
        existing_pr=True,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        preexisting_comments=[_current_head_trigger_comment()],
        comment_reactions_by_id={"1": []},
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        codex_review_ack_timeout_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.comments == []


def test_submit_accepts_new_current_head_codex_output_without_eyes_ack(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCurrentHeadCodexOutputRunner(
        diff_text=diff_text,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        ack_generated_comments=False,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        codex_review_ack_timeout_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert len(runner.comments) == 1


def test_submit_skips_official_codex_request_for_low_risk_fragments(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    payload = _payload_from_managed_body(runner.created_bodies[-1])
    assert payload["official_review"] == {"decision": "skip_risk_low"}
    assert runner.comments == []
    assert not any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)


def test_submit_removes_github_native_links_when_no_closing_refs(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_body=(
            "<!-- github-native-links:start -->\n"
            "Closes #66\n"
            "<!-- github-native-links:end -->\n\n"
            "<!-- pr-flow:start -->\nold\n<!-- pr-flow:end -->\n"
        ),
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(
        tmp_path,
        commit_issues=[{"number": 65, "role": "reference"}],
        refs=[{"number": 65, "role": "reference"}],
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.edited_bodies
    body = runner.edited_bodies[-1]
    assert "<!-- github-native-links:start -->" not in body
    assert "Closes #66" not in body
    payload = _payload_from_managed_body(body)
    issues = payload["issues"]
    assert isinstance(issues, dict)
    assert issues["refs"] == [{"number": 65, "role": "reference"}]


def test_submit_ignores_stale_aggregate_closing_refs_for_native_links(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(
        tmp_path,
        commit_issues=[{"number": 65, "role": "reference"}],
        refs=[{"number": 83, "role": "closes"}],
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    body = runner.created_bodies[-1]
    assert "<!-- github-native-links:start -->" not in body
    assert "Closes #83" not in body
    payload = _payload_from_managed_body(body)
    issues = payload["issues"]
    assert isinstance(issues, dict)
    assert issues["refs"] == [{"number": 65, "role": "reference"}]


def test_submit_skips_official_codex_request_with_user_authorization(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        official_review_skip_authorized_by="liuli195",
        official_review_skip_evidence=(
            "user explicitly authorized official review skip for current HEAD"
        ),
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    payload = _payload_from_managed_body(runner.created_bodies[-1])
    assert payload["official_review"] == {
        "decision": "skip_user_authorized",
        "authorized_by": "liuli195",
        "evidence": "user explicitly authorized official review skip for current HEAD",
    }
    assert runner.comments == []
    assert not any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)


def test_submit_cli_accepts_official_review_skip_authorization() -> None:
    args = pr_flow.build_parser().parse_args(
        [
            "submit",
            "--official-review-skip-authorized-by",
            "liuli195",
            "--official-review-skip-evidence",
            "current conversation",
        ]
    )

    assert args.official_review_skip_authorized_by == "liuli195"
    assert args.official_review_skip_evidence == "current conversation"


def test_submit_rejects_partial_official_review_skip_authorization(
    tmp_path: Path,
) -> None:
    runner = SubmitCreatePrRunner(
        diff_text="diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    )

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        official_review_skip_authorized_by="liuli195",
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.created_bodies == []
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "PR Flow / evidence",
            "source": "official_review",
            "detail": (
                "official review skip authorization requires both "
                "authorized_by and evidence"
            ),
        }
    ]


def test_submit_accepts_official_codex_p2_thread_into_retained(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitOfficialCodexRetainedRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    # Thread accepted pre-CI: only 1 CI checks call (passes first time)
    assert runner.checks_calls == 1
    assert runner.replies
    assert runner.resolved_threads == [runner.thread_id]
    payload = _payload_from_managed_body(runner.created_bodies[-1])
    assert payload["retained"] == [
        {
            "severity": "P2",
            "source": "official_codex",
            "detail": "**P2** retain as follow-up",
        }
    ]


def test_submit_does_not_auto_accept_human_p2_thread(tmp_path: Path) -> None:
    """Human review threads remain manual even when their text has P2 severity."""
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitOfficialCodexRetainedRunner(
        diff_text=diff_text,
        thread_author="human-reviewer",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert not runner.replies
    assert not runner.resolved_threads


class SubmitAutoCloseOutdatedThreadRunner(SubmitCreatePrRunner):
    """submit() inspects outdated P1 Codex threads before waiting for CI.

    Tracks call order: thread must be queried before CI checks are interpreted.
    """

    def __init__(self, *, diff_text: str) -> None:
        super().__init__(diff_text=diff_text)
        self.checks_calls = 0
        self.thread_id = "PRRT_outdated_p1"
        self.replies: list[str] = []
        self.resolved_threads: list[str] = []
        self._thread_query_count = 0
        self._thread_resolved = False
        self._call_sequence: list[str] = []
        self.thread_is_outdated = True
        self.thread_body = "![P1 Badge] outdated finding"
        self.review_threads_unavailable = False

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
        joined = "\n".join(command)
        if command == self._status_rollup_command():
            self.checks_calls += 1
            self._call_sequence.append("checks")
            # CI only returns success AFTER thread is resolved
            state = "SUCCESS" if self._thread_resolved else "FAILURE"
            return self._status_rollup_result(
                [
                    self._status_rollup_item(
                        name="review-status",
                        workflow="PR Flow",
                        state=state,
                        link="https://github.com/checks/review",
                    ),
                    self._status_rollup_item(
                        name="verify-full",
                        workflow="Research Governance",
                        link="https://github.com/runs/1",
                    ),
                    self._status_rollup_item(
                        name="evidence",
                        workflow="PR Flow",
                        state=state,
                        link="https://github.com/runs/2",
                    ),
                ]
            )
        if "addPullRequestReviewThreadReply" in joined:
            body = next(
                (item.removeprefix("body=") for item in command if item.startswith("body=")),
                "",
            )
            self.replies.append(body)
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "addPullRequestReviewThreadReply": {
                                "comment": {"id": "comment-id"}
                            }
                        }
                    }
                ),
                "",
            )
        if "resolveReviewThread" in joined:
            thread_id = next(
                (
                    item.removeprefix("threadId=")
                    for item in command
                    if item.startswith("threadId=")
                ),
                "",
            )
            self.resolved_threads.append(thread_id)
            self._thread_resolved = True
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "resolveReviewThread": {
                                "thread": {"id": thread_id, "isResolved": True}
                            }
                        }
                    }
                ),
                "",
            )
        if "node(id:$threadId)" in joined:
            thread_id = next(
                (
                    item.removeprefix("threadId=")
                    for item in command
                    if item.startswith("threadId=")
                ),
                "",
            )
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "node": {"id": thread_id, "isResolved": self._thread_resolved}
                        }
                    }
                ),
                "",
            )
        if "reviewThreads" in joined:
            self._thread_query_count += 1
            self._call_sequence.append("reviewThreads")
            if self.review_threads_unavailable:
                return pr_flow.CommandResult(1, "", "review threads unavailable")
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "data": {
                            "repository": {
                                "pullRequest": {
                                    "reviewThreads": {
                                        "nodes": [
                                            {
                                                "id": self.thread_id,
                                                "isResolved": False,
                                                "isOutdated": self.thread_is_outdated,
                                                "path": "scripts/research/governance/pr_flow.py",
                                                "line": 321,
                                                "comments": {
                                                    "nodes": [
                                                        {
                                                            "body": self.thread_body,
                                                            "url": (
                                                                "https://github.com/liuli195/"
                                                                "Quant-Trading/pull/88#discussion_r1"
                                                            ),
                                                            "author": {
                                                                "login": "chatgpt-codex-connector[bot]"
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
        return super().run(command, cwd=cwd, input_text=input_text)


def test_submit_blocks_outdated_codex_p1_thread_without_closure_evidence(
    tmp_path: Path,
) -> None:
    """submit() must not auto-close outdated P1 Codex threads without evidence."""
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitAutoCloseOutdatedThreadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.resolved_threads == []
    assert runner.replies == []
    # Thread was queried and resolved BEFORE CI checks ran
    assert "reviewThreads" in runner._call_sequence
    review_idx = runner._call_sequence.index("reviewThreads")
    checks_idx = runner._call_sequence.index("checks")
    assert review_idx < checks_idx, (
        "thread must be auto-processed BEFORE CI checks"
    )
    # CI checks still run once and report the review-status blocker.
    assert runner.checks_calls == 1


def test_submit_writes_resolve_threads_plan_artifact_for_unresolved_codex_thread(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitAutoCloseOutdatedThreadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    review_signals = [
        signal
        for signal in _blocking_signals(status)
        if signal["signal_type"] == "review_thread_unresolved"
    ]
    assert review_signals == [
        {
            "signal_type": "review_thread_unresolved",
            "summary": (
                "unresolved review thread PRRT_outdated_p1 requires closure evidence"
            ),
            "source_context": "official-codex-review-thread",
            "evidence_location": ".local/pr-flow/resolve-threads-plan.json",
            "currentness": "current",
            "is_retryable": True,
        }
    ]
    artifacts = _evidence_artifacts(status)
    assert artifacts == [
        {
            "artifact_type": "resolve_threads_plan",
            "artifact_path": ".local/pr-flow/resolve-threads-plan.json",
            "artifact_summary": "1 unresolved review thread requires explicit action",
        }
    ]
    plan = json.loads(
        (tmp_path / ".local/pr-flow/resolve-threads-plan.json").read_text(
            encoding="utf-8"
        )
    )
    assert plan["schema_version"] == 1
    assert plan["head_sha"] == "1" * 40
    assert plan["threads"] == [
        {
            "thread_id": "PRRT_outdated_p1",
            "root_author": "chatgpt-codex-connector[bot]",
            "comment_url": "https://github.com/liuli195/Quant-Trading/pull/88#discussion_r1",
            "path": "scripts/research/governance/pr_flow.py",
            "line": 321,
            "is_outdated": True,
            "severity": "P1",
            "summary": "![P1 Badge] outdated finding",
            "closure_evidence_state": "missing",
            "current_head_sha": "1" * 40,
            "current_diff_hash": diff_hash,
            "target_evidence_path": ".local/pr-flow/thread-closure-evidence.json",
            "required_dispositions": ["fixed", "false_positive"],
            "builder_input_template": {
                "source": "official_codex_review_thread",
                "thread_id": "PRRT_outdated_p1",
                "severity": "P1",
                "head_sha": "1" * 40,
                "diff_files_hash": diff_hash,
                "disposition": "fixed",
                "evidence": "",
                "fix_commit": "",
                "verification_command": "",
                "reason": "",
            },
            "suggested_action": "provide current-head fixed or false_positive evidence before resolving",
        }
    ]


def test_thread_closure_builder_upserts_fixed_payload_from_plan(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_resolve_threads_plan(
        tmp_path,
        thread_id="PRRT_outdated_p1",
        severity="P1",
        head="1" * 40,
        diff=DEFAULT_DIFF_HASH,
    )
    _write_thread_closure_evidence(
        tmp_path,
        {
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_other",
            "severity": "P1",
            "disposition": "false_positive",
            "evidence": "existing evidence",
            "head_sha": "1" * 40,
            "diff_files_hash": DEFAULT_DIFF_HASH,
            "reason": "already handled",
        },
    )

    code = pr_flow.build_thread_closure_evidence_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_outdated_p1",
            "severity": "P1",
            "head_sha": "1" * 40,
            "diff_files_hash": DEFAULT_DIFF_HASH,
            "disposition": "fixed",
            "evidence": "fixed by current implementation",
            "fix_commit": "1" * 40,
            "verification_command": ".\\.venv\\Scripts\\python.exe -m pytest scripts/research/governance/tests/test_pr_flow_contract.py",
        },
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    evidence = json.loads(
        (tmp_path / ".local/pr-flow/thread-closure-evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["thread_id"] for item in evidence["external_findings"]] == [
        "PRRT_other",
        "PRRT_outdated_p1",
    ]
    assert evidence["external_findings"][-1]["disposition"] == "fixed"


def test_thread_closure_builder_rejects_thread_not_in_plan(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_resolve_threads_plan(
        tmp_path,
        thread_id="PRRT_expected",
        severity="P1",
        head="1" * 40,
        diff=DEFAULT_DIFF_HASH,
    )

    code = pr_flow.build_thread_closure_evidence_from_payload(
        repo_root=tmp_path,
        runner=runner,
        payload={
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_other",
            "severity": "P1",
            "head_sha": "1" * 40,
            "diff_files_hash": DEFAULT_DIFF_HASH,
            "disposition": "fixed",
            "evidence": "fixed by current implementation",
            "fix_commit": "1" * 40,
            "verification_command": ".\\.venv\\Scripts\\python.exe -m pytest scripts/research/governance/tests/test_pr_flow_contract.py",
        },
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert not (tmp_path / ".local/pr-flow/thread-closure-evidence.json").exists()


def test_thread_closure_builder_subcommand_is_agent_only() -> None:
    parser = pr_flow.build_parser()

    args = parser.parse_args(
        ["build-thread-closure-evidence", "--payload-file", "closure.json"]
    )

    assert args.command == "build-thread-closure-evidence"
    assert "build-thread-closure-evidence" not in parser.format_help()


def test_submit_auto_resolves_codex_p1_thread_with_current_fixed_evidence(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitAutoCloseOutdatedThreadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    _write_thread_closure_evidence(
        tmp_path,
        {
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_outdated_p1",
            "severity": "P1",
            "disposition": "fixed",
            "evidence": "fixed by current change",
            "head_sha": "1" * 40,
            "diff_files_hash": diff_hash,
            "fix_commit": "1" * 40,
            "verification_command": ".\\.venv\\Scripts\\python.exe -m pytest scripts/research/governance/tests/test_pr_flow_contract.py",
        },
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.replies
    assert "disposition: `fixed`" in runner.replies[-1]
    assert runner.resolved_threads == ["PRRT_outdated_p1"]
    assert not (tmp_path / ".local/pr-flow/resolve-threads-plan.json").exists()


def test_submit_auto_resolves_codex_p1_thread_with_current_false_positive_evidence(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitAutoCloseOutdatedThreadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    _write_thread_closure_evidence(
        tmp_path,
        {
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_outdated_p1",
            "severity": "P1",
            "disposition": "false_positive",
            "evidence": "current evidence link",
            "head_sha": "1" * 40,
            "diff_files_hash": diff_hash,
            "reason": "finding references code removed from this diff",
        },
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.replies
    assert "disposition: `false_positive`" in runner.replies[-1]
    assert "finding references code removed from this diff" in runner.replies[-1]
    assert runner.resolved_threads == ["PRRT_outdated_p1"]


def test_submit_rejects_codex_p1_thread_closure_evidence_without_disposition(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitAutoCloseOutdatedThreadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    _write_thread_closure_evidence(
        tmp_path,
        {
            "source": "official_codex_review_thread",
            "thread_id": "PRRT_outdated_p1",
            "severity": "P1",
            "status": "fixed",
            "evidence": "fixed by current change",
            "head_sha": "1" * 40,
            "diff_files_hash": diff_hash,
            "fix_commit": "1" * 40,
            "verification_command": ".\\.venv\\Scripts\\python.exe -m pytest scripts/research/governance/tests/test_pr_flow_contract.py",
        },
    )

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.resolved_threads == []


def test_submit_fails_closed_when_pre_ci_review_threads_are_unreadable(
    tmp_path: Path,
) -> None:
    """submit() must not continue toward merge when review threads are unreadable."""
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitAutoCloseOutdatedThreadRunner(diff_text=diff_text)
    runner.review_threads_unavailable = True
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.checks_calls == 0
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "official-codex-review-thread",
            "source": "https://github.com/liuli195/Quant-Trading/pull/88",
            "detail": (
                "official Codex review thread read failed: "
                "GitHub review threads unavailable"
            ),
        }
    ]


def test_submit_rejects_missing_commit_intent_before_creating_pr(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert runner.created_bodies == []
    status = _submit_status(tmp_path)
    failure = _blocking_as_legacy_failures(status)[0]
    assert failure["check"] == "issue-intent"
    assert failure["source"] == ".local/pr-flow/intents"
    assert (
        "branch intent does not cover all current branch commits"
        in failure["detail"]
    )
    assert "111111111111" in failure["detail"]


def test_submit_auto_covers_github_update_branch_merge_commit(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitUpdateBranchMergeRunner(diff_text=diff_text, existing_pr=True)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    payload = _payload_from_managed_body(runner.edited_bodies[-1])
    issues = payload["issues"]
    assert isinstance(issues, dict)
    commits = issues["commits"]
    refs = issues["refs"]
    assert {"sha": runner.update_branch_sha, "no_issue": True} in commits
    assert refs == [
        {"number": 66, "role": "closes"},
    ]


def test_submit_does_not_infer_no_issue_from_forged_update_branch_merge_commit(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitForgedUpdateBranchMergeRunner(diff_text=diff_text, existing_pr=True)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    failure = _blocking_as_legacy_failures(status)[0]
    assert failure["check"] == "issue-intent"
    assert runner.update_branch_sha in failure["detail"]


def test_submit_does_not_infer_no_issue_from_forged_raw_github_identity(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitForgedRawGithubUpdateBranchMergeRunner(
        diff_text=diff_text,
        existing_pr=True,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    failure = _blocking_as_legacy_failures(status)[0]
    assert failure["check"] == "issue-intent"
    assert runner.update_branch_sha in failure["detail"]


def test_submit_does_not_infer_no_issue_from_update_branch_subject_only(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitUpdateBranchSubjectOnlyRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    failure = _blocking_as_legacy_failures(status)[0]
    assert failure["check"] == "issue-intent"
    assert runner.update_branch_sha in failure["detail"]


def test_submit_waits_on_pending_required_checks_until_timeout(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        checks_bucket="pending",
        checks_returncode=8,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR 自动化",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "PR Flow / review-status",
            "source": "",
            "detail": "required check timed out while pending",
        }
    ]
    checkpoints = _checkpoint_statuses(status)
    assert checkpoints["official_codex_review"]["status"] == "pending"
    assert checkpoints["official_codex_review"]["summary"] == (
        "official Codex review has not returned"
    )


def test_submit_matches_raw_status_rollup_required_check_names(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitRawStatusRollupRequiredNamesRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.auto_merge_requested


def test_submit_records_stale_required_check_failure_as_diagnostic_when_current_pending(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitStaleRequiredCheckRunner(
        diff_text=diff_text,
        current_review_bucket="pending",
        current_review_state="PENDING",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "PR Flow / review-status",
            "source": "https://github.com/runs/review-current",
            "detail": "required check timed out while pending",
        }
    ]
    diagnostics = _diagnostic_signals(status)
    assert diagnostics == [
        {
            "signal_type": "stale_required_check_ignored",
            "summary": (
                "stale required check ignored: "
                "PR Flow / review-status https://github.com/runs/review-old"
            ),
            "source_context": "PR Flow / review-status",
            "evidence_location": "https://github.com/runs/review-old",
            "currentness": "stale",
            "is_retryable": True,
        }
    ]
    checkpoints = _checkpoint_statuses(status)
    assert checkpoints["official_codex_review"]["status"] == "pending"
    assert checkpoints["official_codex_review"]["evidence_location"] == (
        "https://github.com/runs/review-current"
    )


def test_submit_records_stale_required_check_failure_as_diagnostic_when_current_passed(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitStaleRequiredCheckRunner(
        diff_text=diff_text,
        current_review_bucket="pass",
        current_review_state="SUCCESS",
        verify_bucket="fail",
        verify_state="FAILURE",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "Research Governance / verify-full",
            "source": "https://github.com/runs/verify",
            "detail": "Research Governance / verify-full https://github.com/runs/verify",
        }
    ]
    diagnostics = _diagnostic_signals(status)
    assert diagnostics[0]["signal_type"] == "stale_required_check_ignored"
    assert diagnostics[0]["source_context"] == "PR Flow / review-status"
    checkpoints = _checkpoint_statuses(status)
    assert checkpoints["required_checks"]["status"] == "failed"
    assert checkpoints["required_checks"]["evidence_location"] == (
        "https://github.com/runs/verify"
    )


def test_submit_treats_empty_required_checks_window_as_pending(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitEmptyRequiredChecksWindowRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "PR Flow / review-status",
            "source": "",
            "detail": "required check timed out while pending",
        },
        {
            "check": "Research Governance / verify-full",
            "source": "",
            "detail": "required check timed out while pending",
        },
        {
            "check": "PR Flow / evidence",
            "source": "",
            "detail": "required check timed out while pending",
        },
    ]


def test_submit_does_not_treat_draft_pr_as_required_check_pending(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitDraftStatusRollupRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["gh", "pr", "ready", "88"] in runner.lifecycle_calls
    assert not _submit_status_path(tmp_path).exists()


def test_submit_fails_closed_when_current_head_required_checks_unavailable(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitUnavailableStatusRollupRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "required-checks",
            "source": "",
            "detail": "current-head required checks unavailable",
        }
    ]


def test_submit_fails_closed_when_pr_head_does_not_match_local_head(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitMismatchedHeadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "github",
            "source": "",
            "detail": "PR head does not match local HEAD",
        }
    ]


def test_submit_writes_required_check_failures_in_contract_order(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitFailingChecksRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert status["snapshot_subject"] == {
        "repository": "liuli195/Quant-Trading",
        "pr_number": "88",
        "head_sha": "1" * 40,
        "head_branch": "feature/contract",
    }
    failures = _blocking_as_legacy_failures(status)
    assert [failure["check"] for failure in failures] == [
        "PR Flow / review-status",
        "Research Governance / verify-full",
        "PR Flow / evidence",
    ]
    assert [failure["source"] for failure in failures] == [
        "https://github.com/runs/review",
        "https://github.com/runs/verify",
        "https://github.com/runs/evidence",
    ]


def test_submit_writes_failed_and_timed_out_required_checks_in_contract_order(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitMixedFailingPendingChecksRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "Research Governance / verify-full",
            "source": "https://github.com/runs/verify",
            "detail": "Research Governance / verify-full https://github.com/runs/verify",
        },
        {
            "check": "PR Flow / evidence",
            "source": "https://github.com/runs/evidence",
            "detail": "required check timed out while pending",
        },
    ]


def test_submit_waits_for_local_stable_checks_before_codex_review(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitLocalStablePendingRunner(
        diff_text=diff_text,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
        preexisting_comments=[_current_head_trigger_comment(head="0" * 40)],
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.comments == []
    status = _submit_status(tmp_path)
    assert status["pr_submit_stop"]["reason_code"] == "WAITING_LOCAL_STABILIZATION"
    assert status["pr_submit_stop"]["phase"] == "submit_local_stabilization"
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "Research Governance / verify-full",
            "source": "https://github.com/runs/verify",
            "detail": "local stabilization timed out while pending",
        },
        {
            "check": "PR Flow / evidence",
            "source": "https://github.com/runs/evidence",
            "detail": "local stabilization timed out while pending",
        },
    ]
    checkpoints = _checkpoint_statuses(status)
    assert checkpoints["official_codex_review"] == {
        "checkpoint_name": "official_codex_review",
        "status": "pending",
        "summary": (
            "official Codex review not requested; waiting for local stable checks"
        ),
        "evidence_location": "",
    }
    assert _evidence_artifacts(status) == [
        {
            "artifact_type": "local_stabilization",
            "artifact_path": ".local/pr-flow/local-stabilization.json",
            "artifact_summary": (
                "official Codex review waits for current-head local stable checks"
            ),
        }
    ]
    local_stable = json.loads(
        (tmp_path / ".local/pr-flow/local-stabilization.json").read_text(
            encoding="utf-8"
        )
    )
    assert local_stable["current_head_sha"] == "1" * 40
    assert local_stable["last_triggered_head_sha"] == "0" * 40
    assert local_stable["previous_trigger_superseded"] is True
    assert local_stable["next_trigger_condition"] == (
        "all local stable checks pass for current head: "
        "Research Governance / verify-full, PR Flow / evidence"
    )


def test_submit_excludes_review_status_from_local_stable_gate(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        checks_bucket="pending",
        checks_returncode=8,
        changed_files_output="scripts/research/governance/pr_flow.py\n",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert len(runner.comments) == 1
    status = _submit_status(tmp_path)
    assert status["pr_submit_stop"]["phase"] == "submit_wait_checks"
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "PR Flow / review-status",
            "source": "",
            "detail": "required check timed out while pending",
        }
    ]


def test_submit_does_not_request_codex_when_local_stable_check_failed(
    tmp_path: Path,
) -> None:
    diff_text = (
        "diff --git a/scripts/research/governance/pr_flow.py "
        "b/scripts/research/governance/pr_flow.py\n+hello\n"
    )
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitStaleRequiredCheckRunner(
        diff_text=diff_text,
        current_review_bucket="pass",
        current_review_state="SUCCESS",
        verify_bucket="fail",
        verify_state="FAILURE",
    )
    runner.changed_files_output = "scripts/research/governance/pr_flow.py\n"
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.comments == []
    status = _submit_status(tmp_path)
    assert status["pr_submit_stop"]["reason_code"] == "REQUIRED_CHECKS_FAILED"
    assert status["pr_submit_stop"]["phase"] == "submit_local_stabilization"
    assert _blocking_as_legacy_failures(status) == [
        {
            "check": "Research Governance / verify-full",
            "source": "https://github.com/runs/verify",
            "detail": "Research Governance / verify-full https://github.com/runs/verify",
        }
    ]


def test_submit_reuses_existing_current_head_trigger_without_duplicate_comment(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        checks_bucket="pending",
        checks_returncode=8,
        existing_pr=True,
        preexisting_comments=[_current_head_trigger_comment()],
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR 自动化",
        runner=runner,
        watch_timeout_seconds=0,
        watch_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert runner.comments == []
    assert not any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)


def test_submit_reuses_current_diff_fragments_after_pr_body_update(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    stale_body = _managed_evidence_body(
        {
            "schema": 2,
            "head": "0" * 40,
            "diff": "old-diff",
            "reviews": {},
            "official_review": {"decision": "required"},
            "issues": {"commits": [], "refs": []},
            "retained": [],
        }
    )
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_body=stale_body,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.edited_bodies
    payload = _payload_from_managed_body(runner.edited_bodies[-1])
    assert payload["head"] == "1" * 40
    assert payload["diff"] == diff_hash
    assert not _submit_status_path(tmp_path).exists()


def test_submit_skips_existing_pr_body_edit_when_evidence_is_current(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    for role in ("standards", "spec", "security"):
        _write_fragment(tmp_path, role, findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    create_runner = SubmitCreatePrRunner(diff_text=diff_text)

    create_code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=create_runner,
    )

    assert create_code == pr_flow.SUCCESS_EXIT_CODE
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_body=create_runner.created_bodies[-1],
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.edited_bodies == []
    assert not any(call[:4] == ["gh", "pr", "edit", "88"] for call in runner.calls)


def test_submit_retriggers_evidence_when_current_body_has_failed_check(
    tmp_path: Path,
) -> None:
    class EvidenceRecoveryRunner(SubmitCreatePrRunner):
        def _default_status_rollup_items(self) -> list[dict[str, object]]:
            items = super()._default_status_rollup_items()
            evidence_state = "SUCCESS" if self.edited_bodies else "FAILURE"
            for item in items:
                if item["name"] == "evidence":
                    item["state"] = evidence_state
            return items

    diff_text = "diff --git a/docs/guides/example.md b/docs/guides/example.md\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    for role in ("standards", "spec", "security"):
        _write_fragment(tmp_path, role, findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)
    create_runner = SubmitCreatePrRunner(diff_text=diff_text)

    create_code = pr_flow.submit(
        repo_root=tmp_path,
        title="PR automation",
        runner=create_runner,
    )

    assert create_code == pr_flow.SUCCESS_EXIT_CODE
    runner = EvidenceRecoveryRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_body=create_runner.created_bodies[-1],
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.edited_bodies


def test_submit_refreshes_same_diff_review_fragment_heads(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    for role in ("standards", "spec", "security"):
        _write_fragment(
            tmp_path,
            role,
            findings=[],
            head="0" * 40,
            diff=diff_hash,
        )
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR automation", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    for role in ("standards", "spec", "security"):
        fragment = json.loads(
            (
                tmp_path
                / ".local"
                / "ai-review"
                / "fragments"
                / f"{role}.json"
            ).read_text(encoding="utf-8")
        )
        expected_fragment: dict[str, object] = {
            "schema": 2,
            "head": "1" * 40,
            "diff": diff_hash,
            "findings": [],
        }
        if role in {"standards", "spec"}:
            expected_fragment["delegation_attempt"] = DEFAULT_DELEGATION_ATTEMPT
        if role == "security":
            expected_fragment["security_review"] = {"tool": "codex-security"}
        assert fragment == expected_fragment


def test_submit_auto_pushes_missing_remote_head_and_creates_pr(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = MissingSubmitRemoteHeadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["git", "push", "-u", "origin", "HEAD:feature/contract"] in runner.lifecycle_calls
    assert runner.created_bodies


def test_submit_reports_exception_when_auto_push_fails(
    tmp_path: Path,
    capsys,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = MissingSubmitRemoteHeadRunner(diff_text=diff_text, push_returncode=1)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in captured.err
    assert "REMOTE_BRANCH_PUSH_FAILED" in captured.err
    assert "remote rejected feature/contract" in captured.err
    assert runner.created_bodies == []


def test_submit_reports_exception_when_auto_push_remote_head_mismatches(
    tmp_path: Path,
    capsys,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = MismatchedAutoPushRemoteHeadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in captured.err
    assert "REMOTE_BRANCH_HEAD_MISMATCH" in captured.err
    assert runner.created_bodies == []


def test_submit_does_not_auto_push_main_branch(
    tmp_path: Path,
    capsys,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = MainBranchMissingSubmitRemoteHeadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path, branch="main")

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in captured.err
    assert "REMOTE_BRANCH_MISSING" in captured.err
    assert not any(call[:3] == ["git", "push", "-u"] for call in runner.lifecycle_calls)
    assert runner.created_bodies == []


def test_submit_treats_auto_merge_already_enabled_as_wait_state(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        merge_returncode=1,
        merge_stdout="",
        merge_stderr="GraphQL: auto-merge is already enabled",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["git", "branch", "-d", "feature/contract"] in runner.lifecycle_calls


def test_submit_short_circuits_already_merged_pr_to_cleanup(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_state="MERGED",
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert runner.comments == []
    assert not any(call[:3] == ["gh", "pr", "comment"] for call in runner.calls)
    assert ["gh", "pr", "ready", "88"] not in runner.lifecycle_calls
    assert not any(call[:3] == ["gh", "pr", "merge"] for call in runner.lifecycle_calls)
    assert ["git", "branch", "-d", "feature/contract"] in runner.lifecycle_calls


def test_submit_cleanup_syncs_main_in_existing_main_worktree(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    main_worktree = tmp_path / "main-worktree"
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_state="MERGED",
        main_worktree_path=str(main_worktree),
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["git", "switch", "--detach", "origin/main"] in runner.lifecycle_calls
    assert ["git", "switch", "main"] not in runner.lifecycle_calls
    assert (
        ["git", "merge", "--ff-only", "origin/main"],
        main_worktree,
    ) in runner.cwd_calls
    assert (
        ["git", "rev-list", "--left-right", "--count", "main...origin/main"],
        main_worktree,
    ) in runner.cwd_calls
    assert (
        ["git", "status", "--porcelain=v2", "--branch"],
        main_worktree,
    ) in runner.cwd_calls
    assert (
        ["git", "status", "--porcelain=v2", "--branch"],
        tmp_path,
    ) not in runner.cwd_calls


def test_submit_cleanup_stops_when_worktree_is_dirty_after_cleanup(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    raw_status = (
        "# branch.oid 1111111111111111111111111111111111111111\n"
        "# branch.head main\n"
        "1 .D N... 100644 100644 000000 "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa docs/rules/old.md\n"
        "1 .M N... 100644 100644 100644 "
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb "
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb scripts/research/governance/pr_flow.py\n"
        "? .local/tmp.txt\n"
    )
    runner = SubmitCreatePrRunner(
        diff_text=diff_text,
        existing_pr=True,
        existing_state="MERGED",
        cleanup_status_output=raw_status,
    )
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = _submit_status(tmp_path)
    assert status["pr_submit_stop"] == {
        "state": "EXCEPTION_REQUIRED",
        "reason_code": "WORKTREE_DIRTY_AFTER_CLEANUP",
        "phase": "cleanup_worktree_health",
        "is_retryable": True,
        "summary": (
            "cleanup_worktree_health: dirty worktree after cleanup: "
            "dirty_count=3 tracked_deleted_count=1 modified_count=1 "
            "untracked_count=1 sample_paths=docs/rules/old.md, "
            "scripts/research/governance/pr_flow.py"
        ),
    }
    signals = _blocking_signals(status)
    assert signals == [
        {
            "signal_type": "pr_submit_blocked",
            "summary": (
                "dirty worktree after cleanup: dirty_count=3 "
                "tracked_deleted_count=1 modified_count=1 untracked_count=1 "
                "sample_paths=docs/rules/old.md, "
                "scripts/research/governance/pr_flow.py"
            ),
            "source_context": "cleanup_worktree_health",
            "evidence_location": ".local/pr-flow/worktree-status-after-cleanup.txt",
            "currentness": "current",
            "is_retryable": True,
        }
    ]
    artifacts = _evidence_artifacts(status)
    assert artifacts == [
        {
            "artifact_type": "worktree_status_after_cleanup",
            "artifact_path": ".local/pr-flow/worktree-status-after-cleanup.txt",
            "artifact_summary": "raw git status --porcelain=v2 --branch after cleanup",
        }
    ]
    artifact_path = tmp_path / artifacts[0]["artifact_path"]
    assert artifact_path.read_text(encoding="utf-8") == raw_status
    assert not any(call[:2] == ["git", "restore"] for call in runner.calls)
    assert not any(call[:3] == ["git", "checkout", "--"] for call in runner.calls)


def test_submit_completes_head_locked_auto_merge_and_local_cleanup(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    assert ["gh", "pr", "ready", "88"] in runner.lifecycle_calls
    assert [
        "gh",
        "pr",
        "merge",
        "88",
        "--merge",
        "--auto",
        "--match-head-commit",
        "1" * 40,
    ] in runner.lifecycle_calls
    assert ["git", "merge", "--ff-only", "origin/main"] in runner.lifecycle_calls
    assert ["git", "branch", "-d", "feature/contract"] in runner.lifecycle_calls
    assert not any(call[:3] == ["git", "push", "origin"] for call in runner.lifecycle_calls)


def test_submit_marks_pr_ready_before_waiting_required_checks(
    tmp_path: Path,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.SUCCESS_EXIT_CODE
    ready_index = runner.ordered_calls.index(["gh", "pr", "ready", "88"])
    checks_index = runner.ordered_calls.index(runner._status_rollup_command())
    assert ready_index < checks_index


def test_contract_v1_rejects_legacy_ac_checked_field() -> None:
    payload = _contract_evidence_payload()
    issues = payload["issues"]
    assert isinstance(issues, dict)
    refs = issues["refs"]
    assert isinstance(refs, list)
    ref = refs[1]
    assert isinstance(ref, dict)
    ref["ac_checked"] = True

    report = pr_review_evidence.validate_pr_body(_managed_evidence_body(payload))

    assert not report.ok
    assert "PR Evidence issues.refs[1].ac_checked is not allowed" in report.errors


def test_codex_review_monitor_waits_for_trigger_with_contract_v1_evidence() -> None:
    report = codex_review_monitor.build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="88",
        pr={
            "head": {"sha": "a" * 40},
            "body": _managed_evidence_body(_contract_evidence_payload()),
        },
        issue_comments=[],
        reviews=[],
        review_comments=[],
        changed_files=("scripts/research/governance/pr_flow.py",),
        labels=("ai-risk-review",),
    )

    assert report.status == "waiting_for_trigger"


def test_codex_review_monitor_skips_low_risk_contract_v1_with_risk_label() -> None:
    payload = _contract_evidence_payload()
    payload["official_review"] = {"decision": "skip_risk_low"}
    report = codex_review_monitor.build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="88",
        pr={"head": {"sha": "a" * 40}, "body": _managed_evidence_body(payload)},
        issue_comments=[],
        reviews=[],
        review_comments=[],
        changed_files=("docs/guides/example.md",),
        labels=("ai-risk-review",),
    )

    assert report.status == "skipped"


def test_codex_review_monitor_rejects_low_risk_contract_v1_skip_for_high_risk_files() -> (
    None
):
    payload = _contract_evidence_payload()
    payload["official_review"] = {"decision": "skip_risk_low"}
    report = codex_review_monitor.build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="88",
        pr={"head": {"sha": "a" * 40}, "body": _managed_evidence_body(payload)},
        issue_comments=[],
        reviews=[],
        review_comments=[],
        changed_files=("scripts/research/governance/pr_flow.py",),
        labels=(),
    )

    assert report.status == "evidence_invalid"
    assert (
        "PR Evidence official_review.skip_risk_low is invalid for high-risk changed files"
        in report.message
    )


def test_codex_review_monitor_skips_contract_v1_user_authorized_official_review() -> (
    None
):
    payload = _contract_evidence_payload()
    payload["official_review"] = {
        "decision": "skip_user_authorized",
        "authorized_by": "liuli195",
        "evidence": "user explicitly authorized official review skip for current HEAD",
    }
    report = codex_review_monitor.build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="88",
        pr={"head": {"sha": "a" * 40}, "body": _managed_evidence_body(payload)},
        issue_comments=[],
        reviews=[],
        review_comments=[],
        changed_files=("scripts/research/governance/pr_flow.py",),
        labels=("ai-risk-review",),
    )

    assert report.status == "skipped"


def test_codex_review_status_uses_contract_context_and_workflow_target(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(**kwargs: object) -> object:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(codex_review_monitor, "_request_json", fake_request_json)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "liuli195/Quant-Trading")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    report = codex_review_monitor.MonitorReport(
        status="waiting_for_codex",
        pr_number="88",
        head_sha="a" * 40,
        trigger_found=True,
        latest_review_url=None,
        latest_review_sha=None,
        blocking_findings=0,
        advisory_findings=0,
        message="waiting",
    )

    codex_review_monitor.sync_commit_status(
        repo="liuli195/Quant-Trading",
        pr={"html_url": "https://github.com/liuli195/Quant-Trading/pull/88"},
        token="token",
        report=report,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["state"] == "pending"
    assert payload["context"] == "PR Flow / review-status"
    assert (
        payload["target_url"]
        == "https://github.com/liuli195/Quant-Trading/actions/runs/123456789"
    )


def test_codex_review_status_writes_error_for_expected_head_mismatch(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(**kwargs: object) -> object:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(codex_review_monitor, "_request_json", fake_request_json)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "liuli195/Quant-Trading")
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    report = codex_review_monitor.MonitorReport(
        status="stale_head",
        pr_number="88",
        head_sha="a" * 40,
        trigger_found=False,
        latest_review_url=None,
        latest_review_sha=None,
        blocking_findings=0,
        advisory_findings=0,
        message="PR head changed before monitor completed",
    )

    codex_review_monitor.sync_commit_status(
        repo="liuli195/Quant-Trading",
        pr={"html_url": "https://github.com/liuli195/Quant-Trading/pull/88"},
        token="token",
        report=report,
    )

    url = captured["url"]
    assert isinstance(url, str)
    assert url.endswith(f"/statuses/{'a' * 40}")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["state"] == "error"
    assert payload["description"] == "PR head changed before monitor completed"
    assert payload["context"] == "PR Flow / review-status"


def test_codex_review_monitor_cli_reports_expected_head_mismatch(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    pr_file = tmp_path / "pr.json"
    pr_file.write_text(
        json.dumps(
            {
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/88",
                "head": {"sha": "b" * 40},
                "body": "",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_REPOSITORY", "liuli195/Quant-Trading")
    monkeypatch.setenv("PR_NUMBER", "88")
    monkeypatch.setenv("EXPECTED_HEAD_SHA", "a" * 40)

    code = codex_review_monitor.main(
        [
            "--pr-file",
            str(pr_file),
            "--expected-head-sha-env",
            "EXPECTED_HEAD_SHA",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "head 已变化" in output
    assert "PR head changed before monitor completed" in output
    assert f"当前 head: `{'a' * 7}`" in output


def test_contract_defines_target_spec_wins_rule() -> None:
    """Target spec wins rule must be machine-readable in the contract."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.target_spec_wins is True


def test_contract_defines_fragment_freshness_rule() -> None:
    """Fragment freshness semantics must be explicit in the contract."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert isinstance(contract.fragment_freshness_same_diff_head_refresh, bool)
    assert contract.fragment_freshness_same_diff_head_refresh is True


def test_contract_defines_security_review_fragment_metadata() -> None:
    """Security fragment review metadata must be machine-readable."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.fragment_security_review_fields == (
        "tool",
        "fallback_reason",
    )
    assert contract.fragment_security_review_default_tool == "codex-security"
    assert (
        contract.fragment_security_review_fallback_required_when_tool_not
        == "codex-security"
    )


def test_contract_defines_delegation_attempt_fragment_metadata() -> None:
    """Standards/Spec delegation evidence must be machine-readable."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.fragment_delegation_attempt_fields == (
        "required",
        "authorization_basis",
        "tool",
        "result",
        "reason",
    )
    assert (
        contract.fragment_delegation_attempt_authorization_basis
        == "AGENTS.md + ADR 0009"
    )
    assert contract.fragment_delegation_attempt_tool == "spawn_agent"
    assert contract.fragment_delegation_attempt_results == (
        "spawned",
        "tool_unavailable",
        "spawn_failed",
    )
    assert contract.fragment_delegation_attempt_reason_required_results == (
        "tool_unavailable",
        "spawn_failed",
    )
    assert "user_not_authorized" in (
        contract.fragment_delegation_attempt_invalid_reason_tokens
    )


def test_contract_defines_review_handoff_and_local_stable_artifacts() -> None:
    """PR Flow handoff and local-stable paths must be machine-readable."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.review_fragments_handoff_path.as_posix() == (
        ".local/pr-flow/review-fragments-handoff.json"
    )
    assert contract.resolve_threads_plan_path.as_posix() == (
        ".local/pr-flow/resolve-threads-plan.json"
    )
    assert contract.thread_closure_evidence_path.as_posix() == (
        ".local/pr-flow/thread-closure-evidence.json"
    )
    assert contract.local_stabilization_path.as_posix() == (
        ".local/pr-flow/local-stabilization.json"
    )


def test_contract_defines_local_stable_gate() -> None:
    """Local stable gate checks and stop labels must be machine-readable."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.local_stable_required_checks == (
        "Research Governance / verify-full",
        "PR Flow / evidence",
    )
    assert contract.local_stable_excluded_checks == ("PR Flow / review-status",)
    assert contract.local_stable_pending_reason_code == "WAITING_LOCAL_STABILIZATION"
    assert contract.local_stable_pending_phase == "submit_local_stabilization"


def test_contract_defines_github_native_closing_links_rule() -> None:
    """GitHub native closing links must come from per-commit evidence."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert isinstance(contract.github_native_closing_links_from_per_commit_evidence, bool)
    assert contract.github_native_closing_links_from_per_commit_evidence is True


def test_contract_defines_codex_thread_automation_rules() -> None:
    """Codex thread automation boundaries must be defined in the contract."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert isinstance(contract.codex_thread_p0_p1_requires_closure_evidence, bool)
    assert contract.codex_thread_p0_p1_requires_closure_evidence is True
    assert isinstance(contract.codex_thread_human_never_auto_resolve, bool)
    assert contract.codex_thread_human_never_auto_resolve is True
    assert isinstance(contract.codex_thread_no_severity_never_auto_resolve, bool)
    assert contract.codex_thread_no_severity_never_auto_resolve is True
    assert isinstance(contract.codex_thread_p2_p3_auto_accept, bool)
    assert contract.codex_thread_p2_p3_auto_accept is True


def test_contract_closure_evidence_documents_required_fields() -> None:
    """Closure evidence docs must include every field PR Flow validates."""
    import yaml

    payload = yaml.safe_load(
        Path("docs/rules/pr-flow-interface-contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    required_fields = payload["submit_status"]["closure_evidence"]["required_fields"]

    assert set(required_fields) >= {
        "source",
        "thread_id",
        "severity",
        "head_sha",
        "diff_files_hash",
        "disposition",
        "evidence",
    }


def test_contract_defines_workflow_pending_rule() -> None:
    """Workflow must publish pending status before execution."""
    contract = pr_flow_contract.load_contract(Path("."))

    assert isinstance(contract.workflow_pending_before_execution, bool)
    assert contract.workflow_pending_before_execution is True


def test_workflow_files_publish_pending_before_validation() -> None:
    """Each required-check workflow must publish pending before time-consuming work."""
    import yaml

    repo_root = Path(".")
    workflow_dir = repo_root / ".github" / "workflows"

    contexts = {
        "pr-flow.yml": "PR Flow / evidence",
        "codex-review-monitor.yml": "PR Flow / review-status",
        "research-governance.yml": "Research Governance / verify-full",
    }

    for filename, expected_context in contexts.items():
        path = workflow_dir / filename
        content = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(content)

        jobs = doc.get("jobs", {}) if isinstance(doc, dict) else {}
        for job_name, job_def in jobs.items():
            if not isinstance(job_def, dict):
                continue
            steps = job_def.get("steps", [])
            if not isinstance(steps, list):
                continue

            pending_step = None
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if step.get("name") == "Publish pending status":
                    pending_step = step
                    break

            assert pending_step is not None, (
                f"{filename}:{job_name} missing 'Publish pending status' step"
            )
            # Verify the step publishes pending for the correct context
            run_script = str(pending_step.get("run", ""))
            assert expected_context in run_script, (
                f"{filename}:{job_name} must publish pending for {expected_context}"
            )
            assert "pending" in run_script, (
                f"{filename}:{job_name} must set state to pending"
            )


def test_required_check_workflow_events_follow_issue_113_contract() -> None:
    """Required checks should only run from events that can change their inputs."""
    import yaml

    workflow_dir = Path(".github") / "workflows"

    def workflow_on(filename: str) -> dict[object, object]:
        doc = yaml.safe_load((workflow_dir / filename).read_text(encoding="utf-8"))
        assert isinstance(doc, dict)
        events = doc.get("on", doc.get(True))
        assert isinstance(events, dict)
        return events

    def event_types(events: dict[object, object], name: str) -> list[str]:
        event = events.get(name)
        if event is None:
            return []
        if event is None or event == "":
            return []
        if isinstance(event, dict):
            types = event.get("types")
            if isinstance(types, list):
                return [str(item) for item in types]
        return []

    verify_events = workflow_on("research-governance.yml")
    assert set(verify_events) == {
        "push",
        "pull_request",
        "schedule",
        "workflow_dispatch",
    }
    assert verify_events["push"] == {"branches": ["main"]}
    assert event_types(verify_events, "pull_request") == [
        "opened",
        "synchronize",
        "reopened",
    ]

    evidence_events = workflow_on("pr-flow.yml")
    assert set(evidence_events) == {"pull_request"}
    assert event_types(evidence_events, "pull_request") == [
        "opened",
        "synchronize",
        "reopened",
        "edited",
    ]

    monitor_events = workflow_on("codex-review-monitor.yml")
    assert set(monitor_events) == {
        "pull_request",
        "pull_request_review",
        "pull_request_review_comment",
        "workflow_dispatch",
    }
    assert event_types(monitor_events, "pull_request") == [
        "opened",
        "synchronize",
        "reopened",
    ]
    assert event_types(monitor_events, "pull_request_review") == [
        "submitted",
        "edited",
        "dismissed",
    ]
    assert event_types(monitor_events, "pull_request_review_comment") == [
        "created",
        "edited",
        "deleted",
    ]

    router_events = workflow_on("codex-review-router.yml")
    assert set(router_events) == {"issue_comment"}
    assert event_types(router_events, "issue_comment") == [
        "created",
        "edited",
        "deleted",
    ]


def test_pr_scoped_required_check_workflows_have_head_concurrency() -> None:
    """Repeated runs for the same workflow and PR head should cancel old runs."""
    import yaml

    workflow_dir = Path(".github") / "workflows"
    for filename in (
        "research-governance.yml",
        "pr-flow.yml",
        "codex-review-monitor.yml",
    ):
        doc = yaml.safe_load((workflow_dir / filename).read_text(encoding="utf-8"))
        assert isinstance(doc, dict)
        concurrency = doc.get("concurrency")
        assert isinstance(concurrency, dict), f"{filename} missing concurrency"
        group = str(concurrency.get("group", ""))
        assert "github.workflow" in group, filename
        assert "github.event.pull_request.number" in group or "github.ref" in group
        assert "github.event.pull_request.head.sha" in group or "github.sha" in group
        assert concurrency.get("cancel-in-progress") is True


def test_codex_review_monitor_has_failure_finalizer_for_pending_status() -> None:
    """The monitor must not leave review-status pending after infrastructure failure."""
    import yaml

    path = Path(".github/workflows/codex-review-monitor.yml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))

    steps = doc["jobs"]["monitor"]["steps"]
    finalizer = next(
        (
            step
            for step in steps
            if isinstance(step, dict)
            and step.get("name") == "Publish monitor failure status"
        ),
        None,
    )

    assert finalizer is not None
    condition = str(finalizer.get("if", ""))
    assert "always()" in condition
    assert "failure()" in condition
    assert "cancelled()" in condition
    run_script = str(finalizer.get("run", ""))
    assert "PR Flow / review-status" in run_script
    assert "failure" in run_script
    assert "error" in run_script
    assert "pulls/$env:PR_NUMBER" in run_script


def test_codex_review_monitor_uses_event_appropriate_checkout_ref() -> None:
    """issue_comment runs trusted code; PR events run PR-compatible code."""
    import yaml

    path = Path(".github/workflows/codex-review-monitor.yml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))

    jobs = doc.get("jobs", {}) if isinstance(doc, dict) else {}
    for job_name, job_def in jobs.items():
        if not isinstance(job_def, dict):
            continue
        steps = job_def.get("steps", [])
        if not isinstance(steps, list):
            continue

        checkout_step = None
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = str(step.get("uses", ""))
            if uses.startswith("actions/checkout@"):
                checkout_step = step
                break

        assert checkout_step is not None, (
            f"{job_name} missing actions/checkout step"
        )
        ref = checkout_step.get("with", {}).get("ref", "")
        assert "steps.pr-head.outputs.sha" in ref, (
            f"{job_name} checkout must use PR-compatible head code, got: {ref}"
        )
        assert "github.event.repository.default_branch" not in ref, (
            f"{job_name} checkout must not pin issue_comment to default branch, got: {ref}"
        )

        resolve_step = next(
            step for step in steps if isinstance(step, dict) and step.get("id") == "pr-head"
        )
        assert "pulls/$env:PR_NUMBER" in str(resolve_step.get("run", "")), (
            f"{job_name} must resolve PR head SHA as data before monitoring"
        )


def test_codex_review_monitor_workflow_dispatch_resolves_input_pr_number() -> None:
    """workflow_dispatch must inspect the manually requested PR number."""
    import yaml

    path = Path(".github/workflows/codex-review-monitor.yml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))

    steps = doc["jobs"]["monitor"]["steps"]
    resolve_step = next(
        step for step in steps if step.get("name") == "Resolve PR head SHA"
    )
    assert (
        resolve_step["env"]["PR_NUMBER"]
        == "${{ inputs.pr_number || github.event.pull_request.number }}"
    )


def test_codex_review_status_uses_router_worker_event_split() -> None:
    """issue_comment must route to the PR-branch worker instead of running it directly."""
    import yaml

    router_path = Path(".github/workflows/codex-review-router.yml")
    worker_path = Path(".github/workflows/codex-review-monitor.yml")

    assert router_path.is_file()
    router_doc = yaml.safe_load(router_path.read_text(encoding="utf-8"))
    worker_doc = yaml.safe_load(worker_path.read_text(encoding="utf-8"))

    router_on = router_doc.get("on", router_doc.get(True))
    worker_on = worker_doc.get("on", worker_doc.get(True))

    assert set(router_on) == {"issue_comment"}
    assert "issue_comment" not in worker_on
    for event_name in (
        "pull_request",
        "pull_request_review",
        "pull_request_review_comment",
        "workflow_dispatch",
    ):
        assert event_name in worker_on


def test_codex_review_router_dispatches_pr_branch_worker_with_head_lock() -> None:
    """Router dispatch must load the PR branch worker and lock the expected head."""
    import yaml

    path = Path(".github/workflows/codex-review-router.yml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")

    permissions = doc["permissions"]
    assert permissions["actions"] == "write"
    assert permissions["pull-requests"] == "read"
    assert permissions["statuses"] == "write"
    assert "actions/checkout" not in text
    assert 'state="success"' not in text

    steps = doc["jobs"]["route-review-status"]["steps"]
    dispatch = next(step for step in steps if step.get("name") == "Dispatch PR branch worker")
    run_script = str(dispatch["run"])
    assert "actions/workflows/codex-review-monitor.yml/dispatches" in run_script
    assert '-f ref="$env:PR_HEAD_REF"' in run_script
    assert "inputs[pr_number]=$env:PR_NUMBER" in run_script
    assert "inputs[expected_head_sha]=$env:PR_HEAD_SHA" in run_script
    assert "inputs[trigger_event]=issue_comment" in run_script
    assert "inputs[trigger_run_id]=$env:TRIGGER_RUN_ID" in run_script
    assert "github.event.comment" not in run_script
    assert "comment.body" not in run_script


def test_codex_review_worker_workflow_dispatch_is_head_locked_and_finalized() -> None:
    """workflow_dispatch is a first-class worker entrypoint with pending/finalizer behavior."""
    import yaml

    path = Path(".github/workflows/codex-review-monitor.yml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    worker_on = doc.get("on", doc.get(True))
    dispatch_inputs = worker_on["workflow_dispatch"]["inputs"]

    assert set(dispatch_inputs) >= {
        "pr_number",
        "expected_head_sha",
        "trigger_event",
        "trigger_run_id",
    }
    assert "actions" not in doc["permissions"]

    steps = doc["jobs"]["monitor"]["steps"]
    pending = next(step for step in steps if step.get("name") == "Publish pending status")
    assert "if" not in pending
    assert (
        pending["env"]["PR_HEAD_SHA"]
        == "${{ inputs.expected_head_sha || steps.pr-head.outputs.sha || github.event.pull_request.head.sha }}"
    )
    assert "PR Flow / review-status" in str(pending["run"])

    guard = next(step for step in steps if step.get("name") == "Guard expected PR head")
    guard_script = str(guard["run"])
    assert "EXPECTED_HEAD_SHA" in guard_script
    assert "PR head changed before monitor completed" in guard_script
    assert 'state="error"' in guard_script

    finalizer = next(
        step for step in steps if step.get("name") == "Publish monitor failure status"
    )
    condition = str(finalizer["if"])
    assert "always()" in condition
    assert "failure()" in condition
    assert "cancelled()" in condition
    assert "github.event_name != 'workflow_dispatch'" not in condition
    assert (
        finalizer["env"]["PR_HEAD_SHA"]
        == "${{ inputs.expected_head_sha || steps.pr-head.outputs.sha || github.event.pull_request.head.sha }}"
    )

    monitor = next(step for step in steps if step.get("name") == "Update Codex review status")
    assert monitor["env"]["EXPECTED_HEAD_SHA"] == "${{ inputs.expected_head_sha }}"
    assert "--expected-head-sha-env EXPECTED_HEAD_SHA" in str(monitor["run"])


def test_codex_review_router_worker_model_is_documented() -> None:
    required_docs = {
        Path("docs/rules/governance.md"): [
            "codex-review-router.yml",
            "codex-review-monitor.yml",
            "expected_head_sha",
            "PR head changed before monitor completed",
        ],
        Path("docs/rules/pr-workflow.md"): [
            "PR head branch worker",
            "不维护 PR Flow changed-files 白名单",
            "接手快照 v3",
            "不新增公开 `diagnose`、`handoff` 或 `refresh` 入口",
        ],
        Path("scripts/research/governance/README.md"): [
            "codex-review-router.yml",
            "codex-review-monitor.yml",
            "trigger_run_id",
            "router 成功调度后不写 success",
        ],
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"): [
            "https://github.com/liuli195/Quant-Trading/issues/94",
            "https://github.com/liuli195/Quant-Trading/issues/104",
            "router dispatch 成功不写 success",
            "不维护 PR Flow changed-files 白名单",
            "接手快照 v3",
        ],
    }

    for path, tokens in required_docs.items():
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token in text, f"{path} missing {token}"


def test_issue_103_113_pr_flow_rules_are_documented() -> None:
    required_docs = {
        Path("docs/rules/pr-workflow.md"): [
            "刷新 PR Evidence JSON、ready-for-review、通过 local stable gate 后按风险/授权触发官方 Codex review、等待 required checks",
            "WORKTREE_DIRTY_AFTER_CLEANUP",
            "cleanup_worktree_health",
            "不自动恢复、不自动删除、不自动修复",
        ],
        Path("docs/rules/governance.md"): [
            "`verify-full` 是 head/diff 级别检查",
            "`PR Flow / evidence` 保留 PR body `edited` 触发",
            "`PR Flow / review-status` 保留 review/thread/workflow_dispatch 触发",
            "不新增 live PR state guard",
            "PR-scoped concurrency",
        ],
        Path("docs/rules/review-guidelines.md"): [
            "current-head verdict",
            "P2/P3 only + all threads resolved",
            "latest current-head trigger",
        ],
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"): [
            "https://github.com/liuli195/Quant-Trading/issues/103",
            "https://github.com/liuli195/Quant-Trading/issues/113",
            "WORKTREE_DIRTY_AFTER_CLEANUP",
            "`ready_for_review` 回归 GitHub 语义",
            "current-head verdict",
        ],
        Path("scripts/research/governance/README.md"): [
            "sync PR Evidence",
            "ready-for-review",
            "WORKTREE_DIRTY_AFTER_CLEANUP",
        ],
    }

    for path, tokens in required_docs.items():
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token in text, f"{path} missing {token}"


def test_issue_97_114_120_pr_flow_rules_are_documented() -> None:
    required_docs = {
        Path("docs/rules/pr-workflow.md"): [
            "review-fragments-handoff.json",
            "thread-closure-evidence.json",
            "WAITING_LOCAL_STABILIZATION",
            "`PR Flow / review-status` 不参与 local stable gate",
        ],
        Path("docs/rules/review-guidelines.md"): [
            "review-fragments-handoff.json",
            "thread-closure-evidence.json",
            "不解析自然语言",
        ],
        Path("docs/rules/governance.md"): [
            "local stable gate",
            "`Research Governance / verify-full` 和 `PR Flow / evidence`",
            "pre-push freshness 仍只提醒",
        ],
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"): [
            "https://github.com/liuli195/Quant-Trading/issues/120",
            "https://github.com/liuli195/Quant-Trading/issues/114",
            "https://github.com/liuli195/Quant-Trading/issues/97",
            "submit_local_stabilization",
        ],
        Path("scripts/research/governance/README.md"): [
            "review-fragments-handoff.json",
            "thread-closure-evidence.json",
            "WAITING_LOCAL_STABILIZATION",
        ],
        Path(".agents/skills/repo-pr-governance/SKILL.md"): [
            "build-review-fragment",
            "build-thread-closure-evidence",
            "WAITING_LOCAL_STABILIZATION",
        ],
    }

    for path, tokens in required_docs.items():
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token in text, f"{path} missing {token}"


def _write_fragment(
    root: Path,
    role: str,
    *,
    findings: list[dict[str, str]],
    head: str = "1" * 40,
    diff: str = DEFAULT_DIFF_HASH,
    security_review: dict[str, str] | None = None,
    delegation_attempt: dict[str, object] | None = DEFAULT_DELEGATION_ATTEMPT,
) -> None:
    path = root / ".local" / "ai-review" / "fragments" / f"{role}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema": 2,
        "head": head,
        "diff": diff,
        "findings": findings,
    }
    if role in {"standards", "spec"} and delegation_attempt is not None:
        payload["delegation_attempt"] = delegation_attempt
    if role == "security":
        payload["security_review"] = security_review or {"tool": "codex-security"}
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _write_fragment_without_security_review(
    root: Path,
    *,
    findings: list[dict[str, str]],
    head: str = "1" * 40,
    diff: str = DEFAULT_DIFF_HASH,
) -> None:
    path = root / ".local" / "ai-review" / "fragments" / "security.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": 2,
                "head": head,
                "diff": diff,
                "findings": findings,
            }
        ),
        encoding="utf-8",
    )


def _managed_evidence_body(payload: dict[str, object]) -> str:
    return (
        "<!-- pr-flow:start -->\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```\n"
        "<!-- pr-flow:end -->\n"
    )


def _contract_evidence_payload() -> dict[str, object]:
    return {
        "schema": 2,
        "head": "a" * 40,
        "diff": "diff-hash",
        "reviews": {
            "standards": {"head": "a" * 40, "diff": "diff-hash"},
            "spec": {"head": "a" * 40, "diff": "diff-hash"},
            "security": {"head": "a" * 40, "diff": "diff-hash"},
        },
        "official_review": {"decision": "required"},
        "issues": {
            "commits": [
                {
                    "sha": "1" * 40,
                    "issues": [{"number": 66, "role": "closes"}],
                },
                {"sha": "2" * 40, "no_issue": True},
            ],
            "refs": [
                {
                    "number": 65,
                    "role": "reference",
                },
                {
                    "number": 66,
                    "role": "closes",
                },
            ],
        },
        "retained": [
            {
                "severity": "P2",
                "source": "security",
                "detail": "accepted follow-up",
            }
        ],
    }


def _current_head_trigger_comment(*, head: str = "1" * 40) -> dict[str, object]:
    return {
        "id": 1,
        "body": pr_flow.render_codex_review_request(
            pr_url="https://github.com/liuli195/Quant-Trading/pull/88",
            head_sha=head,
            review_scope=(),
        ),
        "created_at": "2026-06-01T10:00:00Z",
        "updated_at": "2026-06-01T10:00:00Z",
        "user": {"login": "liuli195"},
    }


def _codex_eyes_reaction(*, created_at: str) -> dict[str, object]:
    return {
        "content": "eyes",
        "created_at": created_at,
        "user": {"login": "chatgpt-codex-connector[bot]"},
    }


def _payload_from_managed_body(body: str) -> dict[str, object]:
    payload = body.split("```json\n", 1)[1].split("\n```", 1)[0]
    parsed = json.loads(payload)
    assert isinstance(parsed, dict)
    return parsed


def _write_branch_intent(
    root: Path,
    *,
    branch: str = "feature/contract",
    commit_issues: list[dict[str, object]] | None = None,
    refs: list[dict[str, object]] | None = None,
) -> None:
    path = root / ".local/pr-flow/intents" / f"{branch}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    commit_issues = commit_issues or [{"number": 66, "role": "closes"}]
    refs = refs or [
        {"number": 65, "role": "reference"},
        {"number": 66, "role": "closes"},
    ]
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "branch": branch,
                "commits": [
                    {
                        "commit_sha": "1" * 40,
                        "issue_policy": "issues",
                        "issues": commit_issues,
                    },
                    {
                        "commit_sha": "2" * 40,
                        "issue_policy": "no_issue",
                        "no_issue_authorization": {
                            "reason": "format-only",
                            "authorized_by": "liuli195",
                            "evidence": "maintenance",
                        },
                    },
                ],
                "issues": refs,
                "no_issue_authorizations": [],
            }
        ),
        encoding="utf-8",
    )


def _write_resolve_threads_plan(
    root: Path,
    *,
    thread_id: str,
    severity: str,
    head: str,
    diff: str,
) -> None:
    path = root / ".local/pr-flow/resolve-threads-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository": "liuli195/Quant-Trading",
                "pr_number": "88",
                "head_sha": head,
                "diff_hash": diff,
                "threads": [
                    {
                        "thread_id": thread_id,
                        "severity": severity,
                        "closure_evidence_state": "missing",
                        "current_head_sha": head,
                        "current_diff_hash": diff,
                        "target_evidence_path": (
                            ".local/pr-flow/thread-closure-evidence.json"
                        ),
                        "required_dispositions": ["fixed", "false_positive"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_thread_closure_evidence(root: Path, finding: dict[str, object]) -> None:
    path = root / ".local" / "pr-flow" / "thread-closure-evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": pr_flow.THREAD_PROCESSING_SCHEMA_VERSION,
                "external_findings": [finding],
            }
        ),
        encoding="utf-8",
    )
