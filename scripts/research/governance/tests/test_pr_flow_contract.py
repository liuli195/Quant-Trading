from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.research.governance import (
    codex_review_monitor,
    pr_flow,
    pr_flow_contract,
    pr_review_evidence,
)


DEFAULT_DIFF_TEXT = "diff --git a/a.txt b/a.txt\n+hello\n"
DEFAULT_DIFF_HASH = hashlib.sha256(DEFAULT_DIFF_TEXT.encode("utf-8")).hexdigest()


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
        self.auto_merge_requested = existing_state.upper() == "MERGED"
        self.created_bodies: list[str] = []
        self.edited_bodies: list[str] = []
        self.comments: list[str] = []
        self.lifecycle_calls: list[list[str]] = []
        self.cwd_calls: list[tuple[list[str], Path | None]] = []

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> pr_flow.CommandResult:
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
        if command[:4] == ["gh", "pr", "edit", "88"]:
            body_file = Path(command[command.index("--body-file") + 1])
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
            self.created_bodies.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(
                0,
                "https://github.com/liuli195/Quant-Trading/pull/88\n",
                "",
            )
        if command[:3] == ["gh", "pr", "comment"]:
            body_file = Path(command[command.index("--body-file") + 1])
            self.comments.append(body_file.read_text(encoding="utf-8"))
            return pr_flow.CommandResult(0, "", "")
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
            "pr",
            "checks",
            "88",
            "--required",
            "--json",
            pr_flow.CHECKS_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(
                self.checks_returncode,
                json.dumps(
                    [
                        {
                            "name": "PR Flow / review-status",
                            "workflow": "",
                            "state": "PENDING"
                            if self.checks_bucket == "pending"
                            else "SUCCESS",
                            "bucket": self.checks_bucket,
                            "link": "",
                        },
                        {
                            "name": "verify-full",
                            "workflow": "Research Governance",
                            "state": "SUCCESS",
                            "bucket": "pass",
                            "link": "https://github.com/runs/1",
                        },
                        {
                            "name": "evidence",
                            "workflow": "PR Flow",
                            "state": "SUCCESS",
                            "bucket": "pass",
                            "link": "https://github.com/runs/2",
                        },
                    ]
                ),
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
        if command == [
            "gh",
            "pr",
            "checks",
            "88",
            "--required",
            "--json",
            pr_flow.CHECKS_JSON_FIELDS,
        ]:
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "name": "evidence",
                            "workflow": "PR Flow",
                            "state": "FAILURE",
                            "bucket": "fail",
                            "link": "https://github.com/runs/evidence",
                        },
                        {
                            "name": "verify-full",
                            "workflow": "Research Governance",
                            "state": "FAILURE",
                            "bucket": "fail",
                            "link": "https://github.com/runs/verify",
                        },
                        {
                            "name": "PR Flow / review-status",
                            "workflow": "",
                            "state": "FAILURE",
                            "bucket": "fail",
                            "link": "https://github.com/runs/review",
                        },
                    ]
                ),
                "",
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


class SubmitOfficialCodexRetainedRunner(SubmitCreatePrRunner):
    def __init__(self, *, diff_text: str) -> None:
        super().__init__(diff_text=diff_text)
        self.checks_calls = 0
        self.thread_id = "PRRT_official_p2"
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
        if (
            command[:6]
            == ["gh", "pr", "checks", "88", "--required", "--json"]
        ):
            self.checks_calls += 1
            review_bucket = "fail" if self.checks_calls == 1 else "pass"
            review_state = "FAILURE" if self.checks_calls == 1 else "SUCCESS"
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "name": "PR Flow / review-status",
                            "workflow": "",
                            "state": review_state,
                            "bucket": review_bucket,
                            "link": "https://github.com/checks/review",
                        },
                        {
                            "name": "verify-full",
                            "workflow": "Research Governance",
                            "state": "SUCCESS",
                            "bucket": "pass",
                            "link": "https://github.com/runs/1",
                        },
                        {
                            "name": "evidence",
                            "workflow": "PR Flow",
                            "state": "SUCCESS",
                            "bucket": "pass",
                            "link": "https://github.com/runs/2",
                        },
                    ]
                ),
                "",
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
                                                            "body": "**P2** retain as follow-up",
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


