# 本地优先研究流程

本流程的核心不是把研究“归档得更整齐”，而是把高频探索尽量留在本地完成：同一份数据快照完成一次预处理后，后续高频扫描应优先走秒级快路径，只把最有价值的少量候选送往云端确认。

## 标准生命周期

1. 用 `jq-research` 或 `scripts.research.cli init` 创建研究项目。
2. 绑定不可变数据快照，或在过渡期绑定已有原始数据。
3. 运行 `fast mode` 做大规模本地粗筛。
4. 用 `promote` 将 shortlist 升级到 `full mode` 做留出集、分段、bootstrap 等精筛。
5. 只有通过本地门槛的候选才进入 `handoff-cloud`。
6. 云端只负责确认，不再承担大规模探索。

中断后可用 `resume --project-dir ... --run-id ...` 复用已保存的运行请求。

参数变体默认登记为 `variant_id`，不新建 Git 分支；结构变体需要先生成分支计划，只有用户显式授权后才创建分支、合并或写回默认参数。

正式流程模板保存在 [workflows/templates](../../scripts/research/workflows/templates) <!-- pathref: scripts/research/workflows/templates -->，治理审计会校验模板 schema。

## 计算分层

| 层级 | 目标 |
| --- | --- |
| 原始数据层 | 保存不可变快照与原始导出 |
| 派生特征层 | 复用价格矩阵、forward return、因子序列等重计算结果 |
| 研究执行层 | 用 scan / replay / robustness 三类能力缩小候选范围 |

### `generic` 模板

- 最基础的模板，提供标准项目骨架和数据契约
- 不预设分析流程，不强制候选漏斗
- 适用于诊断型分析、数据探索、ad-hoc 研究
- 后续可随时引入专业模板的能力

## 模式定义

### `fast mode`

- 热启动目标：`<= 3s`
- 只做必要校验、粗筛、排序和初步决策
- 不默认生成完整报告，也不默认跑高成本 bootstrap

### `full mode`

- 只对 shortlist 做完整复核
- 默认包含 holdout、segment stability、bootstrap 和云端交接材料
- 目标是把候选压缩到适合上云确认的极小集合

## 命令示例

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli init `
  --project-dir strategies\etf_factor_rotation\reports\research\demo_factor_scan `
  --strategy etf_factor_rotation `
  --project demo_factor_scan `
  --template factor_scan `
  --raw-data strategies\etf_factor_rotation\reports\research\window_heterogeneity\inputs\raw\etf_window_research_prices.json

.\.venv\Scripts\python.exe -m scripts.research.cli run `
  --project-dir strategies\etf_factor_rotation\reports\research\demo_factor_scan `
  --run-id 2026-05-17-fast `
  --mode fast

.\.venv\Scripts\python.exe -m scripts.research.cli promote `
  --project-dir strategies\etf_factor_rotation\reports\research\demo_factor_scan `
  --fast-run-id 2026-05-17-fast `
  --full-run-id 2026-05-17-full `
  --top-k 10
```

## 研究判定

- `local_exact`：本地可精确回答，例如因子窗口、阈值与收益响应。
- `local_replayable`：基于 baseline export 可做可信 counterfactual，例如局部权重形状变化。
- `cloud_only`：本地无法可靠复现，例如执行逻辑重构或未导出的外部依赖。

## 关键产物

- `tables/candidate_ranking.csv`
- `tables/discarded_candidates.csv`
- `tables/shortlist.csv`
- `tables/full_candidate_review.csv`
- `tables/cloud_candidates.csv`
- `tables/benchmark.json`
- `manifest.json`
- `status.json`

## `robustness_check` 示例

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli init `
  --project-dir strategies\etf_factor_rotation\reports\research\demo_robustness `
  --strategy etf_factor_rotation `
  --project demo_robustness `
  --template robustness_check `
  --baseline-returns strategies\etf_factor_rotation\backtest_runs\baseline\tabs_raw\daily_returns.md `
  --variant-return variant-a=strategies\etf_factor_rotation\backtest_runs\variant-a\tabs_raw\daily_returns.md
```

`robustness_check` 用于已有真实收益路径后的本地复核；`parameter_followup` 由平台统一编排、由策略专用 adapter 实现 replay 细节。当前仓库内置了 `momentum_tilt` 参考 adapter，后续其他策略按同一边界扩展。

`parameter_followup` 的晋级还受校准结果约束：如果 replay 无法通过已知云端变体校准，`full mode` 可以继续给出诊断，但不得生成 `cloud_candidates`。

## 相关入口

- 研究平台 CLI：[cli.py](../../scripts/research/cli.py) <!-- pathref: scripts/research/cli.py -->
- 研究数据集 CLI：[datasets.py](../../scripts/research/datasets.py) <!-- pathref: scripts/research/datasets.py -->
- 策略变体 CLI：[variants.py](../../scripts/research/variants.py) <!-- pathref: scripts/research/variants.py -->
- 文档索引 CLI：[docs.py](../../scripts/research/docs.py) <!-- pathref: scripts/research/docs.py -->
- 治理审计：[governance/](../../scripts/research/governance) <!-- pathref: scripts/research/governance -->
- 平台核心实现：[platform/](../../scripts/research/platform) <!-- pathref: scripts/research/platform -->
- 平台架构说明：[research-platform-architecture.md](../architecture/research-platform-architecture.md) <!-- pathref: docs/architecture/research-platform-architecture.md -->
