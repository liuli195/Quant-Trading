# 云端交接规则

## 只有以下条件同时满足，才建议送云

1. fast run 已经明显缩小候选范围；
2. full run 的 `cloud_candidates.csv` 非空；
3. 候选通过 holdout 与分段稳定性门槛；
4. 若依赖 replay，本地校准已经通过；
5. 本轮上云候选数量已经被压缩到 baseline + 少量变体。

## 交接动作

1. 先运行 `scripts.research.cli handoff-cloud`。
2. 若需要正式 A/B，委托 `jq-ab-test` 生成和校验配置。
3. 若只需执行已确认配置，委托 `jq-run`。
4. 云端结果回来后，委托 `jq-analyze`，再回到 `jq-research` 做结论整合。

## 不送云的情况

- 本地证据还只是噪声；
- shortlist 本身都不稳定；
- 研究问题仍能继续在本地以低成本扩大搜索；
- 本地 export 契约不完整，导致 replay 可信度不足。
