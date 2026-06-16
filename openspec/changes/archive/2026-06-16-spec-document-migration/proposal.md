## Why

仓库当前有约 69 个文档散落在 `docs/design/`、`docs/superpowers/`、`docs/adr/`、`docs/architecture/` 等目录中。这些文档混合了系统能力规格、已完成设计方案、架构决策记录和外部参考资料，缺乏统一的能力规格层。OpenSpec 的 `specs/<capability>/spec.md` 模型天然适合承载"系统有什么能力与边界"这层语义，而 `changes/archive/` 适合保留已完成决策的可追溯记录。本次迁移建立这两层，实现：

- **能力规格（WHAT）** → `openspec/specs/` — 12 个 capability 的稳定能力定义
- **操作约束（HOW）** → `docs/rules/`、`docs/guides/` — 流程与行为约束，两不互替

## What Changes

### 新建
- 通过本次 change 的 delta spec，在 `openspec/specs/` 下建立 12 个 capability spec

### 归档
- 将 10 个 ADR (`docs/adr/000*.md`) 归档到 `openspec/changes/archive/`
- 将 8 个设计文档 (`docs/design/*.md`) 归档到 `openspec/changes/archive/`
- 将 4 个 Superpowers 方案/计划 (`docs/superpowers/`) 归档到 `openspec/changes/archive/`

### 整理
- `docs/joinquant-data/` → `docs/joinquant-api/`（重命名）
- `cc-switch-cli.md`：从 `docs/design/` 移至 `docs/reference/`
- `docs/exceptions/` + `docs/joinquant-data/quota_ledger/` → `.local/governance/`（治理运行时数据移出 docs）

### 收尾
- 重新生成 `docs/indexes/`
- 清理空目录

### 不变
- `docs/rules/`、`docs/guides/`、`docs/agents/` 内容不动
- 策略代码、研究脚本、治理工具代码不变

## Capabilities

### New Capabilities

- `research-platform`: 本地优先研究平台能力（CLI、候选漏斗、fast/full 模式、云端交接）
- `data-center`: 数据中心能力（快照登记、catalog、压缩存储、pointer 机制）
- `strategy-variant`: 策略变体管理（参数变体、结构变体、物化、合并状态流转）
- `backtest-automation`: 回测自动化（A/B 实验、run/fetch/batch、数据源切换）
- `pr-automation`: PR 自动化（pr-submit、状态机编排、auto-merge、evidence 管理）
- `governance-gate`: 治理门禁（verify-fast/full/explain、CI required checks、pathref 审计）
- `review-system`: Review 系统（双 reviewer 交叉评审、风险分级、Codex review 集成）
- `skill-management`: Skill 管理（单一来源 `.agents/skills/`、symlink 发现、ownership 治理）
- `agent-collaboration`: Agent 协作（分支隔离、任务分发授权、共享工作区约束）
- `documentation-system`: 文档系统（pathref 引用、索引生成、报告 catalog）
- `environment-management`: 环境管理（`.venv` 入口、UTF-8 编码、本地/聚宽平台差异）
- `code-standards`: 代码标准（聚宽 Python 3.6 兼容、向量化、测试要求）

### Modified Capabilities

（无 — 本次为新建，不涉及已有 capability 的 spec 级修改）

## Impact

- 影响：`docs/` 目录结构、`openspec/specs/` 和 `openspec/changes/archive/` 目录、`.local/governance/` 目录
- 不影响：策略代码 (`strategies/`)、研究脚本 (`scripts/research/`)、治理工具 CLI 接口
- pathref 引用：迁移后指向上述移动/重命名文件的内部链接需同步更新
- 索引：`docs/indexes/` 需在迁移完成后重新生成
