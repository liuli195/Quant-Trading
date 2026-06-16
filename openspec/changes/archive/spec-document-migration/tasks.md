---
change: spec-document-migration
design-doc: docs/superpowers/specs/2026-06-17-spec-document-migration-design.md
base-ref: 7ef3f2c78fc184c226191abf7b3e9c85846d6717
---

# Spec Document Migration 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `docs/` 下散落的系统能力规格文档通过单一 OpenSpec change 迁移为标准格式，建立 `openspec/specs/` (能力规格) 和 `openspec/changes/archive/` (历史归档) 两层结构。

**Architecture:** 纯文档迁移，8 阶段顺序执行：sync 同步 delta spec → 目录整理移动/重命名 → 归档历史文档 → 清理源目录 → 治理扫描检测断裂引用 → pathref 修复 → 索引重新生成 → archive 收尾。无代码变更，不涉及策略逻辑或研究脚本修改。

**Tech Stack:** Git、Bash/PowerShell 文件操作、`openspec` CLI、`scripts.tools.path_tools.refactor`、`scripts.research.docs index`、`scripts.research.governance verify`

**设计文档:** [2026-06-17-spec-document-migration-design.md](../specs/2026-06-17-spec-document-migration-design.md) 

---

### 前置确认（执行前必须）

- [ ] 确认 `openspec` CLI 可用：运行 `openspec --version`
- [ ] 确认 `.venv` 虚拟环境可用：运行 `.venv\Scripts\python.exe -c "print('ok')"` 输出 `ok`
- [ ] 确认 `openspec/specs/` 目录不存在（或为空）— 如果已存在则先与用户确认
- [ ] 确认工作区干净：`git status` 无未提交变更

---

### Task 1: Phase 1 — Spec 同步

**Files:**
- Create: `openspec/specs/<capability>/spec.md` (12 个 capability)

- [ ] **Step 1: 运行 openspec sync 将 12 个 delta spec 同步到主 specs**

在工作区根目录执行：

```powershell
openspec sync spec-document-migration
```

预期：在 `openspec/specs/` 下生成 12 个 capability 目录，每个包含 `spec.md`。
12 个 capability 名称为：
- `research-platform`
- `data-center`
- `strategy-variant`
- `backtest-automation`
- `pr-automation`
- `governance-gate`
- `review-system`
- `skill-management`
- `agent-collaboration`
- `documentation-system`
- `environment-management`
- `code-standards`

- [ ] **Step 2: 验证 sync 结果**

```powershell
Get-ChildItem openspec/specs -Directory | Measure-Object | Select-Object -ExpandProperty Count
```

预期：输出 `12`

- [ ] **Step 3: 提交**

```bash
git add openspec/specs/
git commit -m "迁移 Phase 1: openspec sync — 12 个 capability spec 进入 openspec/specs/"
```

---

### Task 2: Phase 2 — 目录整理（移动与重命名）

- [ ] **Step 1: 移动 cc-switch-cli.md 到 reference**

```powershell
Move-Item -Path "docs/design/cc-switch-cli.md" -Destination "docs/reference/cc-switch-cli.md"
```

- [ ] **Step 2: 重命名 joinquant-data 为 joinquant-api**

```powershell
Rename-Item -Path "docs/joinquant-data" -NewName "joinquant-api"
```

- [ ] **Step 3: 创建 .local/governance/exceptions/ 目录并移动 waivers 文件**

```powershell
New-Item -ItemType Directory -Force -Path ".local/governance/exceptions"
Move-Item -Path "docs/exceptions/active-waivers.yaml" -Destination ".local/governance/exceptions/active-waivers.yaml"
```

- [ ] **Step 4: 创建 .local/governance/quota-ledger/ 目录并移动所有 quota JSON 文件**

```powershell
New-Item -ItemType Directory -Force -Path ".local/governance/quota-ledger"
Move-Item -Path "docs/joinquant-api/quota_ledger/*.json" -Destination ".local/governance/quota-ledger/"
```

quota_ledger 中的文件包括：
- `20260505.json`
- `20260506.json`
- `20260507.json`
- `20260508.json`
- `20260514.json`
- `20260515.json`
- `20260517.json`
- `20260518.json`
- `20260524.json`
- `20260526.json`

- [ ] **Step 5: 清理空目录**

```powershell
Remove-Item -Recurse -Force -Path "docs/exceptions"
Remove-Item -Recurse -Force -Path "docs/joinquant-api/quota_ledger"
```

验证这些目录已不存在：

```powershell
Test-Path "docs/exceptions"   # 预期: False
Test-Path "docs/joinquant-api/quota_ledger"   # 预期: False
```

- [ ] **Step 6: 提交**

