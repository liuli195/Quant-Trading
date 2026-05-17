# 审计日志字段

每行一个 JSON 事件，字段随 `event` 类型变化。

## 公共字段
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `seq` | int | 事件序号 |
| `event` | str | run_start / rebalance_signals / rebalance_order / run_end |
| `audit_token` | str | 审计令牌 |
| `current_dt` | str | 当前时间 |
| `previous_date` | str | 上一交易日 |

## rebalance_signals 特有字段
| 字段 | 类型 |
| --- | --- |
| `trend_gates` | list[float] |
| `rp_weights` | list[float] |
| `tilted_weights` | list[float] |
| `crowd_penalties` | list[float] |
| `raw_weights` | list[float] |
| `portfolio_vol_scale` | float |
| `final_weights_before_constraints` | list[float] |
| `final_weights` | list[float] |
