# 组合波动率全量扫描性能冒烟

- **覆盖完整**: `True`
- **当前运行命中特征缓存**: `True`
- **完整扫描预计点数**: `12895`
- **预计完整扫描耗时**: `118.199s`
- **性能门槛**: `180.000s`
- **性能门槛通过**: `True`

## 覆盖摘要

| slice_id | lower_bound | upper_bound | breakpoint_count | interval_count | interval_point_count | evaluation_point_count | missing_breakpoints | missing_intervals | source_portfolio_vol | source_min_weight | source_max_weight | source_max_total_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 0.000000 | 0.382603 | 1290 | 1289 | 1289 | 2579 | 0 | 0 | 1289 | 0 | 0 | 0 |
| 40 | 0.000000 | 0.300645 | 1290 | 1289 | 1289 | 2579 | 0 | 0 | 1289 | 0 | 0 | 0 |
| 60 | 0.000000 | 0.275273 | 1290 | 1289 | 1289 | 2579 | 0 | 0 | 1289 | 0 | 0 | 0 |
| 90 | 0.000000 | 0.241912 | 1290 | 1289 | 1289 | 2579 | 0 | 0 | 1289 | 0 | 0 | 0 |
| 120 | 0.000000 | 0.236324 | 1290 | 1289 | 1289 | 2579 | 0 | 0 | 1289 | 0 | 0 | 0 |

## 冷/热冒烟

| pass | sample_size | runtime_seconds | per_item_ms | error_count |
| --- | --- | --- | --- | --- |
| cold | 80 | 0.750s | 9.378 | 0 |
| warm | 80 | 0.733s | 9.166 | 0 |

## 结论

可以进入正式全量研究。
