# JQ Research 工作流

## 默认顺序

1. 把研究问题归类为：
   - `local_exact`
   - `local_replayable`
   - `cloud_only`
2. 如果适合本地研究，优先创建或复用项目，先跑 `fast mode`。
3. 阅读：
   - `candidate_ranking.csv`
   - `discarded_candidates.csv`
   - `shortlist.csv`
4. 只有 shortlist 值得继续时，才运行 `promote` 进入 `full mode`。
5. 读取：
   - `full_candidate_review.csv`
   - `cloud_candidates.csv`
   - `full_decision.json`
6. 只有 `cloud_candidates` 非空，才进入云端交接。
7. 若使用 `generic` 模板，不经过候选漏斗。研究产出直接写入 `runs/<run_id>/`，分析逻辑由独立模块完成。

## 委托关系

| 情况 | 委托 |
| --- | --- |
| 需要本地修策略 | `jq-fix` |
| 需要单次或批量云端回测 | `jq-run` |
| 需要标准回测分析 | `jq-analyze` |
| 需要云端参数扫描 | `jq-param-scan` |
| 需要严格 A/B 确认 | `jq-ab-test` |

## 解释原则

- 优先说明本地已经淘汰了哪些候选，而不是先讨论上云。
- 若本地证据不足，要明确写“未达到送云门槛”，不要把不确定性外包给云端。
- 若属于 `cloud_only`，直接说明本地不能可靠判断，并给出最小云端确认设计。
