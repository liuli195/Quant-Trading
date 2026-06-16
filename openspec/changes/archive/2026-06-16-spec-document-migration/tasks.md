## 1. Spec 同步

- [ ] 1.1 运行 `openspec sync spec-document-migration` 将 12 个 delta spec 同步到 `openspec/specs/`

## 2. 目录整理（移动与重命名）

- [ ] 2.1 将 `docs/design/cc-switch-cli.md` 移动到 `docs/reference/cc-switch-cli.md`
- [ ] 2.2 将 `docs/joinquant-data/` 重命名为 `docs/joinquant-api/`
- [ ] 2.3 创建 `.local/governance/exceptions/` 目录，将 `docs/exceptions/active-waivers.yaml` 移动过去
- [ ] 2.4 创建 `.local/governance/quota-ledger/` 目录，将 `docs/joinquant-data/quota_ledger/*.json` 全部移动过去
- [ ] 2.5 删除空的 `docs/exceptions/` 目录和 `docs/joinquant-api/quota_ledger/` 空目录

## 3. 文档归档

### 3a. ADR 归档（极简）

- [ ] 3a.1 为 10 个 ADR（0001-0010）创建 `openspec/changes/archive/adr-NNNN-<slug>/` 目录
- [ ] 3a.2 将原 ADR 文件作为 `design.md` 复制入对应 archive 目录
- [ ] 3a.3 为每个 ADR archive 创建 `proposal.md`（标注来源为历史 ADR 迁移，不写 tasks.md）

### 3b. Design 文档归档（标准）

- [ ] 3b.1 为 8 个有效设计文档创建 `openspec/changes/archive/<slug>/` 目录
- [ ] 3b.2 将原设计文档作为 `design.md` 复制入对应 archive 目录
- [ ] 3b.3 为每个 design archive 创建 `proposal.md` 和 `tasks.md`（标注已完成）

### 3c. Superpowers 文档归档（标准）

- [ ] 3c.1 为 `feishu-relay-tools` 创建 archive 目录，将 design.md 和计划文件归档
- [ ] 3c.2 为 `backtest-data-compaction` 创建 archive 目录并归档计划文件
- [ ] 3c.3 为 `etf-vol-relief-ab-test` 创建 archive 目录并归档计划文件

### 3d. Architecture 文档归档（标准）

- [ ] 3d.1 确认 `docs/architecture/research-platform-architecture.md` 内容已被 spec 覆盖
- [ ] 3d.2 将 architecture 文档归档为 `openspec/changes/archive/research-platform-architecture/`

### 3e. 本 change 自身 superpowers 产物归档

- [ ] 3e.1 将 `docs/superpowers/specs/2026-06-17-spec-document-migration-design.md` 归档到 `openspec/changes/archive/spec-document-migration/design.md`
- [ ] 3e.2 将 `docs/superpowers/plans/2026-06-17-spec-document-migration-plan.md`（build 阶段 writing-plans 生成）归档到 `openspec/changes/archive/spec-document-migration/tasks.md`
- [ ] 3e.3 复制本 change 的 `openspec/changes/spec-document-migration/proposal.md` 到归档目录

## 4. 清理源文件

- [ ] 4.1 删除 `docs/adr/000*.md` 和 `docs/adr/index.md`，删除整个 `docs/adr/` 目录
- [ ] 4.2 删除 `docs/design/` 目录（cc-switch-cli.md 已于 2.1 移走）
- [ ] 4.3 删除 `docs/superpowers/` 目录（全部已归档于 3c 和 3e）
- [ ] 4.4 删除 `docs/architecture/` 目录

## 5. 治理扫描（冲突检测与修复）

- [ ] 5.1 扫描 `docs/rules/index.md` — 检查 ADR 和 architecture 引用，更新为 openspec 路径
- [ ] 5.2 扫描 `docs/rules/governance.md`、`pr-workflow.md`、`review-guidelines.md` — 检查 ADR 引用
- [ ] 5.3 扫描 `docs/rules/skills.md` — 检查 design 文档引用
- [ ] 5.4 扫描 `docs/rules/docs-and-pathref.md` — 确认路径约定不与新结构冲突
- [ ] 5.5 扫描 `docs/guides/*`（4 个） — 检查已删除目录引用
- [ ] 5.6 扫描 `docs/agents/domain.md` — 更新规则入口路径
- [ ] 5.7 扫描 `docs/README.md` — 更新目录分层表
- [ ] 5.8 扫描 `AGENTS.md` / `CLAUDE.md` — 更新根入口路径
- [ ] 5.9 扫描 `scripts/research/governance/rules.py` — 确认 `REQUIRED_RULE_DOCS` 不含已删除文件
- [ ] 5.10 扫描 `comet/reference/*.md` — 检查 Comet 内部引用
- [ ] 5.11 扫描 CI workflows (`.github/workflows/`) — 检查硬编码旧路径

## 6. Pathref 修复

- [ ] 6.1 运行 `scripts.tools.path_tools.refactor check` 检测所有断裂引用
- [ ] 6.2 逐文件修复 Phase 5 和 6.1 发现的所有断裂 pathref
- [ ] 6.3 再次运行 `check` 确认 pathref 全绿

## 7. 索引与收尾

- [ ] 7.1 运行 `scripts.research.docs index` 重新生成 `docs/indexes/`
- [ ] 7.2 运行 `scripts.research.governance verify fast` 确认规则不冲突
- [ ] 7.3 确认 `docs/rules/`、`docs/guides/`、`docs/agents/` 内容完整无损

## 8. Archive

- [ ] 8.1 运行 `openspec archive spec-document-migration` 将 delta spec 合并到 `openspec/specs/`
- [ ] 8.2 运行 `scripts.research.governance verify full` 作为 CI 级验证证据（PR 提交时执行）
