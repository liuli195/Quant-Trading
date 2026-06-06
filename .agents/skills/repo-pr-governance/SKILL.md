---
name: repo-pr-governance
description: 准备进入主干的 PR、review 证据、required checks、Codex review、主干保护和分支清理时使用。
---

# Repo PR Governance

本技能负责 PR 准备、review 证据、required checks、主干保护、Codex review 等待和分支清理。

## 必读规则

- `AGENTS.md` — 仓库通用入口和核心规则（含「规则优先」元规则）
- `docs/rules/pr-workflow.md`
- `docs/rules/review-guidelines.md`
- `docs/rules/governance.md`

## 执行规则

- 不把功能分支本地合入 `main`。
- 不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review。
- `gh` CLI 默认按仓库规则提权执行。
- `pr-submit is not a sub-agent dispatcher`：它只校验 PR Flow fragments，缺失时输出 `DISPATCH_REQUIRED`。
- `repo-pr-governance wrapper for $review`：主 agent 使用本技能作为 `$review` 的轻量包装器；不修改 `$review` 技能，不复制完整提示词，不新增包装技能。
- `target spec wins`：当目标 Issue/PRD/spec 与旧规则或 ADR 冲突时，review finding 归类为 rule/ADR drift；规则或 ADR 修改仍必须先获得用户显式授权。
- 看到 pre-push 输出 local review fragments freshness 的 stale diff 提醒后，不得直接运行 `pr-submit`；必须先重新 review / 重新映射 fragments。same diff 仅 head stale 时，可让 `pr-submit` 按规则刷新 fragment head。

## 本地 Review 包装口径

- 先运行 `$review` 的默认逻辑，让它完成 Standards / Spec 双轴审查。
- 有 PR Flow Issue refs 时，只补充 spec hint：`closes = primary spec`，`reference = background`。
- `no Issue refs means default $review`：无 Issue refs 或 no-Issue 时，不补 spec hint，完全走 `$review` 默认逻辑。
- 主 agent 读取 `$review` 文本结论后，只把结果映射为 `.local/ai-review/fragments/standards.json` 和 `.local/ai-review/fragments/spec.json`。
- P0/P1 finding 必须映射 `status=open|fixed|false_positive`；`fixed` 写 current head/diff 下的 `evidence`，`false_positive` 写 `rationale`，不得用空 findings 吞掉 blocker。
- Security review 独立执行并写 `.local/ai-review/fragments/security.json`；不得用 `$review` 替代。security fragment 顶层写 `security_review.tool`；未使用 `codex-security` 时写 `security_review.fallback_reason`。
- 如果缺少可结构化映射的结论，继续停在 `DISPATCH_REQUIRED`，不要从聊天总结推断通过。

## 推荐命令

```powershell
make pr-submit TITLE="<PR标题>"
make pr-resolve-threads THREADS="<thread-id> [<thread-id>...]"
```
