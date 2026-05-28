# 研究流程模板

`workflows/templates/` 保存本地研究平台的轻量流程模板声明。模板只描述输入、阶段、输出和门槛，不承载执行逻辑；执行仍由 `scripts.research.cli` 和 `platform.engine` 完成。

## 命令示例

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit
```

治理审计会校验模板 schema，并检查 engine 支持的正式模板是否都有声明文件。

## 当前模板

- `factor_scan`
- `parameter_followup`
- `robustness_check`
- `generic`
- `portfolio_volatility`
- `cloud_confirmation`

## 常见输入

- `dataset`
- `baseline_returns`
- `variants`
- 具体模板声明的其他输入。

## 常见输出

- `candidate_ranking.csv`
- `shortlist.csv`
- `full_candidate_review.csv`
- `cloud_candidates.csv`
- `cloud_handoff.json`

## 边界

- 不创建 Git 分支。
- 不上传云端回测。
- 不修改主策略默认参数。

## 关联测试

- `scripts/research/platform/tests/test_platform.py`
