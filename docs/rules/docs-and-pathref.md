# 文档和 Pathref 规则

## MUST

### Pathref

- Markdown 内部文件引用使用“可点击链接 + `pathref` 注释”。
- 新增、移动、重命名文档后运行 `scripts.tools.path_tools.refactor check`。
- ADR 已归档到 openspec/changes/archive/，索引由 openspec archive 命令管理。
- 新报告默认进入文档报告索引。
- 规则文档和 ADR 必须保持可机器校验的内部链接。

## SHOULD

- 报告结论应连接到数据快照、run manifest、表格、回测 run 或变体 ID。
- 目录迁移必须同步 docs index、报告索引和 pathref。

## MAY

- 历史报告不强制迁移；只修复仍被引用或影响当前决策的链接。
