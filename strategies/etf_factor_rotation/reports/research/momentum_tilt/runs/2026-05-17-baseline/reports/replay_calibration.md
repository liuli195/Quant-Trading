# Replay 校准

- **整体结论**: `通过`
- **baseline 路径**: `通过`
- **已知变体绝对误差**: `通过`
- **已知变体排序**: `通过`
- **改善方向**: `通过`

| variant | local_annual | cloud_annual | local_sharpe | cloud_sharpe | local_mdd | cloud_mdd |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 15.76% | 15.76% | 1.447 | 1.447 | 8.09% | 8.09% |
| linear_025 | 15.90% | 15.91% | 1.469 | 1.469 | 8.10% | 8.09% |
| extreme_090 | 15.88% | 15.85% | 1.467 | 1.464 | 8.05% | 8.00% |

说明：本地 replay 以云端 baseline 的真实日收益为锚，只估计不同动量倾斜带来的相对差异；
绝对年化、Sharpe、回撤通过 baseline 云端指标做锚定，避免把聚宽内部 Sharpe 口径差异误判为 replay 失真。
