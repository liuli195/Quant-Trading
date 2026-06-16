## Context

仓库当前有两类文档缺乏统一的能力规格层：
- `docs/design/`、`docs/superpowers/`、`docs/architecture/` 中已完成的设计方案
- `docs/rules/` 中隐含的系统能力定义（如 PR 自动化、治理门禁、Skill 管理）

OpenSpec 的 `specs/<capability>/spec.md` 模型用于承载系统能力与边界（WHAT），而 `docs/rules/` 和 `docs/guides/` 保留流程与行为约束（HOW）。本次迁移通过一个专用的 change，利用 OpenSpec 的 delta spec → archive 机制，一次性建立 12 个 capability 规格并归档历史文档。

## Goals / Non-Goals

**Goals:**
- 在 `openspec/specs/` 下建立 12 个 capability 规格，描述系统能力与边界
- 将 24 个已完成设计文档/ADR/方案归档到 `openspec/changes/archive/`
- 整理 `docs/` 目录结构（重命名、移动运行时数据、移出外部文档）
- 重新生成 `docs/indexes/`

**Non-Goals:**
- 不修改 `docs/rules/`、`docs/guides/`、`docs/agents/` 内容
- 不新增或修改任何系统能力的实际行为
- 不修改策略代码、研究脚本、治理工具

## Decisions

### Decision 1: 单一 change 驱动全部迁移

**选择**：通过一个 `spec-document-migration` change，包含 12 个 delta spec，archive 后自动合并到 `openspec/specs/`。

**替代方案**：逐个 capability 创建独立的 change。
**否决原因**：12 个独立 change 会产生 12 次 archive 操作，且各 capability 的归档和目录整理之间存在协调依赖。单一 change 保证原子性。

### Decision 2: Delta spec 使用 ADDED 操作

**选择**：全部 12 个 capability 使用 `## ADDED Requirements`，因为当前 `openspec/specs/` 为空，无已有 spec 需要 MODIFIED。

### Decision 3: ADR 和 design 文档作为 archive change 处理

**选择**：将 10 个 ADR + 8 个 design 文档 + 4 个 superpowers 文档移动到 `openspec/changes/archive/`，按来源分组命名。
**格式**：`openspec/changes/archive/adr-NNNN-name/`、`openspec/changes/archive/<design-name>/`、`openspec/changes/archive/<superpower-name>/`

### Decision 4: 目录整理与能力规格分离

**选择**：目录重命名/移动（`joinquant-data→joinquant-api` 等）在 tasks 中作为独立步骤执行，不纳入 delta spec 定义。这些是物理整理操作，不改变系统能力。

### Decision 5: 治理运行时数据移入 .local

**选择**：`docs/exceptions/` 和 `docs/joinquant-data/quota_ledger/` 移入 `.local/governance/`，因为它们是治理系统的运行时状态数据，非静态文档。

## Risks / Trade-offs

- **Pathref 断裂**：移动和重命名会导致现有 Markdown 文件中的 `pathref` 引用失效 → 迁移完成后运行 `pathref check` 并更新
- **外部引用**：如果有外部工具或 CI 脚本硬编码了 `docs/adr/` 路径 → 本次仅处理文档层面，脚本路径变动需单独评估
- **capability 规格不完整**：12 个 spec 的初始版本只覆盖核心能力边界，不追求详尽 → 后续各 capability 独立演进时补全
- **archive change 缺少 proposal/design/tasks**：原 ADR 文档只有决策记录，缺少 OpenSpec 要求的三件套 → 归档时仅保留原文件作为 design.md，标注为历史迁移

## Open Questions

- 是否需要为归档的 24 个 change 补写 proposal.md 和 tasks.md？当前方案仅保留原文件作为 design 或直接归档