def test_contract_loads_required_checks_and_writes_submit_status(tmp_path: Path) -> None:
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

    status_path = pr_flow_contract.write_submit_status(
        tmp_path,
        contract,
        head="1" * 40,
        failures=[
            pr_flow_contract.SubmitFailure(
                check="PR Flow / evidence",
                source="https://github.com/liuli195/Quant-Trading/actions/runs/1",
                detail="line one\nline two " + ("x" * 260),
            )
        ],
    )

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert list(payload) == ["schema", "head", "failures"]
    assert list(payload["failures"][0]) == ["check", "source", "detail"]
    assert payload["schema"] == 1
    assert payload["head"] == "1" * 40
    assert "\n" not in payload["failures"][0]["detail"]
    assert len(payload["failures"][0]["detail"]) <= contract.detail_max_chars


def test_submit_fails_fast_when_github_contract_preflight_is_missing(
    tmp_path: Path,
) -> None:
    runner = SubmitPreflightRunner()

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert list(status) == ["schema", "head", "failures"]
    assert status["head"] == "1" * 40
    assert status["failures"] == [
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


def test_submit_reports_missing_first_stage_review_fragments(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"] == [
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


def test_submit_requires_security_only_after_first_stage_passes(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(tmp_path, "standards", findings=[])
    _write_fragment(tmp_path, "spec", findings=[])

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"] == [
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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"] == [
        {
            "check": "local-review",
            "source": ".local/ai-review/fragments/standards.json",
            "detail": "standards fragment diff is stale",
        }
    ]


def test_submit_aggregates_first_stage_blockers_before_security(tmp_path: Path) -> None:
    runner = SubmitPreflightRunner(valid_contract=True)
    _write_fragment(
        tmp_path,
        "standards",
        findings=[{"severity": "P1", "detail": "rules drift"}],
    )
    _write_fragment(
        tmp_path,
        "spec",
        findings=[{"severity": "P0", "detail": "AC not implemented"}],
    )

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"] == [
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


def test_pr_review_evidence_accepts_contract_v1_managed_json() -> None:
    body = _managed_evidence_body(_contract_evidence_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert report.ok, report.errors


def test_pr_review_evidence_accepts_legacy_contract_v1_without_official_review() -> (
    None
):
    payload = _contract_evidence_payload()
    payload.pop("official_review")
    body = _managed_evidence_body(payload)

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert report.ok, report.errors


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


def test_pr_review_evidence_rejects_contract_v1_unresolved_threads() -> None:
    body = _managed_evidence_body(_contract_evidence_payload())

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_diff_hash="diff-hash",
        expected_commit_shas=("1" * 40, "2" * 40),
        review_threads=[{"isResolved": False}],
    )

    assert not report.ok
    assert "Codex review must not have unresolved review threads" in report.errors


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
        {"number": 65, "role": "reference"},
        {"number": 66, "role": "closes"},
    ]
    assert payload["retained"] == [
        {"severity": "P2", "source": "security", "detail": "accepted follow-up"}
    ]
    assert runner.comments
    assert "@codex review" in runner.comments[-1]
    assert "https://github.com/liuli195/Quant-Trading/pull/88" in runner.comments[-1]
    assert "1" * 40 in runner.comments[-1]


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
    status = json.loads((tmp_path / ".local" / "pr-flow" / "status.json").read_text())
    assert status["failures"] == [
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
    assert runner.checks_calls == 2
    assert runner.replies
    assert runner.resolved_threads == [runner.thread_id]
    payload = _payload_from_managed_body(runner.edited_bodies[-1])
    retained = payload["retained"]
    assert isinstance(retained, list)
    assert {
        "severity": "P2",
        "source": "official_codex",
        "detail": "**P2** retain as follow-up",
    } in retained


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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"][0]["check"] == "issue-intent"
    assert status["failures"][0]["source"] == ".local/pr-flow/intents"
    assert (
        "branch intent does not cover all current branch commits"
        in status["failures"][0]["detail"]
    )
    assert "111111111111" in status["failures"][0]["detail"]


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
        {"number": 65, "role": "reference"},
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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"][0]["check"] == "issue-intent"
    assert runner.update_branch_sha in status["failures"][0]["detail"]


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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"][0]["check"] == "issue-intent"
    assert runner.update_branch_sha in status["failures"][0]["detail"]


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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"][0]["check"] == "issue-intent"
    assert runner.update_branch_sha in status["failures"][0]["detail"]


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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"] == [
        {
            "check": "PR Flow / review-status",
            "source": "",
            "detail": "required check timed out while pending",
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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert [failure["check"] for failure in status["failures"]] == [
        "PR Flow / review-status",
        "Research Governance / verify-full",
        "PR Flow / evidence",
    ]
    assert [failure["source"] for failure in status["failures"]] == [
        "https://github.com/runs/review",
        "https://github.com/runs/verify",
        "https://github.com/runs/evidence",
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
            "schema": 1,
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
    status = json.loads(
        (tmp_path / ".local/pr-flow/status.json").read_text(encoding="utf-8")
    )
    assert status["failures"] == []


def test_submit_reports_exception_when_remote_head_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = MissingSubmitRemoteHeadRunner(diff_text=diff_text)
    _write_fragment(tmp_path, "standards", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "spec", findings=[], diff=diff_hash)
    _write_fragment(tmp_path, "security", findings=[], diff=diff_hash)
    _write_branch_intent(tmp_path)

    code = pr_flow.submit(repo_root=tmp_path, title="PR 自动化", runner=runner)

    captured = capsys.readouterr()
    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "EXCEPTION_REQUIRED" in captured.err
    assert "PUSH_REQUIRED" not in captured.err
    assert "git push -u origin feature/contract" in captured.err
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


def test_codex_review_monitor_skips_low_risk_contract_v1_without_official_review() -> (
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
        changed_files=("docs/guides/example.md",),
        labels=(),
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


def _write_fragment(
    root: Path,
    role: str,
    *,
    findings: list[dict[str, str]],
    diff: str = DEFAULT_DIFF_HASH,
) -> None:
    path = root / ".local" / "ai-review" / "fragments" / f"{role}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "head": "1" * 40,
                "diff": diff,
                "findings": findings,
            }
        ),
        encoding="utf-8",
    )


def _write_ai_review_report(
    root: Path,
    *,
    risk_level: str = "low",
    requires_official: bool = False,
    changed_files: list[str] | None = None,
    skip_official: bool = False,
) -> None:
    payload = _ai_review_payload(
        risk_level=risk_level,
        requires_official=requires_official,
        changed_files=changed_files,
        skip_official=skip_official,
    )
    local = root / ".local" / "ai-review"
    local.mkdir(parents=True, exist_ok=True)
    (local / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ai_review_payload(
    *,
    risk_level: str = "low",
    requires_official: bool = False,
    changed_files: list[str] | None = None,
    skip_official: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 2,
        "tool": "codex",
        "reviewers": ["standards-reviewer", "spec-reviewer"],
        "risk_level": risk_level,
        "requires_official_codex_review": requires_official,
        "security_review": {
            "tool": "codex-security",
            "evidence": "local security review completed",
        },
        "cross_review": {
            "delegated_to_subagents": True,
            "review_skills": [
                "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
                "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
            ],
            "evidence": "standards and spec reviewers completed",
        },
        "complete_review": {
            "evidence": "reviewers reached no new findings",
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
        "changed_files": changed_files or ["docs/guides/example.md"],
        "findings": [],
        "checks": {},
    }
    if skip_official:
        payload["skip_official_codex_review"] = True
        payload["official_codex_review_skip_authorization"] = {
            "authorized_by": "liuli195",
            "reason": "current PR official review cost is higher than risk",
            "evidence": "user explicitly authorized skipping official review",
        }
    return payload


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
        "schema": 1,
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


def _current_head_trigger_comment() -> dict[str, object]:
    return {
        "id": 1,
        "body": pr_flow.render_codex_review_request(
            pr_url="https://github.com/liuli195/Quant-Trading/pull/88",
            head_sha="1" * 40,
            review_scope=(),
        ),
        "created_at": "2026-06-01T10:00:00Z",
        "updated_at": "2026-06-01T10:00:00Z",
        "user": {"login": "liuli195"},
    }


def _payload_from_managed_body(body: str) -> dict[str, object]:
    payload = body.split("```json\n", 1)[1].split("\n```", 1)[0]
    parsed = json.loads(payload)
    assert isinstance(parsed, dict)
    return parsed


def _write_branch_intent(root: Path) -> None:
    path = root / ".local/pr-flow/intents/feature/contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "branch": "feature/contract",
                "commits": [
                    {
                        "commit_sha": "1" * 40,
                        "issue_policy": "issues",
                        "issues": [{"number": 66, "role": "closes"}],
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
                "issues": [
                    {"number": 65, "role": "reference"},
                    {"number": 66, "role": "closes"},
                ],
                "no_issue_authorizations": [],
            }
        ),
        encoding="utf-8",
    )
