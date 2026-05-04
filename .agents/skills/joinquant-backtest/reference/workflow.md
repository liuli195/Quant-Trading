# JoinQuant 回测完整流程

本文档描述技能的完整执行步骤。这里保留流程与决策规则，不内联大段 JS；需要具体页面脚本时，按步骤加载 `../snippets/*.js`。

## 1. 读取并预检查策略

- 读取 `strategy_file`，确认文件存在且可读。
- 若未传 `strategy_file`，先从用户请求中推断；若仅给策略名，优先用路径别名解析 `strategy_dir(strategy=<name>)`，再尝试 `<strategy_dir>/<name>.py`。
- 计算：
  - `strategy_name`：文件名去掉 `.py`
  - `strategy_dir`：策略所在目录
  - `strategy`：`path_aliases.json` 中使用的策略目录变量，通常等于 `strategies/<strategy>/` 的目录名
- 校验日期范围：
  - 若 `start_date > end_date`，直接报错并要求用户确认，不自动交换。
- 若 `need_performance=true`，确认策略里已包含 `enable_profile()`；缺失时先补齐本地策略再继续。

## 2. 生成上传版本

- 推荐输出文件：`<strategy_dir>/<strategy_name>__upload.py`
- 调用技能自带脚本：

```bash
python "${CLAUDE_SKILL_DIR}/scripts/strip_comments.py" "<src_file>" "<dst_file>"
```

- 读取去注释后的代码到内存，作为网页粘贴内容。
- 优先使用技能目录内脚本，不依赖仓库根目录同名脚本。

## 3. 进入策略列表或编辑页

- 导航到：`https://www.joinquant.com/algorithm/index/list`
- 若跳转到登录页：
  - 提示用户手动登录
  - 登录完成后再次进入列表页
- 以 `strategy_name` 作为聚宽策略名：
  - 若列表中存在同名策略，优先进入最近更新的一条
  - 若不存在，点击“新建策略”，将新策略命名为 `strategy_name`
- 进入编辑页后，确认 URL 已包含 `/algorithm/index/edit`

页面元素与等待规则见 [dom-contracts.md](dom-contracts.md) <!-- pathref: joinquant_skill/reference/dom-contracts.md -->。

## 4. 写入 Ace 编辑器代码

- 读取 [../snippets/editor.js](../snippets/editor.js) <!-- pathref: joinquant_skill/snippets/editor.js -->
- 用 `evaluate_script` 调用其中的逻辑，将上传版本写入 `ace.edit("ide-container")`
- 同时同步隐藏的 `textarea#code`
- 写入完成后，确认返回值包含：
  - `ok=true`
  - `length > 0`

## 5. 编译校验（快速冒烟）

