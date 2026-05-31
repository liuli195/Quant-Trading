# ADR 0001: 规则来源和治理模型

## 状态

Superseded by [ADR 0005](0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md -->

## 背景

仓库由多个 AI 编码助手和本地研究工具共同维护。只依靠口头提醒或分散 README，长期会出现规则入口漂移、工具入口漂移、文档索引漂移和例外常态化。

## 决策

- [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 是 AI 助手的统一入口。此入口模型已由 [ADR 0005](0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md --> 更新为 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 通用入口。
- [docs/rules](../rules) <!-- pathref: docs/rules --> 是仓库级规则正文。
- [ADR 索引](index.md) <!-- pathref: docs/adr/index.md --> 记录重大规则和架构决策原因。
- `scripts.research.governance gate` 将规则入口、registry、catalog、workflow、CODEOWNERS、PR 模板、waiver 和 pathref 纳入自动检查。

## 影响

规则变更不能只改聊天记录或单个工具说明。MUST 级规则变更必须同步规则文档；影响协作模型、目录结构、治理门禁或策略开发流程时必须更新 ADR。
