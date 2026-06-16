# Comet Design Handoff

- Change: spec-document-migration
- Phase: design
- Mode: compact
- Context hash: 6bb5d0dff7ee24952707350ddfb2b6e9d32b5623d9c9efaa2104c03d5297008b

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/spec-document-migration/proposal.md

- Source: openspec/changes/spec-document-migration/proposal.md
- Lines: 1-57
- SHA256: 0a5fa9468b9dc97e39474f2e1f410e92f0681a142b7fe1855cc0993bdff7a342

```md
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
```

## openspec/changes/spec-document-migration/design.md

- Source: openspec/changes/spec-document-migration/design.md
- Lines: 1-57
- SHA256: 01cc0653fe86bfa59a55b792ed615a134700805f036fa9577cf1de3148eb841d

```md
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
```

## openspec/changes/spec-document-migration/tasks.md

- Source: openspec/changes/spec-document-migration/tasks.md
- Lines: 1-80
- SHA256: cc0183c46347279bdf9c35673ccb0c47c1140bb9f7ec7d8e9c31c76168a77ab9

```md
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
```

## openspec/changes/spec-document-migration/specs/agent-collaboration/spec.md

- Source: openspec/changes/spec-document-migration/specs/agent-collaboration/spec.md
- Lines: 1-19
- SHA256: 95fe84f3c5134f603934209a2c9c802872337ace7d2d153cbdc431b2a33b1403

```md
## ADDED Requirements

### Requirement: 分支隔离

Agent 协作系统 SHALL 要求多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支，禁止并行写入同一 repo-tracked 分支。

#### Scenario: 并行工作分配

- **WHEN** 多个 AI agent 需要同时修改仓库代码
- **THEN** 系统为每个 agent 分配独立 Git 分支（命名模板 `agent/<tool>/<topic>`），禁止共享同一分支写入

### Requirement: 任务分发授权

当子 agent 能力可用时，系统 SHALL 默认以用户持续显式授权模式优先将任务分发给子 agent，无能力或强串行依赖时记录原因和替代证据。

#### Scenario: 任务分发

- **WHEN** 主会话面临可独立执行的并行任务
- **THEN** 系统优先将任务分发给子 agent 执行，主会话负责编排、确认和汇总
```

## openspec/changes/spec-document-migration/specs/backtest-automation/spec.md

- Source: openspec/changes/spec-document-migration/specs/backtest-automation/spec.md
- Lines: 1-19
- SHA256: 85ffd95b9a8286c8ef96d5d993e224f9f6c490a8fb3fe317e1369a40c2cb5660

```md
## ADDED Requirements

### Requirement: A/B 实验配置与执行

回测自动化系统 SHALL 支持通过声明式 JSON 配置定义 A/B 实验，支持参数对比和 Git 版本对比，在一次上传会话内完成全部候选的覆盖上传和回测。

#### Scenario: 参数 A/B 对比

- **WHEN** 用户配置 baseline 与 variants 的参数差异（如 `fq_mode='pre'` vs `fq_mode=None`）
- **THEN** 系统为每个候选生成完整策略快照，顺序上传至聚宽编辑器并触发回测

### Requirement: 数据源选择

回测数据获取 SHALL 支持 `--result-source auto|research|detail` 三种模式，auto 优先使用聚宽研究环境 `get_backtest()`，失败后回退到详情页 API。

#### Scenario: auto 模式数据获取

- **WHEN** 用户以 `--result-source auto` 获取回测结果
- **THEN** 系统先尝试研究环境 API，失败后自动回退到详情页接口，两种都失败时记录错误并报告
```

## openspec/changes/spec-document-migration/specs/code-standards/spec.md

- Source: openspec/changes/spec-document-migration/specs/code-standards/spec.md
- Lines: 1-19
- SHA256: c428e12b52f7537884321c0ecfef86a5186b98bc735612a63f4dd6b5affc43f3

```md
## ADDED Requirements

### Requirement: 聚宽兼容性

代码标准系统 SHALL 要求策略代码兼容聚宽 Python 3.6 环境，禁用新语法（`f"{x=}"`、`X | Y`、`match/case`）和本地专属库（`matplotlib`、`seaborn`、`cvxpy`）。

#### Scenario: 语法检查

- **WHEN** 策略代码发生变更
- **THEN** 系统运行语法检查，拒绝包含 Python 3.6+ 新语法或不兼容 API 调用的代码

### Requirement: 策略参数集中定义

策略代码 SHALL 将参数集中定义，避免魔法数字，`initialize` 集中配置与注册，`handle_data` 或 `run_daily` 承载调仓逻辑。

#### Scenario: 策略结构校验

- **WHEN** 新策略代码提交审查
- **THEN** 系统校验参数定义集中、调仓逻辑清晰、停牌/缺失值/仓位上下限有明确处理
```

