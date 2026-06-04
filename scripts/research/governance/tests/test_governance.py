from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

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
from scripts.research.governance import rules as governance_rules
from scripts.research.governance.codex_review_contract import (
    is_codex_review_request,
    render_codex_review_request,
)
from scripts.research.governance.pr_review_evidence import (
    BLOCKING_CODEX_FINDING_PATTERN,
    _parse_next_link,
)
from scripts.research.governance.rules import run_audit
from scripts.research.platform.docs_index import write_adr_index
from scripts.research.registry import default_tool_registry
from scripts.tools.path_tools import refactor as path_refactor
from scripts.tools.path_tools.refactor import should_skip


SKILL_DISCOVERY_CASES = (
    ("新增或修改一个仓库 Skill，并同步 .agents/skills。", "repo-skill-governance"),
    ("这个仓库本地 Python 应该怎么跑，为什么不能用系统 Python？", "repo-python-env"),
    ("我移动了文档和报告链接，怎么检查 pathref 和索引？", "repo-docs-pathref"),
    (
        "准备一个进入主干的 PR，确认 review 证据和 required checks。",
        "repo-pr-governance",
    ),
    ("先本地筛选研究候选，别直接消耗 JoinQuant 云端额度。", "research-local-first"),
    ("把历史回测 run 做成可追溯数据快照。", "research-data-center"),
    ("补齐回测报告并对比多个 run 的收益和回撤。", "research-report-analysis"),
    ("做一个策略参数 A/B 实验，保留控制变量和 delta 归因。", "strategy-experiment"),
    ("JoinQuant 云端策略编译报错，帮我本地定位兼容问题。", "joinquant-strategy-fix"),
    ("上传策略到 JoinQuant 跑云端回测并抓结果，但注意配额。", "joinquant-cloud-run"),
)


def test_pathref_scanner_skips_local_workspace_artifacts() -> None:
    assert should_skip(Path(".local/pytest-governance-tmp/example.md"))


def test_commit_intent_pr_flow_contract_is_documented() -> None:
    required_tokens = {
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"): [
            "commit-scoped intent",
            "branch intent authority",
            "no branch creation gate",
            "PR Evidence JSON issues",
            "target scheme review authority",
            "two-stage review",
            "no AC auto-marking",
        ],
        Path("docs/rules/pr-workflow.md"): [
            "git add",
            "pr_flow intent stage",
            "git commit",
            "branch intent",
        ],
        Path("docs/rules/review-guidelines.md"): [
            "target方案优先",
            "Spec reviewer 按目标方案整体判断",
            "Security-after-Standards/Spec",
            "Standards/Security veto",
        ],
        Path("docs/rules/governance.md"): [
            "commit intent hook",
            "PR Evidence JSON issues",
            "no-Issue PR Evidence minimum",
        ],
        Path("docs/rules/commands.md"): [
            "pr_flow intent stage",
            "pr_flow intent pre-commit",
            "pr_flow intent post-commit",
            "pr_flow intent check-coverage",
        ],
        Path("docs/README.md"): [
            "commit intent",
            "PR Issue binding audit",
        ],
    }
    for path, tokens in required_tokens.items():
        text = path.read_text(encoding="utf-8")
        missing = [token for token in tokens if token not in text]
        assert not missing, f"{path} missing: {missing}"


def test_official_review_pr_flow_contract_is_documented() -> None:
    paths = [
        Path("docs/rules/pr-flow-interface-contract.yaml"),
        Path("docs/rules/governance.md"),
        Path("docs/rules/review-guidelines.md"),
        Path("docs/adr/0006-risk-tiered-pr-review.md"),
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"),
        Path(".agents/skills/repo-pr-governance/SKILL.md"),
    ]
    texts = {path: path.read_text(encoding="utf-8") for path in paths}

    required_tokens = {
        Path("docs/rules/pr-flow-interface-contract.yaml"): [
            "official_review",
            "skip_risk_low",
            "skip_user_authorized",
            "authorized_by",
            "evidence",
        ],
        Path("docs/rules/governance.md"): [
            "official_review.decision",
            "skip_risk_low",
            "skip_user_authorized",
            "authorized_by + evidence",
        ],
        Path("docs/rules/review-guidelines.md"): [
            "target spec wins",
            "rule/ADR drift",
            "official_review.decision",
            "authorized_by + evidence",
            "repo-pr-governance wrapper for $review",
        ],
        Path("docs/adr/0006-risk-tiered-pr-review.md"): [
            "official_review.decision",
            "skip_risk_low",
            "skip_user_authorized",
            "authorized_by + evidence",
        ],
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"): [
            "official_review",
            "skip_risk_low",
            "skip_user_authorized",
            "target spec wins",
            "pr-submit is not a sub-agent dispatcher",
        ],
        Path(".agents/skills/repo-pr-governance/SKILL.md"): [
            "repo-pr-governance wrapper for $review",
            "pr-submit is not a sub-agent dispatcher",
            "target spec wins",
            "closes = primary spec",
            "reference = background",
            "no Issue refs means default $review",
        ],
    }

    for path, tokens in required_tokens.items():
        missing = [token for token in tokens if token not in texts[path]]
        assert not missing, f"{path} missing: {missing}"

    old_drift = "risk=low + 官方 Review=否"
    for path, text in texts.items():
        assert old_drift not in text, (
            f"{path} still documents old official review drift"
        )


