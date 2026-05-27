from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance.branch_protection import (
    check_pre_push_input,
    check_reference_transaction_input,
)
from scripts.research.governance.codex_review_monitor import (
    build_monitor_report,
    render_monitor_comment,
)
from scripts.research.governance import __main__ as governance_main
from scripts.research.governance import gate as governance_gate
from scripts.research.governance.codex_review_contract import (
    is_codex_review_request,
    render_codex_review_request,
)
import scripts.research.governance.pr_review_evidence as pr_review_evidence
from scripts.research.governance.pr_review_evidence import (
    BLOCKING_CODEX_FINDING_PATTERN,
    head_updated_at_from_monitor_state,
    _issue_label_names,
    _parse_next_link,
    render_monitor_head_state,
    validate_pr_body,
)
from scripts.research.governance.rules import run_audit
from scripts.research.registry import default_tool_registry


def _codex_review_request_body(
    *,
    pr_url: str = "https://github.com/liuli195/Quant-Trading/pull/5",
    head_sha: str = "0" * 40,
    review_scope: tuple[str, ...] = (
        "scripts/research/governance/pr_review_evidence.py",
    ),
) -> str:
    return render_codex_review_request(
        pr_url=pr_url,
        head_sha=head_sha,
        review_scope=review_scope,
    )


def test_codex_review_contract_accepts_fixed_template_with_scope() -> None:
    body = _codex_review_request_body(
        review_scope=(
            "scripts/research/governance/pr_review_evidence.py",
            "scripts/research/governance/codex_review_monitor.py",
        )
    )

    assert body == "\n".join(
        [
            "@codex review",
            "",
            "PR：https://github.com/liuli195/Quant-Trading/pull/5",
            f"HEAD：{'0' * 40}",
            "Review Scope：",
            "- scripts/research/governance/pr_review_evidence.py",
            "- scripts/research/governance/codex_review_monitor.py",
            "",
            "审查重点：仅 P0/P1 合并阻断风险",
        ]
    )
    assert is_codex_review_request(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha="0" * 40,
    )


def test_codex_review_contract_accepts_fixed_template_without_scope() -> None:
    body = _codex_review_request_body(review_scope=())

    assert body == "\n".join(
        [
            "@codex review",
            "",
            "PR：https://github.com/liuli195/Quant-Trading/pull/5",
            f"HEAD：{'0' * 40}",
            "Review Scope：",
            "",
            "审查重点：仅 P0/P1 合并阻断风险",
        ]
    )
    assert is_codex_review_request(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha="0" * 40,
    )
    assert not is_codex_review_request(
        "@codex review",
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha="0" * 40,
    )