## openspec/changes/spec-document-migration/specs/data-center/spec.md

- Source: openspec/changes/spec-document-migration/specs/data-center/spec.md
- Lines: 1-19
- SHA256: 9261194759a12b02cc66a8a80274a6e5bd2efc2124b41a5461c1d4df86700acb

```md
## ADDED Requirements

### Requirement: 数据快照登记

数据中心 SHALL 通过 `research_datasets/catalog.json` 集中登记所有可复用数据快照。

#### Scenario: 新快照登记

- **WHEN** 新的回测数据或研究数据准备进入数据中心
- **THEN** 系统在 `catalog.json` 中登记快照元数据，包含原始 SHA256、压缩 SHA256 和文件清单

### Requirement: 回测数据压缩存储

数据中心 SHALL 对回测 run 中的冗余和明细大文件进行压缩存储，run 目录仅保留轻量 pointer 和报告。

#### Scenario: 数据压缩

- **WHEN** 明确重复数据（如 `summary_metrics.json`）和 run 明细大文件（如 `positioninfo.md`）被识别
- **THEN** 系统将其压缩存储在数据中心，run 目录仅保留 pointer 引用
```

## openspec/changes/spec-document-migration/specs/documentation-system/spec.md

- Source: openspec/changes/spec-document-migration/specs/documentation-system/spec.md
- Lines: 1-19
- SHA256: 311bdda7459ad969665c02d71a8854fd2bb39dc8528e3e5f37a6b951a33da400

```md
## ADDED Requirements

### Requirement: Pathref 引用规范

文档系统 SHALL 要求 Markdown 内部文件引用使用"可点击链接 + `pathref` 注释"双轨格式，确保机器可校验。

#### Scenario: 文件引用

- **WHEN** 文档中需要引用另一个仓库内文件
- **THEN** 系统使用 `[文件名](相对路径) <!-- pathref: 目标路径 -->` 格式，允许 `scripts.tools.path_tools.refactor check` 校验引用有效性

### Requirement: 文档报告索引

系统 SHALL 通过 `DocsIndexer` 自动扫描仓库 Markdown 文档，生成 `docs/indexes/` 下的 JSON 和 Markdown 格式索引。

#### Scenario: 索引生成

- **WHEN** 运行 `scripts.research.docs index`
- **THEN** 系统生成 `docs_catalog.json`、`reports_catalog.json`、`datasets_catalog.json`、`variants_catalog.json` 及对应的 Markdown 可读版本
```

## openspec/changes/spec-document-migration/specs/environment-management/spec.md

- Source: openspec/changes/spec-document-migration/specs/environment-management/spec.md
- Lines: 1-19
- SHA256: 55afd1056c08d2cf43f70cd452490a3777d6bad4fd0e6dc656e7b4c081a4a676

```md
## ADDED Requirements

### Requirement: 项目虚拟环境

环境管理系统 SHALL 以项目 `.venv` 作为默认 Python 执行环境，禁止日常命令使用系统 Python。

#### Scenario: 命令执行

- **WHEN** 用户或 AI agent 执行 Python 命令
- **THEN** 系统使用 `.\.venv\Scripts\python.exe` (Windows) 或 `.venv/bin/python` (Linux/macOS)，UTF-8 编码由环境变量 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8` 保障

### Requirement: 本地/聚宽平台差异

环境管理系统 SHALL 明确区分本地开发环境和聚宽云端环境的边界：策略代码仅在聚宽回测/模拟运行，本地负责开发、测试和分析。

#### Scenario: 平台兼容检查

- **WHEN** 策略代码准备上传聚宽
- **THEN** 系统通过 `scripts.tools.jq_automation compile-check` 检查 Python 3.6 兼容性、禁用语法和 API 可用性
```

## openspec/changes/spec-document-migration/specs/governance-gate/spec.md

- Source: openspec/changes/spec-document-migration/specs/governance-gate/spec.md
- Lines: 1-24
- SHA256: fa5f7f58ddb71ab9e88ebbe73f249d067a3e9563af20457d23df3b58db6391ff

```md
## ADDED Requirements

