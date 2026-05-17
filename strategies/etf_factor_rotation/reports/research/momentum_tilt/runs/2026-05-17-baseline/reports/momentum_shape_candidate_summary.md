# 动量倾斜强度扫描

- **Replay 校准**: `通过`
- **Phase 2 gate**: `通过`
- **判定原因**: `candidate_found`

| variant | strength | metrics_status | annual_return | sharpe | max_drawdown | rolling_sharpe_win_rate | dominant_etf_share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| linear-050 | 0.5 | available | 15.76% | 1.447 | 8.09% | 0.00% | 0.00% |
| linear-045 | 0.45 | available | 15.78% | 1.451 | 8.09% | 65.22% | 94.01% |
| linear-040 | 0.4 | available | 15.80% | 1.454 | 8.09% | 62.04% | 83.26% |
| linear-035 | 0.35 | available | 15.84% | 1.459 | 8.10% | 63.29% | 67.48% |
| linear-025 | 0.25 | available | 15.90% | 1.469 | 8.10% | 64.55% | 57.98% |

## 形状候选

_当前未进入形状候选阶段；只有当中间 strength 同时优于 `0.50` 与 `0.25` 时才继续比较非线性形状。_