```bash
git add -A docs/reference/cc-switch-cli.md docs/joinquant-api/ .local/governance/
git add -A docs/exceptions/ docs/joinquant-api/quota_ledger/
git commit -m "迁移 Phase 2: 目录整理 — joinquant-data→joinquant-api, cc-switch-cli→reference/, quota/exceptions→.local/governance/"
```

---

### Task 3: Phase 3 — 文档归档

#### 3a. ADR 归档（极简流程）

10 个 ADR，按极简归档策略：`proposal.md`（自动生成）+ `design.md`（原 ADR 内容），无 `tasks.md`。

ADR 源文件与归档目标目录对照表：

| ADR 编号 | 源文件 | 归档 slug |
|----------|--------|-----------|
| 0001 | `docs/adr/0001-rule-source-and-governance-model.md` | `adr-0001-rule-source-and-governance-model` |
| 0002 | `docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md` | `adr-0002-ai-agent-parallel-work` |
| 0003 | `docs/adr/0003-governance-gate-and-main-branch-protection.md` | `adr-0003-governance-gate-and-main-branch-protection` |
| 0004 | `docs/adr/0004-codex-code-review-governance.md` | `adr-0004-codex-code-review-governance` |
| 0005 | `docs/adr/0005-ai-entry-progressive-disclosure.md` | `adr-0005-ai-entry-progressive-disclosure` |
| 0006 | `docs/adr/0006-risk-tiered-pr-review.md` | `adr-0006-risk-tiered-pr-review` |
| 0007 | `docs/adr/0007-pr-flow-closed-loop-review-evidence.md` | `adr-0007-pr-flow-closed-loop-review-evidence` |
| 0008 | `docs/adr/0008-skill-single-source-agents.md` | `adr-0008-skill-single-source-agents` |
| 0009 | `docs/adr/0009-subagent-delegation-continuous-authorization.md` | `adr-0009-subagent-delegation-continuous-authorization` |
| 0010 | `docs/adr/0010-local-branch-history-rewrite-gate.md` | `adr-0010-local-branch-history-rewrite-gate` |

- [ ] **Step 1: 为每个 ADR 创建 archive 目录**

```powershell
$adrSlugs = @(
    "adr-0001-rule-source-and-governance-model",
    "adr-0002-ai-agent-parallel-work",
    "adr-0003-governance-gate-and-main-branch-protection",
    "adr-0004-codex-code-review-governance",
    "adr-0005-ai-entry-progressive-disclosure",
    "adr-0006-risk-tiered-pr-review",
    "adr-0007-pr-flow-closed-loop-review-evidence",
    "adr-0008-skill-single-source-agents",
    "adr-0009-subagent-delegation-continuous-authorization",
    "adr-0010-local-branch-history-rewrite-gate"
)
foreach ($slug in $adrSlugs) {
    New-Item -ItemType Directory -Force -Path "openspec/changes/archive/$slug"
}
```

- [ ] **Step 2: 为每个 ADR 复制原文件为 design.md 并生成 proposal.md**

以 ADR 0001 为例（其余 9 个照此模式）：

```powershell
# ADR 0001
Copy-Item "docs/adr/0001-rule-source-and-governance-model.md" "openspec/changes/archive/adr-0001-rule-source-and-governance-model/design.md"
```

为 ADR 0001 生成 `proposal.md`，写入内容：

```powershell
@'
# ADR 0001: 规则来源和治理模型

## Why

历史 ADR 迁移 — 决定 CLAUDE.md 作为 AI 助手统一入口，docs/rules/ 为仓库级规则正文，ADR 索引记录重大决策原因，scripts.research.governance gate 纳入自动检查。

## What Changes

- 确立 CLAUDE.md（现 AGENTS.md）为 AI 统一入口
- docs/rules/ 为规则正文
- ADR 记录重大治理和架构决策

## Impact

- 影响：所有 AI 助手的入口行为、规则变更流程
- 状态：Superseded by ADR 0005

---
source: docs/adr/0001-rule-source-and-governance-model.md
migration: 历史 ADR 迁移 — 极简归档
'@ | Out-File -Encoding utf8 "openspec/changes/archive/adr-0001-rule-source-and-governance-model/proposal.md"
```

其余 9 个 ADR 按相同模式处理：从原 ADR 文件提取 **背景** 段落的要点填入 proposal.md 的 Why/What Changes/Impact，标注 `source` 原路径和 `migration: 历史 ADR 迁移 — 极简归档`。

- [ ] **Step 3: 验证 ADR 归档完整性**

```powershell
$adrSlugs | ForEach-Object {
    $design = Test-Path "openspec/changes/archive/$_/design.md"
    $proposal = Test-Path "openspec/changes/archive/$_/proposal.md"
    Write-Host "$_ : design=$design proposal=$proposal"
}
```

预期：全部 10 个条目均为 `True`

- [ ] **Step 4: 提交 ADR 归档**

