# 仓库规则总索引

本目录是仓库级规则正文。AI 助手通用入口是 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；根文档索引见 [indexes.md](../../indexes.md) <!-- pathref: repo/indexes.md -->；Claude Code 专属指针见 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->；重大规则来源和取舍记录在 [ADR](../adr) <!-- pathref: docs/adr -->。

## 规则分级

| 等级 | 含义 | 执行方式 |
| --- | --- | --- |
| MUST | 不允许违反 | `governance gate`、CI、主干保护阻断 |
| SHOULD | 默认遵守，可解释偏离 | PR 说明、review checklist |
| MAY | 建议或偏好 | 文档、示例、onboarding |

## 规则文档

| 文档 | 规则范围 |
| --- | --- |
| [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md --> | 核心 PR 工作流、分支模型、review 与主干同步 |
| [governance.md](governance.md) <!-- pathref: docs/rules/governance.md --> | CI、主干保护、CODEOWNERS、waiver、周期审计 |
| [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> | Codex Code Review 触发方式、评审重点、PR 证据 |
| [commands.md](commands.md) <!-- pathref: docs/rules/commands.md --> | 本地环境、虚拟环境和常用命令 |
| [research-workflow.md](research-workflow.md) <!-- pathref: docs/rules/research-workflow.md --> | 本地研究、云端确认、报告同步 |
| [code-style.md](code-style.md) <!-- pathref: docs/rules/code-style.md --> | 策略代码、注释、参数、测试、环境兼容约束 |
| [environments.md](environments.md) <!-- pathref: docs/rules/environments.md --> | 本地与聚宽回测/模拟/研究四环境差异对照 |
| [docs-and-pathref.md](docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md --> | Markdown、pathref、报告索引 |

## ADR

- [0001-rule-source-and-governance-model.md](../adr/0001-rule-source-and-governance-model.md) <!-- pathref: docs/adr/0001-rule-source-and-governance-model.md -->
- [0002-ai-agent-parallel-work-uses-git-branches.md](../adr/0002-ai-agent-parallel-work-uses-git-branches.md) <!-- pathref: docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md -->
- [0003-governance-gate-and-main-branch-protection.md](../adr/0003-governance-gate-and-main-branch-protection.md) <!-- pathref: docs/adr/0003-governance-gate-and-main-branch-protection.md -->
- [0004-codex-code-review-governance.md](../adr/0004-codex-code-review-governance.md) <!-- pathref: docs/adr/0004-codex-code-review-governance.md -->
- [0005-ai-entry-progressive-disclosure.md](../adr/0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md -->

## 规则变更

MUST 级规则变更必须同步对应 `docs/rules/*.md`。如果影响协作模型、目录结构、治理门禁或策略开发流程，必须新增或更新 ADR，并通过 CODEOWNER review。
