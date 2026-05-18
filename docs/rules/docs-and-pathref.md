# 文档和 Pathref 规则

## MUST

- Markdown 内部文件引用使用“可点击链接 + `pathref` 注释”的双轨格式。
- 新增或移动文档后必须运行 `scripts.tools.path_tools.refactor check`。
- 新报告默认进入文档报告索引。
- 规则文档和 ADR 必须保持可机器校验的内部链接。

## SHOULD

- 设计文档优先写清目标、已知事实、边界、假设、实验、阈值、产出和执行顺序。
- 报告结论应连接到数据快照、run manifest、表格、回测 run 或变体 ID。
- 目录迁移时同时更新 docs index 和 pathref。

## MAY

- 历史报告不强制迁移；只修复仍被引用或影响当前决策的链接。