def test_pr_evidence_v2_contract_does_not_document_legacy_schema_fallback() -> None:
    paths = [
        Path("docs/rules/review-guidelines.md"),
        Path("docs/adr/0007-pr-flow-closed-loop-review-evidence.md"),
    ]
    forbidden_tokens = [
        "过渡期可读旧",
        "旧 evidence 缺失 `official_review` 时按 `required` 读取",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        leaked = [token for token in forbidden_tokens if token in text]
        assert not leaked, f"{path} still documents legacy PR Evidence fallback: {leaked}"


def test_gitignore_audit_rejects_broad_data_ignore_patterns(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(
        "data/\n**/data/\n/data/\n",
        encoding="utf-8",
    )

    findings = governance_rules._audit_gitignore_patterns(tmp_path)

    messages = [finding.message for finding in findings]
    assert any("data/" in message for message in messages)
    assert any("**/data/" in message for message in messages)
    assert not any("/data/" in message and "line 3" in message for message in messages)


def test_pathref_scoped_check_only_scans_requested_markdown_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "path_aliases.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "test",
                "lifecycle": "active",
                "roots": {"repo": "."},
                "aliases": {},
            }
        ),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "target.md").write_text("# Target\n", encoding="utf-8")
    (docs / "included.md").write_text(
        "[Target](target.md) <!-- pathref: repo/docs/target.md -->\n",
        encoding="utf-8",
    )
    (docs / "unscanned.md").write_text(
        "[Missing](missing.md) <!-- pathref: repo/docs/missing.md -->\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert path_refactor.check_markdown_pathrefs(files=[docs / "included.md"]) == 0
    assert path_refactor.check_markdown_pathrefs(files=[docs / "unscanned.md"]) == 1


def test_pathref_scoped_check_rejects_non_markdown_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "path_aliases.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "test",
                "lifecycle": "active",
                "roots": {"repo": "."},
                "aliases": {},
            }
        ),
        encoding="utf-8",
    )
    text_file = tmp_path / "notes.txt"
    text_file.write_text("plain text\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert path_refactor.check_markdown_pathrefs(files=[text_file]) == 2


SKILL_FIXTURES = (
    {
        "skill": "repo-skill-governance",
        "group": "Skill System",
        "description": "创建、修改、验证 Codex 仓库 Skill、.agents/skills、触发语义、ownership 索引和 Skill 发现治理时使用。",
        "owned_rules": ["docs/rules/skills.md"],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership discover",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.registry.tool_registry",
        ],
        "owned_scripts": ["scripts/research/governance/skill_ownership.py"],
        "read_rules": ["docs/rules/skills.md", "docs/rules/governance.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.governance gate",
        ],
        "trigger_phrases": ["新增或修改一个 仓库 Skill", "同步 .agents/skills"],
    },
    {
        "skill": "repo-python-env",
        "group": "Repo Governance",
        "description": "处理本仓库 Python 环境、项目 .venv、UTF-8、本地/云端运行边界和系统 Python 禁用规则时使用。",
        "owned_rules": [
            "docs/rules/commands.md#python-env",
            "docs/rules/environments.md#local-cloud-boundary",
        ],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe",
            ".venv/bin/python",
            ".\\.githooks\\setup-python.ps1",
            ".githooks/setup-python.sh",
        ],
        "owned_scripts": [".githooks/setup-python.ps1", ".githooks/setup-python.sh"],
        "read_rules": ["docs/rules/commands.md", "docs/rules/environments.md"],
        "recommended_commands": [".\\.venv\\Scripts\\python.exe -m pytest"],
        "trigger_phrases": ["本地 Python 应该怎么跑", "不能用系统 Python"],
    },
    {
        "skill": "repo-docs-pathref",
        "group": "Repo Governance",
        "description": "处理 Markdown 链接、pathref、文档索引、报告索引和 catalog 同步时使用。",
        "owned_rules": [
            "docs/rules/index.md",
            "docs/rules/docs-and-pathref.md#pathref",
        ],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.path_tools.refactor check",
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.path_tools.aliases",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.docs index",
        ],
        "owned_scripts": [
            "scripts/tools/path_tools/refactor.py",
            "scripts/tools/path_tools/aliases.py",
        ],
        "read_rules": ["docs/rules/docs-and-pathref.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.path_tools.refactor check"
        ],
        "trigger_phrases": ["移动了文档和报告链接", "检查 pathref 和索引"],
    },
    {
        "skill": "repo-pr-governance",
        "group": "Repo Governance",
        "description": "准备进入主干的 PR、review 证据、required checks、Codex review、主干保护和分支清理时使用。",
        "owned_rules": [
            "docs/rules/pr-workflow.md",
            "docs/rules/review-guidelines.md",
            "docs/rules/governance.md",
            "docs/rules/collaboration.md",
        ],
        "owned_commands": [
            "make pre-pr",
            "make verify-fast",
            "make verify-full",
            "make pr-submit",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.governance",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.pr_flow submit",
        ],
        "owned_scripts": ["scripts/research/governance"],
        "read_rules": [
            "docs/rules/pr-workflow.md",
            "docs/rules/review-guidelines.md",
            "docs/rules/governance.md",
        ],
        "recommended_commands": ['make pr-submit TITLE="<PR标题>"'],
        "trigger_phrases": ["进入主干的 PR", "review 证据", "required checks"],
    },
    {
        "skill": "research-local-first",
        "group": "Strategy Research",
        "description": "处理本地优先研究、候选漏斗、fast/full 筛选和云端交接判断时使用。",
        "owned_rules": ["docs/rules/research-workflow.md#local-first"],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.cli",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.etf_window_research.cli",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.momentum_tilt_research",
            ".\\.venv\\Scripts\\python.exe -m scripts.research.execution_timing_research.cli",
        ],
        "owned_scripts": [
            "scripts/research/cli.py",
            "scripts/research/workflows",
            "scripts/research/etf_window_research",
            "scripts/research/momentum_tilt_research",
            "scripts/research/execution_timing_research",
        ],
        "read_rules": ["docs/rules/research-workflow.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.cli"
        ],
        "trigger_phrases": ["本地筛选研究候选", "别直接消耗 JoinQuant 云端额度"],
    },
    {
        "skill": "research-data-center",
        "group": "Strategy Research",
        "description": "处理回测 run 数据快照、数据中心压缩、catalog、pointer 和可追溯证据时使用。",
        "owned_rules": ["docs/rules/research-workflow.md#data-center"],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.datasets"
        ],
        "owned_scripts": ["scripts/research/platform/datasets.py", "research_datasets"],
        "read_rules": ["docs/rules/research-workflow.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.datasets"
        ],
        "trigger_phrases": ["历史回测 run", "可追溯数据快照"],
    },
    {
        "skill": "research-report-analysis",
        "group": "Strategy Research",
        "description": "处理本地回测报告补齐、结果分析、多个 run 收益回撤对比和报告索引时使用。",
        "owned_rules": ["docs/rules/research-workflow.md#reports"],
        "owned_commands": [],
        "owned_scripts": [
            "scripts/research/platform/reporting.py",
            "scripts/research/cash_decomposition",
        ],
        "read_rules": ["docs/rules/research-workflow.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.docs index"
        ],
        "trigger_phrases": ["补齐回测报告", "对比多个 run", "收益和回撤"],
    },
    {
        "skill": "strategy-experiment",
        "group": "Strategy Research",
        "description": "处理策略参数扫描、A/B 实验、variant registry、控制变量和 delta 归因时使用。",
        "owned_rules": ["docs/rules/research-workflow.md#experiments"],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.variants",
            "jq-auto ab",
        ],
        "owned_scripts": [
            "scripts/research/platform/strategy_variants.py",
            "scripts/tools/jq_automation/abtest.py",
        ],
        "read_rules": ["docs/rules/research-workflow.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.research.variants"
        ],
        "trigger_phrases": ["策略参数 A/B 实验", "控制变量", "delta 归因"],
    },
    {
        "skill": "joinquant-strategy-fix",
        "group": "JoinQuant Automation",
        "description": "处理 JoinQuant 云端策略编译报错、本地兼容定位、compile-check 和最小策略修复时使用。",
        "owned_rules": [
            "docs/rules/environments.md#joinquant-compat",
            "docs/rules/code-style.md#joinquant-strategy",
        ],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation compile-check",
            ".\\.venv\\Scripts\\python.exe -m py_compile",
        ],
        "owned_scripts": [
            "scripts/tools/jq_automation/cli.py#compile-check",
            "scripts/tools/jq_automation/snippets/compile.js",
        ],
        "read_rules": ["docs/rules/environments.md", "docs/rules/code-style.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation compile-check <策略文件>"
        ],
        "trigger_phrases": ["JoinQuant 云端策略编译报错", "本地定位兼容问题"],
    },
    {
        "skill": "joinquant-cloud-run",
        "group": "JoinQuant Automation",
        "description": "处理 JoinQuant 上传、云端回测 run、fetch、batch、结果落盘和配额保护时使用。",
        "owned_rules": [
            "docs/rules/environments.md#joinquant-cloud-run",
            "docs/rules/research-workflow.md#cloud-handoff",
        ],
        "owned_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation upload",
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation run",
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation fetch",
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation batch",
        ],
        "owned_scripts": [
            "scripts/tools/jq_automation/cli.py#cloud-run",
            "scripts/tools/jq_automation/dataset_registration.py",
        ],
        "read_rules": ["docs/rules/environments.md", "docs/rules/research-workflow.md"],
        "recommended_commands": [
            ".\\.venv\\Scripts\\python.exe -m scripts.tools.jq_automation run <场景配置.json> --yes"
        ],
        "trigger_phrases": ["上传策略到 JoinQuant", "跑云端回测", "注意配额"],
    },
)


def _fixture_list(fixture: Mapping[str, object], key: str) -> list[str]:
    value = fixture.get(key, [])
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    return [str(value)]


