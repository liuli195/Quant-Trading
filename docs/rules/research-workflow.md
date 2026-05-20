# 研究流程规则

## MUST

- 本地研究优先使用 `scripts.research.cli` 的 `init/run/promote/resume/handoff-cloud/status` 流程。
- 新数据快照必须进入 `research_datasets/catalog.json`。
- 新回测数据必须进入数据中心快照；`backtest_runs/<run_id>/` 只保留轻量索引、报告和指向数据中心的 pointer。
- 回测原始文件必须按三类处理：
  - 明确重复数据：`summary_metrics.json`、`tabs_raw/daily_returns.md` 压缩进数据中心，RUN 只保留 pointer。
  - 数据中心派生冗余：保留 `data/data.parquet`，不再生成 `data/daily_returns.parquet` 和 `views/daily_returns.csv`。
  - RUN 明细大文件：`positioninfo.md`、`transactioninfo.md`、`balances.md`、`period_risks.md`、`logs.md` 压缩进数据中心，RUN 只保留 pointer。
- 数据中心压缩原始回测文件本地保留，不进入 Git；完整性由 `dataset.json` 中的原始 SHA256、压缩 SHA256 和文件清单记录。
- 新报告必须进入文档报告索引，并保留可追溯证据。
- 本地 replay 结论必须区分“方向性支持”和“准备写回默认参数”。
- 云端回测和 A/B 结果必须保留 run、manifest、audit log 或报告路径。

## SHOULD

- 多候选研究先用本地 fast/full 漏斗缩小范围，再消耗云端额度。
- 复用 `scripts.research.research_core` 的指标、稳健性、回放和报告基础能力。
- 分析脚本读取回测收益、审计日志或原始表时，优先走数据中心 loader 或支持 pointer 的公共解析函数。
- 结构变体进入合并前应完成云端确认，合并后主策略还要重新确认。

## MAY

- 历史 `backtest_runs/` 可用 `scripts.research.datasets migrate-backtest-runs --compact-source` 批量迁移并瘦身。
