# ADR 0003: Governance Gate 和主干保护

## 状态

Accepted

## 背景

本仓库已有治理审计、pathref 校验、本地 hook 和 GitHub workflow。为了防止长期规则漂移，这些检查需要成为进入主干的硬门禁，而不是可选提醒。

GitHub Free 的私有仓库中，远端 branch protection / rulesets 可能不生效。因此主干保护不能只依赖 GitHub 远端设置，还需要把可执行门禁放进仓库代码。

## 决策

- `scripts.research.governance gate` 是本地 hook 和 CI 的统一门禁。
- GitHub 主干保护必须禁止直接 push 和 force push。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push`，在本地阻断直接推送 `main` / `master`。
- `.githooks/reference-transaction` 必须阻断本地 `main` / `master` ref 更新；PR 在 GitHub 云端合并后，本地主干只能用带审计说明的 fast-forward 同步到 `origin/main`。
- PR 必须通过 required checks。
- 关键路径必须由 CODEOWNERS 覆盖并经过 owner review。
- waiver 必须有 owner、批准人、过期时间和迁移计划。
- scheduled drift audit 定期检查规则系统本身是否漂移。

## 影响

在远端保护可用时，最终合并权威是 CI required checks、branch protection 和 CODEOWNER review。在 GitHub Free 私有仓库中，代码化的 `pre-push` 是本地强门禁，CI 是事后审计；紧急绕过必须显式设置环境变量并留下审计说明。PR 合并后的本地主干同步只接受 `origin/main` 的 fast-forward，不接受本地功能分支合并。
