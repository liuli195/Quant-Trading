---
name: joinquant-backtest
description: 执行 JoinQuant 网页回测并保存结构化结果；当用户明确要求聚宽回测、上传策略、backtest 或 performance 分析时使用。
when_to_use: 用户需要把本地 Python 策略上传到 JoinQuant，完成编译校验、正式回测、指标提取、结果落盘，或生成策略分析/性能分析报告时使用。该技能属于多步骤网页工作流，建议通过 /joinquant-backtest 手动调用。
argument-hint: "<策略文件> [开始日期] [结束日期] [初始资金] [是否策略分析] [是否性能分析]"
arguments:
  - strategy_file
  - start_date
  - end_date
  - capital
  - need_performance
  - need_analysis
disable-model-invocation: true
---

# JoinQuant 回测技能

## 技能用途

用于把本地 Python 策略上传到 JoinQuant 网页端，完成以下工作：

- 编译校验与最小可运行性检查
- 正式回测与指标提取
- 回测结果落盘到策略目录
- 生成中文策略分析报告与可选性能分析报告

## 参数约定

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `strategy_file` | 无 | 本地 Python 策略文件路径。若未显式传入，优先尝试从用户请求推断；若用户只给策略名，优先尝试 `strategies/<name>/<name>.py`。 |
| `start_date` | `2023-01-01` | 回测开始日期，格式 `YYYY-MM-DD`。 |
| `end_date` | 最近一个交易日 | 回测结束日期，格式 `YYYY-MM-DD`。 |
| `capital` | `500000` | 初始资金。 |
| `need_analysis` | `true` | 是否执行策略分析。 |
| `need_performance` | `true` | 是否执行性能分析。 |

当前调用参数：

- `strategy_file`: `$strategy_file`
- `start_date`: `$start_date`
- `end_date`: `$end_date`
- `capital`: `$capital`
- `need_performance`: `$need_performance`
- `need_analysis`: `$need_analysis`

## 产出物

- `<strategy_dir>/backtest_runs/<run_id>/report/backtest_report.md`
- `<strategy_dir>/backtest_runs/<run_id>/report/strategy-analysis.md`
- `<strategy_dir>/backtest_runs/<run_id>/report/performance-analysis.md`
- `<strategy_dir>/backtest_runs/<run_id>/`

这些路径对应仓库根目录 `path_aliases.json` 中的语义目录：`backtest_run`、`backtest_report_dir`、`backtest_tabs_dir`。若未来回测产物目录结构调整，优先修改目录别名配置，而不是在流程文档和脚本中散落替换路径。

详细产物结构见 [reference/output-contract.md](reference/output-contract.md)。

## 执行摘要

1. 校验输入参数并定位策略文件。
2. 用 `${CLAUDE_SKILL_DIR}/scripts/strip_comments.py` 生成上传版本。
3. 进入 JoinQuant 策略列表或编辑页，复用已有同名策略或新建策略。
4. 用 [snippets/editor.js](snippets/editor.js) 中的脚本写入 Ace 编辑器。
5. 用 [snippets/compile.js](snippets/compile.js) 完成编译冒烟检查。
6. 用 [snippets/backtest.js](snippets/backtest.js) 设置正式回测日期和资金，并启动回测。
7. 仅用“回测完成”作为完成信号，避免静态文本假阳性。
8. 用 [snippets/extract.js](snippets/extract.js) 抽取标签文本和收益概述。
9. 用 `${CLAUDE_SKILL_DIR}/scripts/save_backtest_data.py` 生成结构化 Markdown 产物，再补写 JSON 元数据和报告。

## 关键约束

- `wait_for` 的 `text` 参数必须传数组，不要传字符串。
- 不要用”策略收益””Alpha””Sharpe””收益概述”等静态文本作为等待条件。
- 编译完成以 `.cancel-build` 先出现、后消失为准，不要用静态图表标题代替。
- 日期需要记录”用户请求值”和”页面实际生效值”两个版本。
- **大表数据优先使用 API 方式**：通过 `fetchAllBacktestData()` 调用内部 XHR 接口获取交易、持仓和每日收益，绕过虚拟滚动限制；`logs`、`profile` 与静态指标标签仍按需用 DOM 补抽。
- 优先用 `evaluate_script` 直接操作 DOM，尽量少依赖快照 uid。

## 支撑文件

- [reference/workflow.md](reference/workflow.md)：完整执行流程
- [reference/dom-contracts.md](reference/dom-contracts.md)：DOM 选择器、等待规则、反模式与虚拟滚动限制
- [reference/output-contract.md](reference/output-contract.md)：输出目录、文件职责与 JSON 约定
- [reference/troubleshooting.md](reference/troubleshooting.md)：失败处理、重试策略与停止条件
- [templates/analysis-report.md](templates/analysis-report.md)：策略分析报告模板
- [templates/performance-report.md](templates/performance-report.md)：性能分析报告模板
- [examples/invocation.md](examples/invocation.md)：典型调用示例

## 代码与脚本索引

- [snippets/editor.js](snippets/editor.js)：Ace 编辑器写入代码
- [snippets/compile.js](snippets/compile.js)：编译状态轮询与错误提取
- [snippets/backtest.js](snippets/backtest.js)：设置日期、资金并启动正式回测
- [snippets/extract.js](snippets/extract.js)：提取标签文本、收益概述和性能分析状态
- [scripts/strip_comments.py](scripts/strip_comments.py)：生成上传用策略文件
- [scripts/save_backtest_data.py](scripts/save_backtest_data.py)：将持久化 JSON 转为结构化 Markdown 和索引文件

## 使用原则

- `SKILL.md` 只保留入口说明与导航；详细步骤放到 supporting files。
- 当你需要具体 DOM 代码时，再按需加载 `snippets/*.js`，不要把大段 JS 回填到本文件。
- 当你需要输出目录、失败处理或报告格式时，再按需加载相应的 `reference/*.md` 或 `templates/*.md`。