- 点击“编译运行”
- 编译日期范围设置为 **1周**，只做语法与最小可运行性检查
- 读取 [../snippets/compile.js](../snippets/compile.js) <!-- pathref: joinquant_skill/snippets/compile.js -->
- 等待与失败判定按 [dom-contracts.md](dom-contracts.md) <!-- pathref: joinquant_skill/reference/dom-contracts.md --> 的“编译完成”规则执行
- 若失败：
  - 打开 `#daily-errors-tab`
  - 提取错误日志
  - 回写本地策略并修复
  - 从第 2 步重新执行；证据保留要求见 [troubleshooting.md](troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md -->

## 6. 设置正式回测参数

- 读取 [../snippets/backtest.js](../snippets/backtest.js) <!-- pathref: joinquant_skill/snippets/backtest.js -->
- 用 DOM 赋值设置：
  - `#startTime`
  - `#endTime`
  - `#daily_backtest_capital_base_box`
- 日期归一化规则：
  - 若用户未指定 `end_date`，默认取最近一个交易日
  - 若用户给定日期是非交易日，回退到该日期之前最近的交易日
  - 归一化优先级：
    1. 聚宽交易日历或 API
    2. 页面日期组件可选值
    3. 手工按天向前回退，最多 15 天
- 参数写入后立即回读页面值，保存为实际生效日期

## 7. 启动正式回测

- 继续使用 [../snippets/backtest.js](../snippets/backtest.js) <!-- pathref: joinquant_skill/snippets/backtest.js -->
- 点击 `#full-backtest-button`
- 若按钮内还有可点击子节点，优先点子节点
- 期望跳转到：
  - `/algorithm/backtest/detail?backtestId=...`

## 8. 等待回测完成

- 按 [dom-contracts.md](dom-contracts.md) <!-- pathref: joinquant_skill/reference/dom-contracts.md --> 的“正式回测完成”规则等待。
- 若超时，按 [troubleshooting.md](troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md --> 的回测超时流程处理。

## 9. 提取全量标签数据

内部 API、虚拟滚动限制和 DOM 降级边界见 [dom-contracts.md](dom-contracts.md) <!-- pathref: joinquant_skill/reference/dom-contracts.md -->；数据完整度标记见 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md -->。

执行顺序：

1. 读取 [../snippets/extract.js](../snippets/extract.js) <!-- pathref: joinquant_skill/snippets/extract.js -->，优先执行 `fetchAllBacktestData()`。
2. API 成功时执行 `dumpFetchedBacktestData()`，将结果保存为 `api_export.json`；再用 DOM 补抽 `logs`、`profile` 和静态指标标签。
3. API 不可用时执行 `collectBacktestTabTexts()` 作为降级结果。
4. 记录本次提取方式，后续按输出契约写入索引和完整度信息。

## 10. 提取收益概述

- 继续使用 [../snippets/extract.js](../snippets/extract.js) <!-- pathref: joinquant_skill/snippets/extract.js -->
- 从 `#tab-summaryinfo` 抽取结构化指标面板
- 输出形如：
  - 指标名称 -> 指标值
- 该结果单独保存，后续写入 `summary_metrics.json`

## 11. 结果落盘

路径、文件职责和完整度标记以 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md --> 为准。需要绝对路径时，先解析并记录本次别名：

```bash
python -m scripts.path_tools.aliases resolve backtest_run strategy=<strategy> run_id=<run_id> --absolute
python -m scripts.path_tools.aliases resolve backtest_report_dir strategy=<strategy> run_id=<run_id> --absolute
python -m scripts.path_tools.aliases resolve backtest_tabs_dir strategy=<strategy> run_id=<run_id> --absolute
```

根据数据来源选择不同落盘方式：

**API 方式（优先）**：
- 将 `dumpFetchedBacktestData()` 返回的 JSON 保存到 `backtest_run(strategy=<strategy>, run_id=<run_id>)/api_export.json`
- 运行：
  ```bash
  python "${CLAUDE_SKILL_DIR}/scripts/save_backtest_data.py" --api "<api_export_json_path>" --strategy "<strategy>" --run-id "<run_id>"
  ```
- 该脚本负责将 API JSON 转为 `tabs_raw/transactioninfo.md`、`tabs_raw/positioninfo.md`、`tabs_raw/daily_returns.md`，并生成 `all_data.json` 索引文件
- 需要 `logs`、`profile` 或静态指标标签时，再按 9b 用 DOM 文本补抽相应标签并写入 `tabs_raw/`

**DOM 方式（降级）**：
- 运行：
  ```bash
  python "${CLAUDE_SKILL_DIR}/scripts/save_backtest_data.py" "<persisted_json_path>" --strategy "<strategy>" --run-id "<run_id>"
  ```
- 该脚本负责解析持久化 JSON → `tabs_raw/*.md`

然后补写：
- `metadata.json`
- `summary_metrics.json`

## 12. 生成策略分析报告

- 使用 [../templates/analysis-report.md](../templates/analysis-report.md) <!-- pathref: joinquant_skill/templates/analysis-report.md --> 作为策略分析报告骨架
- 写入路径：`backtest_report_dir(strategy=<strategy>, run_id=<run_id>)/strategy-analysis.md`


## 13. 生成性能分析报告

`need_performance=true` 时生成正式性能分析报告；第 1 步应已确保策略包含 `enable_profile()`。若 `need_performance=false` 且页面无 profile 数据，按输出契约保留空内容或说明性文件。

- 使用 [../templates/performance-report.md](../templates/performance-report.md) <!-- pathref: joinquant_skill/templates/performance-report.md --> 作为性能分析报告骨架

执行规则：

- 读取 [../snippets/extract.js](../snippets/extract.js) <!-- pathref: joinquant_skill/snippets/extract.js --> 中的性能分析相关函数
- 打开 `#tab-profile`
- 轮询规则见 [dom-contracts.md](dom-contracts.md) <!-- pathref: joinquant_skill/reference/dom-contracts.md --> 的“性能分析就绪”
- 写入路径：`backtest_report_dir(strategy=<strategy>, run_id=<run_id>)/performance-analysis.md`

## 14. 校验完成条件

完成前按 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md --> 校验产物；出现异常时，按 [troubleshooting.md](troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md --> 处理。