def _write_minimal_repo(root: Path) -> None:
    for path in (
        "scripts/research",
        "scripts/research/platform",
        "scripts/research/registry",
        "scripts/research/registry/tests",
        "scripts/research/governance",
        "scripts/research/governance/tests",
        "scripts/research/research_core",
        "scripts/research/research_core/tests",
        "scripts/research/etf_window_research/tests",
        "scripts/research/momentum_tilt_research/tests",
        "scripts/research/execution_timing_research/tests",
        "scripts/research/portfolio_volatility_research/tests",
        "scripts/research/cash_decomposition",
        "scripts/research/workflows/templates",
        "scripts/tools/jq_automation/tests",
        "scripts/tools/path_tools",
        "docs/rules",
        "docs/adr",
        "docs/exceptions",
        "docs/indexes",
        "research_datasets/demo/snap",
        "research_datasets",
        ".github/workflows",
        ".githooks",
        ".claude/skills/jq-research",
        ".claude/skills/jq-ab-test",
        ".codex/skills/quant-pr-workflow/agents",
        ".codex/skills/quant-research-workflow/agents",
        "research_datasets/demo/snap/raw",
        "research_datasets/demo/snap/data",
    ):
        (root / path).mkdir(parents=True, exist_ok=True)

    for path in (
        "scripts/research/README.md",
        "scripts/research/platform/README.md",
        "scripts/research/registry/README.md",
        "scripts/research/governance/README.md",
        "scripts/research/research_core/README.md",
        "scripts/research/etf_window_research/README.md",
        "scripts/research/momentum_tilt_research/README.md",
        "scripts/research/execution_timing_research/README.md",
        "scripts/research/portfolio_volatility_research/README.md",
        "scripts/research/cash_decomposition/README.md",
        "scripts/research/workflows/README.md",
        "scripts/tools/jq_automation/README.md",
        "scripts/tools/path_tools/README.md",
        "docs/guides/research-workflow.md",
        "docs/architecture/research-platform-architecture.md",
        "docs/rules/index.md",
        "docs/rules/pr-workflow.md",
        "docs/rules/governance.md",
        "docs/rules/review-guidelines.md",
        "docs/rules/commands.md",
        "docs/rules/environments.md",
        "docs/rules/research-workflow.md",
        "docs/rules/collaboration.md",
        "docs/rules/code-style.md",
        "docs/rules/docs-and-pathref.md",
        "docs/adr/0001-rule-source-and-governance-model.md",
        "docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md",
        "docs/adr/0003-governance-gate-and-main-branch-protection.md",
        "docs/adr/0004-codex-code-review-governance.md",
        "docs/adr/0005-ai-entry-progressive-disclosure.md",
        "research_datasets/README.md",
        "scripts/research/platform/tests/test_platform.py",
        "scripts/research/registry/tests/test_registry.py",
        "scripts/research/governance/tests/test_governance.py",
        "scripts/research/governance/tests/test_pr_flow.py",
        "scripts/research/research_core/tests/test_research_core.py",
        "scripts/research/etf_window_research/tests/test_analysis.py",
        "scripts/research/momentum_tilt_research/tests/test_analysis.py",
        "scripts/research/execution_timing_research/tests/test_analysis.py",
        "scripts/research/portfolio_volatility_research/tests/test_domain_builder.py",
        "scripts/tools/jq_automation/tests/test_core.py",
        "scripts/tools/jq_automation/tests/test_ab.py",
    ):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")

    (root / "CLAUDE.md").write_text(
        "Claude Code 专用指针。先读 AGENTS.md；Claude Code 专属内容见 .claude/skills。",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "所有 AI 编码助手统一以 AGENTS.md 为通用入口。\n\n"
        "本仓库是基于 Python 的 A 股/场内基金量化策略仓库。\n\n"
        "规则索引见 indexes.md。所有回答和输出使用简体中文，简洁直白。"
        "策略代码仅在聚宽云端运行。"
        "项目 `.venv` 默认提权执行，否则无法读取base Python路径。"
        "命令参考 docs/rules/commands.md。"
        "`gh` CLI 默认提权执行。"
        "进入主干须通过 PR；如用户显式授权，可以按直写主干链路直接提交和推送主干；"
        "禁止把功能分支本地合入 main，细则见 docs/rules/pr-workflow.md。"
        "分支名使用 ASCII 模板，提交说明使用简体中文。"
        "效率：所有任务默认优先派发子 agent，主会话负责编排。"
        "Markdown 内部文件引用使用可点击链接和 pathref。"
        "每次任务后清理临时产物。\n\n"
        "## Review 指南\n\n"
        "Review 前必须先阅读并遵守 docs/rules/review-guidelines.md。"
        "如果无法访问该文件，视为 review 被阻塞。\n",
        encoding="utf-8",
    )
    (root / "indexes.md").write_text(
        "AGENTS.md CLAUDE.md docs/rules/index.md docs/rules/commands.md "
        "docs/rules/review-guidelines.md docs/rules/pr-workflow.md docs/rules/governance.md "
        "docs/rules/environments.md docs/rules/code-style.md "
        "docs/rules/research-workflow.md docs/rules/collaboration.md "
        "docs/rules/docs-and-pathref.md docs/adr",
        encoding="utf-8",
    )
    (root / "docs/rules/commands.md").write_text(
        "scripts.research.cli scripts.research.datasets scripts.research.variants "
        "scripts.research.governance scripts.research.governance gate scripts.research.registry "
        "scripts.tools.path_tools.refactor .\\.githooks\\setup-python.ps1 "
        ".\\.githooks\\run-python.ps1 .githooks/setup-python.sh .githooks/run-python.sh "
        ".\\.venv\\Scripts\\python.exe .venv/bin/python PYTHONUTF8 PYTHONIOENCODING "
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "
        "gh pr checks `gh` CLI 默认提权执行",
        encoding="utf-8",
    )
    (root / "docs/guides/local-python-env.md").write_text(
        "git worktree add .\\.githooks\\setup-python.ps1 .githooks/setup-python.sh "
        "Codex Cloud Environment setup script Codex App Local Environment "
        "requirements-dev.txt\n",
        encoding="utf-8",
    )
    (root / ".githooks/pre-commit").write_text(
        "pre-commit run --hook-stage pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance gate --fast\n",
        encoding="utf-8",
    )
    (root / "Makefile").write_text(
        "ifeq ($(OS),Windows_NT)\n"
        "PYTHON ?= powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./.githooks/run-python.ps1\n"
        "else\n"
        "PYTHON ?= sh .githooks/run-python.sh\n"
        "endif\n"
        "pre-pr:\n\t$(PYTHON) -m pre_commit run --all-files\n"
        "ai-review:\n\t$(PYTHON) -m scripts.research.governance.ai_review_gate validate --report .local/ai-review/latest.json\n"
        "risk-check:\n\t$(PYTHON) -m scripts.research.governance.ai_review_gate risk --report .local/ai-review/latest.json\n"
        'pr-ready:\n\t$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)"\n',
        encoding="utf-8",
    )
    (root / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "  - repo: https://github.com/PyCQA/bandit\n"
        "  - repo: https://github.com/gitleaks/gitleaks\n",
        encoding="utf-8",
    )
    (root / "requirements-dev.txt").write_text(
        "pre-commit\nruff\nbandit\nmypy\npip-audit\n",
        encoding="utf-8",
    )
    (root / ".githooks/run-python.sh").write_text(
        'export PYTHONUTF8=1\nexport PYTHONIOENCODING=utf-8\nuname MINGW MSYS CYGWIN .venv/bin/python .venv/Scripts/python.exe "$@"\n',
        encoding="utf-8",
    )
    (root / ".githooks/run-python.ps1").write_text(
        '$env:PYTHONUTF8 = "1"\n$env:PYTHONIOENCODING = "utf-8"\n'
        "Console]::InputEncoding Console]::OutputEncoding $OutputEncoding & .venv\\Scripts\\python.exe @args\n",
        encoding="utf-8",
    )
    (root / ".githooks/setup-python.ps1").write_text(
        "3.12\nrequirements-dev.txt\ngit config core.hooksPath .githooks\n"
        "PYTHONUTF8\nPYTHONIOENCODING\n",
        encoding="utf-8",
    )
    (root / ".githooks/setup-python.sh").write_text(
        "python3.12\nrequirements-dev.txt\ngit config core.hooksPath .githooks\n"
        "PYTHONUTF8\nPYTHONIOENCODING\n",
        encoding="utf-8",
    )
    (root / ".githooks/pre-push").write_text(
        "\n".join(
            [
                "sh .githooks/run-python.sh -m scripts.research.governance.branch_protection pre-push",
                "sh .githooks/run-python.sh -m scripts.research.governance gate",
                "git lfs pre-push",
            ]
        ),
        encoding="utf-8",
    )
    (root / ".githooks/reference-transaction").write_text(
        "\n".join(
            [
                "STATE=${1:-}",
                "INPUT=$(cat)",
                'if [ "$STATE" = "prepared" ]; then',
                "if [ ! -x .venv/bin/python ] && [ ! -x .venv/Scripts/python.exe ]; then",
                "grep refs/heads/main",
                "grep refs/heads/master",
                "Project virtualenv Python not found",
                "fi",
                "sh .githooks/run-python.sh -m scripts.research.governance.branch_protection reference-transaction",
                "fi",
            ]
        ),
        encoding="utf-8",
    )
    (root / ".github/workflows/research-governance.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 2 * * 1'\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "steps:\n"
        "  - run: python -m ruff check scripts strategies\n"
        "  - run: python -m bandit -q -r scripts strategies\n"
        "  - run: python -m mypy scripts strategies\n"
        "  - run: python -m pip_audit\n"
        "  - run: python -m pytest\n"
        "  - run: python -m scripts.research.governance gate\n"
        "  - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )
    (root / ".github/workflows/codex-review-monitor.yml").write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  issue_comment:\n  pull_request_review:\n"
        "    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n"
        "    types: [created, edited, deleted]\n"
        "permissions:\n  statuses: write\nsteps:\n"
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-comment --sync-status\n",
        encoding="utf-8",
    )
    (root / "scripts/research/governance/README.md").write_text(
        "docs/rules/index.md docs/adr scripts.research.governance gate Codex Review Monitor "
        "git fetch origin main git merge --ff-only origin/main "
        "git branch -d <branch> git push origin --delete <branch>\n",
        encoding="utf-8",
    )
    (root / "docs/rules/pr-workflow.md").write_text(
        "所有进入主干的改动必须通过 PR\n直写主干 ALLOW_DIRECT_MAIN_WRITE DIRECT_MAIN_WRITE_REASON\n"
        "禁止把功能分支本地合入\n"
        "git fetch origin main\ngit merge --ff-only origin/main\n"
        "git branch -d <branch>\ngit push origin --delete <branch>\n",
        encoding="utf-8",
    )
    (root / "docs/rules/collaboration.md").write_text(
        "多个 AI agent\n分支名使用 ASCII\n本地共享工作区\n只读分析不要求创建分支\n"
        "有可用子 agent 能力\n无能力时记录原因\n不采用任务登记\n",
        encoding="utf-8",
    )
    (root / "docs/rules/governance.md").write_text(
        ".githooks/reference-transaction ALLOW_MAIN_REF_UPDATE MAIN_REF_UPDATE_REASON "
        "ALLOW_DIRECT_MAIN_WRITE DIRECT_MAIN_WRITE_REASON Codex Review Monitor "
        "review_mode=complete 官方 Codex Review 跳过授权 "
        "security_review 本地安全 review codex-security security-guidance "
        "git fetch origin main git merge --ff-only origin/main "
        "git branch -d <branch> git push origin --delete <branch> force delete\n",
        encoding="utf-8",
    )
    (root / "CODEOWNERS").write_text(
        "\n".join(
            [
                "CLAUDE.md @research-platform",
                "AGENTS.md @research-platform",
                "indexes.md @research-platform",
                "docs/rules/** @research-platform",
                "docs/adr/** @research-platform",
                ".codex/skills/** @research-platform",
                ".claude/skills/** @research-platform",
                ".github/workflows/** @research-platform",
                ".githooks/** @research-platform",
                "scripts/research/governance/** @research-platform",
                "scripts/research/registry/** @research-platform",
                "path_aliases.json @research-platform",
                "strategies/** @research-platform",
            ]
        ),
        encoding="utf-8",
    )
    (root / ".github/pull_request_template.md").write_text(
        "改动目标\n影响范围\n规则同步\n已运行检查\n子 agent 交叉评审\n"
        "superpowers:subagent-driven-development/spec-reviewer-prompt.md\n"
        "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md\n"
        "reviewers:\n"
        "任务分发说明\nhigh/unknown PR label\n官方 Codex Review 跳过授权\n"
        "本地 AI review 模式\n不完全 Review 模式授权\nCodex Code Review 结论\n"
        "本地安全 review\ncodex-security\nsecurity-guidance\n"
        "Codex\n"
        "<!-- pr-flow:start -->\n<!-- pr-flow:end -->\n"
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate\n"
        "waiver\n证据\n",
        encoding="utf-8",
    )
    (root / ".github/pull_request_template.md").write_text(
        "## 改动目标\n\n"
        "-\n\n"
        "## 影响范围\n\n"
        "-\n\n"
        "<!-- pr-flow:start -->\n"
        '运行 `make pr-ready TITLE="<PR标题>"` 后由脚本更新本区块。\n'
        "<!-- pr-flow:end -->\n\n"
        "## 人工补充\n\n"
        "- 额外证据链接：\n"
        "- waiver：\n",
        encoding="utf-8",
    )
    (root / "docs/rules/review-guidelines.md").write_text(
        "\n".join(
            [
                "# Codex Code Review 指南",
                "Codex Code Review",
                "@codex review",
                "AGENTS.md",
                "docs/rules/review-guidelines.md",
                "P0/P1",
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate",
                "Codex Review Monitor",
                "至少两个独立 reviewer",
                "子 agent 交叉评审",
                "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
                "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
                "reviewers:",
                "review_mode=complete",
                "review_mode=partial",
                "security_review",
                "本地安全 review",
                "codex-security",
                "security-guidance",
                "官方 Codex Review 跳过授权",
                "Codex Code Review 结论",
                "结论: 通过",
                "阻断问题: 无",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs/exceptions/active-waivers.yaml").write_text(
        "schema_version: 1\nwaivers: []\n",
        encoding="utf-8",
    )
    (root / ".claude/skills/jq-research/SKILL.md").write_text(
        "scripts.research.cli scripts.research.governance variant",
        encoding="utf-8",
    )
    (root / ".claude/skills/jq-ab-test/SKILL.md").write_text(
        "variant_id 参数变体 结构变体 scripts.research.variants",
        encoding="utf-8",
    )
    (root / ".codex/skills/quant-pr-workflow/SKILL.md").write_text(
        "Quant PR Workflow docs/rules/pr-workflow.md make pr-ready "
        "scripts.research.governance.pr_flow 不要把功能分支本地合入 main",
        encoding="utf-8",
    )
    (root / ".codex/skills/quant-pr-workflow/agents/openai.yaml").write_text(
        'display_name: "Quant PR 工作流"\n',
        encoding="utf-8",
    )
    (root / ".codex/skills/quant-research-workflow/SKILL.md").write_text(
        "Quant Research Workflow docs/rules/research-workflow.md "
        "scripts.research.cli scripts.research.governance 不要把本地 replay 结论包装成云端确认",
        encoding="utf-8",
    )
    (root / ".codex/skills/quant-research-workflow/agents/openai.yaml").write_text(
        'display_name: "Quant Research 工作流"\n',
        encoding="utf-8",
    )
    (root / "path_aliases.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "research-platform",
                "lifecycle": "active",
                "roots": {
                    "repo": ".",
                    "strategies": "strategies",
                    "research_datasets": "research_datasets",
                },
                "aliases": {"strategy_dir": "{strategies}/{strategy}"},
            }
        ),
        encoding="utf-8",
    )

    dataset = {
        "schema_version": 1,
        "dataset_id": "demo",
        "snapshot_id": "snap",
        "fingerprint": "sha256:x",
        "created_at": "2026-01-01T00:00:00+00:00",
        "owner": "research-platform",
        "lifecycle": "active",
        "row_count": 1,
        "date_range": ["2026-01-01", "2026-01-01"],
        "source": {"kind": "test"},
        "files": {"raw": "raw/source.json.gz", "canonical": "data/data.parquet"},
    }
    (root / "research_datasets/demo/snap/raw/source.json.gz").write_bytes(b"demo")
    (root / "research_datasets/demo/snap/data/data.parquet").write_bytes(b"demo")
    (root / "research_datasets/demo/snap/dataset.json").write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )
    (root / "research_datasets/catalog.json").write_text(
        json.dumps(
            [
                {
                    "dataset_id": "demo",
                    "snapshot_id": "snap",
                    "fingerprint": "sha256:x",
                    "row_count": 1,
                    "date_range": ["2026-01-01", "2026-01-01"],
                    "source_kind": "test",
                    "owner": "research-platform",
                    "lifecycle": "active",
                }
            ]
        ),
        encoding="utf-8",
    )
    for name in (
        "docs_catalog.json",
        "reports_catalog.json",
        "datasets_catalog.json",
        "variants_catalog.json",
    ):
        (root / "docs/indexes" / name).write_text(
            json.dumps({"reports": []}), encoding="utf-8"
        )

    for template in (
        "factor_scan",
        "parameter_followup",
        "robustness_check",
        "generic",
        "portfolio_volatility",
        "cloud_confirmation",
    ):
        (root / "scripts/research/workflows/templates" / f"{template}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "template": template,
                    "inputs": ["dataset"],
                    "stages": ["init", "fast"],
                    "outputs": ["manifest"],
                    "gates": ["documented"],
                }
            ),
            encoding="utf-8",
        )

    default_tool_registry().write_layer_docs(root / "scripts/research/layers")


