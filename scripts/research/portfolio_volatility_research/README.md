# Portfolio Volatility Research

本库沉淀组合波动缩放研究的领域构造、候选评估和报告片段。正式执行入口仍走本地研究平台插件。

## 命令示例

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.cli init `
  --project-dir strategies\etf_factor_rotation\reports\research\cash_utilization `
  --project portfolio_volatility_study `
  --strategy etf_factor_rotation `
  --template portfolio_volatility

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.cli run `
  --project-dir strategies\etf_factor_rotation\reports\research\cash_utilization `
  --run-id <run_id> `
  --mode fast
```

## 输入

- 基准回测审计日志。
- 价格数据包。
- 组合波动缩放候选域。

## 输出

- 候选域表。
- 候选评估表。
- smoke/full 报告片段。

## 边界

- 不直接上传云端回测。
- 不决定是否写回主策略。
- 不替代 `scripts.research.cli` 的运行目录、manifest 和状态管理。

## 关联测试

- `scripts/research/portfolio_volatility_research/tests/test_domain_builder.py`
- `scripts/research/platform/tests/test_platform.py`
