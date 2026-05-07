---
name: jq-param-scan
description: 参数扫描端到端自动化。用于根据口头描述生成扫描网格、委托 jq-run 批量云端回测、产出深度对比分析报告。该技能消耗云端额度，执行前必须展示计划并等待用户确认。不自动修改策略代码，不自动选择最优参数。
---

# JQ Param Scan

端到端参数扫描：生成配置 → 委托 `jq-run` 批量执行 → 产出深度分析报告。

## 输入

用户口头描述扫描需求：参数名、值列表（或起止范围+步长）、策略名。技能负责生成 `ScenarioConfig` sweep 定义。

## 流程

1. 解析用户需求生成参数网格。
2. 生成扫描场景配置文件（格式见 `scripts/jq_automation/config.py` 的 `ScenarioConfig`，`sweep.strategy=grid|list`）。
3. 展示计划：参数组合数、预估单次耗时、总耗时、剩余额度。等待用户确认。
4. 委托 `jq-run batch` 执行。
5. 委托 `jq-analyze` 生成批次对比。
6. 产出 `param-scan-report.md`，报告结构见 [templates/param-scan-report.md](templates/param-scan-report.md) <!-- pathref: jq_param_scan_skill/templates/param-scan-report.md -->。

## 输出

`strategies/<strategy>/test_batches/<batch_id>/report/param-scan-report.md`

## 边界

- 消耗云端额度。执行前必须用户确认。
- 不自动修改策略代码（报告可提出建议，用户决定是否采纳）。
- 扫描配置问题交给 `jq-fix`。
- 报告深度不足时委托 `jq-analyze`。