```bash
git add openspec/changes/archive/adr-*/
git commit -m "迁移 Phase 3a: ADR 归档 — 10 个 ADR 极简归档到 openspec/changes/archive/"
```

#### 3b. Design 文档归档（标准流程）

9 个 design 文档（不含已移至 reference 的 `cc-switch-cli.md`），按标准归档策略：`proposal.md`（提取目标/范围）+ `design.md`（原内容）+ `tasks.md`（标注已完成）。

Design 源文件与归档 slug 对照：

| 源文件 | 归档 slug |
|--------|-----------|
| `docs/design/本地研究平台重构.md` | `local-research-platform-refactor` |
| `docs/design/本地研究平台重构技术实施方案.md` | `local-research-platform-tech-implementation` |
| `docs/design/AB_TEST_DESIGN.md` | `ab-test-design` |
| `docs/design/RESEARCH_BACKTEST_DATA_PLAN.md` | `research-backtest-data-plan` |
| `docs/design/skill-system-migration-review.md` | `skill-system-migration-review` |
| `docs/design/skill-system-refactor.md` | `skill-system-refactor` |
| `docs/design/cross-ai-skill-management.md` | `cross-ai-skill-management` |
| `docs/design/长期项目防止开发规则漂移方案.md` | `long-term-rule-drift-prevention` |
| `docs/design/日常增量验证提速方案设计.md` | `daily-incremental-verify-speedup` |

- [ ] **Step 1: 创建 design archive 目录**

```powershell
$designSlugs = @(
    "local-research-platform-refactor",
    "local-research-platform-tech-implementation",
    "ab-test-design",
    "research-backtest-data-plan",
    "skill-system-migration-review",
    "skill-system-refactor",
    "cross-ai-skill-management",
    "long-term-rule-drift-prevention",
    "daily-incremental-verify-speedup"
)
foreach ($slug in $designSlugs) {
    New-Item -ItemType Directory -Force -Path "openspec/changes/archive/$slug"
}
```

- [ ] **Step 2: 为每个 design 复制原文件并生成 proposal.md 和 tasks.md**

以 `AB_TEST_DESIGN.md` 为例：

```powershell
Copy-Item "docs/design/AB_TEST_DESIGN.md" "openspec/changes/archive/ab-test-design/design.md"
```

生成 `openspec/changes/archive/ab-test-design/proposal.md`：

```powershell
@'
# A/B 实验设计

## Why

设计回测 A/B 实验体系，控制变量法对比策略变体收益与回撤差异。

## What Changes

- 建立 A/B 实验框架（variant registry、控制变量、delta 归因）
- 定义实验执行流程和结果比较标准

## Impact

- 影响：研究流程中策略变体验证方式
- 状态：已完成

---
source: docs/design/AB_TEST_DESIGN.md
'@ | Out-File -Encoding utf8 "openspec/changes/archive/ab-test-design/proposal.md"
```

生成 `openspec/changes/archive/ab-test-design/tasks.md`：

```powershell
@'
# A/B 实验设计 — 任务清单

## 已完成

本设计文档对应的实现任务已完成。原文件见 `docs/design/AB_TEST_DESIGN.md`。

- [x] 设计 A/B 实验框架 ✓
- [x] 定义 variant registry ✓
- [x] 控制变量与 delta 归因 ✓

---
status: 已完成 — 见原文件
'@ | Out-File -Encoding utf8 "openspec/changes/archive/ab-test-design/tasks.md"
```

其余 8 个 design 文档按相同模式处理：从原文件提取核心目标/范围填入 proposal.md，tasks.md 标注已完成。

- [ ] **Step 3: 验证 design 归档完整性**

```powershell
$designSlugs | ForEach-Object {
    $design = Test-Path "openspec/changes/archive/$_/design.md"
    $proposal = Test-Path "openspec/changes/archive/$_/proposal.md"
    $tasks = Test-Path "openspec/changes/archive/$_/tasks.md"
    Write-Host "$_ : design=$design proposal=$proposal tasks=$tasks"
}
```

预期：全部 9 个条目三项均为 `True`

- [ ] **Step 4: 提交 design 归档**

```bash
git add openspec/changes/archive/local-research-platform-refactor/ openspec/changes/archive/local-research-platform-tech-implementation/ openspec/changes/archive/ab-test-design/ openspec/changes/archive/research-backtest-data-plan/ openspec/changes/archive/skill-system-migration-review/ openspec/changes/archive/skill-system-refactor/ openspec/changes/archive/cross-ai-skill-management/ openspec/changes/archive/long-term-rule-drift-prevention/ openspec/changes/archive/daily-incremental-verify-speedup/
git commit -m "迁移 Phase 3b: Design 文档归档 — 9 个设计文档标准归档到 openspec/changes/archive/"
```

