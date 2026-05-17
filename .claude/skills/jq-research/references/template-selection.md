# 模板选择

| 模板 | 适用问题 |
| --- | --- |
| `factor_scan` | 因子、窗口、阈值、分组收益、共享窗口与专属窗口比较 |
| `parameter_followup` | 基于已知 baseline 的参数强度、权重形状、局部阈值跟进 |
| `robustness_check` | 已有云端结果后的 bootstrap、滚动窗口、年度拆解、leave-one-out |

## 选择规则

- 能直接从历史行情与静态公式回答的，选 `factor_scan`。
- 需要基于 baseline 审计日志做 counterfactual 的，选 `parameter_followup`。
- 已经有候选结果，只想判断稳不稳的，选 `robustness_check`。
- 若涉及订单执行逻辑、分钟级依赖或未导出外部数据，判为 `cloud_only`。