### Requirement: 分层验证体系

治理门禁系统 SHALL 提供三层验证：`verify fast`（日常开发、只面向变更文件）、`verify full`（CI 全量门禁）、`verify explain`（展示命中规则和缓存状态）。

#### Scenario: 日常增量验证

- **WHEN** 开发者运行 `verify fast`
- **THEN** 系统基于 staged/worktree diff 运行 scoped checks：Markdown 变更只跑 pathref 检查，Skill 目录变更才跑 `skill_ownership check`，治理代码变更才跑 ruff/mypy/bandit/pytest

#### Scenario: CI 全量验证

- **WHEN** GitHub CI 触发 `verify full`
- **THEN** 系统运行完整治理审计：静态扫描、类型检查、依赖漏洞扫描、测试、pathref gate 和 governance gate

### Requirement: 规则优先元规则

治理门禁 SHALL 执行"规则优先"原则：任何与仓库规则冲突的改动 MUST 获得显式授权方可执行。

#### Scenario: 规则冲突检测

- **WHEN** 改动与 `docs/rules/` 中的 MUST 级规则冲突
- **THEN** 系统在门禁中阻断并报告具体冲突规则，要求显式授权或 waiver
```

## openspec/changes/spec-document-migration/specs/pr-automation/spec.md

- Source: openspec/changes/spec-document-migration/specs/pr-automation/spec.md
- Lines: 1-19
- SHA256: 18e960c03091564a154f2a09eef308ddb36f25b5fbb73a7fe2cdd7889ac0040c

```md
## ADDED Requirements

### Requirement: 统一 PR 提交流程

PR 自动化系统 SHALL 提供 `pr-submit` 作为唯一推荐入口，编排从本地检查到 GitHub auto-merge 的完整自动化流程。

#### Scenario: 标准 PR 提交

- **WHEN** 用户运行 `make pr-submit TITLE="<PR标题>"`
- **THEN** 系统依次执行：校验 review fragments → 创建/更新 draft PR → 刷新 PR Evidence → ready-for-review → 等待 required checks → head-locked auto-merge → 本地收尾

### Requirement: PR Flow 状态机契约

系统 SHALL 通过 `pr-flow-interface-contract.yaml` 定义 PR Flow 的机器接口，包括 required checks、artifact 路径和规则约束。

#### Scenario: Required checks 校验

- **WHEN** `pr-submit` 等待 GitHub checks 完成
- **THEN** 系统校验 `PR Flow / review-status`、`Research Governance / verify-full`、`PR Flow / evidence` 三个 required checks 全部通过后才触发 auto-merge
```

## openspec/changes/spec-document-migration/specs/research-platform/spec.md

- Source: openspec/changes/spec-document-migration/specs/research-platform/spec.md
- Lines: 1-29
- SHA256: ebab494540e8c7b070e3c418fab3f84f28468903b40f0e081fc498d25dcca338

```md
## ADDED Requirements

### Requirement: 本地优先研究流程

研究平台 SHALL 支持本地优先研究流程，通过统一的 CLI 入口管理研究项目的完整生命周期。

#### Scenario: 创建研究项目

- **WHEN** 用户运行 `scripts.research.cli init` 创建研究项目
- **THEN** 系统生成标准项目骨架，包含 `docs/research_spec.md`、`docs/data_contract.md`、`docs/execution_plan.md` 等文档模板

#### Scenario: fast mode 粗筛

- **WHEN** 用户运行 fast mode 进行大规模候选扫描
- **THEN** 系统在热启动条件下于 3 秒内完成粗筛并输出初步排名

### Requirement: 候选漏斗与云端交接

研究平台 SHALL 支持多层候选漏斗（fast → full → handoff-cloud），只在本地精筛通过后将少量候选送往云端确认。

#### Scenario: 候选提升

- **WHEN** fast mode 输出的候选列表通过 `promote` 进入 full mode
- **THEN** 系统对提升候选执行留出集、分段时间段和 bootstrap 精筛

#### Scenario: 云端交接

