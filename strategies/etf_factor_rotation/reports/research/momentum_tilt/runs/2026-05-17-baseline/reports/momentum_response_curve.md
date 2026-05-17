# 动量响应曲线

- **活跃样本数**: `517`
- **主观察 horizon**: `20d`
- **Phase 1 gate**: `通过`
- **discovery 中段 - 高段**: `+159.9 bp`
- **holdout 中段 - 高段**: `+309.2 bp`

## 分区摘要

| segment | etf | etf_label | score_zone | sample_count | mean_forward_bp |
| --- | --- | --- | --- | --- | --- |
| discovery | 159819.XSHE | AI | high | 52 | -102.7 |
| discovery | 159819.XSHE | AI | low | 28 | -371.0 |
| discovery | 159819.XSHE | AI | mid | 196 | 34.6 |
| discovery | 513100.XSHG | NASDAQ | high | 196 | -251.1 |
| discovery | 513100.XSHG | NASDAQ | low | 16 | 368.3 |
| discovery | 513100.XSHG | NASDAQ | mid | 144 | 18.7 |
| discovery | 518880.XSHG | GOLD | high | 168 | 33.3 |
| discovery | 518880.XSHG | GOLD | low | 56 | -27.0 |
| discovery | 518880.XSHG | GOLD | mid | 152 | 105.8 |
| holdout | 159819.XSHE | AI | high | 84 | 95.2 |
| holdout | 159819.XSHE | AI | low | 40 | 185.7 |
| holdout | 159819.XSHE | AI | mid | 131 | 575.3 |
| holdout | 513100.XSHG | NASDAQ | high | 60 | 44.1 |
| holdout | 513100.XSHG | NASDAQ | low | 25 | 484.2 |
| holdout | 513100.XSHG | NASDAQ | mid | 246 | 232.8 |
| holdout | 518880.XSHG | GOLD | high | 139 | 79.5 |
| holdout | 518880.XSHG | GOLD | low | 28 | 537.2 |
| holdout | 518880.XSHG | GOLD | mid | 293 | 338.2 |

## 解读

- `mid` 定义为 `0.50 <= score < 0.90`，`high` 定义为 `score >= 0.90`。
- Phase 1 gate 只有在 discovery 与 holdout 的全局 `mid - high` 都为正时通过。
