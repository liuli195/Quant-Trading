---
name: joinquant-backtest
description: 手动执行 JoinQuant 网页回测、抓取已有回测详情并保存结构化结果；当用户明确要求 /joinquant-backtest、聚宽回测、已有回测数据获取、上传策略时使用。
when_to_use: 用户需要把本地 Python 策略上传到 JoinQuant，完成编译校验、正式回测、数据提取、结果落盘时使用。策略分析与性能分析请基于已下载的数据单独运行。该技能属于有副作用的多步骤网页工作流，应通过 /joinquant-backtest 手动调用。
argument-hint: "<策略文件> [开始日期] [结束日期] [初始资金]"
arguments:
  - strategy_file
  - start_date
  - end_date
  - capital
disable-model-invocation: true
---

# JoinQuant 回测技能

把本地 Python 策略上传到 JoinQuant 网页端，完成编译校验、正式回测、数据提取、结果落盘。策略分析和性能分析基于已下载的回测数据单独运行，不在本技能流程内。上传/回测会修改网页策略和本地文件，应由用户明确调用；已有回测抓取只读取详情页接口并落盘。

## 参数约定

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `strategy_file` | 无 | 本地 Python 策略文件路径。若未显式传入，优先尝试从用户请求推断；若用户只给策略名，优先尝试 `strategies/<name>/<name>.py`。 |
| `start_date` | `2023-01-01` | 回测开始日期，格式 `YYYY-MM-DD`。 |
| `end_date` | 最近一个交易日 | 回测结束日期，格式 `YYYY-MM-DD`。 |
| `capital` | `500000` | 初始资金。 |

当前调用参数：

- `strategy_file`: `$strategy_file`
- `start_date`: `$start_date`
- `end_date`: `$end_date`
- `capital`: `$capital`

## 文档入口

- [reference/workflow.md](reference/workflow.md) <!-- pathref: agents_joinquant_skill/reference/workflow.md -->：完整执行流程
- [reference/browser-contracts.md](reference/browser-contracts.md) <!-- pathref: agents_joinquant_skill/reference/browser-contracts.md -->：浏览器页面契约、DOM 选择器、内部数据 API、提取路径与虚拟滚动限制
- [reference/output-contract.md](reference/output-contract.md) <!-- pathref: agents_joinquant_skill/reference/output-contract.md -->：输出目录、文件职责与 JSON 约定
- [reference/troubleshooting.md](reference/troubleshooting.md) <!-- pathref: agents_joinquant_skill/reference/troubleshooting.md -->：失败处理、重试策略与停止条件
- [examples/invocation.md](examples/invocation.md) <!-- pathref: agents_joinquant_skill/examples/invocation.md -->：典型调用示例

策略分析与性能分析基于已下载的 `api_export.json` 单独执行，模板参见 [templates/](templates/) <!-- pathref: agents_joinquant_skill/templates/ -->。

## 实现入口

- [snippets/editor.js](snippets/editor.js) <!-- pathref: agents_joinquant_skill/snippets/editor.js -->：Ace 编辑器写入代码
- [snippets/compile.js](snippets/compile.js) <!-- pathref: agents_joinquant_skill/snippets/compile.js -->：编译状态轮询与错误提取
- [snippets/backtest.js](snippets/backtest.js) <!-- pathref: agents_joinquant_skill/snippets/backtest.js -->：设置日期、资金并启动正式回测
- [snippets/extract.js](snippets/extract.js) <!-- pathref: agents_joinquant_skill/snippets/extract.js -->：提取标签文本、收益概述和性能分析状态
- [scripts/strip_comments.py](scripts/strip_comments.py) <!-- pathref: agents_joinquant_skill/scripts/strip_comments.py -->：生成上传用策略文件
- [scripts/save_backtest_data.py](scripts/save_backtest_data.py) <!-- pathref: agents_joinquant_skill/scripts/save_backtest_data.py -->：将 DOM JSON 或一次性 API bundle 转为结构化 Markdown、回测汇总和索引文件
