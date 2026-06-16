# 跨 AI 工具 Skill 管理实施计划

## Why
建立一套可扩展的跨 AI 工具 Skill 管理流程，让系统级 Skill 可以通过 cc-switch 在 Claude Code、Codex、Gemini、OpenCode 等工具间同步，同时保留本仓库的规则入口、仓库级 Skill 和治理门禁边界。

## What Changes
- 8 步实施计划：盘点现状 → 定义分层规则 → MCP 依赖规则 → 同步命令规范 → 扩展治理审计 → 无 MCP 试点 → MCP 依赖试点 → 扩展仓库级 Skill
- 四层分类：cc-switch-global、claude-runtime/plugin-managed、codex-runtime/plugin-managed、repo-local
- 新增 requires_cli、requires_app_connector、requires_plugin_runtime 等依赖字段

## Impact
系统级 Skill 通过 cc-switch 跨工具同步。仓库级 Skill 不建议通过 cc-switch 自动同步，继续由仓库 Git 流程管理。当前所有现有 Skill 均不提升为 cc-switch-global。

---
source: docs/design/cross-ai-skill-management.md
