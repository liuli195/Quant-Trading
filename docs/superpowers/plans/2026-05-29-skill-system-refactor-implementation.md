# Skill System Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有仓库 Skill 收敛为 10 个 Codex owner Skill、同名 Claude adapter、结构化 ownership 索引和可验证的自然语言发现闭环。

**Architecture:** 以 `.codex/skills/<owner>/references/ownership.yaml` 作为机器可读 SSOT；`docs/rules/skills.md` 只做人类规则汇总；Claude 侧只保留同名 adapter，不维护第二套规则。治理入口读取 ownership 索引，校验 owner 唯一性、adapter 等价性、推荐命令有效性和自然语言触发样例。

**Tech Stack:** Python 3.12, PyYAML, pytest, existing `scripts.research.governance`, `scripts.tools.path_tools.refactor`, `scripts.research.docs index`, Codex Skill directory, Claude Skill directory.

---

## Design Inputs

- 主方案：[skill-system-refactor.md](../../design/skill-system-refactor.md) <!-- pathref: docs/design/skill-system-refactor.md -->
- 前置跨工具边界：[cross-ai-skill-management.md](../../design/cross-ai-skill-management.md) <!-- pathref: docs/design/cross-ai-skill-management.md -->
- 通用入口：[AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->
- Claude 入口：[CLAUDE.md](../../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->
- 治理规则：[governance.md](../../rules/governance.md) <!-- pathref: docs/rules/governance.md -->
- pathref 规则：[docs-and-pathref.md](../../rules/docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->

## Tracer Bullet Rules

每个切片都必须是一条端到端薄路径：

| 层 | 本计划中的含义 | 每片必须交付 |
| --- | --- | --- |
| 架构 | ownership SSOT、owner 边界、依赖关系 | `ownership.yaml` 字段完整且 owner 唯一 |
| API | Python loader / validator / discover 接口 | 测试能调用 `scripts.research.governance.skill_ownership` |
| 界面 | Agent 可见 Skill、Claude adapter、CLI / gate 输出 | 自然语言请求能命中 owner Skill 并显示推荐命令 |
| 测试 | 单测、治理门禁、pathref、docs index | 每片有可单独运行的验证命令 |

AFK 表示实现过程不需要新的人工判断；实际进入主干仍按 PR 规则执行。HITL 表示该切片必须先有人确认边界或删除策略。

## Slice Tracker

- [ ] S01 [AFK] 建立 `skill-system` pilot 和 ownership validator。
- [ ] S02 [AFK] 迁移 `repo-python-env`，验证 Python 环境请求可发现。
- [ ] S03 [AFK] 迁移 `repo-docs-pathref`，验证文档/pathref 请求可发现。
- [ ] S04 [AFK] 迁移 `repo-pr-governance`，验证 PR 治理请求可发现。
- [ ] S05 [AFK] 迁移 `research-local-first`，验证本地优先研究请求可发现。
- [ ] S06 [AFK] 迁移 `research-data-center`，验证数据快照/run 导入请求可发现。
- [ ] S07 [AFK] 迁移 `research-report-analysis`，验证报告分析请求可发现。
- [ ] S08 [AFK] 迁移 `strategy-experiment`，验证参数扫描和 A/B 请求可发现。
- [ ] S09 [AFK] 迁移 `joinquant-strategy-fix`，验证云端编译错误修复请求可发现。
- [ ] S10 [AFK] 迁移 `joinquant-cloud-run`，验证云端运行请求可发现且保留确认门槛。
- [ ] S11 [AFK] 全量治理闭环：adapter 等价性、owner 唯一性、命令有效性、触发样例。
- [ ] S12 [HITL] 人工确认旧 Skill 兼容入口删除窗口。
- [ ] S13 [AFK] 删除旧 `.claude/skills/jq-*` / `agent-doc-*` 和旧 `.codex/skills/quant-*` 兼容入口。
- [ ] S14 [AFK] 刷新文档索引并完成最终门禁。

## File Structure

**Create: `scripts/research/governance/skill_ownership.py`**

职责：
- 读取 `.codex/skills/*/references/ownership.yaml`。
- 校验 owner Skill 目录、Claude adapter、字段完整性、唯一 ownership 和触发语义。
- 提供 `discover` CLI，便于用自然语言样例演示命中结果。

**Modify: `scripts/research/governance/rules.py`**

职责：
- 在 `run_audit()` 中调用 skill ownership 校验。
- 将发现的问题渲染成现有 `AuditFinding`。

**Modify: `scripts/research/governance/tests/test_governance.py`**

职责：
- 覆盖 ownership loader、重复 owner、adapter 不等价、触发短语冲突、治理 gate 集成。

**Create: `docs/rules/skills.md`**

职责：
- 人类可读 Skill 规则汇总。
- 只解释 owner / adapter / discovery 规则，不重复 ownership 明细。

**Create per owner: `.codex/skills/<skill>/...`**

标准结构：

```text
.codex/skills/<skill>/
  SKILL.md
  agents/openai.yaml
  references/ownership.yaml
  references/workflow.md
  references/commands.md
  templates/
```

**Create per adapter: `.claude/skills/<same-skill-name>/SKILL.md`**

职责：
- 指向对应 Codex owner Skill。
- 保留等价 description、必读规则、推荐命令和失败处理。
- 不声明第二 owner，不复制规则正文和脚本实现。

## Owner Map

| Owner Skill | Group | 迁移来源 | 首条演示请求 |
| --- | --- | --- | --- |
| `skill-system` | Skill System | `agent-doc-add`、`agent-doc-refactor` 中的 Skill/入口治理方法 | 新增或修改一个 owner Skill，并同步 Claude adapter。 |
| `repo-python-env` | Repo Governance | `docs/rules/commands.md`、`docs/rules/environments.md`、现有 `.venv` 规则 | 这个仓库本地 Python 应该怎么跑？ |
| `repo-docs-pathref` | Repo Governance | pathref、docs index、报告 index 规则 | 我移动了文档和报告链接，怎么检查 pathref 和索引？ |
| `repo-pr-governance` | Repo Governance | `quant-pr-workflow`、PR/review/governance 规则 | 准备一个进入主干的 PR，确认 review 证据和 required checks。 |
| `research-local-first` | Strategy Research | `jq-research` 本地候选漏斗 | 先本地筛选研究候选，别直接消耗 JoinQuant 云端额度。 |
| `research-data-center` | Strategy Research | 数据快照、run 导入、catalog 规则 | 把历史回测 run 做成可追溯数据快照。 |
| `research-report-analysis` | Strategy Research | `jq-analyze`、报告模板和报告索引 | 补齐回测报告并对比多个 run 的收益和回撤。 |
| `strategy-experiment` | Strategy Research | `jq-param-scan`、`jq-ab-test`、variant registry | 做一个策略参数 A/B 实验，保留控制变量和 delta 归因。 |
| `joinquant-strategy-fix` | JoinQuant Automation | `jq-fix` | JoinQuant 云端策略编译报错，帮我本地定位兼容问题。 |
| `joinquant-cloud-run` | JoinQuant Automation | `jq-run` 云端执行 | 上传策略到 JoinQuant 跑云端回测并抓结果，但注意配额。 |

## Task S01 [AFK]: `skill-system` Pilot And Validator

**Demo:** `discover "新增或修改一个 owner Skill，并同步 Claude adapter。"` 输出 `skill-system`、必读 `docs/rules/skills.md`、推荐 Skill 校验命令。

**Files:**
- Create: `scripts/research/governance/skill_ownership.py`
- Modify: `scripts/research/governance/rules.py`
- Modify: `scripts/research/governance/tests/test_governance.py`
- Create: `docs/rules/skills.md`
- Create: `.codex/skills/skill-system/SKILL.md`
- Create: `.codex/skills/skill-system/agents/openai.yaml`
- Create: `.codex/skills/skill-system/references/ownership.yaml`
- Create: `.codex/skills/skill-system/references/workflow.md`
- Create: `.codex/skills/skill-system/references/commands.md`
- Create: `.claude/skills/skill-system/SKILL.md`

- [ ] **Step 1: 写失败测试，证明自然语言能命中 pilot owner**

在 `scripts/research/governance/tests/test_governance.py` 增加：

```python
def test_skill_ownership_discovers_skill_system_owner(tmp_path: Path) -> None:
    skill_root = tmp_path / ".codex" / "skills" / "skill-system" / "references"
    skill_root.mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "skill-system").mkdir(parents=True)
    (tmp_path / ".codex" / "skills" / "skill-system" / "SKILL.md").write_text(
        "---\n"
        "name: skill-system\n"
        "description: 创建、修改、验证 owner Skill 与 Claude adapter。\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "skills" / "skill-system" / "SKILL.md").write_text(
        "---\n"
        "name: skill-system\n"
        "description: 创建、修改、验证 owner Skill 与 Claude adapter。\n"
        "---\n",
        encoding="utf-8",
    )
    (skill_root / "ownership.yaml").write_text(
        "skill: skill-system\n"
        "group: Skill System\n"
        "owned_rules:\n"
        "  - docs/rules/skills.md\n"
        "owned_commands:\n"
        "  - scripts.research.governance.skill_ownership\n"
        "owned_scripts:\n"
        "  - scripts/research/governance/skill_ownership.py\n"
        "uses: []\n"
        "adapters:\n"
        "  - .claude/skills/skill-system/SKILL.md\n"
        "trigger_phrases:\n"
        "  - 新增或修改一个 owner Skill\n"
        "read_rules:\n"
        "  - docs/rules/skills.md\n"
        "recommended_commands:\n"
        "  - .\\.venv\\Scripts\\python.exe -m scripts.research.governance.skill_ownership check\n"
        "status: active\n",
        encoding="utf-8",
    )

    from scripts.research.governance.skill_ownership import discover_owner

    result = discover_owner(tmp_path, "新增或修改一个 owner Skill，并同步 Claude adapter。")

    assert [match.skill for match in result.matches] == ["skill-system"]
    assert result.matches[0].read_rules == ("docs/rules/skills.md",)
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py::test_skill_ownership_discovers_skill_system_owner -q
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.research.governance.skill_ownership`.

- [ ] **Step 2: 增加 ownership API**

在 `scripts/research/governance/skill_ownership.py` 写入：

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


REQUIRED_OWNER_SKILLS = (
    "skill-system",
    "repo-python-env",
    "repo-docs-pathref",
    "repo-pr-governance",
    "research-local-first",
    "research-data-center",
    "research-report-analysis",
    "strategy-experiment",
    "joinquant-strategy-fix",
    "joinquant-cloud-run",
)


@dataclass(frozen=True)
class SkillOwnership:
    skill: str
    group: str
    owned_rules: tuple[str, ...]
    owned_commands: tuple[str, ...]
    owned_scripts: tuple[str, ...]
    uses: tuple[str, ...]
    adapters: tuple[str, ...]
    trigger_phrases: tuple[str, ...]
    read_rules: tuple[str, ...]
    recommended_commands: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class DiscoveryResult:
    query: str
    matches: tuple[SkillOwnership, ...]


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    return (str(value),)


def load_ownerships(repo_root: str | Path = ".") -> tuple[SkillOwnership, ...]:
    root = Path(repo_root)
    ownerships: list[SkillOwnership] = []
    for path in sorted((root / ".codex" / "skills").glob("*/references/ownership.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        ownerships.append(
            SkillOwnership(
                skill=str(data["skill"]),
                group=str(data["group"]),
                owned_rules=_tuple(data.get("owned_rules")),
                owned_commands=_tuple(data.get("owned_commands")),
                owned_scripts=_tuple(data.get("owned_scripts")),
                uses=_tuple(data.get("uses")),
                adapters=_tuple(data.get("adapters")),
                trigger_phrases=_tuple(data.get("trigger_phrases")),
                read_rules=_tuple(data.get("read_rules")),
                recommended_commands=_tuple(data.get("recommended_commands")),
                status=str(data.get("status", "active")),
            )
        )
    return tuple(ownerships)


def discover_owner(repo_root: str | Path, query: str) -> DiscoveryResult:
    normalized = query.lower()
    matches = []
    for ownership in load_ownerships(repo_root):
        phrases = [ownership.skill, *ownership.trigger_phrases]
        if any(phrase.lower() in normalized or normalized in phrase.lower() for phrase in phrases):
            matches.append(ownership)
    return DiscoveryResult(query=query, matches=tuple(matches))


def validate_ownerships(repo_root: str | Path = ".") -> list[str]:
    root = Path(repo_root)
    errors: list[str] = []
    ownerships = load_ownerships(root)
    by_skill = {item.skill: item for item in ownerships}
    for skill in REQUIRED_OWNER_SKILLS:
        if skill not in by_skill:
            errors.append(f"missing owner skill: {skill}")
            continue
        if not (root / ".codex" / "skills" / skill / "SKILL.md").exists():
            errors.append(f"missing Codex owner SKILL.md: {skill}")
    seen: dict[tuple[str, str], str] = {}
    for ownership in ownerships:
        for field_name in ("owned_rules", "owned_commands", "owned_scripts"):
            for value in getattr(ownership, field_name):
                key = (field_name, value)
                if key in seen:
                    errors.append(f"duplicate {field_name} owner for {value}: {seen[key]} and {ownership.skill}")
                else:
                    seen[key] = ownership.skill
        for adapter in ownership.adapters:
            if not (root / adapter).exists():
                errors.append(f"missing adapter for {ownership.skill}: {adapter}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("query")
    args = parser.parse_args(argv)
    if args.command == "check":
        errors = validate_ownerships(Path.cwd())
        for error in errors:
            print(error)
        return 1 if errors else 0
    result = discover_owner(Path.cwd(), args.query)
    for match in result.matches:
        print(match.skill)
        print("read_rules=" + ",".join(match.read_rules))
        print("recommended_commands=" + ",".join(match.recommended_commands))
    return 0 if len(result.matches) == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 建立 `skill-system` owner 和 Claude adapter**

`.codex/skills/skill-system/SKILL.md` frontmatter:

```markdown
---
name: skill-system
description: 创建、修改、验证 Codex owner Skill、Claude adapter、触发语义、ownership 索引和 Skill 发现治理时使用。
---
```

`.codex/skills/skill-system/references/ownership.yaml`:

```yaml
skill: skill-system
group: Skill System
owned_rules:
  - docs/rules/skills.md
owned_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
  - .\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover
owned_scripts:
  - scripts/research/governance/skill_ownership.py
uses:
  - repo-docs-pathref
  - repo-pr-governance
adapters:
  - .claude/skills/skill-system/SKILL.md
trigger_phrases:
  - 新增或修改一个 owner Skill
  - 同步 Claude adapter
  - 优化 Skill description
  - 校验 Skill 发现
read_rules:
  - docs/rules/skills.md
  - docs/rules/governance.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
  - .\.venv\Scripts\python.exe -m scripts.research.governance gate
status: active
```

`.claude/skills/skill-system/SKILL.md` frontmatter:

```markdown
---
name: skill-system
description: 创建、修改、验证 Codex owner Skill、Claude adapter、触发语义、ownership 索引和 Skill 发现治理时使用。
---
```

- [ ] **Step 4: 接入治理 gate**

在 `scripts/research/governance/rules.py` 中导入：

```python
from scripts.research.governance.skill_ownership import validate_ownerships
```

在 `run_audit()` 的规则检查区追加：

```python
for message in validate_ownerships(root):
    findings.append(
        AuditFinding(
            rule_id="skill_ownership",
            severity="error",
            path=".",
            message=message,
        )
    )
```

- [ ] **Step 5: 验证 pilot 闭环**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py::test_skill_ownership_discovers_skill_system_owner -q
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "新增或修改一个 owner Skill，并同步 Claude adapter。"
```

Expected:

```text
skill-system
read_rules=docs/rules/skills.md,docs/rules/governance.md
recommended_commands=.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check,.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

## Task S02 [AFK]: `repo-python-env`

**Demo:** `discover "这个仓库本地 Python 应该怎么跑，为什么不能用系统 Python？"` 输出 `repo-python-env`。

**Files:**
- Create: `.codex/skills/repo-python-env/SKILL.md`
- Create: `.codex/skills/repo-python-env/agents/openai.yaml`
- Create: `.codex/skills/repo-python-env/references/ownership.yaml`
- Create: `.codex/skills/repo-python-env/references/workflow.md`
- Create: `.codex/skills/repo-python-env/references/commands.md`
- Create: `.claude/skills/repo-python-env/SKILL.md`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

Test query:

```python
result = discover_owner(repo_root, "这个仓库本地 Python 应该怎么跑，为什么不能用系统 Python？")
assert [match.skill for match in result.matches] == ["repo-python-env"]
assert "docs/rules/commands.md" in result.matches[0].read_rules
assert any(".venv" in command for command in result.matches[0].recommended_commands)
```

- [ ] **Step 2: 写 owner ownership**

```yaml
skill: repo-python-env
group: Repo Governance
owned_rules:
  - docs/rules/commands.md#python-env
  - docs/rules/environments.md#local-cloud-boundary
owned_commands:
  - .\.venv\Scripts\python.exe
  - .venv/bin/python
  - .\.githooks\setup-python.ps1
  - .githooks/setup-python.sh
owned_scripts:
  - .githooks/setup-python.ps1
  - .githooks/setup-python.sh
uses: []
adapters:
  - .claude/skills/repo-python-env/SKILL.md
trigger_phrases:
  - 本地 Python 应该怎么跑
  - 不能用系统 Python
  - 项目 .venv
  - PYTHONUTF8
read_rules:
  - docs/rules/commands.md
  - docs/rules/environments.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m pytest
  - .\.venv\Scripts\python.exe -m scripts.research.governance gate
status: active
```

- [ ] **Step 3: 写最小可用界面**

`SKILL.md` 只保留触发语义、必读规则、推荐命令和边界：

```markdown
# Repo Python Env

本技能负责本仓库 Python 环境、项目 `.venv`、UTF-8 环境变量、本地/云端运行边界和跨平台 wrapper 入口。

## 必读规则

- `docs/rules/commands.md`
- `docs/rules/environments.md`

## 执行规则

- 默认使用项目 `.venv`，不改用系统 Python。
- 策略代码只在 JoinQuant 云端运行；本地只做编写、测试、文档和回测分析。
- 声明环境已配置前，先运行实际命令验证。
```

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "这个仓库本地 Python 应该怎么跑，为什么不能用系统 Python？"
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py -q
```

Expected: exactly one match, `repo-python-env`.

## Task S03 [AFK]: `repo-docs-pathref`

**Demo:** `discover "我移动了文档和报告链接，怎么检查 pathref 和索引？"` 输出 `repo-docs-pathref`。

**Files:**
- Create owner and adapter under `.codex/skills/repo-docs-pathref/` and `.claude/skills/repo-docs-pathref/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "我移动了文档和报告链接，怎么检查 pathref 和索引？")
assert [match.skill for match in result.matches] == ["repo-docs-pathref"]
assert "docs/rules/docs-and-pathref.md" in result.matches[0].read_rules
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: repo-docs-pathref
group: Repo Governance
owned_rules:
  - docs/rules/docs-and-pathref.md
owned_commands:
  - .\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
  - .\.venv\Scripts\python.exe -m scripts.research.docs index
owned_scripts:
  - scripts/tools/path_tools/refactor.py
  - scripts/research/platform/docs_index.py
uses: []
adapters:
  - .claude/skills/repo-docs-pathref/SKILL.md
trigger_phrases:
  - 检查 pathref
  - 文档索引
  - 报告索引
  - 移动了文档和报告链接
read_rules:
  - docs/rules/docs-and-pathref.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
  - .\.venv\Scripts\python.exe -m scripts.research.docs index
status: active
```

- [ ] **Step 3: 写界面文档**

`SKILL.md` 说明只处理 Markdown/pathref/catalog，不处理 PR review 或研究结论。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "我移动了文档和报告链接，怎么检查 pathref 和索引？"
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: exactly one match, `repo-docs-pathref`; pathref check passes.

## Task S04 [AFK]: `repo-pr-governance`

**Demo:** `discover "准备一个进入主干的 PR，确认 review 证据和 required checks。"` 输出 `repo-pr-governance`。

**Files:**
- Create owner and adapter under `.codex/skills/repo-pr-governance/` and `.claude/skills/repo-pr-governance/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "准备一个进入主干的 PR，确认 review 证据和 required checks。")
assert [match.skill for match in result.matches] == ["repo-pr-governance"]
assert "docs/rules/pr-workflow.md" in result.matches[0].read_rules
assert "make pr-ready" in " ".join(result.matches[0].recommended_commands)
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: repo-pr-governance
group: Repo Governance
owned_rules:
  - docs/rules/pr-workflow.md
  - docs/rules/review-guidelines.md
  - docs/rules/governance.md#pr
owned_commands:
  - make pr-ready
  - make ai-review
  - make risk-check
  - .\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow
owned_scripts:
  - scripts/research/governance/pr_flow.py
  - scripts/research/governance/pr_review_evidence.py
  - scripts/research/governance/codex_review_monitor.py
uses:
  - repo-docs-pathref
adapters:
  - .claude/skills/repo-pr-governance/SKILL.md
trigger_phrases:
  - 准备一个进入主干的 PR
  - review 证据
  - required checks
  - Codex review
  - 主干保护
read_rules:
  - docs/rules/pr-workflow.md
  - docs/rules/review-guidelines.md
  - docs/rules/governance.md
recommended_commands:
  - make pr-ready TITLE="<PR标题>"
  - make ai-review
  - make risk-check
status: active
```

- [ ] **Step 3: 写界面文档**

`SKILL.md` 明确：

```markdown
- 不把功能分支本地合入 `main`。
- 不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review。
- `gh` CLI 默认按仓库规则提权执行。
```

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "准备一个进入主干的 PR，确认 review 证据和 required checks。"
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py -q
```

Expected: exactly one match, `repo-pr-governance`; PR flow tests pass.

## Task S05 [AFK]: `research-local-first`

**Demo:** `discover "先本地筛选研究候选，别直接消耗 JoinQuant 云端额度。"` 输出 `research-local-first`。

**Files:**
- Create owner and adapter under `.codex/skills/research-local-first/` and `.claude/skills/research-local-first/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "先本地筛选研究候选，别直接消耗 JoinQuant 云端额度。")
assert [match.skill for match in result.matches] == ["research-local-first"]
assert "docs/rules/research-workflow.md" in result.matches[0].read_rules
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: research-local-first
group: Strategy Research
owned_rules:
  - docs/rules/research-workflow.md#local-first
owned_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.cli
owned_scripts:
  - scripts/research/cli.py
  - scripts/research/workflows
uses:
  - research-data-center
  - research-report-analysis
  - strategy-experiment
adapters:
  - .claude/skills/research-local-first/SKILL.md
trigger_phrases:
  - 本地优先研究
  - 本地筛选研究候选
  - 别直接消耗 JoinQuant 云端额度
  - 候选漏斗
read_rules:
  - docs/rules/research-workflow.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.cli
  - .\.venv\Scripts\python.exe -m scripts.research.governance gate
status: active
```

- [ ] **Step 3: 写界面文档**

从旧 `jq-research` 迁移本地优先、候选漏斗、云端交接边界；不复制旧 Skill 的长规则正文。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "先本地筛选研究候选，别直接消耗 JoinQuant 云端额度。"
.\.venv\Scripts\python.exe -m scripts.research.cli --help
```

Expected: exactly one match, `research-local-first`; CLI help exits 0.

## Task S06 [AFK]: `research-data-center`

**Demo:** `discover "把历史回测 run 做成可追溯数据快照。"` 输出 `research-data-center`。

**Files:**
- Create owner and adapter under `.codex/skills/research-data-center/` and `.claude/skills/research-data-center/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "把历史回测 run 做成可追溯数据快照。")
assert [match.skill for match in result.matches] == ["research-data-center"]
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: research-data-center
group: Strategy Research
owned_rules:
  - docs/rules/research-workflow.md#data-center
owned_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.datasets
owned_scripts:
  - scripts/research/platform/datasets.py
  - research_datasets
uses:
  - repo-docs-pathref
adapters:
  - .claude/skills/research-data-center/SKILL.md
trigger_phrases:
  - 历史回测 run
  - 可追溯数据快照
  - 数据中心
  - catalog
read_rules:
  - docs/rules/research-workflow.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.datasets
  - .\.venv\Scripts\python.exe -m scripts.research.docs index
status: active
```

- [ ] **Step 3: 写界面文档**

边界写清：不把本地 replay 包装成云端确认；数据快照和 catalog 必须可追溯。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "把历史回测 run 做成可追溯数据快照。"
.\.venv\Scripts\python.exe -m scripts.research.datasets --help
```

Expected: exactly one match, `research-data-center`; datasets CLI help exits 0.

## Task S07 [AFK]: `research-report-analysis`

**Demo:** `discover "补齐回测报告并对比多个 run 的收益和回撤。"` 输出 `research-report-analysis`。

**Files:**
- Create owner and adapter under `.codex/skills/research-report-analysis/` and `.claude/skills/research-report-analysis/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "补齐回测报告并对比多个 run 的收益和回撤。")
assert [match.skill for match in result.matches] == ["research-report-analysis"]
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: research-report-analysis
group: Strategy Research
owned_rules:
  - docs/rules/research-workflow.md#reports
owned_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.docs index
owned_scripts:
  - scripts/research/platform/reporting.py
uses:
  - research-data-center
  - repo-docs-pathref
adapters:
  - .claude/skills/research-report-analysis/SKILL.md
trigger_phrases:
  - 补齐回测报告
  - 对比多个 run
  - 收益和回撤
  - fix-missing
read_rules:
  - docs/rules/research-workflow.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.docs index
status: active
```

- [ ] **Step 3: 写界面文档**

从旧 `jq-analyze` 迁移本地分析、缺失报告补全、趋势和跨策略对比触发语义。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "补齐回测报告并对比多个 run 的收益和回撤。"
.\.venv\Scripts\python.exe -m scripts.research.docs index
```

Expected: exactly one match, `research-report-analysis`; docs index exits 0.

## Task S08 [AFK]: `strategy-experiment`

**Demo:** `discover "做一个策略参数 A/B 实验，保留控制变量和 delta 归因。"` 输出 `strategy-experiment`。

**Files:**
- Create owner and adapter under `.codex/skills/strategy-experiment/` and `.claude/skills/strategy-experiment/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "做一个策略参数 A/B 实验，保留控制变量和 delta 归因。")
assert [match.skill for match in result.matches] == ["strategy-experiment"]
assert any("scripts.research.variants" in command for command in result.matches[0].recommended_commands)
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: strategy-experiment
group: Strategy Research
owned_rules:
  - docs/rules/research-workflow.md#experiments
owned_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.variants
  - jq-auto ab expand
  - jq-auto ab report
owned_scripts:
  - scripts/research/platform/strategy_variants.py
  - scripts/tools/jq_automation/abtest.py
uses:
  - research-local-first
  - research-report-analysis
  - joinquant-cloud-run
adapters:
  - .claude/skills/strategy-experiment/SKILL.md
trigger_phrases:
  - 策略参数 A/B 实验
  - 参数扫描
  - 控制变量
  - delta 归因
  - variant registry
read_rules:
  - docs/rules/research-workflow.md
recommended_commands:
  - .\.venv\Scripts\python.exe -m scripts.research.variants
  - .\.venv\Scripts\python.exe -m scripts.research.governance gate
status: active
```

- [ ] **Step 3: 写界面文档**

从旧 `jq-param-scan` 和 `jq-ab-test` 迁移：执行前展示计划、云端额度确认、参数变体不默认开 Git 分支、不自动修改默认参数。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "做一个策略参数 A/B 实验，保留控制变量和 delta 归因。"
.\.venv\Scripts\python.exe -m scripts.research.variants --help
```

Expected: exactly one match, `strategy-experiment`; variants CLI help exits 0.

## Task S09 [AFK]: `joinquant-strategy-fix`

**Demo:** `discover "JoinQuant 云端策略编译报错，帮我本地定位兼容问题。"` 输出 `joinquant-strategy-fix`。

**Files:**
- Create owner and adapter under `.codex/skills/joinquant-strategy-fix/` and `.claude/skills/joinquant-strategy-fix/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "JoinQuant 云端策略编译报错，帮我本地定位兼容问题。")
assert [match.skill for match in result.matches] == ["joinquant-strategy-fix"]
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: joinquant-strategy-fix
group: JoinQuant Automation
owned_rules:
  - docs/rules/environments.md#joinquant
  - docs/rules/code-style.md
owned_commands:
  - jq-auto compile-check
  - .\.venv\Scripts\python.exe -m py_compile
owned_scripts:
  - scripts/tools/jq_automation
uses:
  - repo-python-env
adapters:
  - .claude/skills/joinquant-strategy-fix/SKILL.md
trigger_phrases:
  - JoinQuant 云端策略编译报错
  - 本地定位兼容问题
  - compile-check
  - 策略本地修复
read_rules:
  - docs/rules/environments.md
  - docs/rules/code-style.md
recommended_commands:
  - jq-auto compile-check <策略文件>
  - .\.venv\Scripts\python.exe -m py_compile <策略文件>
status: active
```

- [ ] **Step 3: 写界面文档**

从旧 `jq-fix` 迁移边界：只做本地修复，不上传策略，不启动云端回测；需要云端复验时建议最小 `joinquant-cloud-run` 场景。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "JoinQuant 云端策略编译报错，帮我本地定位兼容问题。"
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation --help
```

Expected: exactly one match, `joinquant-strategy-fix`; jq automation help exits 0.

## Task S10 [AFK]: `joinquant-cloud-run`

**Demo:** `discover "上传策略到 JoinQuant 跑云端回测并抓结果，但注意配额。"` 输出 `joinquant-cloud-run`。

**Files:**
- Create owner and adapter under `.codex/skills/joinquant-cloud-run/` and `.claude/skills/joinquant-cloud-run/`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 加发现测试**

```python
result = discover_owner(repo_root, "上传策略到 JoinQuant 跑云端回测并抓结果，但注意配额。")
assert [match.skill for match in result.matches] == ["joinquant-cloud-run"]
assert "docs/rules/environments.md" in result.matches[0].read_rules
```

- [ ] **Step 2: 写 ownership**

```yaml
skill: joinquant-cloud-run
group: JoinQuant Automation
owned_rules:
  - docs/rules/environments.md#joinquant
  - docs/rules/research-workflow.md#cloud-handoff
owned_commands:
  - jq-auto upload
  - jq-auto run
  - jq-auto fetch
  - jq-auto batch
owned_scripts:
  - scripts/tools/jq_automation
uses:
  - joinquant-strategy-fix
  - research-data-center
  - research-report-analysis
adapters:
  - .claude/skills/joinquant-cloud-run/SKILL.md
trigger_phrases:
  - 上传策略到 JoinQuant
  - 跑云端回测
  - 抓取云端结果
  - 注意配额
read_rules:
  - docs/rules/environments.md
  - docs/rules/research-workflow.md
recommended_commands:
  - jq-auto run <场景配置.json> --yes
  - jq-auto fetch <回测URL或ID> --strategy <策略名>
status: active
```

- [ ] **Step 3: 写界面文档**

从旧 `jq-run` 迁移云端执行流程，并保留人工确认门槛：正式 run/batch 前必须展示计划；`--yes` 表示确认已完成。

- [ ] **Step 4: 验证本片**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership discover "上传策略到 JoinQuant 跑云端回测并抓结果，但注意配额。"
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation --help
```

Expected: exactly one match, `joinquant-cloud-run`; jq automation help exits 0.

## Task S11 [AFK]: Full Governance Closure

**Demo:** `governance gate` 同时覆盖 owner 存在、adapter 等价、触发短语唯一、推荐命令不漂移。

**Files:**
- Modify: `scripts/research/governance/skill_ownership.py`
- Modify: `scripts/research/governance/tests/test_governance.py`
- Modify: `scripts/research/governance/rules.py`

- [ ] **Step 1: 加重复 owner 测试**

```python
def test_skill_ownership_rejects_duplicate_owned_rule(repo_root: Path) -> None:
    errors = validate_ownerships(repo_root)
    assert not any("duplicate owned_rules owner" in error for error in errors)
```

在一个单独 tmp repo case 中故意让两个 Skill 都拥有 `docs/rules/commands.md`，断言报错包含：

```text
duplicate owned_rules owner for docs/rules/commands.md
```

- [ ] **Step 2: 加 adapter 等价测试**

检查每个 adapter：

```python
assert adapter_frontmatter["name"] == owner_frontmatter["name"]
assert owner_frontmatter["description"] in adapter_frontmatter["description"] or adapter_frontmatter["description"] in owner_frontmatter["description"]
```

失败信息包含 adapter 路径，便于直接修复。

- [ ] **Step 3: 加触发短语冲突测试**

对所有 `trigger_phrases` 建立标准化索引；同一短语不能属于两个 active owner。失败信息：

```text
duplicate trigger phrase "<phrase>": <skill_a> and <skill_b>
```

- [ ] **Step 4: 加推荐命令有效性检查**

先实现轻量检查：

```python
VALID_COMMAND_PREFIXES = (
    ".\\.venv\\Scripts\\python.exe",
    ".venv/bin/python",
    "make ",
    "jq-auto ",
)
```

`recommended_commands` 不匹配这些前缀时，报：

```text
unsupported recommended command for <skill>: <command>
```

- [ ] **Step 5: 验证治理闭环**

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\research\governance\skill_ownership.py scripts\research\governance\rules.py
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py -q
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

Expected: py_compile passes, governance tests pass, gate exits 0.

## Task S12 [HITL]: Old Skill Removal Review

**Demo:** 人工能看到旧 Skill 到新 owner Skill 的映射、风险和删除清单，并明确批准删除窗口。

**Files:**
- Create: `docs/design/skill-system-migration-review.md`

- [ ] **Step 1: 生成迁移审查文档**

文档包含：

| Old Skill | New Owner | 删除前必须满足 |
| --- | --- | --- |
| `.claude/skills/agent-doc-add` | `skill-system` | `skill-system` 发现样例通过，`docs/rules/skills.md` 已存在 |
| `.claude/skills/agent-doc-refactor` | `skill-system` | `skill-system` adapter 已覆盖入口文档治理 |
| `.claude/skills/jq-research` | `research-local-first` | 本地优先样例通过 |
| `.claude/skills/jq-analyze` | `research-report-analysis` | 报告分析样例通过 |
| `.claude/skills/jq-param-scan` | `strategy-experiment` | 参数扫描触发短语已覆盖 |
| `.claude/skills/jq-ab-test` | `strategy-experiment` | A/B 触发短语已覆盖 |
| `.claude/skills/jq-fix` | `joinquant-strategy-fix` | 编译错误触发短语已覆盖 |
| `.claude/skills/jq-run` | `joinquant-cloud-run` | 云端 run/fetch 触发短语已覆盖 |
| `.codex/skills/quant-pr-workflow` | `repo-pr-governance` | PR 治理样例通过 |
| `.codex/skills/quant-research-workflow` | `research-local-first` + research owners | 研究样例全部通过 |

- [ ] **Step 2: 人工确认**

人工确认问题：

```text
是否同意删除旧 Skill 兼容入口，只保留 10 个新 owner Skill 和同名 Claude adapter？
```

Expected: 只有回答明确同意后，才执行 S13。

## Task S13 [AFK]: Remove Old Compatibility Skills

**Precondition:** S12 人工同意。

**Demo:** 删除旧 Skill 后，10 条发现样例仍全部唯一命中新 owner，治理 gate 通过。

**Files:**
- Delete: `.claude/skills/agent-doc-add/`
- Delete: `.claude/skills/agent-doc-refactor/`
- Delete: `.claude/skills/jq-ab-test/`
- Delete: `.claude/skills/jq-analyze/`
- Delete: `.claude/skills/jq-fix/`
- Delete: `.claude/skills/jq-param-scan/`
- Delete: `.claude/skills/jq-research/`
- Delete: `.claude/skills/jq-run/`
- Delete: `.codex/skills/quant-pr-workflow/`
- Delete: `.codex/skills/quant-research-workflow/`
- Modify: `scripts/research/governance/rules.py`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 更新治理 expected Skill 清单**

移除 `REQUIRED_CODEX_SKILLS` 中的旧 `quant-pr-workflow` / `quant-research-workflow` 检查；改由 `skill_ownership.REQUIRED_OWNER_SKILLS` 负责新 owner 检查。

- [ ] **Step 2: 删除旧目录**

使用 PowerShell 原生命令逐个删除已批准路径；删除前确认 resolved path 都在 repo 内。

- [ ] **Step 3: 验证无旧触发入口**

Run:

```powershell
rg -n "jq-run|jq-fix|jq-analyze|jq-param-scan|jq-ab-test|jq-research|agent-doc-add|agent-doc-refactor|quant-pr-workflow|quant-research-workflow" .codex .claude docs scripts
```

Expected: 只允许迁移审查文档和历史计划中出现旧名称；活跃 Skill 目录、治理必需清单不再引用旧名称。

- [ ] **Step 4: 验证新发现闭环**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

Expected: both exit 0.

## Task S14 [AFK]: Docs Index And Final Gate

**Demo:** 文档 catalog 能找到本计划、`docs/rules/skills.md`、迁移审查文档；pathref 和治理 gate 通过。

**Files:**
- Modify: `docs/indexes/docs_catalog.json`
- Modify as generated: `docs/indexes/*.json`, `docs/indexes/*.md`

- [ ] **Step 1: 刷新 docs index**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.docs index
```

Expected: exits 0 and records new docs.

- [ ] **Step 2: 跑 pathref**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: exits 0.

- [ ] **Step 3: 跑治理 gate**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

Expected: exits 0.

- [ ] **Step 4: 最终差异检查**

Run:

```powershell
git status --short
git diff --check
```

Expected: no whitespace errors; diff only包含计划、Skill、治理、测试、docs index 和已批准的旧 Skill 删除。

## Non-Goals

- 不在本计划中删除根 `indexes.md`。本轮只把机器发现职责迁移到 `ownership.yaml`，根索引继续作为人类入口，避免冲突 AGENTS 入口规则。
- 不把 `docs/rules/**` 正文复制进 Skill。
- 不把 `scripts/**` 实现复制进 Skill。
- 不从 Codex/Claude 插件缓存导入插件 Skill。
- 不改变 JoinQuant 云端确认门槛，不默认消耗云端额度。

## Acceptance Checklist

- [ ] 10 个 `.codex/skills/<owner>/references/ownership.yaml` 全部存在。
- [ ] 10 个 `.claude/skills/<same-owner>/SKILL.md` 全部存在。
- [ ] 10 条发现样例都唯一命中目标 owner Skill。
- [ ] 同一规则、命令、脚本没有多 owner。
- [ ] Claude adapter 不声明 `owned_rules`、`owned_commands` 或 `owned_scripts`。
- [ ] `docs/rules/skills.md` 存在且不重复维护 ownership 明细。
- [ ] 旧 Skill 删除经过 S12 HITL 同意。
- [ ] `.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py -q` 通过。
- [ ] `.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check` 通过。
- [ ] `.\.venv\Scripts\python.exe -m scripts.research.governance gate` 通过。
