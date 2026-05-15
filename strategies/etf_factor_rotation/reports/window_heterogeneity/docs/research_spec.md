# ETF 时间窗异质性研究规格

制定日期：2026-05-15  
执行计划：[2026-05-15-window-heterogeneity-validation-plan.md](../../2026-05-15-window-heterogeneity-validation-plan.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/2026-05-15-window-heterogeneity-validation-plan.md -->  
策略主文件：[etf_factor_rotation.py](../../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->

## 1. 研究边界

### 纳入

- 趋势门槛
- 动量
- 拥挤度子因子

### 不纳入

- 风险平价窗口
- 组合波动率窗口
- RSRS 回归 / 标准化窗口
- 拥挤度长期分位窗口 `CrowdWindow`

## 2. 资产与样本

| 资产 | 代码 |
|---|---|
| 人工智能 ETF | `159819.XSHE` |
| 纳指 ETF | `513100.XSHG` |
| 黄金 ETF | `518880.XSHG` |

| 用途 | 区间 |
|---|---|
| 主评分区间 | `2021-01-01 ~ 2026-04-30` |
| 发现集 | `2021-01-01 ~ 2024-12-31` |
| 留出验证集 | `2025-01-01 ~ 2026-04-30` |
| 分段 1 | `2021-2022` |
| 分段 2 | `2023-2024` |
| 分段 3 | `2025-2026` |

预热历史仅用于计算指标，不纳入评分。

## 3. 数据契约

### 导出字段

| 字段 | 用途 |
|---|---|
| `date` | 交易日索引 |
| `close` | 趋势、动量、拥挤度收益、均线偏离 |
| `high` | 预留给策略对账与后续扩展 |
| `low` | 预留给策略对账与后续扩展 |
| `money` | 成交额拥挤度 |

### 导出结构

原始导出使用 JSON：

```json
{
  "metadata": {
    "strategy": "etf_factor_rotation",
    "score_start": "2021-01-01",
    "score_end": "2026-04-30"
  },
  "calendar": ["2020-12-31", "2021-01-04"],
  "prices": {
    "159819.XSHE": [
      {
        "date": "2020-12-31",
        "close": 1.0,
        "high": 1.01,
        "low": 0.99,
        "money": 1000000.0
      }
    ]
  }
}
```

### 周频锚点

- 采用每个自然周的首个交易日作为信号日。
- 信号只使用信号日前一个交易日已知的数据。
- 前向收益用“信号日前一交易日收盘价 → 未来第 `h` 个交易日收盘价”的代理口径。
- 若前向窗口不完整，则该样本在对应 horizon 下剔除。
- 截至 `2026-05-15`，样本尾部对 `20/40` 日前向收益仍会自然缩短；脚本会保留完整样本、自动剔除尚未成熟的尾部观测。

## 4. 窗口清单

| 模块 | 候选窗口 |
|---|---|
| 趋势 / 动量 | `10, 20, 30, 40, 60, 80, 100, 120, 160` |
| 拥挤度收益窗 | `10, 20, 30, 40, 60, 80, 120` |
| 成交额 / 偏离 / 短波动窗 | `10, 20, 30, 40, 60` |

| 档位 | 定义 |
|---|---|
| 短窗 | `<= 30` |
| 中窗 | `40 ~ 80` |
| 长窗 | `>= 100` |

## 5. 因子定义

| 因子 | 定义 | 主指标 |
|---|---|---|
| 趋势门槛 | `Close_t > MA_t(window)` | 门槛开启收益 - 关闭收益 |
| 动量 | `Close_t / Close_{t-window} - 1` | 高分组收益 - 低分组收益 |
| 拥挤度收益 | 收益率滚动分位高于阈值 | 非高拥挤收益 - 高拥挤收益 |
| 成交额拥挤 | `money` 滚动均值分位高于阈值 | 非高拥挤收益 - 高拥挤收益 |
| 偏离拥挤 | `Close / MA(window) - 1` 分位高于阈值 | 非高拥挤收益 - 高拥挤收益 |
| 波动拥挤 | 短期波动率分位高于阈值 | 非高拥挤收益 - 高拥挤收益 |

统一原则：所有 `benefit` 字段都定义为“越大越好”。

## 6. 默认信号复现口径

需要复现的默认参数：

| 参数 | 默认值 |
|---|---:|
| `MA_long_by_etf` | `[20, 40, 100]` |
| `MomShort` | `20` |
| `MomMid` | `60` |
| `MomLong` | `120` |
| `CrowdRetShort` | `20` |
| `CrowdRetMid` | `60` |
| `AmountMAWindow` | `20` |
| `DeviationMAWindow` | `20` |
| `CrowdVolWindow` | `20` |

对账对象：

- 当前策略代码
- 最近完整回测的 `audit_log.jsonl`
- 深度归因报告中的默认参数结论

## 7. 通过 / 失败判定

### 研究层通过

同时满足：

1. 至少 `2/3` 个方向因子家族出现 ETF 专属偏好。
2. ETF 专属窗口优于共享窗口 control。
3. 留出集不反转。
4. 多数分段中偏好档位稳定。
5. 不是单一年份或单一 ETF 独撑结果。

### 结论分级

| 级别 | 含义 |
|---|---|
| A | 可进入策略确认实验 |
| B | 有现象，但证据不足，继续观察 |
| C | 不支持 ETF 专属窗口 |

## 8. 本地分析产物

| 文件 | 说明 |
|---|---|
| `reports/data_integrity.md` | 字段、日期、缺失和可用样本概览 |
| `tables/default_signal_reproduction.csv` | 默认信号逐点对账 |
| `reports/default_signal_reproduction.md` | 默认信号对账摘要 |
| `tables/factor_window_grid.csv` | 全量 `ETF × 因子 × 窗口` 结果 |
| `curves/*.csv` | 各因子的窗口响应曲线 |
| `tables/best_window_summary.csv` | 每个 ETF 的最佳窗口和 1-SE 稳健带 |
| `tables/pooled_vs_etf_specific.csv` | 共享窗口与 ETF 专属窗口对照 |
| `tables/holdout_validation.csv` | 留出集验证 |
| `tables/segment_stability.csv` | 分段稳定性 |
| `tables/bootstrap_summary.csv` | Bootstrap 结果摘要 |
| `reports/robustness_check.md` | 稳健性结论 |
| `reports/window-heterogeneity-validation-report.md` | 最终研究报告 |

## 9. 执行命令

### 9.1 生成聚宽研究环境导出脚本

```powershell
.\.venv\Scripts\python.exe -m scripts.etf_window_research.cli export-script `
  --project-dir strategies\etf_factor_rotation\reports\window_heterogeneity
```

把生成的 `jq_research_export.py` 放到聚宽研究环境运行后，下载导出的原始 JSON。

### 9.2 自动抓取研究原始数据

```powershell
.\.venv\Scripts\python.exe -m scripts.etf_window_research.cli fetch `
  --project-dir strategies\etf_factor_rotation\reports\window_heterogeneity `
  --headless
```

该命令复用 `.local/chrome-jq/` 的聚宽登录态，在研究页执行同一份导出逻辑并把 JSON 拉回本地。

### 9.3 本地生成研究产物

```powershell
.\.venv\Scripts\python.exe -m scripts.etf_window_research.cli analyze `
  --project-dir strategies\etf_factor_rotation\reports\window_heterogeneity `
  --run-id 2026-05-15-baseline `
  --audit-log strategies\etf_factor_rotation\backtest_runs\20260514-1959-bt1a70c5cd71fac1c27eed2268045ad80a\tabs_raw\audit_log.jsonl
```

### 9.4 先读哪些产物

1. 先读 `data_integrity.md`，确认 Step 2 没有脏数据。
2. 再读 `default_signal_reproduction.md`，确认 Step 3 对账通过。
3. 然后读 `best_window_summary.csv` 和 `pooled_vs_etf_specific.csv`，回答第一层猜想。
4. 最后读 `holdout_validation.csv`、`segment_stability.csv`、`robustness_check.md`，判断是否值得推进到云端确认。

## 10. 当前已知事实

- `MA_long` 已支持 ETF 异质性：
  - AI 偏短窗
  - 纳指偏中窗
  - 黄金偏长窗
- 本轮研究只回答：
  - 动量是否也存在同类异质性
  - 拥挤度相关窗口是否也存在同类异质性
