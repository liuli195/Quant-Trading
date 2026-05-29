# PR #21/#22 流程问题复盘

本文记录 PR #21 `重构仓库 Skill 所有权治理` 以及后续 PR #22 `docs-pr21-flow-problems` 从提交、Review、required checks、合并主干到分支清理的流程问题。结论来自 GitHub PR comments、workflow runs、review threads、本地 git log、PR 自动化输出和仓库规则。

关联规则和实现入口：

- [pr-workflow.md](../rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->：PR、主干同步、分支清理规则。
- [review-guidelines.md](../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->：本地 AI review、Codex Review 和 PR 证据规则。
- [governance.md](../rules/governance.md) <!-- pathref: docs/rules/governance.md -->：required checks、hooks 和治理门禁。
- [pr_flow.py](../../scripts/research/governance/pr_flow.py) <!-- pathref: scripts/research/governance/pr_flow.py -->：本地 PR 自动化状态机。
- [pr_review_evidence.py](../../scripts/research/governance/pr_review_evidence.py) <!-- pathref: scripts/research/governance/pr_review_evidence.py -->：PR 证据校验。
- [skill_ownership.py](../../scripts/research/governance/skill_ownership.py) <!-- pathref: scripts/research/governance/skill_ownership.py -->：Skill ownership 治理校验。

优先级口径：P0 是合并硬阻断或规则口径冲突；P1 是需要人工介入或明显拖慢流程的问题；P2 是效率优化项。

| 优先级 | 类别 | 问题 | 遇到次数 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | 阻断/规则冲突 | 未 resolved review thread 阻断合并 | PR #21：3 个 P2 thread；PR #22：5 个 Codex thread | 代码规则曾允许 P2 有条件保留，`pr_flow` 也更关注 P0/P1；但 GitHub ruleset 按 review thread 是否 resolved 阻断合并，不按 P1/P2 区分。PR #22 中部分 outdated thread 也需要 resolve 后才能合并。 | 是。本分支已同步 `review-guidelines.md`、`governance.md`、`pr-workflow.md`、`pr_flow`、`pr-review-evidence` 和 `Codex Review Monitor`：只要 ruleset 要求 conversation resolution，任何未 resolved review thread 都进入阻断状态。 | 无。 |
| P0 | 阻断/规则冲突 | required check 被 workflow `job.if` 跳过后阻断合并 | PR #22：1 次 | `pr-review-evidence` 在某些路径变化下被 job-level `if` 跳过，GitHub required check 看到的是 skipped，不是 success，导致 ruleset 阻断。 | 是。`11223ba` 改为 job 始终运行、内部 no-op success，并增加治理审计阻断 required job 使用 job-level `if`。 | 无。 |
| P0 | 阻断 | Codex Review P1 必须修复后继续 | PR #21：6 个 P1；PR #22：5 个 P1 | PR #21 的 `skill_ownership` 门禁缺口和 PR #22 的增量治理路径判定、缓存、删除文件、workflow 触发范围等问题都属于会让错误进入主干的 P1，必须改代码和测试后才能继续。 | 是。PR #21 用 `3e6e295` 增加门禁和回归测试；PR #22 用 `f01686b` 修复增量治理 P1 并补测试。 | 无。 |
| P1 | 阻断/效率 | PR body 或 `pr-review-evidence` 当前 head 证据不同步 | PR #21：1 次；PR #22：3 轮 | required check 要求 PR body 中的 Codex trigger、completion、head 和 review 结论匹配当前 head。两次 PR 都出现过代码已修、review 已完成，但 PR body 证据仍落后，导致 `pr-review-evidence` 失败或需要重新写 evidence。 | 部分。PR #21 的 trigger contract 在 `9b6f24e` 修复；PR #22 的当前 head 证据最终由 `pr_flow ready` 写回并通过。自动推进仍不完整。 | `pr_flow ready` 在检测到当前 head 已有合格 completion 时自动同步 PR body、必要时 rerun failed checks，并输出明确 stop reason。 |
| P1 | 阻断/规则冲突 | `pr_flow` 旧逻辑与官方 Codex trigger 模板规则不一致 | PR #21：1 次 | 规则要求 trigger 包含当前 PR、当前 head、Review Scope、审查重点，并禁止模板外限制上下文；旧 `pr_flow` 识别过宽，导致 `pr-review-evidence` 判定 trigger 不合格。 | 是。`9b6f24e` 改为复用 `codex_review_contract.is_codex_review_request`，并加回归测试。 | 无。 |
| P1 | 阻断 | CI `pytest --basetemp` 父目录不存在 | PR #22：1 次 | GitHub Actions 中治理测试使用的临时目录父目录没有提前创建，导致 workflow 失败。这不是业务逻辑失败，但会让 required check 阻断合并。 | 是。`71776f5` 在命令准备阶段创建父目录，并补 CI 命令路径测试。 | 无。 |
| P1 | 效率/规则冲突 | GitHub 合并提示要求 auto-merge，但仓库禁用 auto-merge | PR #22：1 次合并尝试链路 | `gh pr merge --match-head-commit` 返回需要 `--auto`，但 `--auto` 又因仓库禁用 auto-merge 失败。真正阻断原因仍要继续查 ruleset、threads 和 checks。 | 否。 | `pr_flow diagnose` 直接读取 merge state、ruleset blocker、required checks 和 review threads；仓库禁用 auto-merge 时不要把 `--auto` 作为建议路径。 |
| P1 | 阻断/效率 | `.git` 权限或 lock 问题导致提交、分支清理需要提权 | PR #21：1 次分支删除；PR #22：1 次提交/index 写入 | PR #21 本地删分支时无法创建 `.git/refs/...lock`；PR #22 提交阶段也遇到 `.git/index.lock` 权限边界。问题来自本机环境，不是代码。 | 否。环境问题仍可能复现。 | 增加 `pr_flow cleanup` 或 `make pr-cleanup`：自动执行 fetch、切 main、受控 fast-forward、删本地和远端分支，并在 `.git` lock 权限失败时给出固定提权路径。 |
| P1 | 效率 | 网络/API/EOF/TLS 偶发失败需要重试 | PR #21：1 次；PR #22：2 次 | `gh` 或 GitHub API 读取 comments、PR body、workflow 状态时偶发 EOF/TLS/读取失败。失败不是代码或规则问题，但会中断自动流程并拖慢判断。 | 部分。`pr_flow` 已有 fail-closed 方向，但重试和分类还弱。 | 对 GitHub API、GraphQL、`gh` 读取加有限重试、退避和清晰分类：网络异常走 `EXCEPTION_REQUIRED`，不要混成 review blocker。 |
| P1 | 效率/规则冲突 | `pr_flow ready` 不能完整替代排障入口 | PR #21：1 轮；PR #22：4 轮 | 规则希望 `pr_flow ready` 拥有 wait loop，但实际仍需要手工查 GitHub comments、review threads、workflow runs、logs、mergeStateStatus 才能判断下一步。 | 是。本分支新增 `pr_flow diagnose --pr <number>` 和 `make pr-diagnose PR=<number>`，汇总 head、PR body evidence、latest trigger、completion、threads、required checks、mergeStateStatus 和 reviewDecision，并给出下一步机器状态。 | 无。 |
| P2 | 效率 | 官方 Codex Review 多轮触发 | PR #21：4 个 head；PR #22：4 个 head | 大 PR 加后续修复会不断产生新 head，每次都要等待 Codex Review 和证据回写。PR #21 head 包括 `d3bd995`、`3e6e295`、`9b6f24e`、`794d307`；PR #22 head 包括 `1dd1ceb`、`f01686b`、`71776f5`、`11223ba`。 | 部分。发现的问题已转成测试；但大 PR 多轮 review 仍会慢。 | 后续按实施计划拆更小 PR：核心门禁、owner 迁移、兼容入口删除、流程修复分开；每个 PR 缩小 review scope。 |
| P2 | 效率 | required checks 多次重跑 | PR #21：多轮；PR #22：至少 2 个失败 run 需要 rerun | `Research Governance`、`pr-review-evidence`、`Codex Review Monitor` 需要跟当前 head 对齐。PR body stale、旧失败 run、skipped required check 都会造成重复等待。 | 部分。`11223ba` 已解决 skipped required check；head-specific evidence 自动推进还不够。 | 把"当前 head trigger -> completion -> PR body -> rerun checks"做成一个自动状态循环，并在旧 run 和当前 head 不一致时明确提示。 |
| P2 | 效率 | 本地验证重复成本高 | PR #21：1 条完整验证链；PR #22：多轮 fast/full/专项测试 | P1/P2 修复后反复跑 governance tests、pathref、mypy、governance gate、pre-commit/pre-push 或 `verify full`。质量上合理，但人工选择命令组合和等待时间都偏高。 | 部分。PR #22 已引入增量治理验证入口，但合并前仍需要 full 证据。 | `pr_flow ready` 自动选择受影响验证和最终 full 验证，记录证据，避免重复手工拼命令。 |

## 后续建议

1. 已补 `pr_flow diagnose`，解决排障入口分散的问题。
2. 已同步规则口径：如果仓库要求 review thread 全 resolved，就不能把带未解决 thread 的 P2/outdated thread 视为可保留。
3. 再补 `pr_flow cleanup`，把合并后的本地同步和分支清理固定成自动流程。
4. 继续收敛 `pr_flow ready` 的 head-specific evidence、failed checks rerun 和网络重试逻辑。