#### 3c. Superpowers 文档归档（标准流程）

4 个 superpowers 文件分属 3 个条目归档：

| 条目 | 源文件 | 归档 slug |
|------|--------|-----------|
| feishu-relay-tools | `docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md` (→ design.md) | `feishu-relay-tools` |
| feishu-relay-tools | `docs/superpowers/plans/2026-05-20-feishu-relay-tools-implementation.md` (→ tasks.md) | `feishu-relay-tools` |
| backtest-data-compaction | `docs/superpowers/plans/2026-05-20-backtest-data-redundancy-compaction.md` (→ design.md) | `backtest-data-compaction` |
| etf-vol-relief-ab-test | `docs/superpowers/plans/2026-05-26-etf-vol-relief-ab-test.md` (→ design.md) | `etf-vol-relief-ab-test` |

- [ ] **Step 1: 创建 superpowers archive 目录**

```powershell
$spSlugs = @("feishu-relay-tools", "backtest-data-compaction", "etf-vol-relief-ab-test")
foreach ($slug in $spSlugs) {
    New-Item -ItemType Directory -Force -Path "openspec/changes/archive/$slug"
}
```

- [ ] **Step 2: 归档 feishu-relay-tools**

```powershell
Copy-Item "docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md" "openspec/changes/archive/feishu-relay-tools/design.md"
Copy-Item "docs/superpowers/plans/2026-05-20-feishu-relay-tools-implementation.md" "openspec/changes/archive/feishu-relay-tools/tasks.md"
```

生成 `openspec/changes/archive/feishu-relay-tools/proposal.md`：

```powershell
@'
# 飞书 Relay 工具

## Why

实现聚宽模拟交易到飞书通知的中继工具，打通策略信号→飞书通知链路。

## What Changes

- 飞书 webhook relay 实现
- 交易信号格式化与推送
- 错误重试机制

## Impact

- 影响：聚宽模拟交易通知通道
- 状态：已完成

---
source: docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md
'@ | Out-File -Encoding utf8 "openspec/changes/archive/feishu-relay-tools/proposal.md"
```

- [ ] **Step 3: 归档 backtest-data-compaction**

```powershell
Copy-Item "docs/superpowers/plans/2026-05-20-backtest-data-redundancy-compaction.md" "openspec/changes/archive/backtest-data-compaction/design.md"
```

生成 `openspec/changes/archive/backtest-data-compaction/proposal.md`：

```powershell
@'
# 回测数据冗余压缩

## Why

回测 run 数据目录膨胀，需建立压缩存储机制降低磁盘占用，同时保持可追溯性。

## What Changes

- 数据中心压缩存储设计
- catalog 与 pointer 机制
- 压缩脚本实现

## Impact

- 影响：数据存储、快照回溯
- 状态：已完成

---
source: docs/superpowers/plans/2026-05-20-backtest-data-redundancy-compaction.md
'@ | Out-File -Encoding utf8 "openspec/changes/archive/backtest-data-compaction/proposal.md"
```

生成 `openspec/changes/archive/backtest-data-compaction/tasks.md`：

```powershell
@'
# 回测数据冗余压缩 — 任务清单

## 已完成

本计划已执行完毕。原文件见 `docs/superpowers/plans/2026-05-20-backtest-data-redundancy-compaction.md`。

---
status: 已完成 — 见原文件
'@ | Out-File -Encoding utf8 "openspec/changes/archive/backtest-data-compaction/tasks.md"
```

- [ ] **Step 4: 归档 etf-vol-relief-ab-test**

```powershell
Copy-Item "docs/superpowers/plans/2026-05-26-etf-vol-relief-ab-test.md" "openspec/changes/archive/etf-vol-relief-ab-test/design.md"
```

生成 `openspec/changes/archive/etf-vol-relief-ab-test/proposal.md`：

```powershell
@'
# ETF 波动缩减 A/B 实验

## Why

通过 A/B 实验验证 ETF 波动率缩减策略的有效性，对比不同参数配置下的收益与回撤表现。

## What Changes

- ETF 波动缩减策略变体设计
- A/B 实验参数配置
- 回测对比分析方法

## Impact

- 影响：ETF 策略参数优化决策
- 状态：已完成

---
source: docs/superpowers/plans/2026-05-26-etf-vol-relief-ab-test.md
'@ | Out-File -Encoding utf8 "openspec/changes/archive/etf-vol-relief-ab-test/proposal.md"
```

生成 `openspec/changes/archive/etf-vol-relief-ab-test/tasks.md`：

```powershell
@'
# ETF 波动缩减 A/B 实验 — 任务清单

## 已完成

本计划已执行完毕。原文件见 `docs/superpowers/plans/2026-05-26-etf-vol-relief-ab-test.md`。

---
status: 已完成 — 见原文件
'@ | Out-File -Encoding utf8 "openspec/changes/archive/etf-vol-relief-ab-test/tasks.md"
```

