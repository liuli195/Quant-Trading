# JQ Param Scan 流程

## 阶段一：配置生成

1. 从用户描述中提取：参数名、值列表或范围+步长、策略文件路径。
2. 生成 `ScenarioConfig` sweep 配置：
   - `sweep.strategy` = `"grid"`（多参数正交）或 `"list"`（单参数枚举）
   - `sweep.dimensions` 定义参数维度
3. 将配置写入 `strategies/<strategy>/test_batches/<batch_id>/scenario.json`。

## 阶段二：计划展示

计算并展示：

- 参数组合数 = 各维度水平数的乘积
- 预估单次回测耗时（基于历史数据估算）
- 总耗时 = 组合数 × 单次耗时
- 当日剩余额度
- 确认提示：`--yes` 表示已确认

## 阶段三：批量执行

委托 `jq-run batch`：

```bash
python -m scripts.jq_automation batch <manifest.json> --yes
```

## 阶段四：分析报告

1. 委托 `jq-analyze` 生成批次对比。
2. 按 [param-scan-report.md](../templates/param-scan-report.md) 模板生成深度分析。

## 报告要求

每一章必须包含数据来源引用（具体 run_id 或 summary_metrics.json）。
数值引用精确到 2 位小数。
报告格式见 [param-scan-report.md](../templates/param-scan-report.md) 模板。