def _write_owner_skill(root: Path, fixture: Mapping[str, object]) -> None:
    skill = str(fixture["skill"])
    description = str(fixture["description"])
    read_rules = _fixture_list(fixture, "read_rules")
    recommended_commands = _fixture_list(fixture, "recommended_commands")
    owner_root = root / ".agents" / "skills" / skill
    (owner_root / "agents").mkdir(parents=True, exist_ok=True)
    (owner_root / "references").mkdir(parents=True, exist_ok=True)
    skill_text = (
        "---\n"
        f"name: {skill}\n"
        f"description: {description}\n"
        "---\n\n"
        f"# {skill}\n"
        "\n## 必读规则\n\n"
        + "\n".join(f"- `{rule}`" for rule in read_rules)
        + "\n\n## 推荐命令\n\n"
        + "\n".join(f"- `{command}`" for command in recommended_commands)
        + "\n"
    )
    (owner_root / "SKILL.md").write_text(skill_text, encoding="utf-8")
    (owner_root / "agents" / "openai.yaml").write_text(
        f"interface:\n  display_name: {skill}\n",
        encoding="utf-8",
    )
    data = {
        "skill": skill,
        "group": str(fixture["group"]),
        "owned_rules": _fixture_list(fixture, "owned_rules"),
        "owned_commands": _fixture_list(fixture, "owned_commands"),
        "owned_scripts": _fixture_list(fixture, "owned_scripts"),
        "uses": _fixture_list(fixture, "uses"),
        "tools": ["claude-code", "codex"],
        "trigger_phrases": _fixture_list(fixture, "trigger_phrases"),
        "read_rules": read_rules,
        "recommended_commands": recommended_commands,
        "status": "active",
    }
    (owner_root / "references" / "ownership.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_all_owner_skills(root: Path) -> None:
    for fixture in SKILL_FIXTURES:
        _write_owner_skill(root, fixture)


def test_skill_ownership_discovers_agents_ssot_skill(tmp_path: Path) -> None:
    skill_root = tmp_path / ".agents" / "skills" / "repo-skill-governance"
    (skill_root / "agents").mkdir(parents=True)
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: repo-skill-governance\n"
        "description: Maintain repo skill governance from .agents/skills/.\n"
        "---\n\n"
        "# repo-skill-governance\n",
        encoding="utf-8",
    )
    (skill_root / "agents" / "openai.yaml").write_text(
        "interface:\n  display_name: Repo Skill Governance\n",
        encoding="utf-8",
    )
    (skill_root / "references" / "ownership.yaml").write_text(
        "skill: repo-skill-governance\n"
        "group: Skill System\n"
        "owned_rules:\n"
        "  - docs/rules/skills.md\n"
        "owned_commands:\n"
        "  - .\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check\n"
        "owned_scripts:\n"
        "  - scripts/research/governance/skill_ownership.py\n"
        "uses: []\n"
        "tools:\n"
        "  - claude-code\n"
        "  - codex\n"
        "trigger_phrases:\n"
        "  - repo skill governance\n"
        "read_rules:\n"
        "  - docs/rules/skills.md\n"
        "recommended_commands:\n"
        "  - .\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check\n"
        "status: active\n",
        encoding="utf-8",
    )

    from scripts.research.governance.skill_ownership import discover_owner

    result = discover_owner(tmp_path, "repo skill governance")

    assert [match.skill for match in result.matches] == ["repo-skill-governance"]
    assert result.matches[0].tools == ("claude-code", "codex")


def test_skill_ownership_discovers_repo_skill_governance(tmp_path: Path) -> None:
    skill_root = tmp_path / ".agents" / "skills" / "repo-skill-governance"
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: repo-skill-governance\n"
        "description: 创建、修改、验证仓库 Skill 与 .agents/skills。\n"
        "---\n",
        encoding="utf-8",
    )
    (skill_root / "references" / "ownership.yaml").write_text(
        "skill: repo-skill-governance\n"
        "group: Skill System\n"
        "owned_rules:\n"
        "  - docs/rules/skills.md\n"
        "owned_commands:\n"
        "  - .\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check\n"
        "owned_scripts:\n"
        "  - scripts/research/governance/skill_ownership.py\n"
        "uses: []\n"
        "tools:\n"
        "  - codex\n"
        "trigger_phrases:\n"
        "  - 新增或修改一个仓库 Skill\n"
        "read_rules:\n"
        "  - docs/rules/skills.md\n"
        "recommended_commands:\n"
        "  - .\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check\n"
        "status: active\n",
        encoding="utf-8",
    )

    from scripts.research.governance.skill_ownership import discover_owner

    result = discover_owner(tmp_path, "新增或修改一个仓库 Skill")

    assert [match.skill for match in result.matches] == ["repo-skill-governance"]
    assert result.matches[0].read_rules == ("docs/rules/skills.md",)


def test_skill_ownership_discovers_all_owner_examples() -> None:
    from scripts.research.governance.skill_ownership import discover_owner

    repo_root = Path.cwd()
    for query, expected_skill in SKILL_DISCOVERY_CASES:
        result = discover_owner(repo_root, query)
        assert [match.skill for match in result.matches] == [expected_skill]


def test_skill_ownership_discovers_partial_natural_language_queries() -> None:
    from scripts.research.governance.skill_ownership import discover_owner

    repo_root = Path.cwd()

    assert [
        match.skill for match in discover_owner(repo_root, "Python 怎么跑").matches
    ] == ["repo-python-env"]
    assert [
        match.skill for match in discover_owner(repo_root, "pathref 怎么检查").matches
    ] == ["repo-docs-pathref"]


