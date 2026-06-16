# Brainstorm Summary

- Change: spec-document-migration
- Date: 2026-06-17

## 确认的技术方案

将 `docs/` 下散落的系统能力规格文档通过单一 OpenSpec change 迁移为标准格式：

1. **先 sync 后 archive**：Phase 1 执行 `openspec sync` 将 12 个 delta spec 同步到 `openspec/specs/`，Phase 8 最后执行 `openspec archive` 统一收尾
2. **混合归档策略**：ADR 用极简归档（原文件=design.md + 自动生成 proposal.md），design/superpowers/architecture 用标准归档（完整三件套）
3. **彻底删除源文件**：归档后删除 `docs/adr/`、`docs/design/`、`docs/superpowers/`、`docs/architecture/` 全部文件及目录
4. **治理扫描**：目录清理后扫描 `docs/rules/`、`docs/guides/`、`docs/agents/`、`AGENTS.md`、`CLAUDE.md`、`scripts/research/governance/rules.py` 和 CI workflows，检测与本次改动的冲突并修复
5. **目录整理**：`joinquant-data→joinquant-api`、`cc-switch-cli→reference/`、`exceptions+quota_ledger→.local/governance/`
6. **自归档**：本 change 在 design/build 阶段自身生成的 `docs/superpowers/specs/` 和 `docs/superpowers/plans/` 文件，同样走标准归档流程，在 Phase 3 中一并归档到 `openspec/changes/archive/spec-document-migration/`，确保 `docs/superpowers/` 目录彻底清空

### 执行流程

```
Phase 1: sync          → openspec sync delta→main specs
Phase 2: 目录整理       → 重命名/移动
Phase 3: 文档归档       → 25+ 个 archive changes（24 历史 + 本 change 自身 superpowers 产物）
Phase 4: 清理源文件      → 删除旧目录
Phase 5: 治理扫描       → rules/guides/agents/scripts/CI 冲突检测
Phase 6: pathref 修复   → 所有断裂引用修复
Phase 7: indexes 重新生成 → docs index
Phase 8: archive        → openspec archive
```

## 关键取舍与风险

- **极简 vs 标准归档**：ADR 不补 tasks.md（只有决策记录，补全无价值）
- **Pathref 断裂**：`docs/design/` 和 `docs/adr/` 被大量文件引用，需逐文件修复
- **`REQUIRED_RULE_DOCS`**：`scripts/research/governance/rules.py` 硬编码了 `docs/rules/` 路径列表，需确认 adr 不在其中
- **根入口**：`AGENTS.md` / `CLAUDE.md` 可能引用 `docs/adr/index.md`，需更新

## 测试策略

- 每阶段完成后运行 `scripts.tools.path_tools.refactor check` 验证 pathref
- Phase 5 治理扫描使用 `scripts.research.governance verify fast` 检测规则冲突
- Phase 7 后运行完整 `verify fast` 确认全绿
- 最终 `verify full` 作为 CI 级证据

## Spec Patch

无（delta spec 在 open 阶段已完整，无需修改）
