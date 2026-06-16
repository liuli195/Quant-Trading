# ADR 0005: AI 入口采用渐进式披露

## Why
根目录的 AGENTS.md 和 CLAUDE.md 同时承载大量规则，导致入口重复、职责不清，不利于不同 AI 工具按需读取规则。

## What Changes
- AGENTS.md 是所有 AI 编码助手的通用入口
- 规则索引归 docs/rules/index.md，ADR 入口归 docs/adr/index.md
- CLAUDE.md 是 File Symlink 指向 AGENTS.md
- 命令和本地环境规则独立为 commands.md
- governance gate 必须检查新的入口模型

## Impact
新增或修改 AI 规则时，先判断是否属于根入口。只有每次任务都相关的内容进入 AGENTS.md；工具专属内容进入对应工具入口；细则进入 docs/rules/*.md。

---
source: docs/adr/0005-ai-entry-progressive-disclosure.md
migration: 历史 ADR 迁移 — 极简归档
