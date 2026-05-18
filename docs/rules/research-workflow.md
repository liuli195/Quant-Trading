# 研究流程规则

## MUST

- 本地研究优先使用 `scripts.research.cli` 的 `init/run/promote/resume/handoff-cloud/status` 流程。
- 新数据快照必须进入 `research_datasets/catalog.json`。
- 新报告必须进入文档报告索引，并保留可追溯证据。
- 本地 replay 结论必须区分“方向性支持”和“准备写回默认参数”。
- 云端回测和 A/B 结果必须保留 run、manifest、audit log 或报告路径。

## SHOULD

- 多候选研究先用本地 fast/full 漏斗缩小范围，再消耗云端额度。
- 复用 `scripts.research.research_core` 的指标、稳健性、回放和报告基础能力。
- 结构变体进入合并前应完成云端确认，合并后主策略还要重新确认。

## MAY

- 历史 `backtest_runs/` 不强制搬迁；需要复用时再导入数据中心。
