---
comet_change: spec-document-migration
role: technical-design
canonical_spec: openspec
---

# Spec Document Migration — 技术设计

## 任务概述

将 `docs/` 下散落的系统能力规格文档（ADR、design、superpowers、architecture）通过单一 OpenSpec change 迁移为标准格式。12 个 capability spec 从 delta spec 同步到 `openspec/specs/`，历史文档归档到 `openspec/changes/archive/`，同时整理 `docs/` 目录结构。

## 执行流程（8 阶段）

```
Phase 1: sync            openspec sync → 12 delta spec 进入 openspec/specs/
Phase 2: 目录整理         joinquant-data→joinquant-api, cc-switch-cli→reference/,
                         exceptions+quota_ledger→.local/governance/
Phase 3: 文档归档         25+ archive changes 创建（24 历史 + 本 change 自身 superpowers 产物）
Phase 4: 清理源文件       删除 docs/adr/, docs/design/, docs/superpowers/, docs/architecture/
Phase 5: 治理扫描         扫描 rules/guides/agents/AGENTS.md/CLAUDE.md/
                         scripts/research/governance/rules.py/CI workflows
                         检测并记录与本次改动冲突的引用
Phase 6: pathref 修复     修复 Phase 5 发现的所有断裂引用
Phase 7: indexes 重新生成  docs index 重新扫描全仓 Markdown
Phase 8: archive          openspec archive spec-document-migration
```

## 归档策略

### 极简归档（ADR × 10）
- `proposal.md`：自动生成，标注 `source: docs/adr/NNNN-*.md` 和"历史 ADR 迁移"
- `design.md`：原 ADR 文件内容
- 无 `tasks.md`

### 标准归档（design × 8 + superpowers × 4 + architecture × 1 + 本 change 自身）
- `proposal.md`：从原文件提取目标/范围
- `design.md`：原文件内容
- `tasks.md`：标注"已完成，见原文件"

### 本 change 自身产物的自归档

本 change 在 design 阶段生成的 `docs/superpowers/specs/2026-06-17-spec-document-migration-design.md` 和 build 阶段 writing-plans 生成的 plan 文件，在 Phase 3 中与其他 superpowers 文件一起归档到 `openspec/changes/archive/spec-document-migration/`。确保 `docs/superpowers/` 在 Phase 4 后完全清空。

## 目录整理映射

| 源路径 | 目标路径 | 操作 |
|--------|---------|------|
| `docs/joinquant-data/` | `docs/joinquant-api/` | 重命名 |
| `docs/design/cc-switch-cli.md` | `docs/reference/cc-switch-cli.md` | 移动 |
| `docs/exceptions/active-waivers.yaml` | `.local/governance/exceptions/active-waivers.yaml` | 移动 |
| `docs/joinquant-data/quota_ledger/*.json` | `.local/governance/quota-ledger/*.json` | 移动 |

## 治理扫描范围

| 扫描目标 | 检查项 |
|---------|--------|
| `docs/rules/index.md` | 是否引用已删除目录 |
| `docs/rules/governance.md` | 是否硬编码旧路径 |
| `docs/rules/pr-workflow.md` | ADR 引用路径 |
| `docs/rules/skills.md` | design 文档引用 |
| `docs/rules/docs-and-pathref.md` | 路径约定冲突 |
| `docs/guides/*` (4 个) | 已删除目录引用 |
| `docs/agents/domain.md` | 规则入口路径 |
| `docs/README.md` | 目录分层表 |
| `AGENTS.md` / `CLAUDE.md` | 根入口路径 |
| `scripts/research/governance/rules.py` | `REQUIRED_RULE_DOCS` 列表 |
| `comet/reference/*.md` | Comet 内部引用 |
| CI workflows (`.github/workflows/`) | 硬编码旧路径 |

## 自归档细节

Phase 3 执行时，本 change 的 superpowers 产物路径：

```
docs/superpowers/specs/2026-06-17-spec-document-migration-design.md
  → openspec/changes/archive/spec-document-migration/design.md

docs/superpowers/plans/2026-06-17-spec-document-migration-plan.md（build 阶段 writing-plans 生成）
  → openspec/changes/archive/spec-document-migration/tasks.md
```

归档时本 change 自己的 `proposal.md` 由原 change 的 `proposal.md` 复制。

## 收尾验证

1. `scripts.tools.path_tools.refactor check` — 确认 pathref 全绿
2. `scripts.research.governance verify fast` — 规则冲突检测通过
3. `scripts.research.governance verify full` — CI 级全量验证（PR 提交时执行）
4. `docs/rules/`、`docs/guides/`、`docs/agents/` 内容 SHA 与迁移前一致（不含本次修改的引用）
