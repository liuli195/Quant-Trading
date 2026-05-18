# 组合波动率全量扫描性能冒烟

- **覆盖完整**: `True`
- **当前运行命中特征缓存**: `False`
- **完整扫描预计点数**: `8835`
- **预计完整扫描耗时**: `34.264s`
- **性能门槛**: `60.000s`
- **性能门槛通过**: `False`

## 覆盖摘要

| slice_id | lower_bound | upper_bound | breakpoint_count | interval_count | interval_point_count | evaluation_point_count | missing_breakpoints | missing_intervals | source_portfolio_vol | source_min_weight | source_max_weight | source_max_total_weight |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | 0.000000 | 0.623684 | 884 | 883 | 883 | 1767 | 0 | 0 | 253 | 508 | 122 | 3 |
| 40 | 0.000000 | 0.487462 | 884 | 883 | 883 | 1767 | 0 | 0 | 253 | 508 | 122 | 8 |
| 60 | 0.000000 | 0.409435 | 884 | 883 | 883 | 1767 | 0 | 0 | 253 | 508 | 122 | 6 |
| 90 | 0.000000 | 0.378792 | 884 | 883 | 883 | 1767 | 0 | 0 | 253 | 508 | 122 | 7 |
| 120 | 0.000000 | 0.344714 | 884 | 883 | 883 | 1767 | 0 | 0 | 253 | 508 | 122 | 7 |

## 冷/热冒烟

| pass | sample_size | runtime_seconds | per_item_ms | error_count |
| --- | --- | --- | --- | --- |
| cold | 80 | 0.313s | 3.911 | 0 |
| warm | 80 | 0.310s | 3.878 | 0 |

## 结论

暂不进入正式全量研究，先处理未通过的覆盖或性能门槛。
