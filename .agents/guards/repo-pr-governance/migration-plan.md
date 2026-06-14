# Migration Plan（迁移计划）

Guard Profile（守卫画像）：repo-pr-governance

- 初始化只写项目级 Guard Runtime（守卫运行时）和 Guard Profile（守卫画像）骨架。
- 不修改被守卫对象。
- 初始化阶段不安装 Hook（钩子）；当前项目已安装 Codex Hook（Codex 钩子），不安装 agent-guard Git Hook（Git 钩子），保留仓库既有 `.githooks/pre-push`。
- 后续按单个 Guard Point（守卫点）独立启用、验证和回滚。