- **WHEN** full mode 验证通过的候选触发 `handoff-cloud`
- **THEN** 系统生成云端确认请求，不将未通过本地门槛的候选送往云端
```

## openspec/changes/spec-document-migration/specs/review-system/spec.md

- Source: openspec/changes/spec-document-migration/specs/review-system/spec.md
- Lines: 1-28
- SHA256: a17198a863d575f2608abd685c08e930c24e82b67ada78adce164200b9029001

```md
## ADDED Requirements

### Requirement: 双 Reviewer 交叉评审

Review 系统 SHALL 要求每个 PR 至少完成两个独立 reviewer 的交叉评审，记录评审证据到结构化 fragment。

#### Scenario: 交叉评审完成

- **WHEN** Standards reviewer 和 Spec reviewer 分别产出 review fragment（`.local/ai-review/fragments/standards.json` 和 `spec.json`）
- **THEN** 系统在 fragment 中记录 `reviewers: A, B`，且每个 reviewer 最后一轮 `no_new_findings=true`

### Requirement: 风险分级评审

Review 系统 SHALL 按风险等级决定是否需要官方 Codex review：P0/P1 阻断合并，P2/P3 作为 retained finding 记录。

#### Scenario: P0 阻断

- **WHEN** 任一 reviewer 发现 P0 级 finding 且状态为 `open`
- **THEN** 系统阻断 PR 进入下一阶段，直到 finding 被标记为 `fixed` 或 `false_positive` 并提供当前 head/diff 下的证据

### Requirement: 官方 Codex Review 集成

当 `official_review.decision=required` 时，系统 SHALL 触发 `@codex review` 并等待 current-head verdict，P2/P3 由系统自动接受并 resolve。

#### Scenario: 触发官方 review

- **WHEN** 本地双 reviewer 评审通过且风险等级为 P0/P1
- **THEN** 系统通过 PR comment 触发 `@codex review`，在 3 分钟内等待 Codex bot 的 `eyes` reaction 确认远端已接收
```

## openspec/changes/spec-document-migration/specs/skill-management/spec.md

- Source: openspec/changes/spec-document-migration/specs/skill-management/spec.md
- Lines: 1-19
- SHA256: 4cc2a6ec9a466cbff1f5fbbcd87b086bb047e260c0ad184df98e9befe0955f48

```md
## ADDED Requirements

### Requirement: 单一来源管理

Skill 管理系统 SHALL 以 `.agents/skills/<skill>/` 作为仓库级 Skill 的唯一事实来源（SSOT），Codex 直接读取，Claude Code 通过 `.claude/skills` Directory Symlink 指向同一份内容。

#### Scenario: Skill 创建

- **WHEN** 新增仓库级 Skill
- **THEN** 系统在 `.agents/skills/<skill>/` 下创建完整的 `SKILL.md`、`agents/openai.yaml` 和 `references/*`，同步更新 `ownership.yaml`

### Requirement: 自然语言发现

Skill SHALL 支持通过自然语言请求唯一命中目标 Skill，命中后先读取 `read_rules` 列出的规则文件再执行推荐命令。

#### Scenario: 自然语言匹配

- **WHEN** 用户发起符合某 Skill 触发语义的自然语言请求
- **THEN** 系统唯一命中目标 Skill，加载对应的规则文件和操作指令
```

## openspec/changes/spec-document-migration/specs/strategy-variant/spec.md

- Source: openspec/changes/spec-document-migration/specs/strategy-variant/spec.md
- Lines: 1-19
- SHA256: a716988f8584b79dc042cbeb7ccdc49fe61644a5db18589bcc2548e0d1d3879b

```md
## ADDED Requirements

### Requirement: 参数变体管理

策略变体系统 SHALL 通过 `VariantRegistry` 登记参数变体（params diff）和结构变体（Git 代码差异），参数变体默认不使用 Git 分支。

#### Scenario: 登记参数变体

- **WHEN** 用户通过 `variant_id` 登记一组参数差异（如 `TopK=2, TargetVol=0.12`）
- **THEN** 系统生成 `variants/<variant_id>.json` 配置文件，不创建 Git 分支

### Requirement: 结构变体状态流转

结构变体 SHALL 遵循标准状态流转：`candidate → in_research → cloud_confirmed → merge_ready → merged_pending_validation → merged_confirmed`。

#### Scenario: 结构变体合并

- **WHEN** 结构变体通过云端确认后进入 `merge_ready` 状态
- **THEN** `VariantMergeManager` 生成合并计划，仅在用户显式授权后执行合并
```

