---
name: quant-pr-workflow
description: 在 D:\My Project\Quant Trading 中处理 PR 准备、分支入主干、主干保护、PR review 证据、Codex review 等待、分支清理或相关治理检查时使用。
---

# Quant PR Workflow

本技能是薄入口。不要在这里复制 PR 规则正文；执行前先读取仓库规则。

## 必读规则

当 `cwd` 是 `D:\My Project\Quant Trading` 时，先读：

- `docs/rules/pr-workflow.md`
- 做 review 前读 `docs/rules/review-guidelines.md`
- 声明门禁或治理保证前读 `docs/rules/governance.md`

## 执行规则

- PR 准备优先使用 `make pr-ready TITLE="<PR标题>"` 或 `scripts.research.governance.pr_flow`。
- 规则文档是事实来源；当前代码和测试是验证证据。
- 不要把功能分支本地合入 `main`。
- 不要伪造安全 review、交叉 review 或官方 Codex review 结论。
- 如果规则和代码不一致，先说明冲突并验证，再继续。

## 验证

在声明 PR 流程已准备好或安全前，按当前规则文档运行相关仓库检查，并说明无法验证的部分。
