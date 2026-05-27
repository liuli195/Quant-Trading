# 协作规则

## 分支与工作区

- 多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支；不得并行写同一 repo-tracked 分支。
- 分支名使用 ASCII 模板：`agent/<tool>/<topic>`、`research/<strategy>/<topic>`、`fix/<scope>/<issue>`；提交说明使用简体中文。
- 本地共享工作区只用于只读探索、临时验证或单 agent 串行工作。
- 只读分析不要求创建分支，但不得修改 repo-tracked 文件。

## 任务分发

- 有可用子 agent 能力时，任务优先分发给子 agent；无能力、只读查询、强串行依赖或权限只在主会话可用时，记录不分发原因；无能力时记录原因和替代证据。
- 不采用任务登记作为主要协作机制；Git 分支、commit、diff、PR 和 review 承担追踪。