- [ ] **Step 5: 验证 superpowers 归档完整性**

```powershell
$spSlugs | ForEach-Object {
    $design = Test-Path "openspec/changes/archive/$_/design.md"
    $proposal = Test-Path "openspec/changes/archive/$_/proposal.md"
    $tasks = Test-Path "openspec/changes/archive/$_/tasks.md"
    Write-Host "$_ : design=$design proposal=$proposal tasks=$tasks"
}
```

预期：全部 3 个条目三项均为 `True`

- [ ] **Step 6: 提交 superpowers 归档**

```bash
git add openspec/changes/archive/feishu-relay-tools/ openspec/changes/archive/backtest-data-compaction/ openspec/changes/archive/etf-vol-relief-ab-test/
git commit -m "迁移 Phase 3c: Superpowers 文档归档 — 3 个条目标准归档到 openspec/changes/archive/"
```

#### 3d. Architecture 文档归档（标准流程）

- [ ] **Step 1: 归档 architecture 文档**

```powershell
New-Item -ItemType Directory -Force -Path "openspec/changes/archive/research-platform-architecture"
Copy-Item "docs/architecture/research-platform-architecture.md" "openspec/changes/archive/research-platform-architecture/design.md"
```

生成 `proposal.md`：

```powershell
@'
# 研究平台架构

## Why

定义量化研究平台的总体架构：数据层、研究层、策略层、交易层的分层设计和组件关系。

## What Changes

- 平台分层架构设计
- 各层职责与接口定义
- 本地与云端环境分工

## Impact

- 影响：新功能开发和技术选型的架构指导
- 状态：已完成 — 内容已被 openspec/specs/research-platform 等 capability spec 覆盖

---
source: docs/architecture/research-platform-architecture.md
'@ | Out-File -Encoding utf8 "openspec/changes/archive/research-platform-architecture/proposal.md"
```

生成 `tasks.md`：

```powershell
@'
# 研究平台架构 — 任务清单

## 已完成

架构设计已完成，内容已被 `openspec/specs/research-platform/spec.md` 等 capability spec 覆盖。

---
status: 已完成 — 见原文件
'@ | Out-File -Encoding utf8 "openspec/changes/archive/research-platform-architecture/tasks.md"
```

- [ ] **Step 2: 提交 architecture 归档**

```bash
git add openspec/changes/archive/research-platform-architecture/
git commit -m "迁移 Phase 3d: Architecture 文档归档 — 研究平台架构标准归档到 openspec/changes/archive/"
```

#### 3e. 本 change 自身 superpowers 产物归档

- [ ] **Step 1: 为 spec-document-migration 创建 archive 目录**

```powershell
New-Item -ItemType Directory -Force -Path "openspec/changes/archive/spec-document-migration"
```

- [ ] **Step 2: 归档本 change 的 design doc 和 plan**

```powershell
Copy-Item "docs/superpowers/specs/2026-06-17-spec-document-migration-design.md" "openspec/changes/archive/spec-document-migration/design.md"
Copy-Item "docs/superpowers/plans/2026-06-17-spec-document-migration-plan.md" "openspec/changes/archive/spec-document-migration/tasks.md"
Copy-Item "openspec/changes/spec-document-migration/proposal.md" "openspec/changes/archive/spec-document-migration/proposal.md"
```

- [ ] **Step 3: 验证自归档完整性**

```powershell
$ok = @(
    (Test-Path "openspec/changes/archive/spec-document-migration/proposal.md"),
    (Test-Path "openspec/changes/archive/spec-document-migration/design.md"),
    (Test-Path "openspec/changes/archive/spec-document-migration/tasks.md")
)
Write-Host "proposal=$($ok[0]) design=$($ok[1]) tasks=$($ok[2])"
```

预期：三项均为 `True`

- [ ] **Step 4: 提交自归档**

```bash
git add openspec/changes/archive/spec-document-migration/
git commit -m "迁移 Phase 3e: 本 change superpowers 产物自归档"
```

---

### Task 4: Phase 4 — 清理源文件

**Files:**
- Delete: `docs/adr/` (整个目录)
- Delete: `docs/design/` (整个目录，cc-switch-cli.md 已于 Phase 2 移走)
- Delete: `docs/superpowers/` (整个目录)
- Delete: `docs/architecture/` (整个目录)

- [ ] **Step 1: 删除四个源目录**

```powershell
Remove-Item -Recurse -Force -Path "docs/adr"
Remove-Item -Recurse -Force -Path "docs/design"
Remove-Item -Recurse -Force -Path "docs/superpowers"
Remove-Item -Recurse -Force -Path "docs/architecture"
```

- [ ] **Step 2: 验证目录已删除**

