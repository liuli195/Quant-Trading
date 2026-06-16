# ADR 0001: 规则来源和治理模型

## Why
仓库由多个 AI 编码助手和本地研究工具共同维护。只依靠口头提醒或分散 README，长期会出现规则入口漂移、工具入口漂移、文档索引漂移和例外常态化。

## What Changes
- CLAUDE.md（现 AGENTS.md）是 AI 助手的统一入口
- docs/rules/ 是仓库级规则正文
- ADR 索引记录重大规则和架构决策原因
- 治理门禁纳入自动检查

## Impact
规则变更不能只改聊天记录或单个工具说明。MUST 级规则变更必须同步规则文档；影响协作模型、目录结构、治理门禁或策略开发流程时必须更新 ADR。

---
source: docs/adr/0001-rule-source-and-governance-model.md
migration: 历史 ADR 迁移 — 极简归档
