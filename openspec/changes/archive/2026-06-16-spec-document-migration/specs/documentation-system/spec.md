## ADDED Requirements

### Requirement: Pathref 引用规范

文档系统 SHALL 要求 Markdown 内部文件引用使用"可点击链接 + `pathref` 注释"双轨格式，确保机器可校验。

#### Scenario: 文件引用

- **WHEN** 文档中需要引用另一个仓库内文件
- **THEN** 系统使用 `[文件名](相对路径) ` 格式，允许 `scripts.tools.path_tools.refactor check` 校验引用有效性

### Requirement: 文档报告索引

系统 SHALL 通过 `DocsIndexer` 自动扫描仓库 Markdown 文档，生成 `docs/indexes/` 下的 JSON 和 Markdown 格式索引。

#### Scenario: 索引生成

- **WHEN** 运行 `scripts.research.docs index`
- **THEN** 系统生成 `docs_catalog.json`、`reports_catalog.json`、`datasets_catalog.json`、`variants_catalog.json` 及对应的 Markdown 可读版本
