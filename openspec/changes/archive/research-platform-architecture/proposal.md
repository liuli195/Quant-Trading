# 研究平台架构

## Why
定义量化研究平台的总体架构：5 层结构（策略库、数据中心、流程编排层、研究工具库、文档报告库）。Git 只管理代码结构变体；参数变体默认用 variant_id 和配置文件登记。

## What Changes
- 策略库：VariantRegistry、StrategyMaterializer、StructuralBranchManager、VariantMergeManager
- 数据中心：DatasetRegistry、BacktestRunImporter、DataViewLoader、压缩存储和 pointer 机制
- 流程编排层：init → run → promote → full review → handoff-cloud → cloud confirmation
- 研究工具库：MetricToolkit、RobustnessToolkit、ReplayAdapter、ReportPrimitives
- 文档报告库：DocsIndexer、ReportRegistry、EvidenceLinker、统一索引
- 治理审计：工具登记、README/文档/测试锚点、CLI help、workflow template schema

## Impact
内容已被 openspec/specs/research-platform 等 capability spec 覆盖。新增云端回测抓取完成后默认登记到数据中心，大文件压缩保存不进入 Git。

---
source: docs/architecture/research-platform-architecture.md