```powershell
@("docs/adr", "docs/design", "docs/superpowers", "docs/architecture") | ForEach-Object {
    Write-Host "$_ exists: $(Test-Path $_)"
}
```

预期：全部 `False`

- [ ] **Step 3: 提交**

```bash
git add -A docs/adr/ docs/design/ docs/superpowers/ docs/architecture/
git commit -m "迁移 Phase 4: 清理源文件 — 删除 docs/adr/, docs/design/, docs/superpowers/, docs/architecture/"
```

---

### Task 5: Phase 5 — 治理扫描（冲突检测）

扫描范围与检查项如下表。执行扫描后逐文件修复，修复操作在 Task 6 中集中执行。

| 扫描文件 | 检查内容 | 预期断裂引用 |
|---------|---------|-------------|
| `docs/rules/index.md` | ADR 索引引用 `docs/adr/index.md` | `../adr/index.md` 路径失效 |
| `docs/rules/governance.md` | 是否引用 ADR | 检查 `adr/` 路径 |
| `docs/rules/pr-workflow.md` | ADR 引用 | 检查 `adr/` 路径 |
| `docs/rules/review-guidelines.md` | ADR 引用 | 检查 `adr/` 路径 |
| `docs/rules/skills.md` | design 文档引用 | 检查 `../design/` 路径 |
| `docs/rules/docs-and-pathref.md` | 路径约定 | 检查目录引用是否冲突 |
| `docs/guides/feishu-relay-tools.md` | 已删除目录引用 | 检查所有内部链接 |
| `docs/guides/research-workflow-migration.md` | 已删除目录引用 | 检查所有内部链接 |
| `docs/guides/local-python-env.md` | 已删除目录引用 | 检查所有内部链接 |
| `docs/guides/research-workflow.md` | 已删除目录引用 | 检查所有内部链接 |
| `docs/agents/domain.md` | 规则入口路径 | 检查 `adr/`、`design/`、`architecture/` 引用 |
| `docs/README.md` | 目录分层表 | adr/architecture/design 行需更新或删除 |
| `AGENTS.md` | 根入口路径 | 检查 `adr/`、`design/` 引用 |
| `CLAUDE.md` | 根入口路径 | 同上（symlink 或同文件） |
| `scripts/research/governance/rules.py` | `REQUIRED_RULE_DOCS` 列表 | 确认不含已删除文件路径 |
| `.github/workflows/research-governance.yml` | 硬编码旧路径 | 确认无 `docs/adr/` 等硬编码 |
| `.github/workflows/pr-flow.yml` | 硬编码旧路径 | 同上 |
| `.github/workflows/codex-review-router.yml` | 硬编码旧路径 | 同上 |
| `.github/workflows/codex-review-monitor.yml` | 硬编码旧路径 | 同上 |

- [ ] **Step 1: 扫描 docs/rules/ 目录（8 个规则文件）**

逐一打开以下文件，搜索 `adr/`、`design/`、`architecture/` 等已删除目录引用，记录所有需要修复的行号和内容。

执行：

```powershell
$ruleFiles = @(
    "docs/rules/index.md",
    "docs/rules/governance.md",
    "docs/rules/pr-workflow.md",
    "docs/rules/review-guidelines.md",
    "docs/rules/skills.md",
    "docs/rules/docs-and-pathref.md"
)
foreach ($f in $ruleFiles) {
    Write-Host "=== $f ==="
    Select-String -Path $f -Pattern "adr/|design/|architecture/|superpowers/" -SimpleMatch | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
}
```

- [ ] **Step 2: 扫描 docs/guides/ 目录（4 个文件）**

```powershell
$guideFiles = @(
    "docs/guides/feishu-relay-tools.md",
    "docs/guides/research-workflow-migration.md",
    "docs/guides/local-python-env.md",
    "docs/guides/research-workflow.md"
)
foreach ($f in $guideFiles) {
    Write-Host "=== $f ==="
    Select-String -Path $f -Pattern "adr/|design/|architecture/|superpowers/" -SimpleMatch | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
}
```

- [ ] **Step 3: 扫描 docs/agents/domain.md**

```powershell
Write-Host "=== docs/agents/domain.md ==="
Select-String -Path "docs/agents/domain.md" -Pattern "adr/|design/|architecture/|superpowers/" -SimpleMatch | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
```

- [ ] **Step 4: 扫描 docs/README.md**

```powershell
Write-Host "=== docs/README.md ==="
Select-String -Path "docs/README.md" -Pattern "adr/|design/|architecture/|superpowers/" -SimpleMatch | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
```

注意：`docs/README.md` 的目录分层表中有 adr、architecture、design、joinquant-data 四行，需全部更新。

- [ ] **Step 5: 扫描 AGENTS.md / CLAUDE.md**