def test_skill_ownership_rejects_duplicate_owned_rule(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    first = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    second = tmp_path / ".agents/skills/repo-python-env/references/ownership.yaml"
    first_data = yaml.safe_load(first.read_text(encoding="utf-8"))
    second_data = yaml.safe_load(second.read_text(encoding="utf-8"))
    first_data["owned_rules"] = ["docs/rules/commands.md"]
    second_data["owned_rules"] = ["docs/rules/commands.md"]
    first.write_text(
        yaml.safe_dump(first_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    second.write_text(
        yaml.safe_dump(second_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "duplicate owned_rules owner for docs/rules/commands.md" in error
        for error in errors
    )


def test_skill_ownership_rejects_unowned_skill(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    owner = tmp_path / ".agents/skills/unowned/SKILL.md"
    owner.parent.mkdir(parents=True)
    owner.write_text(
        "---\nname: unowned\ndescription: 未登记 Skill。\n---\n",
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unowned skill: .agents/skills/unowned/SKILL.md" in error for error in errors
    )


def test_skill_ownership_rejects_missing_owned_script_path(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_scripts"] = ["scripts/research/governance/missing.py"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "missing owned script for repo-skill-governance: scripts/research/governance/missing.py"
        in error
        for error in errors
    )


def test_skill_ownership_reports_invalid_records_without_discovery_crash(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-python-env/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.pop("trigger_phrases")
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any("missing fields: trigger_phrases" in error for error in errors)


def test_skill_ownership_rejects_missing_owned_rule_anchor(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_rules"] = ["docs/rules/skills.md#missing-anchor"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "missing markdown anchor in owned rule for repo-skill-governance: docs/rules/skills.md#missing-anchor"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_missing_claude_symlink_post_86(
    tmp_path: Path,
) -> None:
    """When .claude/skills symlink is missing, validate_ownerships must error.

    This test replaces the old ``test_skill_ownership_rejects_missing_claude_skill link``
    with symlink semantics (post-#86).
    """
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    _remove_skill_symlink(tmp_path)

    errors = validate_ownerships(tmp_path)

    assert any(
        ".claude/skills must be a Symlink to .agents/skills" in error
        for error in errors
    )


def test_skill_ownership_rejects_unknown_tool(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["tools"] = ["claude-code", "codex", "unknown-tool"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unsupported tool for repo-skill-governance: unknown-tool" in error
        for error in errors
    )


def test_skill_ownership_rejects_missing_frontmatter_name_or_description(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    skill = tmp_path / ".agents/skills/repo-skill-governance/SKILL.md"
    skill.write_text("---\ndescription: 创建 Skill。\n---\n", encoding="utf-8")

    errors = validate_ownerships(tmp_path)

    assert any(
        "SKILL.md missing frontmatter name for repo-skill-governance" in error
        for error in errors
    )


def test_skill_ownership_rejects_duplicate_trigger_phrase(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-python-env/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["trigger_phrases"] = ["新增或修改一个 仓库 Skill"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        'duplicate trigger phrase "新增或修改一个 仓库 Skill"' in error
        for error in errors
    )


def test_skill_ownership_rejects_non_active_required_owner(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["status"] = "draft"
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "required skill must be active: repo-skill-governance" in error
        for error in errors
    )


def test_skill_ownership_rejects_unsupported_recommended_command(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["recommended_commands"] = ["python -m scripts.research.governance gate"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unsupported recommended command for repo-skill-governance" in error
        for error in errors
    )


def test_skill_ownership_rejects_unsupported_owned_command_prefix(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_commands"] = ["python -m not.real.module"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unsupported owned command for repo-skill-governance: python -m not.real.module"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_owner_missing_read_rule_and_command(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    owner = tmp_path / ".agents/skills/repo-skill-governance/SKILL.md"
    owner.write_text(
        "---\n"
        "name: repo-skill-governance\n"
        f"description: {SKILL_FIXTURES[0]['description']}\n"
        "---\n"
        "docs/rules/skills.md\n",
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "SKILL.md missing read rule for repo-skill-governance: docs/rules/governance.md"
        in error
        for error in errors
    )
    assert any(
        "SKILL.md missing recommended command for repo-skill-governance" in error
        for error in errors
    )


def test_skill_ownership_rejects_unknown_python_module_command(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["recommended_commands"] = [".\\.venv\\Scripts\\python.exe -m not.real.module"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unknown python module in recommended command for repo-skill-governance: not.real.module"
        in error
        for error in errors
    )


def test_skill_ownership_command_cover_does_not_treat_python_as_owner() -> None:
    from scripts.research.governance.skill_ownership import _command_covers

    python = ".\\.venv\\Scripts\\python.exe"
    assert not _command_covers(python, f"{python} -m scripts.research.unowned")
    assert not _command_covers(
        f"{python} -m scripts.research.cli typo",
        f"{python} -m scripts.research.cli",
    )
    assert _command_covers(
        f"{python} -m scripts.research.governance",
        f"{python} -m scripts.research.governance audit",
    )
    assert _command_covers(
        f"{python} -m scripts.research.docs index",
        f"{python} -m scripts.research.docs",
    )
    assert not _command_covers(
        f"{python} -m scripts.research.docs index bogus",
        f"{python} -m scripts.research.docs",
    )


def test_skill_ownership_rejects_owned_command_runtime_options(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = (
        tmp_path / ".agents/skills/research-report-analysis/references/ownership.yaml"
    )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_commands"] = [
        ".\\.venv\\Scripts\\python.exe -m scripts.research.docs index --reports"
    ]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "owned command for research-report-analysis must be a command prefix" in error
        for error in errors
    )


def test_skill_ownership_rejects_unknown_owned_command_subcommand(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/research-local-first/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_commands"] = [
        ".\\.venv\\Scripts\\python.exe -m scripts.research.cli typo"
    ]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unsupported python command arguments in owned command for research-local-first: scripts.research.cli typo"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_extra_owned_command_position_args(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-docs-pathref/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_commands"] = [
        ".\\.venv\\Scripts\\python.exe -m scripts.research.docs index bogus"
    ]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unsupported python command arguments in owned command for repo-docs-pathref: scripts.research.docs index bogus"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_unknown_jq_auto_subcommand(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/strategy-experiment/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["owned_commands"] = ["jq-auto ab bogus"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "unknown jq-auto command in owned command for strategy-experiment: jq-auto ab bogus"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_legacy_active_skill_directories(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    legacy = tmp_path / ".codex/skills"
    legacy.mkdir(parents=True)
    errors = validate_ownerships(tmp_path)

    assert any(
        "legacy skill directory must be removed: .codex/skills" in error
        for error in errors
    )


def test_skill_ownership_rejects_unowned_rule_doc(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/rules/unowned.md").write_text("unowned\n", encoding="utf-8")

    errors = validate_ownerships(tmp_path)

    assert any(
        "rule doc missing owner: docs/rules/unowned.md" in error for error in errors
    )


def test_skill_ownership_rejects_unowned_make_target(tmp_path: Path) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8") + "\nextra-target:\n\t@echo extra\n",
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "make target missing owner: make extra-target" in error for error in errors
    )


def test_skill_ownership_rejects_trigger_phrase_not_covered_by_description(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["trigger_phrases"] = ["苹果香蕉梨子"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any(
        "trigger phrase not covered by skill description for repo-skill-governance"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_trigger_phrase_ambiguous_discovery(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    path = tmp_path / ".agents/skills/repo-python-env/references/ownership.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["trigger_phrases"] = ["仓库 Skill"]
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any('trigger phrase "仓库 Skill" is ambiguous' in error for error in errors)


def test_skill_ownership_rejects_skills_doc_without_human_summary(
    tmp_path: Path,
) -> None:
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/rules/skills.md").write_text(
        "# Skill 规则\n\nownership.yaml 是机器可读 SSOT。\n",
        encoding="utf-8",
    )

    errors = validate_ownerships(tmp_path)

    assert any("skills.md missing skill summary" in error for error in errors)


def test_governance_audit_flags_missing_owner_skill(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    (
        tmp_path / ".agents/skills/repo-skill-governance/references/ownership.yaml"
    ).unlink()

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "skill_ownership"
        and "missing skill: repo-skill-governance" in finding.message
        for finding in report.findings
    )


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
                "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub> provide unified diff**",
                "",
                "I cannot complete a static review because this conversation did not include the actual code diff.",
            ]
        ),
        "user": {"login": "chatgpt-codex-connector[bot]"},
    }


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
        "research_datasets/demo/snap/raw",
        "research_datasets/demo/snap/data",
    ):
        (root / path).mkdir(parents=True, exist_ok=True)

    for path in (
        "scripts/research/README.md",
        "scripts/research/cli.py",
        "scripts/research/datasets.py",
        "scripts/research/docs.py",
        "scripts/research/variants.py",
        "scripts/research/platform/README.md",
        "scripts/research/platform/datasets.py",
        "scripts/research/platform/reporting.py",
        "scripts/research/platform/strategy_variants.py",
        "scripts/research/registry/README.md",
        "scripts/research/registry/tool_registry.py",
        "scripts/research/governance/README.md",
        "scripts/research/governance/pr_flow.py",
        "scripts/research/governance/skill_ownership.py",
        "scripts/research/research_core/README.md",
        "scripts/research/etf_window_research/cli.py",
        "scripts/research/etf_window_research/README.md",
        "scripts/research/momentum_tilt_research/README.md",
        "scripts/research/execution_timing_research/cli.py",
        "scripts/research/execution_timing_research/README.md",
        "scripts/research/portfolio_volatility_research/README.md",
        "scripts/research/cash_decomposition/README.md",
        "scripts/research/workflows/README.md",
        "scripts/tools/jq_automation/README.md",
        "scripts/tools/jq_automation/__init__.py",
        "scripts/tools/jq_automation/abtest.py",
        "scripts/tools/jq_automation/cli.py",
        "scripts/tools/jq_automation/dataset_registration.py",
        "scripts/tools/jq_automation/snippets/compile.js",
        "scripts/tools/path_tools/README.md",
        "scripts/tools/path_tools/aliases.py",
        "scripts/tools/path_tools/refactor.py",
        "docs/guides/research-workflow.md",
        "docs/architecture/research-platform-architecture.md",
        "docs/rules/index.md",
        "docs/rules/pr-workflow.md",
        "docs/rules/governance.md",
        "docs/rules/pr-flow-interface-contract.yaml",
        "docs/rules/skills.md",
        "docs/rules/review-guidelines.md",
        "docs/rules/commands.md",
        "docs/rules/environments.md",
        "docs/rules/research-workflow.md",
        "docs/rules/collaboration.md",
        "docs/rules/code-style.md",
        "docs/rules/docs-and-pathref.md",
        "docs/adr/index.md",
        "docs/adr/0001-rule-source-and-governance-model.md",
        "docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md",
        "docs/adr/0003-governance-gate-and-main-branch-protection.md",
        "docs/adr/0004-codex-code-review-governance.md",
        "docs/adr/0005-ai-entry-progressive-disclosure.md",
        "research_datasets/README.md",
        "scripts/research/platform/tests/test_platform.py",
        "scripts/research/registry/tests/test_registry.py",
        "scripts/research/governance/tests/test_governance.py",
        "scripts/research/governance/tests/test_pr_flow_contract.py",
        "scripts/research/governance/tests/test_verify.py",
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

    write_adr_index(root)

    # CLAUDE.md is now a File Symlink to AGENTS.md (not a separate file).
    # Content of both files is identical by design.
    _remove_claude_md_symlink(root)
    _write_claude_md_symlink(root)
    (root / "AGENTS.md").write_text(
        "所有 AI 编码助手统一以 AGENTS.md 为通用入口。\n\n"
        "本仓库是基于 Python 的 A 股/场内基金量化策略仓库。\n\n"
        "所有回答和输出使用简体中文，简洁直白。"
        "策略代码仅在聚宽云端运行。"
        "默认必须提权使用项目 `.venv`，不改用系统 Python。"
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
    (root / "docs/rules/commands.md").write_text(
        "# 命令和本地环境规则\n\n"
        "## Python Env\n\n"
        "scripts.research.cli scripts.research.datasets scripts.research.variants "
        "scripts.research.governance scripts.research.governance gate "
        "scripts.research.governance verify fast scripts.research.governance verify full "
        "scripts.research.registry "
        "scripts.tools.path_tools.refactor .\\.githooks\\setup-python.ps1 "
        ".githooks/setup-python.sh "
        ".\\.venv\\Scripts\\python.exe .venv/bin/python PYTHONUTF8 PYTHONIOENCODING "
        "Python 命令默认必须提权使用项目 `.venv`，不改用系统 Python "
        "gh pr checks `gh` CLI 默认提权执行",
        encoding="utf-8",
    )
    (root / "docs/rules/environments.md").write_text(
        "# 本地与聚宽环境差异\n\n"
        "## Local Cloud Boundary\n\n"
        "本地负责开发、测试、文档和分析。\n\n"
        "## JoinQuant Compat\n\n"
        "策略代码必须兼容聚宽 Python 3.6。\n\n"
        "## JoinQuant Cloud Run\n\n"
        "云端回测和本地研究分工明确。\n",
        encoding="utf-8",
    )
    (root / "docs/rules/research-workflow.md").write_text(
        "# 研究流程规则\n\n"
        "## Local First\n\n"
        "先本地 fast/full 漏斗。\n\n"
        "## Data Center\n\n"
        "新数据快照登记 catalog。\n\n"
        "## Reports\n\n"
        "报告保留可追溯证据。\n\n"
        "## Cloud Handoff\n\n"
        "云端回测保留 run 和 manifest。\n\n"
        "## Experiments\n\n"
        "A/B 保留控制变量。\n",
        encoding="utf-8",
    )
    (root / "docs/rules/code-style.md").write_text(
        "# 代码风格和策略实现规则\n\n## JoinQuant Strategy\n\n策略代码必须兼容聚宽。\n",
        encoding="utf-8",
    )
    (root / "docs/rules/docs-and-pathref.md").write_text(
        "# 文档和 Pathref 规则\n\n## Pathref\n\nMarkdown 内部文件引用使用 pathref。\n",
        encoding="utf-8",
    )
    (root / "docs/rules/skills.md").write_text(
        "# Skill 规则\n\n"
        "ownership.yaml 是机器可读 SSOT；本文只保留人类可读汇总。\n\n"
        "## Skill 汇总\n\n"
        "| Skill | 范围 |\n"
        "| --- | --- |\n"
        "| `repo-skill-governance` | Skill 创建、单一来源和 ownership 治理 |\n"
        "| `repo-python-env` | Python 环境和本地/云端边界 |\n"
        "| `repo-docs-pathref` | 文档链接、pathref 和索引 |\n"
        "| `repo-pr-governance` | PR、review 证据和主干保护 |\n"
        "| `research-local-first` | 本地优先研究和候选漏斗 |\n"
        "| `research-data-center` | run 快照和数据 catalog |\n"
        "| `research-report-analysis` | 报告补齐和跨 run 对比 |\n"
        "| `strategy-experiment` | 参数扫描、A/B 和变体治理 |\n"
        "| `joinquant-strategy-fix` | JoinQuant 编译和兼容修复 |\n"
        "| `joinquant-cloud-run` | JoinQuant 云端 run、fetch、batch |\n",
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
        "sh .githooks/run-python.sh -m scripts.research.governance.pr_flow intent pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance verify fast --staged\n",
        encoding="utf-8",
    )
    (root / ".githooks/post-commit").write_text(
        "sh .githooks/run-python.sh -m scripts.research.governance.pr_flow intent post-commit\n",
        encoding="utf-8",
    )
    (root / "Makefile").write_text(
        "ifeq ($(OS),Windows_NT)\n"
        "PYTHON ?= ./.venv/Scripts/python.exe\n"
        "else\n"
        "PYTHON ?= .venv/bin/python\n"
        "endif\n"
        "verify-fast:\n\t$(PYTHON) -m scripts.research.governance verify fast --staged\n"
        "verify-full:\n\t$(PYTHON) -m scripts.research.governance verify full\n"
        "pre-pr:\n\t$(PYTHON) -m pre_commit run --all-files\n\t$(MAKE) verify-full\n"
        'pr-submit:\n\t$(PYTHON) -m scripts.research.governance.pr_flow submit --title "$(TITLE)"\n',
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
        'uname MINGW MSYS CYGWIN .venv/bin/python .venv/Scripts/python.exe "$@"\n',
        encoding="utf-8",
    )
    (root / ".githooks/run-python.ps1").write_text(
        "& .venv\\Scripts\\python.exe @args\n",
        encoding="utf-8",
    )
    (root / ".githooks/setup-python.ps1").write_text(
        "3.12\nrequirements-dev.txt\ngit config core.hooksPath .githooks\n"
        "PYTHONUTF8\nPYTHONIOENCODING\ngit config core.symlinks true\n",
        encoding="utf-8",
    )
    (root / ".githooks/setup-python.sh").write_text(
        "python3.12\nrequirements-dev.txt\ngit config core.hooksPath .githooks\n"
        "PYTHONUTF8\nPYTHONIOENCODING\n.githooks/post-commit\ngit config core.symlinks true\n",
        encoding="utf-8",
    )
    (root / ".githooks/pre-push").write_text(
        "\n".join(
            [
                "sh .githooks/run-python.sh -m scripts.research.governance.branch_protection pre-push",
                "sh .githooks/run-python.sh -m scripts.research.governance verify full",
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
        "  - run: git config core.symlinks true\n"
        "  - run: python -m scripts.research.governance verify full\n",
        encoding="utf-8",
    )
    (root / ".github/workflows/pr-flow.yml").write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          ref: ${{ github.event.pull_request.head.sha }}\n"
        "          fetch-depth: 0\n"
        "      - run: git fetch --no-tags --prune origin +refs/heads/${{ github.event.pull_request.base.ref }}:refs/remotes/origin/${{ github.event.pull_request.base.ref }}\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )
    (root / ".github/workflows/codex-review-monitor.yml").write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  issue_comment:\n  pull_request_review:\n"
        "    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n"
        "    types: [created, edited, deleted]\n"
        "permissions:\n  statuses: write\nsteps:\n"
        "  - uses: actions/checkout@v4\n"
        "    with:\n"
        "      ref: ${{ steps.pr-head.outputs.sha }}\n"
        "  - run: python -m pip install -r requirements-dev.txt\n"
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-status\n"
        "  - name: Publish monitor failure status\n"
        "    if: ${{ always() && github.event_name != 'workflow_dispatch' && (failure() || cancelled()) }}\n"
        "    run: gh api pulls/$env:PR_NUMBER -f context='PR Flow / review-status' -f state=failure -f state=error\n",
        encoding="utf-8",
    )
    (root / ".codex/environments").mkdir(parents=True, exist_ok=True)
    (root / ".codex/environments/environment.toml").write_text(
        ".\\.githooks\\setup-python.ps1\ngit config core.symlinks true\n",
        encoding="utf-8",
    )
    (root / "scripts/research/governance/README.md").write_text(
        "docs/rules/index.md docs/adr/index.md scripts.research.governance gate PR Flow / review-status "
        "git fetch origin main git merge --ff-only origin/main "
        "git branch -d <branch> remote branch deletion by GitHub\n",
        encoding="utf-8",
    )
    (root / "docs/rules/pr-workflow.md").write_text(
        "所有进入主干的改动必须通过 PR\n直写主干 ALLOW_DIRECT_MAIN_WRITE DIRECT_MAIN_WRITE_REASON\n"
        "禁止把功能分支本地合入\n"
        "git fetch origin main\ngit merge --ff-only origin/main\n"
        "git branch -d <branch>\n远端分支删除交给 GitHub\n",
        encoding="utf-8",
    )
    (root / "docs/rules/collaboration.md").write_text(
        "多个 AI agent\n分支名使用 ASCII\n本地共享工作区\n只读分析不要求创建分支\n"
        "有可用子 agent 能力\n无能力时记录原因\n不采用任务登记\n",
        encoding="utf-8",
    )
    (root / "docs/rules/governance.md").write_text(
        ".githooks/reference-transaction ALLOW_MAIN_REF_UPDATE MAIN_REF_UPDATE_REASON "
        "ALLOW_DIRECT_MAIN_WRITE DIRECT_MAIN_WRITE_REASON PR Flow / review-status "
        "Research Governance / verify-full PR Flow / evidence PR Evidence JSON issues "
        "no-Issue PR Evidence minimum "
        "review_mode=complete official Codex required check "
        "security_review 本地安全 review codex-security security-guidance "
        "git fetch origin main git merge --ff-only origin/main "
        "git branch -d <branch> 远端分支删除交给 GitHub force delete\n",
        encoding="utf-8",
    )
    (root / "CODEOWNERS").write_text(
        "\n".join(
            [
                "CLAUDE.md @research-platform",
                "AGENTS.md @research-platform",
                "docs/agents/** @research-platform",
                "docs/rules/** @research-platform",
                "docs/adr/** @research-platform",
                ".agents/skills/** @research-platform",
                ".codex/environments/** @research-platform",
                ".claude/settings.json @research-platform",
                ".claude/settings.local.json @research-platform",
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
        "任务分发说明\nPR Evidence JSON\nPR Flow fragments\nofficial Codex required check\n"
        "official_review\nretained\nCodex Code Review 结论\n"
        "本地安全 review\ncodex-security\nsecurity-guidance\n"
        "Codex\n"
        "<!-- pr-flow:start -->\n<!-- pr-flow:end -->\n"
        ".\\.venv\\Scripts\\python.exe -m scripts.research.governance gate\n"
        "waiver\n证据\n",
        encoding="utf-8",
    )
    (root / ".github/pull_request_template.md").write_text(
        "## 改动目标\n\n"
        "-\n\n"
        "## 影响范围\n\n"
        "-\n\n"
        "<!-- pr-flow:start -->\n"
        "```json\n"
        "{}\n"
        "```\n"
        '运行 `make pr-submit TITLE="<PR标题>"` 后由脚本更新本区块。\n'
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
                ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full",
                "PR Flow / review-status",
                "PR Flow / evidence",
                "PR Evidence JSON",
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
                "retained",
                "official Codex required check",
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
    _write_all_owner_skills(root)
    _write_skill_symlink(root)
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


def test_governance_main_rejects_legacy_fast_gate(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        governance_main.main(["gate", "--repo-root", str(tmp_path), "--fast"])

    assert exc.value.code == 2


def test_governance_gate_rejects_legacy_fast_flag(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc:
        governance_gate.main(["--repo-root", str(tmp_path), "--fast"])

    assert exc.value.code == 2


def test_governance_audit_flags_pre_commit_without_fast_gate(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-commit").write_text(
        "pre-commit run --hook-stage pre-commit\n"
        ".venv/bin/python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-commit hook must use verify fast --staged" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pre_push_with_fast_gate(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-push").write_text(
        "\n".join(
            [
                ".venv/bin/python -m scripts.research.governance.branch_protection pre-push",
                ".venv/bin/python -m scripts.research.governance gate --fast",
                "git lfs pre-push",
            ]
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-push hook must use verify full" in finding.message
        for finding in report.findings
    )


def test_local_review_entrypoints_are_tracked(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Makefile").write_text(
        "ifeq ($(OS),Windows_NT)\n"
        "PYTHON ?= ./.venv/Scripts/python.exe\n"
        "else\n"
        "PYTHON ?= .venv/bin/python\n"
        "endif\n"
        "verify-fast:\n\t$(PYTHON) -m scripts.research.governance verify fast --staged\n"
        "verify-full:\n\t$(PYTHON) -m scripts.research.governance verify full\n"
        "pre-pr:\n\t$(PYTHON) -m pre_commit run --all-files\n\t$(MAKE) verify-full\n"
        'pr-submit:\n\t$(PYTHON) -m scripts.research.governance.pr_flow submit --title "$(TITLE)"\n',
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
        "sh .githooks/run-python.sh -m scripts.research.governance.pr_flow intent pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance verify fast --staged\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]


def test_local_review_entrypoints_require_pr_submit(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8").replace(
            'pr-submit:\n\t$(PYTHON) -m scripts.research.governance.pr_flow submit --title "$(TITLE)"\n',
            "",
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "local_review"
        and "Makefile missing pr-submit" in finding.message
        for finding in report.findings
    )


def test_local_review_entrypoints_require_verify_targets(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        makefile.read_text(encoding="utf-8").replace("verify-fast", "verify-quick"),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "local_review"
        and "Makefile missing verify-fast" in finding.message
        for finding in report.findings
    )


def test_tool_registry_registers_pr_flow_cli() -> None:
    tool = default_tool_registry().get("research.pr_flow")

    assert tool.entry_module == "scripts.research.governance.pr_flow"
    assert "submit" in (tool.cli or "")
    assert ".local/ai-review/fragments/*.json" in tool.inputs


def test_tool_registry_registers_governance_verify_cli() -> None:
    tool = default_tool_registry().get("research.governance_verify")

    assert tool.entry_module == "scripts.research.governance"
    assert "verify" in (tool.cli or "")
    assert "changed files" in tool.inputs
    assert "explicit --files" in tool.inputs


def test_local_review_entrypoints_reject_wrapper_make_python(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Makefile").write_text(
        "PYTHON := powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./.githooks/run-python.ps1\n"
        "pre-pr:\n\t$(PYTHON) -m pre_commit run --all-files\n"
        'pr-submit:\n\t$(PYTHON) -m scripts.research.governance.pr_flow submit --title "$(TITLE)"\n',
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "local_review"
        and finding.message == "Makefile must use direct project .venv Python"
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
    (tmp_path / ".github/workflows/pr-flow.yml").write_text(
        "name: PR Flow\non:\n  pull_request:\n    types: [opened, synchronize, reopened]\n"
        "jobs:\n  evidence:\n    steps:\n      - run: echo missing\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate" and "PR Flow evidence" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_review_evidence_without_inline_comment_deleted_event(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/pr-flow.yml").write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited]\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
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
    (tmp_path / ".github/workflows/pr-flow.yml").write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
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
    (tmp_path / ".github/workflows/pr-flow.yml").write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "labeled and unlabeled events" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pr_flow_status_publish_without_open_pr_guard(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/pr-flow.yml"
    workflow.write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "permissions:\n  statuses: write\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          ref: ${{ github.event.pull_request.head.sha }}\n"
        "          fetch-depth: 0\n"
        "      - run: git fetch --no-tags --prune origin +refs/heads/${{ github.event.pull_request.base.ref }}:refs/remotes/origin/${{ github.event.pull_request.base.ref }}\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n"
        "      - name: Publish PR Flow evidence status\n"
        "        if: ${{ always() }}\n"
        "        run: gh api repos/x/y/statuses/${{ github.event.pull_request.head.sha }}\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "open PR before publishing evidence status" in finding.message
        for finding in report.findings
    )


def test_governance_workflow_uses_single_verify_full_entrypoint(tmp_path: Path) -> None:
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
        "  verify-full:\n"
        "    steps:\n"
        "      - run: git config core.symlinks true\n"
        "      - run: python -m scripts.research.governance verify full\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]


def test_governance_audit_flags_workflow_without_pr_review_evidence_gate(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/pr-flow.yml"
    workflow.write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - run: echo missing\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        "PR Flow evidence workflow missing scripts.research.governance.pr_review_evidence"
        in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pr_flow_without_pr_head_checkout_and_base_fetch(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/pr-flow.yml"
    workflow.write_text(
        "name: PR Flow\n"
        "on:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n"
        "  evidence:\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    messages = {finding.message for finding in report.findings}
    assert "PR Flow evidence workflow must checkout the current PR head" in messages
    assert "PR Flow evidence workflow must fetch full history" in messages
    assert "PR Flow evidence workflow must fetch the PR base branch" in messages


def test_governance_audit_flags_workflow_without_skill_symlink_config(
    tmp_path: Path,
) -> None:
    """CI workflow must configure core.symlinks true before verify full (post-#86)."""
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
        "      - run: python -m scripts.research.governance verify full\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        "CI workflow must configure core.symlinks true before verify full"
        in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_pr_review_evidence_job_level_if(
    tmp_path: Path,
) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/pr-flow.yml"
    workflow.write_text(
        "name: PR Flow\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
        "  pull_request_review:\n    types: [submitted, edited, dismissed]\n"
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n"
        "jobs:\n"
        "  evidence:\n"
        "    if: github.event_name == 'pull_request'\n"
        "    steps:\n"
        "      - run: python -m scripts.research.governance.pr_review_evidence --body-env PR_BODY\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        "required PR Flow evidence job must not use job-level if" in finding.message
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
        and "PR Flow / review-status" in finding.message
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
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-status\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "deleted inline review comments" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_monitor_status_comment_sync(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/workflows/codex-review-monitor.yml").write_text(
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review, labeled, unlabeled]\n"
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
        and "status comments" in finding.message
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
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-status\n",
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
        "  - run: python -m scripts.research.governance.codex_review_monitor --sync-status\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "pull_request labeled and unlabeled events" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_monitor_checkout_default_branch_for_comments(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/codex-review-monitor.yml"
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace(
            "ref: ${{ steps.pr-head.outputs.sha }}",
            "ref: ${{ github.event_name == 'issue_comment' && github.event.repository.default_branch || steps.pr-head.outputs.sha }}",
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "must checkout PR head" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_monitor_without_failure_finalizer(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/codex-review-monitor.yml"
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(
        text.replace(
            "  - name: Publish monitor failure status\n"
            "    if: ${{ always() && github.event_name != 'workflow_dispatch' && (failure() || cancelled()) }}\n"
            "    run: gh api pulls/$env:PR_NUMBER -f context='PR Flow / review-status' -f state=failure -f state=error\n",
            "",
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "codex_review_monitor"
        and "failure status finalizer" in finding.message
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


def test_governance_audit_flags_missing_adr_index(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/adr/index.md").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "adr" and "docs/adr/index.md missing" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_stale_adr_index(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/adr/index.md").write_text(
        "# ADR 索引\n\nstale\n", encoding="utf-8"
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "adr" and "docs/adr/index.md stale" in finding.message
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


def test_governance_audit_flags_codex_environment_without_core_symlinks(
    tmp_path: Path,
) -> None:
    """environment.toml must include git config core.symlinks true (post-#86)."""
    _write_minimal_repo(tmp_path)
    (tmp_path / ".codex/environments/environment.toml").write_text(
        ".\\.githooks\\setup-python.ps1\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "environment.toml missing git config core.symlinks true"
        in finding.message
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
        ".venv/bin/python .\\.venv\\Scripts\\python.exe .venv/bin/python "
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


def test_governance_audit_flags_pre_commit_without_intent_gate(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-commit").write_text(
        "pre-commit run --hook-stage pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance verify fast --staged\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "pre-commit hook missing intent pre-commit gate" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_post_commit_hook(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/post-commit").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and ".githooks/post-commit missing" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_post_commit_without_intent_gate(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/post-commit").write_text(
        "sh .githooks/run-python.sh -m scripts.research.governance verify fast\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "post-commit hook missing intent post-commit gate" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_post_commit_without_python_wrapper(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/post-commit").write_text(
        "python -m scripts.research.governance.pr_flow intent post-commit\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "post-commit hook must use run-python.sh" in finding.message
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
        and "pre-push hook missing full governance verification" in finding.message
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


def test_governance_audit_flags_missing_hooks_path(tmp_path, monkeypatch) -> None:
    """core.hooksPath must be set to .githooks."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    _write_minimal_repo(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        governance_rules,
        "_read_git_hooks_path",
        lambda _root: None,
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "core.hooksPath must be set to .githooks" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_missing_hooks_path_in_linked_worktree(
    tmp_path, monkeypatch
) -> None:
    """core.hooksPath is still required when .git is a linked-worktree file."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    _write_minimal_repo(tmp_path)
    (tmp_path / ".git").write_text("gitdir: ../.git/worktrees/example\n", encoding="utf-8")
    monkeypatch.setattr(
        governance_rules,
        "_read_git_hooks_path",
        lambda _root: None,
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "core.hooksPath must be set to .githooks" in finding.message
        for finding in report.findings
    )


def test_governance_audit_accepts_correct_hooks_path(tmp_path, monkeypatch) -> None:
    """No finding when core.hooksPath is .githooks."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    _write_minimal_repo(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        governance_rules,
        "_read_git_hooks_path",
        lambda _root: ".githooks",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    hooks_path_findings = [f for f in report.findings if "core.hooksPath" in f.message]
    assert not hooks_path_findings


def test_governance_audit_skips_hooks_path_in_ci(tmp_path, monkeypatch) -> None:
    """core.hooksPath check is skipped in CI (GITHUB_ACTIONS set)."""
    _write_minimal_repo(tmp_path)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        governance_rules,
        "_read_git_hooks_path",
        lambda _root: None,
    )
    monkeypatch.setitem(os.environ, "GITHUB_ACTIONS", "true")
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    hooks_path_findings = [f for f in report.findings if "core.hooksPath" in f.message]
    assert not hooks_path_findings


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
                "  .venv/bin/python -m scripts.research.governance.branch_protection reference-transaction",
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
        "scripts.research.cli git fetch origin main\n\n"
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


def test_governance_audit_accepts_agents_review_guideline_rule_item(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8").replace(
            "## Review 指南\n\n"
            "Review 前必须先阅读并遵守 docs/rules/review-guidelines.md。"
            "如果无法访问该文件，视为 review 被阻塞。",
            "- **review 指南**：Review 前必须先阅读并遵守 "
            "docs/rules/review-guidelines.md",
        ),
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok


def test_governance_audit_flags_agents_without_python_venv_rule(
    tmp_path,
) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        "所有 AI 编码助手统一以 AGENTS.md 为通用入口。\n\n"
        "所有回答和输出使用简体中文。\n\n"
        "## Review guidelines\n\n"
        "Before reviewing, read and apply docs/rules/review-guidelines.md. "
        "If you cannot access that file, treat the review as blocked.\n",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "agent_entry_sync"
        and "默认必须提权使用项目 `.venv`，不改用系统 Python" in finding.message
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


def test_governance_audit_flags_claude_md_not_a_symlink(tmp_path: Path) -> None:
    """CLAUDE.md must be a symlink to AGENTS.md (post-#86)."""
    _write_minimal_repo(tmp_path)
    # Remove the symlink and write CLAUDE.md as a regular file
    claude_md = tmp_path / "CLAUDE.md"
    if claude_md.is_symlink():
        claude_md.unlink()
    claude_md.write_text(
        "先读 AGENTS.md。遇到沙箱/权限阻断时申请提权。",
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        finding.rule_id == "skill_ownership"
        and "CLAUDE.md must be a Symlink to AGENTS.md" in finding.message
        for finding in report.findings
    )


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
        and "远端分支删除交给 GitHub" in finding.message
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


def _managed_evidence_body(payload: Mapping[str, object]) -> str:
    return (
        "<!-- pr-flow:start -->\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n```\n"
        "<!-- pr-flow:end -->\n"
    )


def _contract_pr_body(
    *,
    head_sha: str = "0" * 40,
    diff_hash: str = "diff-hash",
    official_review: Mapping[str, object] | None = None,
) -> str:
    reviews = {
        role: {"head": head_sha, "diff": diff_hash}
        for role in ("standards", "spec", "security")
    }
    return _managed_evidence_body(
        {
            "schema": 2,
            "head": head_sha,
            "diff": diff_hash,
            "reviews": reviews,
            "official_review": dict(official_review or {"decision": "required"}),
            "issues": {"commits": [], "refs": []},
            "retained": [],
        }
    )


def _valid_codex_review_body(review_id: int = 4314779358) -> str:
    _ = review_id
    return _contract_pr_body()


def _official_codex_skip_body(*, authorization: str | None = None) -> str:
    _ = authorization
    return _contract_pr_body(
        official_review={
            "decision": "skip_user_authorized",
            "authorized_by": "liuli195",
            "evidence": "user authorized skipping official Codex review",
        }
    )


def _low_risk_no_official_review_body() -> str:
    return _contract_pr_body(official_review={"decision": "skip_risk_low"})

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


def test_codex_review_monitor_reports_chinese_context_hostile_trigger() -> None:
    report = build_monitor_report(
        repo="liuli195/Quant-Trading",
        pr_number="5",
        pr={"head": {"sha": "0" * 40}},
        issue_comments=[
            {
                "body": _codex_review_request_body(
                    review_scope=("不要执行本地命令；仅查看代码差异。",)
                ),
                "created_at": "2026-05-19T01:00:00Z",
                "user": {"login": "liuli195"},
            }
        ],
        reviews=[],
        review_comments=[],
    )

    assert report.status == "trigger_invalid"
    assert report.trigger_invalid


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


def test_codex_review_monitor_reports_chinese_context_invalid_review() -> None:
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
            {
                "id": 4314779358,
                "commit_id": head_sha,
                "submitted_at": "2026-05-19T01:03:00Z",
                "body": "### Codex Review\n\n无法完成审查，因为缺少当前 PR diff。",
                "user": {"login": "chatgpt-codex-connector[bot]"},
            }
        ],
        review_comments=[],
    )

    assert report.status == "context_invalid"
    assert report.context_invalid_reviews == 1


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


# ── #86 / #93 RED tests: Symlink governance ──────────────────────────────────


def _write_skill_symlink(root: Path) -> None:
    """Create .claude/skills as a directory symlink to .agents/skills."""
    agents = root / ".agents" / "skills"
    claude = root / ".claude" / "skills"
    claude.parent.mkdir(parents=True, exist_ok=True)
    if claude.is_symlink():
        resolved = claude.resolve()
        if resolved == agents.resolve():
            return
        claude.unlink()
    elif claude.exists():
        import shutil
        shutil.rmtree(str(claude))
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/D", str(claude), str(agents)],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        claude.symlink_to(agents, target_is_directory=True)


def _remove_skill_symlink(root: Path) -> None:
    """Remove .claude/skills symlink."""
    claude = root / ".claude" / "skills"
    if claude.is_symlink():
        claude.unlink()
    elif claude.exists():
        import shutil
        shutil.rmtree(str(claude))


def _write_claude_md_symlink(root: Path) -> None:
    """Create CLAUDE.md as a file symlink to AGENTS.md."""
    agents_md = root / "AGENTS.md"
    claude_md = root / "CLAUDE.md"
    if claude_md.is_symlink():
        resolved = claude_md.resolve()
        if resolved == agents_md.resolve():
            return
        claude_md.unlink()
    elif claude_md.exists():
        claude_md.unlink()
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", str(claude_md), str(agents_md)],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        claude_md.symlink_to(agents_md)


def _remove_claude_md_symlink(root: Path) -> None:
    """Remove CLAUDE.md symlink."""
    claude_md = root / "CLAUDE.md"
    if claude_md.is_symlink():
        claude_md.unlink()
    elif claude_md.exists():
        claude_md.unlink()


def _write_minimal_repo_symlink(root: Path) -> None:
    """Minimal repo set up for symlink-based governance (post-#86).

    Calls _write_minimal_repo then ensures both tracked symlink surfaces exist.
    """
    _write_minimal_repo(root)
    _remove_skill_symlink(root)
    _write_skill_symlink(root)
    claude_md = root / "CLAUDE.md"
    if claude_md.exists() and not claude_md.is_symlink():
        claude_md.unlink()
    _write_claude_md_symlink(root)


# ── #86 RED: symlink audit tests (skill_ownership.py) ────────────────────────


def test_skill_ownership_rejects_missing_claude_symlink(
    tmp_path: Path,
) -> None:
    """When .claude/skills symlink is missing, validate_ownerships must error."""
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo_symlink(tmp_path)
    _remove_skill_symlink(tmp_path)

    errors = validate_ownerships(tmp_path)

    assert any(
        ".claude/skills must be a Symlink to .agents/skills when tools includes claude-code"
        in error
        for error in errors
    )


def test_skill_ownership_rejects_missing_claude_md_symlink(
    tmp_path: Path,
) -> None:
    """When CLAUDE.md symlink is missing, validate_ownerships must error."""
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo_symlink(tmp_path)
    _remove_claude_md_symlink(tmp_path)

    errors = validate_ownerships(tmp_path)

    assert any(
        "CLAUDE.md must be a Symlink to AGENTS.md" in error
        for error in errors
    )


def test_skill_ownership_symlink_skipped_on_non_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symlink checks are platform-gated: non-Windows skips them.

    We mock the platform guard at the function level rather than patching
    ``os.name`` globally (which breaks pathlib on Windows).
    """
    from scripts.research.governance import skill_ownership as mod

    _write_minimal_repo_symlink(tmp_path)
    _remove_skill_symlink(tmp_path)
    _remove_claude_md_symlink(tmp_path)

    # Simulate non-Windows: the guard function returns True (valid) regardless
    monkeypatch.setattr(mod, "_is_expected_skills_symlink", lambda _root: True)
    monkeypatch.setattr(mod, "_is_expected_claude_md_symlink", lambda _root: True)

    errors = mod.validate_ownerships(tmp_path)

    assert not any(
        "must be a Symlink" in error for error in errors
    )


def test_skill_ownership_symlink_passes(
    tmp_path: Path,
) -> None:
    """When both symlinks are valid, validate_ownerships must pass for symlink checks."""
    from scripts.research.governance.skill_ownership import validate_ownerships

    _write_minimal_repo_symlink(tmp_path)

    errors = validate_ownerships(tmp_path)

    assert not any(
        "must be a Symlink" in error for error in errors
    )


# ── #86 RED: governance audit tests (rules.py) ───────────────────────────────


def test_governance_audit_requires_core_symlinks_in_setup_ps1(
    tmp_path: Path,
) -> None:
    """setup-python.ps1 must include git config core.symlinks true."""
    _write_minimal_repo_symlink(tmp_path)
    text = (tmp_path / ".githooks/setup-python.ps1").read_text(encoding="utf-8")
    text = text.replace("git config core.symlinks true", "")
    (tmp_path / ".githooks/setup-python.ps1").write_text(text, encoding="utf-8")

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "setup-python.ps1 missing git config core.symlinks true" in finding.message
        for finding in report.findings
    )


def test_governance_audit_requires_core_symlinks_in_setup_sh(
    tmp_path: Path,
) -> None:
    """setup-python.sh must include git config core.symlinks true."""
    _write_minimal_repo_symlink(tmp_path)
    text = (tmp_path / ".githooks/setup-python.sh").read_text(encoding="utf-8")
    text = text.replace("git config core.symlinks true", "")
    (tmp_path / ".githooks/setup-python.sh").write_text(text, encoding="utf-8")

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "setup-python.sh missing git config core.symlinks true" in finding.message
        for finding in report.findings
    )


def test_governance_audit_requires_core_symlinks_in_environment_toml(
    tmp_path: Path,
) -> None:
    """environment.toml must include git config core.symlinks true."""
    _write_minimal_repo_symlink(tmp_path)
    (tmp_path / ".codex/environments/environment.toml").write_text(
        ".\\.githooks\\setup-python.ps1\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not report.ok
    assert any(
        finding.rule_id == "governance_gate"
        and "environment.toml missing git config core.symlinks true" in finding.message
        for finding in report.findings
    )


def test_governance_audit_ci_symlink_setup_is_ok(
    tmp_path: Path,
) -> None:
    """CI workflow must accept the symlink setup model (post-#86)."""
    _write_minimal_repo_symlink(tmp_path)

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not any(
        finding.rule_id == "governance_gate" and "CI workflow" in finding.message
        for finding in report.findings
    )


def test_governance_audit_setup_ps1_symlink_config_is_ok(
    tmp_path: Path,
) -> None:
    """setup-python.ps1 must accept the symlink setup model (post-#86)."""
    _write_minimal_repo_symlink(tmp_path)

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert not any(
        finding.rule_id == "governance_gate"
        and "setup-python.ps1" in finding.message
        for finding in report.findings
    )


def test_governance_audit_passes_symlink_repo(
    tmp_path: Path,
) -> None:
    """Full governance audit passes with symlink-based repo (post-#86)."""
    _write_minimal_repo_symlink(tmp_path)

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]


# ── #93 RED: ADR source issue reference tests ────────────────────────────────


@pytest.mark.parametrize(
    "adr_path,expected_token",
    [
        ("docs/adr/0007-pr-flow-closed-loop-review-evidence.md", "https://github.com/liuli195/Quant-Trading/issues/54"),
        ("docs/adr/0007-pr-flow-closed-loop-review-evidence.md", "https://github.com/liuli195/Quant-Trading/issues/65"),
        ("docs/adr/0008-skill-single-source-agents.md", "https://github.com/liuli195/Quant-Trading/issues/44"),
    ],
)
def test_adr_references_source_issue(
    adr_path: str,
    expected_token: str,
) -> None:
    """Each ADR that originated from a P1/P2 PRD must cite its source Issue URL."""
    path = Path(adr_path)
    text = path.read_text(encoding="utf-8")

    assert expected_token in text, f"{adr_path} missing {expected_token}"


def test_agents_md_contains_adr_drop_rule() -> None:
    """AGENTS.md must include a concise ADR drop rule in the 工作边界 section."""
    text = Path("AGENTS.md").read_text(encoding="utf-8")

    relevant = text.split("### 工作边界", 1)
    assert len(relevant) == 2, "AGENTS.md missing 工作边界 section"

    section = relevant[1]  # Everything after 工作边界 up to the next ### heading
    next_section = section.find("\n### ")
    if next_section != -1:
        section = section[:next_section]

    assert (
        "ADR" in section
    ), "AGENTS.md 工作边界 missing ADR 落盘 rule"
