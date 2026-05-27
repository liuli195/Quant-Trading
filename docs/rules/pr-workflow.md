# PR 工作流规则

Review 细则见 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->；门禁见 [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->。

## MUST

- 多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支；不得并行写同一 repo-tracked 分支。
- 有可用子 agent 能力时，任务优先分发给子 agent；无能力、只读查询、强串行依赖或权限只在主会话可用时，记录不分发原因；无能力时记录原因和替代证据。
- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权直写主干。
- “合并到主干”默认指创建、更新或准备 PR，不是本地合并 `main`。
- 等待云端 Codex review 时，默认使用 `gh pr checks <PR号或URL> --required --watch --fail-fast --interval 10` 等待 required checks；超时后只做一次 `scripts.research.governance.codex_review_monitor` 手动兜底；不得自行定时轮询 GitHub 原始评论。
- 禁止把功能分支本地合入 `main`；GitHub 合并后的本地同步只能走受控 fast-forward。
- 直写主干必须设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`，且只允许 fast-forward，禁止 reset、删除或 force rewrite。
- PR 在 GitHub 合并后，本地 `main` 先 `git fetch origin main`，再设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并只用 `git merge --ff-only origin/main` 或等价 fast-forward 同步。
- PR 合并授权包含删除已合并提交分支；清理前确认不在该分支，再执行 `git branch -d <branch>` 和 `git push origin --delete <branch>`。远端已自动删除时确认不存在；不得 force delete 掩盖未合并分支。
- 不采用任务登记作为主要协作机制；Git 分支、commit、diff、PR 和 review 承担追踪。
- AI 工具通用入口是 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；[CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 只保留 Claude Code 指针。

## SHOULD

- 分支名使用 ASCII 模板：`agent/<tool>/<topic>`、`research/<strategy>/<topic>`、`fix/<scope>/<issue>`；提交说明使用简体中文。
- 长期研究分支定期 rebase 或关闭。
- 本地共享工作区只用于只读探索、临时验证或单 agent 串行工作。

## MAY

- 简单文档修补可使用短生命周期分支。
- 只读分析不要求创建分支，但不得修改 repo-tracked 文件。
