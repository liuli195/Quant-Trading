# PR 工作流规则

Review 细则见 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->；门禁见 [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->。

## 默认入口

- 日常用 `make pr-ready TITLE="<PR标题>"`，等价于 `.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow ready --title "<PR标题>"`。
- `pr-ready` / `pr_flow ready` 是一键 PR 状态机：准备本地 evidence、同步 PR、加必要的 `ai-risk-review` label、触发必要的 `@codex review`，并在当前 head 的官方 review 无 P0/P1 时自动记录真实证据后继续等待 required checks。
- Skills / agents 负责 review 判断和结论；`pr_flow` 只同步结构化证据，不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review；缺本地 review evidence 时必须停止并进入任务分发。
- Git hooks 只守本地不变量：pre-commit 走快速治理门禁，pre-push 和 CI 走完整治理门禁。

## 主干规则

- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权直写主干。
- “合并到主干”默认指创建、更新或准备 PR，不是本地合并 `main`。
- 禁止把功能分支本地合入 `main`；GitHub 合并后的本地同步只能走受控 fast-forward。
- 直写主干或 GitHub 合并后的本地 `main` 同步都必须走受控 fast-forward；前者设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`，后者先 `git fetch origin main`，再设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并用 `git merge --ff-only origin/main` 或等价 fast-forward 同步；禁止 reset、删除或 force rewrite。
- PR 合并授权包含删除已合并提交分支；清理前确认不在该分支，再执行 `git branch -d <branch>` 和 `git push origin --delete <branch>`。远端已自动删除时确认不存在；不得 force delete 掩盖未合并分支。

## Review 和等待

- Review 按 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> 执行。
- `pr-ready` / `pr_flow ready` 负责按 Review 规则推进无问题路径；只有异常处理、任务分发、问题回复三类情况需要人工或 agents 介入。手工排障才单独使用 `gh pr checks <PR号或URL> --required --watch --interval 10` 或 `scripts.research.governance.codex_review_monitor`。
