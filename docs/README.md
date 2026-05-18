# 文档入口

`docs/` 根目录只保留文档入口。具体文档按用途放入子目录；仓库级规则入口仍以 [CLAUDE.md](../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 为准。

## 目录分层

| 目录 | 内容 | 入口 |
| --- | --- | --- |
| [rules](rules) <!-- pathref: docs/rules --> | 仓库级规则正文 | [rules/index.md](rules/index.md) <!-- pathref: docs/rules/index.md --> |
| [adr](adr) <!-- pathref: docs/adr --> | 重大治理和架构决策记录 | [0001-rule-source-and-governance-model.md](adr/0001-rule-source-and-governance-model.md) <!-- pathref: docs/adr/0001-rule-source-and-governance-model.md --> |
| [guides](guides) <!-- pathref: docs/guides --> | 日常操作、研究流程、环境说明 | [research-workflow.md](guides/research-workflow.md) <!-- pathref: docs/guides/research-workflow.md --> |
| [architecture](architecture) <!-- pathref: docs/architecture --> | 平台结构和长期架构说明 | [research-platform-architecture.md](architecture/research-platform-architecture.md) <!-- pathref: docs/architecture/research-platform-architecture.md --> |
| [design](design) <!-- pathref: docs/design --> | 实施方案、重构方案、治理方案草案 | [本地研究平台重构技术实施方案.md](design/本地研究平台重构技术实施方案.md) <!-- pathref: docs/design/本地研究平台重构技术实施方案.md --> |
| [reference](reference) <!-- pathref: docs/reference --> | 外部平台资料和分析参考 | [joinquant-api.md](reference/joinquant-api.md) <!-- pathref: docs/reference/joinquant-api.md --> |
| [joinquant-data](joinquant-data) <!-- pathref: docs/joinquant-data --> | 聚宽数据专题资料 | [JQ_场内基金数据.md](joinquant-data/JQ_场内基金数据.md) <!-- pathref: docs/joinquant-data/JQ_场内基金数据.md --> |
| [indexes](indexes) <!-- pathref: docs/indexes --> | 机器生成的文档、报告、数据和变体索引 | [docs_catalog.json](indexes/docs_catalog.json) <!-- pathref: docs/indexes/docs_catalog.json --> |

## 维护约定

- 新增说明型文档优先放入 `guides/`、`architecture/`、`design/` 或 `reference/`。
- 新增或移动文档后运行 `.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check`。
- 文档和报告索引用 `.\.venv\Scripts\python.exe -m scripts.research.docs index` 重新生成。