```powershell
Write-Host "=== AGENTS.md ==="
Select-String -Path "AGENTS.md" -Pattern "adr/|design/|architecture/|superpowers/" -SimpleMatch | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
```

- [ ] **Step 6: 扫描 scripts/research/governance/rules.py**

搜索 `REQUIRED_RULE_DOCS` 列表和 `render_adr_index` 引用，确认无指向已删除目录的路径。

```powershell
Select-String -Path "scripts/research/governance/rules.py" -Pattern "adr|render_adr_index" | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
```

- [ ] **Step 7: 扫描 CI workflows**

```powershell
$wfFiles = @(
    ".github/workflows/research-governance.yml",
    ".github/workflows/pr-flow.yml",
    ".github/workflows/codex-review-router.yml",
    ".github/workflows/codex-review-monitor.yml"
)
foreach ($f in $wfFiles) {
    Write-Host "=== $f ==="
    Select-String -Path $f -Pattern "adr/|design/|architecture/|superpowers/" -SimpleMatch | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
}
```

- [ ] **Step 8: 记录扫描结果**

汇总 Step 1-7 的所有匹配行，记入临时笔记。每项标注：
- 文件路径
- 行号
- 原有引用文本
- 预期修复方式（删除引用/改为 openspec 路径/改为 reference 路径）

- [ ] **Step 9: 提交扫描结果（作为 task 分界点）**

```bash
git commit --allow-empty -m "迁移 Phase 5: 治理扫描完成 — 记录所有断裂引用待 Phase 6 修复"
```

---

### Task 6: Phase 6 — Pathref 修复

**Files:**
- Modify: `docs/rules/index.md` — 修改 ADR 索引引用
- Modify: `docs/README.md` — 更新目录分层表
- Modify: `docs/agents/domain.md` — 如有断裂引用则修复
- Modify: 其他 Phase 5 扫描发现的文件

- [ ] **Step 1: 运行 pathref check 获取完整断裂列表**

