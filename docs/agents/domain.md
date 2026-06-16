# 领域文档

本仓库按 single-context 处理。

## 开始探索前先读这些文件

- [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->：共享 AI 规则。
- [docs/README.md](../README.md) <!-- pathref: docs/README.md -->：docs 入口。
- [docs/rules/index.md](../rules/index.md) <!-- pathref: docs/rules/index.md -->：受治理约束的流程和编码规则。
- [openspec/changes/archive](../../openspec/changes/archive) <!-- pathref: openspec/changes/archive -->：历史架构决策记录已归档。
- [openspec/specs](../../openspec/specs) <!-- pathref: openspec/specs -->：当前系统能力规格。

如果后续新增根目录 `CONTEXT.md`，优先读取它。如果后续新增 `CONTEXT-MAP.md`，按它切换为 multi-context 路由。

## 使用项目已有词汇

输出中命名项目概念时，使用现有文档和 ADR 中的说法。如果术语缺失或不清楚，直接说明这个缺口，不要自造一套新词。

## 标出 ADR 冲突

如果方案和已有 ADR 冲突，必须明确指出，并写出对应 ADR。
