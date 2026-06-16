## ADDED Requirements

### Requirement: 分层验证体系

治理门禁系统 SHALL 提供三层验证：`verify fast`（日常开发、只面向变更文件）、`verify full`（CI 全量门禁）、`verify explain`（展示命中规则和缓存状态）。

#### Scenario: 日常增量验证

- **WHEN** 开发者运行 `verify fast`
- **THEN** 系统基于 staged/worktree diff 运行 scoped checks：Markdown 变更只跑 pathref 检查，Skill 目录变更才跑 `skill_ownership check`，治理代码变更才跑 ruff/mypy/bandit/pytest

#### Scenario: CI 全量验证

- **WHEN** GitHub CI 触发 `verify full`
- **THEN** 系统运行完整治理审计：静态扫描、类型检查、依赖漏洞扫描、测试、pathref gate 和 governance gate

### Requirement: 规则优先元规则

治理门禁 SHALL 执行"规则优先"原则：任何与仓库规则冲突的改动 MUST 获得显式授权方可执行。

#### Scenario: 规则冲突检测

- **WHEN** 改动与 `docs/rules/` 中的 MUST 级规则冲突
- **THEN** 系统在门禁中阻断并报告具体冲突规则，要求显式授权或 waiver
