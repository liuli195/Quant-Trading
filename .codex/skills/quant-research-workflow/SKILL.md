---
name: quant-research-workflow
description: Use when working in D:\My Project\Quant Trading on quant research workflow, local-first research, dataset snapshots, backtest run artifacts, cloud handoff, promotion, replay conclusions, or research report traceability.
---

# Quant Research Workflow

薄入口。不要在这里复制研究流程规则正文；执行前读取仓库规则文档。

## 必读规则

当 `cwd` 是 `D:\My Project\Quant Trading` 时，先读：

- `docs/rules/research-workflow.md`
- 涉及 PR、主干或 review 时再读 `docs/rules/pr-workflow.md`
- 声明门禁或治理保证前再读 `docs/rules/governance.md`

## 执行规则

- 以规则文档为事实来源；当前代码、数据目录和测试结果是验证证据。
- 研究任务优先走仓库现有 CLI、数据中心、报告索引和公共解析能力；常用入口包括 `scripts.research.cli` 和 `scripts.research.governance`。
- 如果规则、代码或现有产物不一致，先说明冲突并验证，再继续。
- 不要把本地 replay 结论包装成云端确认或默认参数写回结论。

## 验证

完成前按当前规则文档运行相关检查；无法验证的部分要明确说明。
