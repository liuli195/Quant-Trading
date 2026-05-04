---
name: joinquant-backtest
description: 手动执行 JoinQuant 网页回测并保存结构化结果；当用户明确要求 /joinquant-backtest、聚宽回测、上传策略、backtest 或 performance 分析时使用。
when_to_use: 用户需要把本地 Python 策略上传到 JoinQuant，完成编译校验、正式回测、指标提取、结果落盘，或生成策略分析/性能分析报告时使用。该技能属于有副作用的多步骤网页工作流，应通过 /joinquant-backtest 手动调用。
argument-hint: "<策略文件> [开始日期] [结束日期] [初始资金] [是否性能分析]"
arguments:
  - strategy_file
  - start_date
  - end_date
  - capital
  - need_performance
disable-model-invocation: true
---

# JoinQuant 回测技能

把本地 Python 策略上传到 JoinQuant 网页端，完成编译校验、正式回测、数据提取、结果落盘，并生成策略分析报告；性能分析由 `need_performance` 控制。该工作流会修改网页策略和本地文件，应由用户明确调用。

## 参数约定

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `strategy_file` | 无 | 本地 Python 策略文件路径。若未显式传入，优先尝试从用户请求推断；若用户只给策略名，优先尝试 `strategies/<name>/<name>.py`。 |
| `start_date` | `2023-01-01` | 回测开始日期，格式 `YYYY-MM-DD`。 |
| `end_date` | 最近一个交易日 | 回测结束日期，格式 `YYYY-MM-DD`。 |
| `capital` | `500000` | 初始资金。 |
| `need_performance` | `true` | 是否执行性能分析。策略分析报告固定生成。 |

当前调用参数：

- `strategy_file`: `$strategy_file`
- `start_date`: `$start_date`
- `end_date`: `$end_date`
- `capital`: `$capital`
- `need_performance`: `$need_performance`

## 文档入口

- [reference/workflow.md](reference/workflow.md) <!-- pathref: joinquant_skill/reference/workflow.md -->：完整执行流程
- [reference/dom-contracts.md](reference/dom-contracts.md) <!-- pathref: joinquant_skill/reference/dom-contracts.md -->：DOM 选择器、等待规则、反模式与虚拟滚动限制
- [reference/output-contract.md](reference/output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md -->：输出目录、文件职责与 JSON 约定
- [reference/troubleshooting.md](reference/troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md -->：失败处理、重试策略与停止条件
- [templates/analysis-report.md](templates/analysis-report.md) <!-- pathref: joinquant_skill/templates/analysis-report.md -->：策略分析报告模板
- [templates/performance-report.md](templates/performance-report.md) <!-- pathref: joinquant_skill/templates/performance-report.md -->：性能分析报告模板
- [examples/invocation.md](examples/invocation.md) <!-- pathref: joinquant_skill/examples/invocation.md -->：典型调用示例

## 实现入口

- [snippets/editor.js](snippets/editor.js) <!-- pathref: joinquant_skill/snippets/editor.js -->：Ace 编辑器写入代码
- [snippets/compile.js](snippets/compile.js) <!-- pathref: joinquant_skill/snippets/compile.js -->：编译状态轮询与错误提取
- [snippets/backtest.js](snippets/backtest.js) <!-- pathref: joinquant_skill/snippets/backtest.js -->：设置日期、资金并启动正式回测
- [snippets/extract.js](snippets/extract.js) <!-- pathref: joinquant_skill/snippets/extract.js -->：提取标签文本、收益概述和性能分析状态
- [scripts/strip_comments.py](scripts/strip_comments.py) <!-- pathref: joinquant_skill/scripts/strip_comments.py -->：生成上传用策略文件
- [scripts/save_backtest_data.py](scripts/save_backtest_data.py) <!-- pathref: joinquant_skill/scripts/save_backtest_data.py -->：将持久化 JSON 转为结构化 Markdown 和索引文件
