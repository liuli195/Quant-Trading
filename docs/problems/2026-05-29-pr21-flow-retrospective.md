# PR #21 流程问题复盘

本文记录 PR #21 `重构仓库 Skill 所有权治理` 从提交、Review、required checks 到合并主干的流程问题。结论来自 GitHub PR comments、workflow runs、review threads、本地 git log 和仓库规则。

关联规则和实现入口：

- [pr-workflow.md](../rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->：PR、主干同步、分支清理规则。
- [review-guidelines.md](../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->：本地 AI review、Codex Review 和 PR 证据规则。
- [governance.md](../rules/governance.md) <!-- pathref: docs/rules/governance.md -->：required checks、hooks 和治理门禁。
- [pr_flow.py](../../scripts/research/governance/pr_flow.py) <!-- pathref: scripts/research/governance/pr_flow.py -->：本地 PR 自动化状态机。
- [pr_review_evidence.py](../../scripts/research/governance/pr_review_evidence.py) <!-- pathref: scripts/research/governance/pr_review_evidence.py -->：PR 证据校验。
- [skill_ownership.py](../../scripts/research/governance/skill_ownership.py) <!-- pathref: scripts/research/governance/skill_ownership.py -->：Skill ownership 治理校验。

| 类别 | 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- | --- |
| 阻断 | 首轮 Codex Review 报 6 个 P1 | `skill_ownership` 门禁缺口会让未登记 owner Skill、失效 `owned_scripts`、缺同名 Claude adapter、缺 frontmatter、非 active 必需 owner、owner 正文缺规则或命令等问题进入主干。必须改代码和测试后才能继续。 | 是。`3e6e295` 增加门禁和回归测试。 | 无。 |
| 阻断 | `pr-review-evidence` 报 Codex 触发证据不合格 | 失败不是 Skill 业务代码，而是 PR 自动化证据链问题：`pr_flow` 曾接受非严格模板的 `@codex review`，但 `pr-review-evidence` 要求固定 contract，导致找不到合格 trigger 或 completion 不匹配最新 trigger。 | 是。`9b6f24e` 改为复用 `codex_review_contract.is_codex_review_request`，并加回归测试。 | 无。 |
| 阻断 | 第二轮 Review 出 3 个 P2 后仍无法合并 | 代码规则允许 P2 有条件保留，但 GitHub ruleset 要求 review thread 全部 resolved。实际合并被 review-thread resolution 阻断，所以 P2 也必须处理或明确 resolve。 | 对 PR #21 是。`794d307` 修复 3 个 P2 并 resolved threads。流程规则层面未完全解决。 | 更新规则和 `pr_flow`：只要 GitHub ruleset 要求 thread resolution，任何未 resolved 且未 outdated 的 review thread 都进入 `REPLY_OR_FIX_REQUIRED`，不只看 P0/P1。 |
| 阻断 | PR body 证据落后于当前 head | 最终 head 是 `794d307`，但有一次 `pr-review-evidence` 运行时 PR body 还指向旧 Codex completion，导致 required check 失败。需要 rerun 自动化把当前 head 的 review 链接写回 PR body。 | 部分。当前 PR 已修正并通过；自动化仍需要更顺滑。 | `pr_flow ready` 在检测到当前 head 已有合格 completion 时，应自动同步 PR body 并触发或等待最新 required check，而不是让人判断下一步。 |
| 阻断 | 本地分支清理遇到 `.git` 权限问题 | `git branch -d refactor-skill-rules-commands` 因无法创建 `.git/refs/...lock` 失败，提权后成功。这是本机权限问题，不是代码问题。 | 否。环境问题仍可能复现。 | 增加 `pr_flow cleanup` 或 `make pr-cleanup`：自动执行 fetch、切 main、受控 fast-forward、删本地和远端分支，并在 `.git` lock 权限失败时给出固定提权路径。 |
| 效率 | 官方 Codex Review 触发了多轮 | 本 PR 先后触发 `d3bd995`、`3e6e295`、`9b6f24e`、`794d307` 的 review。大 PR 加修复后重新取证导致等待时间明显增加。 | 部分。已发现的问题已转成测试；但大 PR 多轮 review 仍会慢。 | 后续按实施计划拆更小 PR：核心门禁、owner 迁移、兼容入口删除分开；每个 PR 缩小 Review Scope。 |
| 效率 | required checks 多次重跑 | `Research Governance` 多次成功，但 `pr-review-evidence` 因证据链或 PR body 不匹配反复失败，消耗等待时间。 | 部分。模板识别 bug 已修；head-specific evidence 自动推进还不够。 | 把“当前 head trigger -> completion -> PR body -> rerun checks”做成一个自动状态循环，并输出明确 stop reason。 |
| 效率 | 本地验证重复成本高 | P2 修复后跑了 governance tests、全 governance tests、skill ownership、pathref、mypy、governance gate、pre-commit 等完整链路。质量上合理，但耗时大。 | 否。当前靠人工选择命令组合。 | 增加分层命令：`pr-verify-fast` 跑受影响测试，`pr-verify-full` 跑合并前全套；`pr_flow ready` 自动选择并记录证据。 |
| 效率 | 网络/API/TLS 偶发失败需要重试 | 会话中 `pr_flow ready` 有 GitHub/API 读取失败或握手类问题，需要重跑；这类失败不是代码或规则问题，但会拖慢流程。 | 部分。已有 fail-closed 思路，但重试体验还弱。 | 对 GitHub API、GraphQL、`gh` 读取加有限重试、退避和清晰分类：网络异常走 `EXCEPTION_REQUIRED`，不要混成 review blocker。 |
| 规则冲突 | “P2 可保留”与“review threads 必须 resolved”冲突 | 文档里 P2 可作为保留项，但 GitHub ruleset 无法按 P2/P1 区分，只看 thread 是否 resolved。所以只要 P2 是 inline thread，也会阻断合并。 | 否。PR #21 已处理，但规则仍需对齐。 | 修改 `review-guidelines.md` 和 `pr-workflow.md`：P2 可保留只适用于无未解决 GitHub thread 的情况；若是 thread，必须修复或回复后 resolve。 |
| 规则冲突 | `pr_flow` 旧逻辑与官方 Codex trigger 模板规则冲突 | 规则要求 trigger 包含当前 PR、当前 head、Review Scope、审查重点，并禁止模板外限制上下文；旧 `pr_flow` 识别过宽。 | 是。`9b6f24e` 已持久化修复。 | 无。 |
| 规则冲突 | “日常由 `pr_flow ready` 拥有 wait loop”与实际排障路径不一致 | 规则希望自动化推进，但本次仍需要多次用 GitHub connector 或 `gh` 检查 comments、threads、workflow runs、logs 来判断原因。 | 否。工具能力还没完全覆盖排障。 | 增加 `pr_flow diagnose --pr <number>`：汇总 head、PR body evidence、latest trigger、completion、threads、required checks、mergeStateStatus，并给出下一步机器状态。 |

## 后续建议

1. 先补 `pr_flow diagnose`，解决排障入口分散的问题。
2. 再补 `pr_flow cleanup`，把合并后的本地同步和分支清理固定成自动流程。
3. 同步规则口径：如果仓库要求 review thread 全 resolved，就不能把带未解决 thread 的 P2 视为可保留。
