# 回测数据冗余压缩

## Why
回测数据存在三类冗余：明确重复数据 (daily_returns.md, summary_metrics.json)、数据中心内部派生冗余 (data/daily_returns.parquet, views/daily_returns.csv)、RUN 里的大 Markdown 明细。需建立压缩存储机制降低磁盘占用，同时保持可追溯性。

## What Changes
- 扩展回测 raw 文件清单，将标记文件纳入数据中心压缩保存
- pointer 记录 dataset_id、snapshot_id 和原始/压缩 SHA256
- 裁剪派生冗余：停止生成 data/daily_returns.parquet 和 views/daily_returns.csv
- 新增 migrate-backtest-runs --compact-source 命令

## Impact
数据中心保存可追溯压缩原始快照，RUN 目录只保留轻量 pointer 和报告。常规分析继续读取 Parquet 或统一 loader，追溯原始表时由 loader 解压读取。

---
source: docs/superpowers/plans/2026-05-20-backtest-data-redundancy-compaction.md
