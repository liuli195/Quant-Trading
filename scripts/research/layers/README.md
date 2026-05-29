# 本地研究平台工具分层索引

本目录按平台5层核心整理工具视图，内容由工具注册表生成。

生成命令：
- Windows：`.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry write-layers`
- POSIX：`.venv/bin/python -m scripts.research.registry.tool_registry write-layers`

| 层 | 文件 | 职责 | 工具数 |
| --- | --- | --- | ---: |
| 第一层：策略库 | [strategy_library.md](strategy_library.md) <!-- pathref: scripts/research/layers/strategy_library.md --> | 策略结构、变体定义、物化和合并计划。 | 1 |
| 第二层：数据中心 | [data_center.md](data_center.md) <!-- pathref: scripts/research/layers/data_center.md --> | 本地不可变数据集、快照、目录和数据导入。 | 1 |
| 第三层：流程编排层 | [workflow_orchestration.md](workflow_orchestration.md) <!-- pathref: scripts/research/layers/workflow_orchestration.md --> | 研究项目生命周期、流程模板、插件调度和聚宽自动化。 | 4 |
| 第四层：研究工具库 | [research_toolkit.md](research_toolkit.md) <!-- pathref: scripts/research/layers/research_toolkit.md --> | 可复用研究计算库和专题研究工具。 | 9 |
| 第五层：文档报告库 | [docs_reports.md](docs_reports.md) <!-- pathref: scripts/research/layers/docs_reports.md --> | 报告、索引、证据链接和文档产出。 | 1 |
| 横向治理：注册与审计 | [governance.md](governance.md) <!-- pathref: scripts/research/layers/governance.md --> | 跨层注册、审计、路径引用和提交门禁。 | 6 |

源码仍按库维护，分层目录只提供结构化索引，避免同一工具在物理目录和库目录之间重复实现。