def test_governance_audit_passes_minimal_repo_without_expensive_checks(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert report.ok
    assert report.findings == ()


def test_governance_main_forwards_fast_gate(monkeypatch, tmp_path: Path) -> None:
    captured: list[str] = []

    def fake_gate_main(argv: list[str]) -> int:
        captured.extend(argv)
        return 0

    monkeypatch.setattr(governance_main, "gate_main", fake_gate_main)

    code = governance_main.main(["gate", "--repo-root", str(tmp_path), "--fast"])

    assert code == 0
    assert captured == ["--repo-root", str(tmp_path), "--fast"]


def test_governance_gate_fast_skips_slow_checks_and_fails_on_audit_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class StubAudit:
        ok = False

        def to_dict(self) -> dict[str, object]:
            return {"ok": False, "findings": ["audit error"]}

    def fake_run_audit(
        root: Path,
        *,
        check_cli_help: bool,
        check_pathrefs: bool,
    ) -> StubAudit:
        captured["root"] = root
        captured["check_cli_help"] = check_cli_help
        captured["check_pathrefs"] = check_pathrefs
        return StubAudit()

    def fail_pathref(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("fast gate must not run pathref")

    monkeypatch.setattr(governance_gate, "run_audit", fake_run_audit)
    monkeypatch.setattr(governance_gate.subprocess, "run", fail_pathref)

    code = governance_gate.main(["--repo-root", str(tmp_path), "--fast"])

    assert code == 1
    assert captured == {
        "root": tmp_path.resolve(),
        "check_cli_help": False,
        "check_pathrefs": False,
    }


def test_governance_audit_flags_pre_commit_without_fast_gate(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-commit").write_text(
        "pre-commit run --hook-stage pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance gate\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-commit hook must use fast governance gate" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pre_push_with_fast_gate(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-push").write_text(
        "\n".join(
            [
                "sh .githooks/run-python.sh -m scripts.research.governance.branch_protection pre-push",
                "sh .githooks/run-python.sh -m scripts.research.governance gate --fast",
                "git lfs pre-push",
            ]
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-push hook must use full governance gate" in finding.message
        for finding in report.findings
    )


def test_local_review_entrypoints_are_tracked(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Makefile").write_text(
        "ifeq ($(OS),Windows_NT)\n"
        "PYTHON ?= powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./.githooks/run-python.ps1\n"
        "else\n"
        "PYTHON ?= sh .githooks/run-python.sh\n"
        "endif\n"
        "pre-pr:\n\t$(PYTHON) -m pre_commit run --all-files\n"
        "ai-review:\n\t$(PYTHON) -m scripts.research.governance.ai_review_gate validate --report .local/ai-review/latest.json\n"
        "risk-check:\n\t$(PYTHON) -m scripts.research.governance.ai_review_gate risk --report .local/ai-review/latest.json\n"
        'pr-ready:\n\t$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)"\n',
        encoding="utf-8",
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "  - repo: https://github.com/PyCQA/bandit\n"
        "  - repo: https://github.com/gitleaks/gitleaks\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements-dev.txt").write_text(
        "pre-commit\nruff\nbandit\nmypy\npip-audit\n",
        encoding="utf-8",
    )
    (tmp_path / ".githooks/pre-commit").write_text(
        "pre-commit run --hook-stage pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance gate --fast\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]


def test_local_review_entrypoints_require_pr_ready(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8").replace(
            'pr-ready:\n\t$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)"\n',
            "",
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "local_review"
        and "Makefile missing pr-ready" in finding.message
        for finding in report.findings
    )


def test_tool_registry_registers_pr_flow_cli() -> None:
    tool = default_tool_registry().get("research.pr_flow")

    assert tool.entry_module == "scripts.research.governance.pr_flow"
    assert "ready" in (tool.cli or "")


def test_local_review_entrypoints_require_posix_make_wrapper(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Makefile").write_text(
        "PYTHON := powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./.githooks/run-python.ps1\n"
        "pre-pr:\n\t$(PYTHON) -m pre_commit run --all-files\n"
        "ai-review:\n\t$(PYTHON) -m scripts.research.governance.ai_review_gate validate --report .local/ai-review/latest.json\n"
        "risk-check:\n\t$(PYTHON) -m scripts.research.governance.ai_review_gate risk --report .local/ai-review/latest.json\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "local_review"
        and finding.message == "Makefile must use run-python.sh on non-Windows"
        for finding in report.findings
    )


def test_governance_audit_flags_missing_local_review_entrypoints(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Makefile").unlink()

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(finding.rule_id == "local_review" for finding in report.findings)


def test_governance_audit_flags_catalog_drift(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "research_datasets/catalog.json").write_text("[]", encoding="utf-8")
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "dataset_catalog" for finding in report.findings)


def test_governance_audit_flags_unregistered_cli_module(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    tool = tmp_path / "scripts/research/new_tool.py"
    tool.write_text(
        "\n".join(
            [
                "import argparse",
                "",
                "def main(argv=None):",
                "    parser = argparse.ArgumentParser()",
                "    parser.parse_args(argv)",
                "    return 0",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        "CLI module not registered: scripts.research.new_tool" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_stale_layer_docs(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "scripts/research/layers/strategy_library.md").write_text(
        "stale\n", encoding="utf-8"
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "layer_docs" for finding in report.findings)


def test_governance_audit_flags_invalid_path_aliases(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "path_aliases.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "",
                "lifecycle": "active",
                "roots": {},
                "aliases": {},
            }
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "path_aliases" for finding in report.findings)


def test_governance_audit_flags_project_config_without_owner(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    project = tmp_path / "strategies/demo/reports/research/topic/project.json"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "strategy": "demo",
                "project": "topic",
                "template": "generic",
                "plugin": "generic",
                "datasets": [],
                "inputs": {},
                "runtime": {
                    "fast_top_k": 1,
                    "cloud_top_k": 0,
                    "fast_mode_slo_seconds": 1.0,
                    "full_mode_slo_seconds": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "project_config" and "owner is required" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_codeowners_coverage(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "CODEOWNERS").write_text(
        "CLAUDE.md @research-platform\n", encoding="utf-8"
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "codeowners" and "docs/rules/**" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_invalid_pr_template(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/pull_request_template.md").write_text(
        "改动目标\n", encoding="utf-8"
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "pr_template" and "pr-flow:start" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pr_template_without_pr_flow_block(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    template = tmp_path / ".github/pull_request_template.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("<!-- pr-flow:start -->", ""),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "pr_template" and "pr-flow:start" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_review_guidelines(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/rules/review-guidelines.md").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "review_guidelines" for finding in report.findings)


def test_governance_audit_flags_workflow_without_review_evidence_gate(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/research-governance.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 2 * * 1'\nsteps:\n"
        "  - run: python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate" and "PR review evidence" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_review_evidence_without_inline_comment_deleted_event(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/research-governance.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 2 * * 1'\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited]\nsteps:\n"
        "  - run: python -m scripts.research.governance gate\n"
        "  - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "deleted inline review comments" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_review_evidence_without_review_dismissed_event(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/research-governance.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 2 * * 1'\n"
        "  pull_request_review:\n    types: [submitted, edited]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\nsteps:\n"
        "  - run: python -m scripts.research.governance gate\n"
        "  - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate" and "dismissed events" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_review_evidence_without_label_events(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/research-governance.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 2 * * 1'\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\nsteps:\n"
        "  - run: python -m scripts.research.governance gate\n"
        "  - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "labeled and unlabeled events" in finding.message
        for finding in report.findings
    )


def test_governance_workflow_contains_pr_review_evidence_gate(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/research-governance.yml"
    workflow.write_text(
        "name: Research Governance\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "  schedule:\n    - cron: '0 2 * * 1'\n"
        "jobs:\n"
        "  governance:\n"
        "    steps:\n"
        "      - run: python -m ruff check scripts strategies\n"
        "      - run: python -m bandit -q -r scripts strategies\n"
        "      - run: python -m mypy scripts strategies\n"
        "      - run: python -m pip_audit\n"
        "      - run: python -m pytest\n"
        "      - run: python -m scripts.research.governance gate\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]


def test_governance_audit_flags_workflow_without_pr_review_evidence_gate(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/research-governance.yml"
    workflow.write_text(
        "name: Research Governance\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "  schedule:\n    - cron: '0 2 * * 1'\n"
        "jobs:\n"
        "  governance:\n"
        "    steps:\n"
        "      - run: python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        "CI workflow missing PR review evidence gate" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_codex_review_monitor(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/codex-review-monitor.yml").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "codex_review_monitor" for finding in report.findings)


def test_governance_audit_flags_governance_docs_without_required_monitor_status(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/rules/governance.md").write_text(
        ".githooks/reference-transaction ALLOW_MAIN_REF_UPDATE MAIN_REF_UPDATE_REASON\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "Codex Review Monitor" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_monitor_without_inline_comment_deleted_event(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/codex-review-monitor.yml").write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened]\n"
        "  issue_comment:\n    types: [created, edited, deleted]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited]\n"
        "permissions:\n  statuses: write\nsteps:\n"
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-comment --sync-status\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "deleted inline review comments" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_monitor_without_review_dismissed_event(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/codex-review-monitor.yml").write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened]\n"
        "  issue_comment:\n    types: [created, edited, deleted]\n"
        "  pull_request_review:\n    types: [submitted, edited]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "permissions:\n  statuses: write\nsteps:\n"
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-comment --sync-status\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "dismissed events" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_monitor_without_label_events(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/codex-review-monitor.yml").write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened, edited]\n"
        "  issue_comment:\n    types: [created, edited, deleted]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "permissions:\n  statuses: write\nsteps:\n"
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-comment --sync-status\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "pull_request labeled and unlabeled events" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_expired_waiver(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/exceptions/active-waivers.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "waivers:",
                "  - id: WAIVER-2000-001",
                "    rule_id: test-rule",
                "    path: docs/**",
                "    reason: test",
                "    owner: research-platform",
                "    approved_by: research-platform",
                "    expires_at: 2000-01-01",
                "    migration_plan: docs/migration.md",
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "waiver" and "expired" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_adr_number_gap(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "adr" and "continuous" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_pre_push_branch_protection(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-push").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate" and "pre-push" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_posix_hook_python_wrapper(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.sh").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate" and "run-python.sh" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_python_setup_scripts(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/setup-python.ps1").unlink(missing_ok=True)
    (tmp_path / ".githooks/setup-python.sh").unlink(missing_ok=True)
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and ".githooks/setup-python.ps1 missing" in finding.message
        for finding in report.findings
    )
    assert any(
        finding.rule_id == "governance_gate"
        and ".githooks/setup-python.sh missing" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_python_env_docs_without_setup_examples(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/guides").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/guides/local-python-env.md").write_text(
        "run-python wrapper only\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/rules/commands.md").write_text(
        "scripts.research.cli scripts.research.datasets scripts.research.variants "
        "scripts.research.governance scripts.research.registry "
        "scripts.tools.path_tools.refactor .\\.githooks\\run-python.ps1 "
        ".githooks/run-python.sh .\\.venv\\Scripts\\python.exe .venv/bin/python "
        "PYTHONUTF8 PYTHONIOENCODING powershell.exe -NoProfile "
        "-ExecutionPolicy Bypass -File",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "command_rules"
        and "local-python-env.md missing worktree setup example" in finding.message
        for finding in report.findings
    )
    assert any(
        finding.rule_id == "command_rules"
        and "commands.md missing .\\.githooks\\setup-python.ps1" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_single_platform_hook_python_wrapper(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.sh").write_text(
        '.venv/Scripts/python.exe "$@"\n',
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "run-python.sh missing .venv/bin/python" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_hook_python_wrapper_without_platform_branch(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.sh").write_text(
        "\n".join(
            [
                'if [ -x ".venv/bin/python" ]; then',
                '  exec ".venv/bin/python" "$@"',
                'elif [ -x ".venv/Scripts/python.exe" ]; then',
                '  exec ".venv/Scripts/python.exe" "$@"',
                "fi",
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "run-python.sh must choose venv by platform" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_hook_python_wrapper_system_python_fallback(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.sh").write_text(
        "\n".join(
            [
                'if [ -x ".venv/bin/python" ]; then',
                '  PYTHON=".venv/bin/python"',
                'elif [ -x ".venv/Scripts/python.exe" ]; then',
                '  PYTHON=".venv/Scripts/python.exe"',
                "else",
                '  PYTHON="python"',
                "fi",
                'exec "$PYTHON" "$@"',
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "run-python.sh must not fall back to system Python" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_posix_hook_python_wrapper_without_utf8_env(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.sh").write_text(
        'uname MINGW MSYS CYGWIN .venv/bin/python .venv/Scripts/python.exe "$@"\n',
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "run-python.sh missing UTF-8 environment" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_powershell_hook_python_wrapper_without_utf8_env(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.ps1").write_text(
        "& .venv\\Scripts\\python.exe @args\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "run-python.ps1 missing UTF-8 environment" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_powershell_hook_python_wrapper_system_python_fallback(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/run-python.ps1").write_text(
        'if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }\n'
        "& $Python @args\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "run-python.ps1 must not fall back to system Python" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_hooks_that_require_powershell(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-commit").write_text(
        "powershell.exe -NoProfile -File .githooks/run-python.ps1 -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-commit hook must use run-python.sh" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pre_push_without_gate(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-push").write_text(
        "python -m scripts.research.governance.branch_protection pre-push\n"
        "git lfs pre-push\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-push hook missing governance gate" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pre_push_without_lfs_handoff(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-push").write_text(
        "python -m scripts.research.governance.branch_protection pre-push\n"
        "python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate" and "Git LFS handoff" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_reference_transaction_hook(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/reference-transaction").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "reference-transaction" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_reference_transaction_without_branch_protection(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/reference-transaction").write_text(
        "exit 0\n", encoding="utf-8"
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "local branch protection" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_reference_transaction_without_pre_setup_guard(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/reference-transaction").write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                'STATE="${1:-}"',
                'if [ "$STATE" = "prepared" ]; then',
                "  sh .githooks/run-python.sh -m scripts.research.governance.branch_protection reference-transaction",
                "fi",
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "reference-transaction hook missing pre-setup worktree guard"
        in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_agents_with_detailed_rule_duplication(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        "所有 AI 编码助手统一以 AGENTS.md 为通用入口。\n\n"
        "规则索引见 indexes.md。scripts.research.cli git fetch origin main\n\n"
        "## Review guidelines\n\n"
        "Before reviewing, read and apply docs/rules/review-guidelines.md. "
        "If you cannot access that file, treat the review as blocked.\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "agent_entry_sync"
        and "should not duplicate detailed rules" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_agents_without_sandbox_escalation_rule(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        "所有 AI 编码助手统一以 AGENTS.md 为通用入口。\n\n"
        "规则索引见 indexes.md。所有回答和输出使用简体中文。\n\n"
        "## Review guidelines\n\n"
        "Before reviewing, read and apply docs/rules/review-guidelines.md. "
        "If you cannot access that file, treat the review as blocked.\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "agent_entry_sync"
        and "项目 `.venv` 默认提权执行，否则无法读取base Python路径" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_agents_without_gh_cli_escalation_rule(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace("`gh` CLI 默认提权执行。", ""),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "agent_entry_sync"
        and "`gh` CLI 默认提权执行" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_claude_with_codex_or_review_rules(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "CLAUDE.md").write_text(
        "Claude Code 专用指针。先读 AGENTS.md；Claude Code 专属内容见 .claude/skills。"
        "遇到沙箱/权限阻断时申请提权。Claude Code 不能用自审替代官方 Codex Code Review。",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "claude_sync"
        and "Codex-only or standard review rules" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_codex_pr_skill(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".codex/skills/quant-pr-workflow/SKILL.md").unlink()

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "skill_sync"
        and "quant-pr-workflow skill missing" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_stale_codex_research_skill(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".codex/skills/quant-research-workflow/SKILL.md").write_text(
        "Quant Research Workflow",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "skill_sync"
        and "quant-research-workflow skill missing docs/rules/research-workflow.md"
        in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_root_indexes(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "indexes.md").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "root_index" for finding in report.findings)


def test_governance_audit_flags_missing_pr_cleanup_workflow_tokens(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/rules/pr-workflow.md").write_text(
        "所有进入主干的改动必须通过 PR\n直写主干 ALLOW_DIRECT_MAIN_WRITE DIRECT_MAIN_WRITE_REASON\n"
        "禁止把功能分支本地合入\n"
        "git fetch origin main\ngit merge --ff-only origin/main\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "git push origin --delete <branch>" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_dispatch_first_workflow_tokens(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/rules/collaboration.md").write_text(
        "多个 AI agent\n分支名使用 ASCII\n本地共享工作区\n只读分析不要求创建分支\n"
        "不采用任务登记\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "collaboration.md missing 有可用子 agent 能力" in finding.message
        for finding in report.findings
    )


def test_pre_push_branch_protection_blocks_main() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/main def456\n",
        environ={},
    )
    assert violations == ["main"]


def test_pre_push_branch_protection_allows_feature_branch() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/feature/topic def456\n",
        environ={},
    )
    assert violations == []


def test_pre_push_branch_protection_allows_explicit_bypass() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/main def456\n",
        environ={
            "ALLOW_PROTECTED_BRANCH_PUSH": "1",
            "PROTECTED_BRANCH_PUSH_REASON": "emergency user-approved push",
        },
    )
    assert violations == []


def test_pre_push_branch_protection_requires_explicit_bypass_reason() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/main def456\n",
        environ={"ALLOW_PROTECTED_BRANCH_PUSH": "1"},
    )
    assert violations == ["main"]


def test_pre_push_branch_protection_allows_direct_main_write() -> None:
    violations = check_pre_push_input(
        "refs/heads/main abc123 refs/heads/main def456\n",
        environ={
            "ALLOW_DIRECT_MAIN_WRITE": "1",
            "DIRECT_MAIN_WRITE_REASON": "user explicitly authorized direct main sync",
        },
    )
    assert violations == []


def test_pre_push_branch_protection_requires_direct_main_reason() -> None:
    violations = check_pre_push_input(
        "refs/heads/main abc123 refs/heads/main def456\n",
        environ={"ALLOW_DIRECT_MAIN_WRITE": "1"},
    )
    assert violations == ["main"]


def test_reference_transaction_branch_protection_blocks_main_update() -> None:
    violations = check_reference_transaction_input(
        "0" * 40 + " " + "1" * 40 + " refs/heads/main\n",
        environ={},
    )
    assert violations == ["main"]


def test_reference_transaction_branch_protection_allows_feature_update() -> None:
    violations = check_reference_transaction_input(
        "0" * 40 + " " + "1" * 40 + " refs/heads/fix/topic\n",
        environ={},
    )
    assert violations == []


def test_reference_transaction_branch_protection_requires_bypass_reason() -> None:
    violations = check_reference_transaction_input(
        "0" * 40 + " " + "1" * 40 + " refs/heads/main\n",
        environ={"ALLOW_MAIN_REF_UPDATE": "1"},
    )
    assert violations == ["main"]


def test_reference_transaction_branch_protection_allows_direct_main_fast_forward() -> (
    None
):
    violations = check_reference_transaction_input(
        "1" * 40 + " " + "2" * 40 + " refs/heads/main\n",
        environ={
            "ALLOW_DIRECT_MAIN_WRITE": "1",
            "DIRECT_MAIN_WRITE_REASON": "user explicitly authorized direct main commit",
        },
        remote_heads={"main": "1" * 40},
        is_ancestor=lambda _old_sha, _new_sha: True,
    )
    assert violations == []


def test_reference_transaction_branch_protection_requires_direct_main_reason() -> None:
    violations = check_reference_transaction_input(
        "1" * 40 + " " + "2" * 40 + " refs/heads/main\n",
        environ={"ALLOW_DIRECT_MAIN_WRITE": "1"},
        remote_heads={"main": "1" * 40},
        is_ancestor=lambda _old_sha, _new_sha: True,
    )
    assert violations == ["main"]


def test_reference_transaction_branch_protection_blocks_direct_main_non_fast_forward() -> (
    None
):
    violations = check_reference_transaction_input(
        "2" * 40 + " " + "1" * 40 + " refs/heads/main\n",
        environ={
            "ALLOW_DIRECT_MAIN_WRITE": "1",
            "DIRECT_MAIN_WRITE_REASON": "user explicitly authorized direct main commit",
        },
        remote_heads={"main": "2" * 40},
        is_ancestor=lambda _old_sha, _new_sha: False,
    )
    assert violations == ["main"]


def test_reference_transaction_branch_protection_allows_audited_bypass() -> None:
    violations = check_reference_transaction_input(
        "0" * 40 + " " + "1" * 40 + " refs/heads/main\n",
        environ={
            "ALLOW_MAIN_REF_UPDATE": "1",
            "MAIN_REF_UPDATE_REASON": "sync origin/main after PR merge",
        },
        remote_heads={"main": "1" * 40},
    )
    assert violations == []


def test_reference_transaction_branch_protection_blocks_audited_non_origin_update() -> (
    None
):
    violations = check_reference_transaction_input(
        "1" * 40 + " " + "3" * 40 + " refs/heads/main\n",
        environ={
            "ALLOW_MAIN_REF_UPDATE": "1",
            "MAIN_REF_UPDATE_REASON": "sync origin/main after PR merge",
        },
        remote_heads={"main": "2" * 40},
        is_ancestor=lambda _old_sha, _new_sha: True,
    )
    assert violations == ["main"]


def test_reference_transaction_branch_protection_blocks_audited_non_fast_forward_update() -> (
    None
):
    violations = check_reference_transaction_input(
        "2" * 40 + " " + "1" * 40 + " refs/heads/main\n",
        environ={
            "ALLOW_MAIN_REF_UPDATE": "1",
            "MAIN_REF_UPDATE_REASON": "sync origin/main after PR merge",
        },
        remote_heads={"main": "1" * 40},
        is_ancestor=lambda _old_sha, _new_sha: False,
    )
    assert violations == ["main"]


LOCAL_SECURITY_REVIEW_LINE = (
    "- 本地安全 review: provider=codex；tool=codex-security；"
    "evidence=Codex Security local review completed"
)


def _valid_codex_review_body(review_id: int = 4314779358) -> str:
    cross_review = (
        "- 子 agent 交叉评审: "
        "superpowers:subagent-driven-development/spec-reviewer-prompt.md；"
        "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；"
        "至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；"
        "见 `.local/ai-review/latest.md`"
    )
    return "\n".join(
        [
            "## AI Review 风险分级",
            "",
            "- 风险等级: high",
            "- 是否需要官方 Codex Review: 是",
            "- 本地 AI review: `.local/ai-review/latest.md`",
            LOCAL_SECURITY_REVIEW_LINE,
            cross_review,
            "- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent",
            "- P0/P1 未关闭项: 无",
            "",
            "## P2 保留项",
            "",
            "- 无",
            "",
            "## Codex Code Review \u7ed3\u8bba",
            "",
            "- Reviewer: `Codex`",
            "- \u89e6\u53d1\u65b9\u5f0f: `@codex review`",
            "- \u7ed3\u8bba: \u901a\u8fc7",
            "- \u963b\u65ad\u95ee\u9898: \u65e0",
            "- \u5173\u952e\u8bc1\u636e:",
            f"  - Codex review \u94fe\u63a5\uff1ahttps://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-{review_id}",
            "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
        ]
    )


def test_low_risk_pr_body_does_not_require_codex_review() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors


def test_pr_review_evidence_requires_governance_gate_wrapper_command() -> None:
    body = """
## AI Review 风险分级

- 风险等级: high
- 是否需要官方 Codex Review: 是
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review`
- 结论: 通过
- 阻断问题: 无
- 关键证据:
  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358
  - `scripts.research.governance gate`
"""

    report = validate_pr_body(body)

    assert not report.ok
    assert (
        "review evidence must include governance gate wrapper command" in report.errors
    )


def test_low_risk_pr_body_requires_cross_review_and_dispatch_evidence() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must be filled" in report.errors
    assert "任务分发说明 must be filled" in report.errors


def test_low_risk_pr_body_requires_local_security_review_evidence() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "本地安全 review must be filled" in report.errors


def test_low_risk_pr_body_rejects_template_security_review_placeholder() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex / claude；tool=codex-security / security-guidance；evidence=<安全 review 证据>
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "本地安全 review must not contain placeholder text" in report.errors


def test_low_risk_pr_body_rejects_mismatched_security_review_tool_assignment() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=security-guidance；evidence=codex-security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert (
        "本地安全 review must include tool=codex-security for provider=codex"
        in report.errors
    )


def test_low_risk_pr_body_rejects_empty_security_review_evidence() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "本地安全 review evidence must be filled" in report.errors


def test_low_risk_pr_body_rejects_empty_security_review_chinese_evidence() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；证据=
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "本地安全 review evidence must be filled" in report.errors


def test_low_risk_pr_body_rejects_unassigned_security_review_evidence() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "本地安全 review evidence must be filled" in report.errors


def test_low_risk_pr_body_requires_superpowers_cross_review_skills() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: 已由两个 reviewer 完成
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert any("子 agent 交叉评审 must include" in error for error in report.errors)


def test_low_risk_pr_body_requires_two_reviewer_cross_review_evidence() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must include two reviewer names" in report.errors


def test_low_risk_pr_body_rejects_duplicate_reviewer_names_with_markup() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: alice, `alice`；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must include two reviewer names" in report.errors


def test_low_risk_pr_body_requires_actual_reviewer_names() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must include two reviewer names" in report.errors


def test_low_risk_pr_body_accepts_reviewer_names_without_fixed_phrase() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors


def test_pr_body_partial_ai_review_mode_requires_user_authorization() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地 AI review 模式: partial
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "不完全 Review 模式授权 must be filled" in report.errors


def test_pr_body_partial_ai_review_mode_rejects_empty_authorization_values() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 官方 Codex Review 跳过授权: 无
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 本地 AI review 模式: partial
- 不完全 Review 模式授权: authorized_by=；reason=；evidence=
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "不完全 Review 模式授权 authorized_by must be filled" in report.errors
    assert "不完全 Review 模式授权 reason must be filled" in report.errors
    assert "不完全 Review 模式授权 evidence must be filled" in report.errors


def test_pr_body_partial_ai_review_mode_rejects_unassigned_authorization_values() -> (
    None
):
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 官方 Codex Review 跳过授权: 无
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 本地 AI review 模式: partial
- 不完全 Review 模式授权: authorized_by reason evidence
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "不完全 Review 模式授权 authorized_by must be filled" in report.errors
    assert "不完全 Review 模式授权 reason must be filled" in report.errors
    assert "不完全 Review 模式授权 evidence must be filled" in report.errors


def test_pr_body_partial_ai_review_mode_accepts_user_authorization() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地 AI review 模式: partial
- 不完全 Review 模式授权: authorized_by=用户；reason=本次只做紧急小范围文档修订；evidence=当前对话中用户明确授权不完全 review 模式
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors


def test_low_risk_pr_body_rejects_placeholder_reviewer_names() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: <规格评审子agent>, <代码质量评审子agent>；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must include two reviewer names" in report.errors


def test_low_risk_pr_body_rejects_controller_or_implementer_reviewers() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: 主会话, 实现者；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must include two reviewer names" in report.errors


def test_low_risk_pr_body_rejects_mixed_invalid_reviewer_names() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent, 实现者；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "子 agent 交叉评审 must not include invalid reviewer names" in report.errors


def test_low_risk_pr_body_requires_local_ai_review_report_field() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "本地 AI review must be filled" in report.errors


def test_low_risk_pr_body_with_high_risk_changed_files_requires_codex_review() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(
        body,
        comments=[],
        changed_files=["scripts/research/governance/pr_review_evidence.py"],
    )

    assert not report.ok
    assert "high-risk changed files require official Codex Review" in report.errors
    assert "PR body missing section: Codex Code Review 结论" in report.errors


def test_low_risk_pr_body_with_ai_risk_label_requires_codex_review() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[], labels=["ai-risk-review"])

    assert not report.ok
    assert "ai-risk-review label requires official Codex Review" in report.errors
    assert "PR body missing section: Codex Code Review 结论" in report.errors


def test_high_risk_pr_body_requires_ai_risk_label_when_labels_available() -> None:
    report = validate_pr_body(_valid_codex_review_body(), comments=[], labels=[])

    assert not report.ok
    assert "high/unknown PR must include ai-risk-review label" in report.errors


def test_issue_label_names_extracts_github_issue_labels() -> None:
    assert _issue_label_names(
        {"labels": [{"name": "ai-risk-review"}, {"name": "docs"}]}
    ) == ("ai-risk-review", "docs")


def test_low_risk_pr_body_requires_p2_section() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "PR body missing section: P2 保留项" in report.errors


def test_pr_body_accepts_p2_none_before_managed_block_end() -> None:
    body = f"""
## {pr_review_evidence.AI_REVIEW_SECTION_HEADER}

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `{pr_review_evidence.REQUIRED_GOVERNANCE_GATE_COMMANDS[0]}`

## {pr_review_evidence.P2_SECTION_HEADER}

- 无
<!-- pr-flow:end -->
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors


def test_low_risk_pr_body_requires_local_governance_gate_command() -> None:
    body = f"""
## {pr_review_evidence.AI_REVIEW_SECTION_HEADER}

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## {pr_review_evidence.P2_SECTION_HEADER}

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert (
        "local check evidence must include governance gate wrapper command"
        in report.errors
    )


def test_low_risk_pr_body_accepts_chinese_p2_fields() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- AIR-002：大型数据产物无法逐文件人工核验。
  - 不修原因: 逐文件核验成本过高。
  - 风险接受理由: 自动化检查覆盖 catalog、manifest 和 pathref。
  - 处理方式: 合并后通过治理门禁和后续抽样复核跟踪。
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors


def test_low_risk_pr_body_rejects_p2_none_mixed_with_unjustified_item() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## P2 保留项

- 无
- AIR-002：大型数据产物无法逐文件人工核验。
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "P2 保留项 must include defer_reason or 不修原因" in report.errors
    assert "P2 保留项 must include risk_acceptance or 风险接受理由" in report.errors
    assert "P2 保留项 must include handling or 处理方式" in report.errors


def test_low_risk_pr_body_rejects_empty_dispatched_detail() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "任务分发说明 must include dispatched task detail" in report.errors


def test_low_risk_pr_body_accepts_dispatched_detail_with_no_undispatched_items() -> (
    None
):
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent；无未分发项
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors


def test_low_risk_pr_body_requires_reason_when_task_not_dispatched() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 未分发
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "任务分发说明 must include reason when 未分发" in report.errors


def test_low_risk_pr_body_rejects_empty_not_dispatched_reason() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 未分发，原因：
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "任务分发说明 must include reason when 未分发" in report.errors


def test_low_risk_pr_body_rejects_weak_not_dispatched_reason() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 未分发，原因：-
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "任务分发说明 must include reason when 未分发" in report.errors


def test_low_risk_pr_body_rejects_none_not_dispatched_reason() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 未分发：无
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert "任务分发说明 must include reason when 未分发" in report.errors


def test_high_risk_pr_body_requires_codex_review() -> None:
    body = """
## AI Review 风险分级

- 风险等级: high
- 是否需要官方 Codex Review: 是
- 本地 AI review: `.local/ai-review/latest.md`
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review`
- 结论: 未执行
- 阻断问题: 未确认
- 关键证据:
  - Codex review 链接：https://github.com/example/repo/pull/1#pullrequestreview-1
  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert any(
        "PR comments must include the required @codex review trigger" in error
        for error in report.errors
    )


def _official_codex_skip_body(*, authorization: str | None = None) -> str:
    authorization_line = (
        authorization
        if authorization is not None
        else "authorized_by=用户；reason=当前 PR 官方 Codex review 成本高于风险；evidence=当前对话中用户明确授权跳过官方 Codex review"
    )
    return f"""
## AI Review 风险分级

- 风险等级: high
- 是否需要官方 Codex Review: 否
- 官方 Codex Review 跳过授权: {authorization_line}
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- 无
"""


def _low_risk_no_official_review_body() -> str:
    return """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 官方 Codex Review 跳过授权: 无
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex；tool=codex-security；evidence=Codex Security local review completed
- 本地 AI review 模式: complete
- 不完全 Review 模式授权: 无
- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发给规格符合度评审和代码质量评审子 agent
- P0/P1 未关闭项: 无

## 已运行检查

- governance gate: `.githooks/run-python.sh -m scripts.research.governance gate`

## P2 保留项

- 无
"""


def test_high_risk_pr_body_can_skip_codex_review_with_user_authorization() -> None:
    report = validate_pr_body(_official_codex_skip_body(), comments=[])

    assert report.ok, report.errors


def test_high_risk_pr_body_rejects_skip_without_user_authorization() -> None:
    report = validate_pr_body(
        _official_codex_skip_body(authorization="无"),
        comments=[],
    )

    assert not report.ok
    assert "官方 Codex Review 跳过授权 must be filled" in report.errors
    assert "PR body missing section: Codex Code Review 结论" in report.errors


def test_high_risk_pr_body_rejects_template_skip_authorization_placeholder() -> None:
    report = validate_pr_body(
        _official_codex_skip_body(
            authorization="无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>"
        ),
        comments=[],
    )

    assert not report.ok
    assert (
        "官方 Codex Review 跳过授权 must not contain placeholder text" in report.errors
    )


def test_high_risk_pr_body_rejects_empty_skip_authorization_values() -> None:
    report = validate_pr_body(
        _official_codex_skip_body(authorization="authorized_by=；reason=；evidence="),
        comments=[],
    )

    assert not report.ok
    assert "官方 Codex Review 跳过授权 authorized_by must be filled" in report.errors
    assert "官方 Codex Review 跳过授权 reason must be filled" in report.errors
    assert "官方 Codex Review 跳过授权 evidence must be filled" in report.errors


def test_high_risk_pr_body_rejects_unassigned_skip_authorization_values() -> None:
    report = validate_pr_body(
        _official_codex_skip_body(authorization="authorized_by reason evidence"),
        comments=[],
    )

    assert not report.ok
    assert "官方 Codex Review 跳过授权 authorized_by must be filled" in report.errors
    assert "官方 Codex Review 跳过授权 reason must be filled" in report.errors
    assert "官方 Codex Review 跳过授权 evidence must be filled" in report.errors


def test_codex_skip_authorization_does_not_bypass_unresolved_blocking_threads() -> None:
    report = validate_pr_body(
        _official_codex_skip_body(),
        comments=[],
        review_threads=[
            {
                "isResolved": False,
                "isOutdated": False,
                "comments": [
                    {
                        "body": "[P1] blocking finding",
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                    }
                ],
            }
        ],
    )

    assert not report.ok
    assert (
        "Codex review must not have unresolved non-outdated P0/P1 threads"
        in report.errors
    )


def _codex_completion_comment(
    comment_id: int = 4484023766,
    *,
    created_at: str = "2026-05-19T01:00:00Z",
    reaction_created_at: str = "2026-05-19T01:01:00Z",
) -> dict[str, object]:
    return {
        "id": comment_id,
        "html_url": f"https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-{comment_id}",
        "body": _codex_review_request_body(),
        "created_at": created_at,
        "reaction_items": [
            {
                "content": "+1",
                "created_at": reaction_created_at,
                "user": {"login": "chatgpt-codex-connector"},
            }
        ],
    }


def _codex_no_major_issues_comment(
    comment_id: int = 4484229220,
    *,
    created_at: str = "2026-05-19T01:04:00Z",
) -> dict[str, object]:
    return {
        "id": comment_id,
        "html_url": f"https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-{comment_id}",
        "body": "Codex Review: Didn't find any major issues. :+1:",
        "created_at": created_at,
        "user": {"login": "chatgpt-codex-connector[bot]"},
    }


def _codex_context_invalid_review(
    *,
    review_id: int = 4314779358,
    head_sha: str = "0" * 40,
    submitted_at: str = "2026-05-19T01:03:00Z",
) -> dict[str, object]:
    return {
        "id": review_id,
        "commit_id": head_sha,
        "submitted_at": submitted_at,
        "body": "\n".join(
            [
                "### Codex Review",
                "",
                "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  provide unified diff**",
                "",
                "I cannot complete a static review because this conversation did not include the actual code diff for commit `c933986f031fca7d7dce72d5d65cf9cdc15afbbf`.",
            ]
        ),
        "user": {"login": "chatgpt-codex-connector[bot]"},
    }


def test_pr_review_evidence_accepts_approved_codex_conclusion() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[_codex_review_request_body()],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.ok
    assert report.errors == ()


def test_pr_review_evidence_rejects_context_invalid_codex_review() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[_codex_context_invalid_review(head_sha=head_sha)],
        review_comments=[],
    )

    assert not report.ok
    assert "Codex review context is invalid for the current head" in report.errors


def test_pr_review_evidence_rejects_equivalent_context_invalid_wording() -> None:
    head_sha = "0" * 40
    for wording in (
        "I am unable to see the diff for this pull request.",
        "I couldn't access the PR diff.",
        "I couldn\u2019t access the PR diff.",
        "I can\u2019t review the diff.",
        "I don't have access to the diff for the current PR.",
        "I don't have access to the repository or diff.",
        "I don't have access to the codebase or unified diff.",
        "Please provide the PR diff so I can review it.",
        "无法查看当前 PR diff，因此不能完成 review。",
    ):
        report = validate_pr_body(
            _valid_codex_review_body(),
            expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
            expected_head_sha=head_sha,
            comments=[
                {
                    "body": _codex_review_request_body(),
                    "created_at": "2026-05-19T01:00:00Z",
                    "user": {"login": "liuli195"},
                }
            ],
            reviews=[
                {
                    "id": 4314779358,
                    "commit_id": head_sha,
                    "submitted_at": "2026-05-19T01:01:00Z",
                    "body": f"### Codex Review\n\n{wording}",
                    "user": {"login": "chatgpt-codex-connector[bot]"},
                }
            ],
            review_comments=[],
        )

        assert not report.ok
        assert "Codex review context is invalid for the current head" in report.errors


def test_pr_review_evidence_allows_normal_unified_diff_review_wording() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\n基于当前 PR 统一 diff 审查，No blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.ok
    assert "Codex review context is invalid for the current head" not in report.errors


def test_pr_review_evidence_allows_no_blocking_issues_diff_wording() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nI cannot see any blocking issues in the diff.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.ok
    assert "Codex review context is invalid for the current head" not in report.errors


def test_pr_review_evidence_rejects_context_hostile_codex_trigger() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": "@codex review\nPlease only do a static diff review and do not execute local commands.",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert not report.ok
    assert (
        "required @codex review trigger must not disable repository context"
        in report.errors
    )


def test_pr_review_evidence_rejects_contracted_context_hostile_codex_trigger() -> None:
    head_sha = "0" * 40
    for wording in (
        "Please don't run local commands.",
        "Please don\u2019t execute local commands.",
    ):
        report = validate_pr_body(
            _valid_codex_review_body(),
            expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
            expected_head_sha=head_sha,
            comments=[
                {
                    "body": f"@codex review\n{wording}",
                    "created_at": "2026-05-19T01:00:00Z",
                    "user": {"login": "liuli195"},
                }
            ],
            reviews=[
                {
                    "id": 4314779358,
                    "commit_id": head_sha,
                    "submitted_at": "2026-05-19T01:01:00Z",
                    "body": "### Codex Review\n\nNo blocking findings.",
                    "user": {"login": "chatgpt-codex-connector[bot]"},
                }
            ],
            review_comments=[],
        )

        assert not report.ok
        assert (
            "required @codex review trigger must not disable repository context"
            in report.errors
        )


def test_pr_review_evidence_rejects_equivalent_context_hostile_codex_trigger() -> None:
    head_sha = "0" * 40
    for wording in (
        "不要执行命令。",
        "Do not use tools.",
        "Do not read the repository or GitHub diff.",
        "只做静态 diff 评审。",
        "只看 diff。",
        "仅做静态 diff 评审。",
        "仅看 diff。",
    ):
        report = validate_pr_body(
            _valid_codex_review_body(),
            expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
            expected_head_sha=head_sha,
            comments=[
                {
                    "body": f"@codex review\n{wording}",
                    "created_at": "2026-05-19T01:00:00Z",
                    "user": {"login": "liuli195"},
                }
            ],
            reviews=[
                {
                    "id": 4314779358,
                    "commit_id": head_sha,
                    "submitted_at": "2026-05-19T01:01:00Z",
                    "body": "### Codex Review\n\nNo blocking findings.",
                    "user": {"login": "chatgpt-codex-connector[bot]"},
                }
            ],
            review_comments=[],
        )

        assert not report.ok
        assert (
            "required @codex review trigger must not disable repository context"
            in report.errors
        )


def test_pr_review_evidence_rejects_safe_command_constraint_extra_text() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": "@codex review\nDo not run destructive commands; use repository context and local checks as needed.",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert not report.ok
    assert (
        "required @codex review trigger must not disable repository context"
        in report.errors
    )
    assert "PR comments must include the required @codex review trigger" in (
        report.errors
    )


def test_pr_review_evidence_rejects_safe_chinese_command_constraint_extra_text() -> (
    None
):
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": "@codex review\n不要执行破坏性命令；请使用当前 PR 仓库上下文和本地检查。",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert not report.ok
    assert (
        "required @codex review trigger must not disable repository context"
        in report.errors
    )
    assert "PR comments must include the required @codex review trigger" in (
        report.errors
    )


def test_pr_review_evidence_allows_new_compliant_trigger_after_context_hostile_trigger() -> (
    None
):
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": "@codex review\nPlease only do a static diff review and do not execute local commands.",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:05:00Z",
                "user": {"login": "liuli195"},
            },
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:06:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.ok
    assert "required @codex review trigger must not disable repository context" not in (
        report.errors
    )


def test_pr_review_evidence_ignores_later_context_hostile_trigger_after_valid_review() -> (
    None
):
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            {
                "body": "@codex review\nPlease only do a static diff review and do not execute local commands.",
                "created_at": "2026-05-19T01:10:00Z",
                "user": {"login": "liuli195"},
            },
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:05:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.ok
    assert (
        "required @codex review trigger must not disable repository context"
        not in report.errors
    )


def test_pr_review_evidence_ignores_superseded_context_invalid_review_after_later_pass() -> (
    None
):
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(4314779360),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:02:00Z",
            ),
            {
                "id": 4314779360,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:05:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
        ],
        review_comments=[],
    )

    assert report.ok
    assert "Codex review context is invalid for the current head" not in report.errors


def test_low_risk_pr_body_can_still_require_official_codex_review() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body().replace("- 风险等级: high", "- 风险等级: low"),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[_codex_review_request_body()],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.ok
    assert report.errors == ()


def test_pr_review_evidence_rejects_unexecuted_codex_conclusion() -> None:
    report = validate_pr_body(
        "\n".join(
            [
                "## AI Review 风险分级",
                "",
                "- 风险等级: high",
                "- 是否需要官方 Codex Review: 是",
                "- 本地 AI review: `.local/ai-review/latest.md`",
                "- 子 agent 交叉评审: superpowers:subagent-driven-development/spec-reviewer-prompt.md；superpowers:subagent-driven-development/code-quality-reviewer-prompt.md；至少两个独立 reviewer；reviewers: spec-review-subagent, quality-review-subagent；见 `.local/ai-review/latest.md`",
                "- 任务分发说明: 已分发给实现、规格符合度评审和代码质量评审子 agent",
                "- P0/P1 未关闭项: 无",
                "",
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 未执行",
                "- 阻断问题: 未确认",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        )
    )
    assert not report.ok
    assert "结论 must be 通过" in report.errors


def test_pr_review_evidence_rejects_placeholder_codex_review_link() -> None:
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        )
    )
    assert not report.ok
    assert (
        "review evidence must include a real Codex review link for this PR"
        in report.errors
    )


def test_pr_review_evidence_rejects_other_pr_review_link() -> None:
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/4#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
    )
    assert not report.ok
    assert (
        "review evidence must include a real Codex review link for this PR"
        in report.errors
    )


def test_pr_review_evidence_rejects_discussion_link_as_review() -> None:
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#discussion_r3262925410",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
    )
    assert not report.ok
    assert (
        "review evidence must include a real Codex review link for this PR"
        in report.errors
    )


def test_pr_review_evidence_rejects_missing_required_trigger_comment() -> None:
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        comments=["looks good"],
    )
    assert not report.ok
    assert (
        "PR comments must include the required @codex review trigger" in report.errors
    )


def test_pr_review_evidence_rejects_template_extra_text_trigger() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": "@codex review\nPlease use the current PR context and GitHub diff.",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert not report.ok
    assert (
        "required @codex review trigger must not disable repository context"
        in report.errors
    )
    assert "PR comments must include the required @codex review trigger" in (
        report.errors
    )


def test_pr_review_evidence_rejects_single_line_template_trigger() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": "@codex review",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert not report.ok
    assert (
        "required @codex review trigger must not disable repository context"
        in report.errors
    )
    assert "PR comments must include the required @codex review trigger" in (
        report.errors
    )


def test_pr_review_evidence_rejects_review_from_old_head() -> None:
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha="1" * 40,
        reviews=[
            {
                "id": 4314779358,
                "commit_id": "0" * 40,
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
    )
    assert not report.ok
    assert (
        "Codex review link must match a Codex review on the current head"
        in report.errors
    )


def test_pr_review_evidence_rejects_dismissed_codex_review_link() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "state": "DISMISSED",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex review link must match a Codex review on the current head"
        in report.errors
    )


def test_pr_review_evidence_ignores_dismissed_blocking_codex_review() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(4314779360),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "state": "DISMISSED",
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
            {
                "id": 4314779360,
                "commit_id": head_sha,
                "state": "COMMENTED",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
        ],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_accepts_changes_requested_review_without_p0_p1() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "state": "CHANGES_REQUESTED",
                "body": "### Codex Review\n\nNo badge text.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_accepts_codex_completion_reaction_without_review() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "#pullrequestreview-4314779358",
        "#issuecomment-4484023766",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[_codex_completion_comment()],
        reviews=[],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_accepts_issue_comment_completion_link() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/issues/5#issuecomment-4484023766",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[_codex_completion_comment()],
        reviews=[],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_accepts_codex_no_major_issues_comment() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
            },
            _codex_no_major_issues_comment(),
        ],
        reviews=[],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_completion_comment_supersedes_earlier_invalid_review() -> (
    None
):
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            _codex_no_major_issues_comment(created_at="2026-05-19T01:05:00Z"),
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:02:00Z",
            )
        ],
        review_comments=[],
    )

    assert report.ok
    assert "Codex review context is invalid for the current head" not in report.errors


def test_pr_review_evidence_completion_reaction_supersedes_earlier_invalid_review() -> (
    None
):
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484023766",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            _codex_completion_comment(
                created_at="2026-05-19T01:00:00Z",
                reaction_created_at="2026-05-19T01:05:00Z",
            ),
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:02:00Z",
            )
        ],
        review_comments=[],
    )

    assert report.ok
    assert "Codex review context is invalid for the current head" not in report.errors


def test_pr_review_evidence_completion_comment_keeps_earlier_blocking_review() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            _codex_no_major_issues_comment(created_at="2026-05-19T01:05:00Z"),
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:02:00Z",
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking finding**",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert not report.ok
    assert (
        "Codex review must not contain P0/P1 findings on the current head"
        in report.errors
    )


def test_pr_review_evidence_completion_comment_rejects_later_invalid_review() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            _codex_no_major_issues_comment(created_at="2026-05-19T01:05:00Z"),
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:06:00Z",
            )
        ],
        review_comments=[],
    )

    assert not report.ok
    assert "Codex review context is invalid for the current head" in report.errors


def test_pr_review_evidence_main_uses_current_pr_body_over_stale_event_env(
    monkeypatch, capsys
) -> None:
    head_sha = "0" * 40
    current_body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    stale_body = current_body.replace(
        "- \u7ed3\u8bba: \u901a\u8fc7", "- \u7ed3\u8bba: \u672a\u6267\u884c"
    ).replace(
        "- \u963b\u65ad\u95ee\u9898: \u65e0",
        "- \u963b\u65ad\u95ee\u9898: \u672a\u786e\u8ba4",
    )

    monkeypatch.setenv("PR_BODY", stale_body)
    monkeypatch.setenv("PR_URL", "https://github.com/liuli195/Quant-Trading/pull/5")
    monkeypatch.setenv("GITHUB_REPOSITORY", "liuli195/Quant-Trading")
    monkeypatch.setenv("PR_NUMBER", "5")
    monkeypatch.setenv("PR_HEAD_SHA", head_sha)
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_pr_metadata",
        lambda *, repo, pr_number, token: {
            "body": current_body,
            "html_url": "https://github.com/liuli195/Quant-Trading/pull/5",
            "head": {"sha": head_sha},
        },
    )
    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_pr_comments",
        lambda *, repo, pr_number, token: [
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            _codex_no_major_issues_comment(),
        ],
    )
    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_pr_reviews",
        lambda *, repo, pr_number, token: [],
    )
    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_pr_review_comments",
        lambda *, repo, pr_number, token: [],
    )
    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_pr_review_threads",
        lambda *, repo, pr_number, token: [],
    )
    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_pr_changed_files",
        lambda *, repo, pr_number, token: (
            "scripts/research/governance/pr_review_evidence.py",
        ),
    )
    monkeypatch.setattr(
        pr_review_evidence,
        "_fetch_issue_metadata",
        lambda *, repo, pr_number, token: {"labels": [{"name": "ai-risk-review"}]},
    )

    assert (
        pr_review_evidence.main(
            [
                "--body-env",
                "PR_BODY",
                "--pr-url-env",
                "PR_URL",
                "--repo-env",
                "GITHUB_REPOSITORY",
                "--pr-number-env",
                "PR_NUMBER",
                "--head-sha-env",
                "PR_HEAD_SHA",
                "--github-token-env",
                "GITHUB_TOKEN",
            ]
        )
        == 0
    )
    assert "PR review evidence ok" in capsys.readouterr().out


def test_pr_review_evidence_ignores_codex_help_text_when_matching_trigger() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    codex_comment = _codex_no_major_issues_comment()
    codex_comment["body"] = (
        "Codex Review: Didn't find any major issues. Hooray!\n\n"
        "<details><summary>About Codex</summary>\n"
        'Reviews are triggered when you comment "@codex review".\n'
        "</details>"
    )

    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            codex_comment,
        ],
        reviews=[],
        review_comments=[],
    )

    assert report.ok


def test_pr_review_evidence_ignores_later_non_trigger_comment_for_no_major_issues() -> (
    None
):
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
        "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            {
                "id": 4484212277,
                "html_url": "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484212277",
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
            },
            _codex_no_major_issues_comment(created_at="2026-05-19T01:05:00Z"),
            {
                "id": 4484999999,
                "body": "<!-- codex-review-monitor -->\n## Codex Review Monitor",
                "created_at": "2026-05-19T01:10:00Z",
            },
        ],
        reviews=[],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_ignores_later_non_trigger_comment_for_completion_reaction() -> (
    None
):
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "#pullrequestreview-4314779358",
        "#issuecomment-4484023766",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            _codex_completion_comment(created_at="2026-05-19T01:00:00Z"),
            {
                "id": 4484999999,
                "body": "<!-- codex-review-monitor -->\n## Codex Review Monitor",
                "created_at": "2026-05-19T01:10:00Z",
            },
        ],
        reviews=[],
        review_comments=[],
    )
    assert report.ok


def test_pr_review_evidence_rejects_completion_before_latest_required_trigger() -> None:
    head_sha = "0" * 40
    body = _valid_codex_review_body().replace(
        "#pullrequestreview-4314779358",
        "#issuecomment-4484023766",
    )
    report = validate_pr_body(
        body,
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:59:00Z",
        comments=[
            _codex_completion_comment(created_at="2026-05-19T01:00:00Z"),
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:05:00Z",
            },
        ],
        reviews=[],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex completion comment must match the latest required @codex review trigger"
        in report.errors
    )


def test_pr_review_evidence_reads_monitor_head_state_for_head_cutoff() -> None:
    head_sha = "0" * 40
    comment = {
        "body": render_monitor_head_state(
            head_sha=head_sha,
            head_updated_at="2026-05-19T02:00:00Z",
        )
    }
    assert (
        head_updated_at_from_monitor_state([comment], expected_head_sha=head_sha)
        == "2026-05-19T02:00:00Z"
    )


def test_pr_review_evidence_rejects_codex_review_with_blocking_body_finding() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking finding**",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex review must not contain P0/P1 findings on the current head"
        in report.errors
    )


def test_pr_review_evidence_rejects_codex_review_with_blocking_inline_finding() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[
            {
                "pull_request_review_id": 4314779358,
                "body": "**![P0 Badge](https://img.shields.io/badge/P0-red?style=flat) blocking finding**",
            }
        ],
    )
    assert not report.ok
    assert (
        "Codex review must not contain P0/P1 findings on the current head"
        in report.errors
    )


def test_pr_review_evidence_rejects_review_before_required_trigger_comment() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:10:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:09:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex review must be submitted after the required @codex review trigger"
        in report.errors
    )


def test_pr_review_evidence_waits_for_review_after_latest_required_trigger() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:00:00Z",
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:05:00Z",
            },
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:15:00Z",
            },
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:10:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex review must be submitted after the required @codex review trigger"
        in report.errors
    )


def test_pr_review_evidence_rejects_trigger_before_current_head() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:10:00Z",
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:09:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:11:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "required @codex review trigger must be submitted after the current head"
        in report.errors
    )


def test_pr_review_evidence_uses_comment_updated_at_for_trigger_time() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        expected_head_created_at="2026-05-19T00:07:00Z",
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:08:00Z",
                "updated_at": "2026-05-19T00:12:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:10:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex review must be submitted after the required @codex review trigger"
        in report.errors
    )


def test_pr_review_evidence_rejects_any_current_head_blocking_codex_review() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        "\n".join(
            [
                "## Codex Code Review 结论",
                "",
                "- Reviewer: `Codex`",
                "- 触发方式: `@codex review`",
                "- 结论: 通过",
                "- 阻断问题: 无",
                "- 关键证据:",
                "  - Codex review 链接：https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358",
                "  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate`",
            ]
        ),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:09:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:10:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
            {
                "id": 4314779360,
                "commit_id": head_sha,
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-05-19T00:11:00Z",
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
        ],
        review_comments=[],
    )
    assert not report.ok
    assert (
        "Codex review must not contain P0/P1 findings on the current head"
        in report.errors
    )


def test_pr_review_evidence_rejects_unresolved_blocking_codex_threads() -> None:
    head_sha = "0" * 40
    report = validate_pr_body(
        _valid_codex_review_body(),
        expected_pr_url="https://github.com/liuli195/Quant-Trading/pull/5",
        expected_head_sha=head_sha,
        comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:09:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:10:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
        review_threads=[
            {
                "isResolved": False,
                "isOutdated": False,
                "comments": [
                    {
                        "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                    }
                ],
            }
        ],
    )
    assert not report.ok
    assert (
        "Codex review must not have unresolved non-outdated P0/P1 threads"
        in report.errors
    )


def test_parse_next_link_finds_github_pagination_next_url() -> None:
    header = (
        '<https://api.github.com/repos/liuli195/Quant-Trading/issues/5/comments?page=2>; rel="next", '
        '<https://api.github.com/repos/liuli195/Quant-Trading/issues/5/comments?page=4>; rel="last"'
    )
    assert (
        _parse_next_link(header)
        == "https://api.github.com/repos/liuli195/Quant-Trading/issues/5/comments?page=2"
    )


def test_codex_review_monitor_reports_waiting_for_codex_after_trigger() -> None:
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": "0" * 40}},
        issue_comments=[{"body": _codex_review_request_body()}],
        reviews=[],
        review_comments=[],
    )
    assert report.status == "waiting_for_codex"
    assert report.trigger_found
    assert "等待 Codex review" in render_monitor_comment(report)


def test_codex_review_monitor_reports_context_hostile_trigger() -> None:
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": "0" * 40}},
        issue_comments=[
            {
                "body": "@codex review\nDo not execute local commands; only do a static diff review.",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[],
        review_comments=[],
    )

    assert report.status == "trigger_invalid"
    assert report.trigger_invalid
    assert "trigger context invalid" in render_monitor_comment(report)


def test_codex_review_monitor_allows_new_compliant_trigger_after_context_hostile_trigger() -> (
    None
):
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": "0" * 40}},
        issue_comments=[
            {
                "body": "@codex review\nDo not execute local commands; only do a static diff review.",
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:05:00Z",
                "user": {"login": "liuli195"},
            },
        ],
        reviews=[],
        review_comments=[],
    )

    assert report.status == "waiting_for_codex"
    assert report.trigger_found
    assert not report.trigger_invalid


def test_codex_review_monitor_passes_when_official_review_is_authorized_skipped() -> (
    None
):
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}, "body": _official_codex_skip_body()},
        issue_comments=[],
        reviews=[],
        review_comments=[],
    )

    assert report.status == "skipped"
    assert not report.trigger_found
    assert "授权跳过" in render_monitor_comment(report)


def test_codex_review_monitor_blocks_official_errors_before_skip_authorization() -> (
    None
):
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}, "body": _official_codex_skip_body()},
        issue_comments=[],
        reviews=[],
        review_comments=[],
        changed_files=("scripts/research/governance/pr_review_evidence.py",),
        labels=(),
    )

    assert report.status == "evidence_invalid"
    assert "ai-risk-review" in report.message


def test_codex_review_monitor_blocks_official_errors_after_codex_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}, "body": _valid_codex_review_body()},
        issue_comments=[{"body": _codex_review_request_body()}],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
        changed_files=("scripts/research/governance/codex_review_monitor.py",),
        labels=(),
    )

    assert report.status == "evidence_invalid"
    assert "ai-risk-review" in report.message


def test_codex_review_monitor_passes_low_risk_without_official_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr={"head": {"sha": head_sha}, "body": _low_risk_no_official_review_body()},
        pr_number="5",
        issue_comments=[],
        reviews=[],
        review_comments=[],
        changed_files=("docs/README.md",),
        labels=(),
    )

    assert report.status == "skipped"
    assert not report.trigger_found
    assert "无需执行" in render_monitor_comment(report)


def test_codex_review_monitor_blocks_unresolved_blocking_threads() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[{"body": _codex_review_request_body()}],
        reviews=[],
        review_comments=[],
        review_threads=[
            {
                "isResolved": False,
                "isOutdated": False,
                "comments": [
                    {
                        "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
                        "author": {"login": "chatgpt-codex-connector[bot]"},
                    }
                ],
            }
        ],
    )
    assert report.status == "blocked"
    assert report.blocking_findings == 1


def test_codex_review_monitor_passes_on_codex_completion_reaction() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T00:59:00Z",
        issue_comments=[_codex_completion_comment()],
        reviews=[],
        review_comments=[],
    )
    assert report.status == "passed"
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484023766"
    )


def test_codex_review_monitor_passes_on_codex_no_major_issues_comment() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T00:59:00Z",
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
            },
            _codex_no_major_issues_comment(),
        ],
        reviews=[],
        review_comments=[],
    )
    assert report.status == "passed"
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220"
    )


def test_codex_review_monitor_ignores_codex_help_text_when_matching_trigger() -> None:
    head_sha = "0" * 40
    codex_comment = _codex_no_major_issues_comment()
    codex_comment["body"] = (
        "Codex Review: Didn't find any major issues. Hooray!\n\n"
        "<details><summary>About Codex</summary>\n"
        'Reviews are triggered when you comment "@codex review".\n'
        "</details>"
    )

    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T00:59:00Z",
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            codex_comment,
        ],
        reviews=[],
        review_comments=[],
    )

    assert report.status == "passed"
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220"
    )


def test_codex_review_monitor_waits_for_completion_after_latest_required_trigger() -> (
    None
):
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T00:59:00Z",
        issue_comments=[
            _codex_completion_comment(created_at="2026-05-19T01:00:00Z"),
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:05:00Z",
            },
        ],
        reviews=[],
        review_comments=[],
    )
    assert report.status == "waiting_for_codex"
    assert report.trigger_found
    assert report.latest_review_url is None


def test_codex_review_monitor_rejects_trigger_before_current_head() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T01:00:00Z",
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T00:59:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.status == "waiting_for_trigger"
    assert not report.trigger_found


def test_codex_review_monitor_waits_for_review_after_required_trigger() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T01:00:00Z",
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:02:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.status == "waiting_for_codex"
    assert report.trigger_found


def test_codex_review_monitor_waits_for_review_after_latest_required_trigger() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T01:00:00Z",
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:02:00Z",
            },
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:05:00Z",
            },
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:04:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.status == "waiting_for_codex"
    assert report.trigger_found


def test_codex_review_monitor_reports_passed_current_head_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[{"body": _codex_review_request_body()}],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:00:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.status == "passed"
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779358"
    )


def test_codex_review_monitor_reports_context_invalid_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[_codex_context_invalid_review(head_sha=head_sha)],
        review_comments=[],
    )

    assert report.status == "context_invalid"
    assert report.context_invalid_reviews == 1
    assert "context invalid" in render_monitor_comment(report)


def test_codex_review_monitor_ignores_superseded_context_invalid_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:02:00Z",
            ),
            {
                "id": 4314779360,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:05:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
        ],
        review_comments=[],
    )

    assert report.status == "passed"
    assert report.context_invalid_reviews == 0


def test_codex_review_monitor_completion_supersedes_context_invalid_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T00:59:00Z",
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            _codex_no_major_issues_comment(created_at="2026-05-19T01:05:00Z"),
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:02:00Z",
            )
        ],
        review_comments=[],
    )

    assert report.status == "passed"
    assert report.context_invalid_reviews == 0
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484229220"
    )


def test_codex_review_monitor_completion_reaction_supersedes_context_invalid_review() -> (
    None
):
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        head_created_at="2026-05-19T00:59:00Z",
        issue_comments=[
            _codex_completion_comment(
                created_at="2026-05-19T01:00:00Z",
                reaction_created_at="2026-05-19T01:05:00Z",
            ),
        ],
        reviews=[
            _codex_context_invalid_review(
                review_id=4314779358,
                head_sha=head_sha,
                submitted_at="2026-05-19T01:02:00Z",
            )
        ],
        review_comments=[],
    )

    assert report.status == "passed"
    assert report.context_invalid_reviews == 0
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#issuecomment-4484023766"
    )


def test_codex_review_monitor_ignores_later_hostile_trigger_after_valid_review() -> (
    None
):
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            },
            {
                "body": "@codex review\nPlease only do a static diff review and do not execute local commands.",
                "created_at": "2026-05-19T01:10:00Z",
                "user": {"login": "liuli195"},
            },
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:05:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.status == "passed"
    assert not report.trigger_invalid


def test_codex_review_monitor_ignores_dismissed_reviews() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "state": "DISMISSED",
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )
    assert report.status == "waiting_for_codex"
    assert report.blocking_findings == 0


def test_codex_review_monitor_reports_blocked_on_p1_inline_comment() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[{"body": _codex_review_request_body()}],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:00:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[
            {
                "pull_request_review_id": 4314779358,
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
            }
        ],
    )
    assert report.status == "blocked"
    assert report.blocking_findings == 1


def test_codex_review_priority_patterns_match_plain_text_titles() -> None:
    assert BLOCKING_CODEX_FINDING_PATTERN.search("[P1] blocking finding")
    assert BLOCKING_CODEX_FINDING_PATTERN.search("**[P0] blocking finding**")

    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[
            {
                "body": _codex_review_request_body(),
                "created_at": "2026-05-19T01:00:00Z",
            }
        ],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:01:00Z",
                "body": "### Codex Review",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[
            {"pull_request_review_id": 4314779358, "body": "[P1] blocking finding"},
            {"pull_request_review_id": 4314779358, "body": "[P2] advisory finding"},
        ],
    )
    assert report.status == "blocked"
    assert report.blocking_findings == 1
    assert report.advisory_findings == 1


def test_codex_review_monitor_blocks_on_any_current_head_codex_review() -> None:
    head_sha = "0" * 40
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": head_sha}},
        issue_comments=[{"body": _codex_review_request_body()}],
        reviews=[
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:00:00Z",
                "body": "**![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat) blocking**",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
            {
                "id": 4314779360,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T00:01:00Z",
                "body": "### Codex Review\n\nNo blocking findings.",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            },
        ],
        review_comments=[],
    )
    assert report.status == "blocked"
    assert report.blocking_findings == 1
    assert (
        report.latest_review_url
        == "https://github.com/liuli195/Quant-Trading/pull/5#pullrequestreview-4314779360"
    )
