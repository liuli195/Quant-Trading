## ADDED Requirements

### Requirement: 数据快照登记

数据中心 SHALL 通过 `research_datasets/catalog.json` 集中登记所有可复用数据快照。

#### Scenario: 新快照登记

- **WHEN** 新的回测数据或研究数据准备进入数据中心
- **THEN** 系统在 `catalog.json` 中登记快照元数据，包含原始 SHA256、压缩 SHA256 和文件清单

### Requirement: 回测数据压缩存储

数据中心 SHALL 对回测 run 中的冗余和明细大文件进行压缩存储，run 目录仅保留轻量 pointer 和报告。

#### Scenario: 数据压缩

- **WHEN** 明确重复数据（如 `summary_metrics.json`）和 run 明细大文件（如 `positioninfo.md`）被识别
- **THEN** 系统将其压缩存储在数据中心，run 目录仅保留 pointer 引用
