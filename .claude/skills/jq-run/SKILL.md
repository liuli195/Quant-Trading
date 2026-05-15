---
name: jq-run
description: 执行 JoinQuant 云端回测流程。用于上传本地 Python 策略到聚宽、编译、启动正式云端回测、只读抓取已有回测详情、保存云端结果、更新批次与场景映射。该技能消耗每日云端额度，正式回测前必须先计划并等待用户确认。
---

# JQ Run

通过 `jq-auto` CLI（Playwright 浏览器自动化）执行云端回测。不再使用 MCP Chrome DevTools。

## 子命令

| 命令 | 用途 |
|------|------|
| `jq-auto compile-check <策略文件> [--write-upload]` | 本地 py_compile 检查，可选生成上传版 |
| `jq-auto upload <策略文件> [--strategy-name <名称>]` | 上传代码到聚宽编辑器 |
| `jq-auto run <场景配置.json> [--yes]` | 完整自动化：上传、编译、设置参数、启动回测、等待完成、抓取、落盘 |
| `jq-auto fetch <回测URL或ID> --strategy <策略名>` | 只读抓取已有回测详情 |
| `jq-auto batch <manifest.json> [--scenario <场景ID>] [--yes]` | 批量运行 manifest 中的待处理场景 |
| `jq-auto ab expand <实验配置.json>` | 展开 A/B 实验设计，生成分支策略和场景配置 |
| `jq-auto ab run <实验目录> [--yes]` | 执行 A/B 实验的所有场景回测 |
| `jq-auto ab report <实验目录>` | 生成 A/B 实验 delta 归因报告（含 bootstrap 显著性检验） |

浏览器参数（upload/run/fetch/batch/ab 通用）：`--headless`、`--slow-mo <毫秒>`、`--user-data-dir <路径>`

## 流程

1. 根据用户意图选择子命令。
2. 正式回测前，先输出计划：场景、区间、预计耗时、剩余额度。
3. 执行 `jq-auto` 命令（虚拟环境路径：`.\.venv\Scripts\python.exe -m scripts.jq_automation`）。
4. 结果自动落盘到 `strategies/<strategy>/backtest_runs/<run_id>/`。
5. 如属批次，manifest 自动更新。

## 边界

- 正式回测前必须用户确认（run/batch 使用 `--yes` 表示已确认）。
- 每日云端额度 60 分钟保护。
- 编译失败或策略问题交给 `jq-fix`。
- 报告和多场景对比交给 `jq-analyze`。
- 场景配置文件格式见 `scripts/jq_automation/config.py` 中的 `ScenarioConfig`。
