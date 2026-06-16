# ADR 0003: Governance Gate 和主干保护

## Why
本仓库已有治理审计、pathref 校验、本地 hook 和 GitHub workflow。为了防止长期规则漂移，这些检查需要成为进入主干的硬门禁。GitHub Free 的私有仓库中远端 branch protection / rulesets 可能不生效，因此需要代码化门禁补充。

## What Changes
- 治理门禁为本地 hook 和 CI 的统一入口
- GitHub 主干保护必须禁止直接 push 和 force push
- .githooks/pre-push 必须调用代码化主干保护
- 手工直写主干必须通过单次 wrapper 授权
- PR 必须通过 required checks
- waiver 必须有 owner、批准人、过期时间和迁移计划

## Impact
在远端保护可用时，最终合并权威是 CI required checks、branch protection / ruleset。GitHub Free 场景下代码化 pre-push 是本地强门禁，CI 是事后审计。

---
source: docs/adr/0003-governance-gate-and-main-branch-protection.md
migration: 历史 ADR 迁移 — 极简归档