```powershell
.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

记录所有断裂引用（与 Phase 5 的手动扫描结果交叉验证）。

- [ ] **Step 2: 修复 docs/rules/index.md**

该文件引用 `docs/adr/index.md`。将：

```markdown
规则来源见 [ADR 索引](../adr/index.md) 
```

改为：

```markdown
规则来源见 [ADR 索引(..) <!-- pathref: openspec/changes/archive -->
```

将底部变更段落的：

```markdown
同步 [ADR 索引](../adr/index.md) 
```

改为删除该 pathref（ADR 索引已不存在，决策记录分散在各 archive 目录中）：

```markdown
同步 openspec/changes/archive/ 中的对应 ADR 决策记录
```

- [ ] **Step 3: 修复 docs/README.md 目录分层表**

当前目录分层表包含 adr、architecture、design、joinquant-data 四行需要更新：

```markdown
| [adr/index.md](adr/index.md)  | 重大治理和架构决策记录 | [0001-rule-source-and-governance-model.md](adr/0001-rule-source-and-governance-model.md)  |
| [architecture](architecture)  | 平台结构和长期架构说明 | [research-platform-architecture.md](architecture/research-platform-architecture.md)  |
| [design](design)  | 实施方案、重构方案、治理方案草案 | [本地研究平台重构技术实施方案.md](design/本地研究平台重构技术实施方案.md)  |
| [joinquant-data](joinquant-data)  | 聚宽数据专题资料 | [JQ_场内基金数据.md](joinquant-data/JQ_场内基金数据.md)  |
```

改为删除 adr/architecture/design 三行（已归档），更新 joinquant-data 行为 joinquant-api：

```markdown
| [joinquant-api](../../../../docs/joinquant-api) <!-- pathref: docs/joinquant-api --> | 聚宽数据专题资料 | [JQ_场内基金数据.md](../../../../docs/joinquant-api/JQ_场内基金数据.md) <!-- pathref: docs/joinquant-api/JQ_场内基金数据.md --> |
| [openspec/specs(../../../specs) <!-- pathref: openspec/specs --> | 系统能力规格 | 12 个 capability spec |
| [openspec/changes/archive(..) <!-- pathref: openspec/changes/archive --> | 历史决策与设计归档 | ADR、设计文档、架构决策 |
```

- [ ] **Step 4: 修复 docs/agents/domain.md**

检查 `docs/agents/domain.md` 中是否有 `adr/` 的引用。典型引用模式：

```markdown
[ADR 索引](../adr/index.md) 
```

如有此类引用，改为：

```markdown
[ADR 归档(..) <!-- pathref: openspec/changes/archive -->
```

- [ ] **Step 5: 修复 Phase 5 发现的其他断裂引用**

针对 Phase 5 记录的其余断裂 pathref，逐文件执行修复。修复原则：
- `docs/adr/*.md` 的引用 → `openspec/changes/archive/adr-*/` 对应目录
- `docs/design/*.md` 的引用 → `openspec/changes/archive/<slug>/` 对应目录  
- `docs/architecture/*.md` 的引用 → `openspec/changes/archive/research-platform-architecture/`
- `docs/joinquant-data/` 的引用 → `docs/joinquant-api/` (已重命名)
- `docs/superpowers/` 的引用 → `openspec/changes/archive/<slug>/`

- [ ] **Step 6: 再次运行 pathref check 确认全绿**

```powershell
.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

预期：所有断裂 pathref 已修复，输出无 ERROR。

- [ ] **Step 7: 提交 pathref 修复**

```bash
git add -A
git commit -m "迁移 Phase 6: pathref 修复 — 修复 Phase 5 发现的所有断裂引用，pathref check 全绿"
```

---

### Task 7: Phase 7 — 索引与收尾

- [ ] **Step 1: 重新生成 docs indexes**

```powershell
.venv\Scripts\python.exe -m scripts.research.docs index
```

预期：在 `docs/indexes/` 下重新生成所有索引文件（`docs_catalog.json` 等），不再包含已删除目录的条目。

- [ ] **Step 2: 运行 governance verify fast**

```powershell
.venv\Scripts\python.exe -m scripts.research.governance verify fast
```

预期：规则冲突检测通过，无 CRITICAL 级别错误。

- [ ] **Step 3: 验证规则文件内容完整性**

确认 `docs/rules/`、`docs/guides/`、`docs/agents/` 目录下的所有 .md 文件存在且内容非空：

```powershell
$dirs = @("docs/rules", "docs/guides", "docs/agents")
foreach ($d in $dirs) {
    Write-Host "=== $d ==="
    Get-ChildItem $d -Filter "*.md" | ForEach-Object {
        $size = (Get-Item $_.FullName).Length
        Write-Host "  $($_.Name): $size bytes"
    }
}
```

预期：所有文件大小 > 0，文件数与原目录结构一致（无文件丢失）。

- [ ] **Step 4: 验证 docs/ 目录最终结构**

```powershell
Get-ChildItem docs -Directory | Select-Object Name
```

预期输出：
```
guides
indexes
joinquant-api
reference
rules
```

不应存在 `adr`、`design`、`superpowers`、`architecture`、`exceptions`。

- [ ] **Step 5: 提交 phase 7 产物**

```bash
git add docs/indexes/
git commit -m "迁移 Phase 7: 索引重新生成 — docs index 重新扫描 + governance verify fast 通过"
```

---

### Task 8: Phase 8 — Archive 收尾

- [ ] **Step 1: 运行 openspec archive 合并 delta spec**

```powershell
openspec archive spec-document-migration
```

预期：delta spec 合并到 `openspec/specs/`，change 标记为已归档。

- [ ] **Step 2: 运行 governance verify full 作为 CI 级验证**

```powershell
.venv\Scripts\python.exe -m scripts.research.governance verify full
```

预期：全部检查通过。如有失败，根据失败项决定修复或记录偏差。

- [ ] **Step 3: 最终 git status 检查**

```powershell
git status
```

确认：
- `docs/` 下无残留空目录
- `openspec/specs/` 包含 12 个 capability spec
- `openspec/changes/archive/` 包含所有归档条目
- 无未追踪的临时文件

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "迁移 Phase 8: Archive 收尾 — openspec archive + governance verify full 通过"
```

---

### 完成后验证清单

全部 8 个 Phase 执行完毕后，逐一确认：

- [ ] `openspec/specs/` 包含 12 个 capability 目录，每个含 `spec.md`
- [ ] `openspec/changes/archive/` 包含：
  - 10 个 `adr-NNNN-*/` 目录（极简归档：proposal.md + design.md）
  - 9 个 design 归档目录（标准归档：proposal.md + design.md + tasks.md）
  - 3 个 superpowers 归档目录（标准归档）
  - 1 个 architecture 归档目录 (research-platform-architecture)
  - 1 个本 change 自归档目录 (spec-document-migration)
- [ ] `docs/adr/`、`docs/design/`、`docs/superpowers/`、`docs/architecture/` 已删除
- [ ] `docs/joinquant-api/` 存在（原 joinquant-data 重命名）
- [ ] `docs/reference/cc-switch-cli.md` 存在
- [ ] `.local/governance/exceptions/active-waivers.yaml` 存在
- [ ] `.local/governance/quota-ledger/` 包含全部 10 个 quota JSON
- [ ] `pathref check` 全绿，无断裂引用
- [ ] `governance verify fast` 通过
- [ ] `docs/rules/`、`docs/guides/`、`docs/agents/` 内容完整（文件数与迁移前一致）
- [ ] `docs/README.md` 目录分层表已更新
- [ ] `docs/indexes/` 已重新生成
