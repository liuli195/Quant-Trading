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
    def __init__(self, *, diff_text: str, checks_bucket: str = "pass") -> None:
        super().__init__(valid_contract=True)
        self.diff_text = diff_text
        self.checks_bucket = checks_bucket
        self.created_bodies: list[str] = []
        self.comments: list[str] = []
        self.lifecycle_calls: list[list[str]] = []

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
        if command == ["gh", "pr", "view", "--json", "number,url,state,isDraft"]:
            return pr_flow.CommandResult(1, "", "no pull request")
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
            return pr_flow.CommandResult(0, "auto-merge enabled\n", "")
        if command == [
            "gh",
            "pr",
            "view",
            "88",
            "--json",
            "number,state,mergedAt,headRefName,baseRefName,isCrossRepository",
        ]:
            self.lifecycle_calls.append(command)
            return pr_flow.CommandResult(
                0,
                json.dumps(
                    {
                        "number": 88,
                        "state": "MERGED",
                        "mergedAt": "2026-06-01T10:00:00Z",
                        "headRefName": "feature/contract",
                        "baseRefName": "main",
                        "isCrossRepository": False,
                    }
                ),
                "",
            )
        if command in (
            ["git", "fetch", "--prune", "origin"],
            ["git", "switch", "main"],
            ["git", "merge", "--ff-only", "origin/main"],
            ["git", "branch", "-d", "feature/contract"],
        ):
            self.lifecycle_calls.append(command)
            return pr_flow.CommandResult(0, "", "")
        return super().run(command, cwd=cwd, input_text=input_text)


def test_contract_loads_required_checks_and_writes_submit_status(tmp_path: Path) -> None:
    contract = pr_flow_contract.load_contract(Path("."))

    assert contract.required_checks == (
        "PR Flow / review-status",
        "Research Governance / verify-full",
        "PR Flow / evidence",
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
    body = _managed_evidence_body(
        {
            "schema": 1,
            "head": "a" * 40,
            "diff": "diff-hash",
            "reviews": {
                "standards": {"head": "a" * 40, "diff": "diff-hash"},
                "spec": {"head": "a" * 40, "diff": "diff-hash"},
                "security": {"head": "a" * 40, "diff": "diff-hash"},
            },
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
                        "ac_checked": True,
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
    )

    report = pr_review_evidence.validate_pr_body(
        body,
        expected_head_sha="a" * 40,
        expected_commit_shas=("1" * 40, "2" * 40),
    )

    assert report.ok, report.errors


def test_submit_creates_draft_pr_with_contract_evidence_json(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text)
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
    assert list(payload) == ["schema", "head", "diff", "reviews", "issues", "retained"]
    assert payload["head"] == "1" * 40
    assert payload["diff"] == diff_hash
    assert payload["reviews"] == {
        "standards": {"head": "1" * 40, "diff": diff_hash},
        "spec": {"head": "1" * 40, "diff": diff_hash},
        "security": {"head": "1" * 40, "diff": diff_hash},
    }
    issues = payload["issues"]
    assert isinstance(issues, dict)
    assert issues["commits"] == [
        {"sha": "1" * 40, "issues": [{"number": 66, "role": "closes"}]},
        {"sha": "2" * 40, "no_issue": True},
    ]
    assert issues["refs"] == [
        {"number": 65, "role": "reference"},
        {"number": 66, "role": "closes", "ac_checked": True},
    ]
    assert payload["retained"] == [
        {"severity": "P2", "source": "security", "detail": "accepted follow-up"}
    ]
    assert runner.comments
    assert "@codex review" in runner.comments[-1]
    assert "https://github.com/liuli195/Quant-Trading/pull/88" in runner.comments[-1]
    assert "1" * 40 in runner.comments[-1]


def test_submit_waits_on_pending_required_checks_until_timeout(tmp_path: Path) -> None:
    diff_text = "diff --git a/a.txt b/a.txt\n+hello\n"
    diff_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    runner = SubmitCreatePrRunner(diff_text=diff_text, checks_bucket="pending")
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


def test_codex_review_status_uses_contract_context_and_pending(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(**kwargs: object) -> object:
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(codex_review_monitor, "_request_json", fake_request_json)
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


def _write_fragment(
    root: Path,
    role: str,
    *,
    findings: list[dict[str, str]],
    diff: str = "current-diff",
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


def _managed_evidence_body(payload: dict[str, object]) -> str:
    return (
        "<!-- pr-flow:start -->\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```\n"
        "<!-- pr-flow:end -->\n"
    )


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
