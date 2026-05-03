# JoinQuant 回测完整流程

本文档描述技能的完整执行步骤。这里保留流程与决策规则，不内联大段 JS；需要具体页面脚本时，按步骤加载 `../snippets/*.js`。

## 1. 读取并预检查策略

- 读取 `strategy_file`，确认文件存在且可读。
- 若未传 `strategy_file`，先从用户请求中推断；若仅给策略名，优先尝试 `strategies/<name>/<name>.py`。
- 计算：
  - `strategy_name`：文件名去掉 `.py`
  - `strategy_dir`：策略所在目录
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

页面元素与等待规则见 [dom-contracts.md](dom-contracts.md)。

## 4. 写入 Ace 编辑器代码

- 读取 [../snippets/editor.js](../snippets/editor.js)
- 用 `evaluate_script` 调用其中的逻辑，将上传版本写入 `ace.edit("ide-container")`
- 同时同步隐藏的 `textarea#code`
- 写入完成后，确认返回值包含：
  - `ok=true`
  - `length > 0`

## 5. 编译校验

- 点击“编译运行”
- 编译日期范围设置为 1 周，只做语法与最小可运行性检查
- 读取 [../snippets/compile.js](../snippets/compile.js)
- 等待策略：
  - 阶段 A：最多 10 秒内确认 `.cancel-build` 出现
  - 阶段 B：在“已见过 `.cancel-build`”的前提下，等待其消失，最多 30 秒
  - 若页面文本包含 `ERROR` 或 `Traceback`，判定为失败
- 若失败：
  - 打开 `#daily-errors-tab`
  - 提取错误日志
  - 回写本地策略并修复
  - 从第 2 步重新执行

## 6. 设置正式回测参数

- 读取 [../snippets/backtest.js](../snippets/backtest.js)
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

- 继续使用 [../snippets/backtest.js](../snippets/backtest.js)
- 点击 `#full-backtest-button`
- 若按钮内还有可点击子节点，优先点子节点
- 期望跳转到：
  - `/algorithm/backtest/detail?backtestId=...`

## 8. 等待回测完成

- 只用 `wait_for(["回测完成"])` 等待
- 不要把“策略收益”“Alpha”“收益概述”等静态文本混进等待条件
- 超时阈值建议为 180 秒
- 若超时：
  - 记录当前 URL
  - 提取状态区文本
  - 再让用户决定继续等待还是终止

## 9. 提取全量标签数据

分两步执行：交易、持仓和每日收益优先通过内部 API 获取；`logs`、`profile` 和静态指标标签按需通过页面 DOM 补抽。仅当 API 不可用时，才用 DOM 方式降级抓取交易/持仓等大表。

### 9a. API 全量提取（优先）

- 读取 [../snippets/extract.js](../snippets/extract.js)，从中加载 `fetchAllBacktestData` 函数
- 用 `evaluate_script` 执行：
  ```javascript
  fetchAllBacktestData().then((data) => {
    window.__fetchedData = data;
    return {
      error: data.error || null,
      internalId: data.internalId || null,
      counts: data.counts || null,
    };
  })
  ```
- 预期结果：`{ error: null, internalId: "...", counts: { transactions: N, positions: M, resultPages: P } }`
- 确认返回值无 `error` 字段，且 `internalId` 与 `counts` 均非空
- 导出全量数据：执行 `dumpFetchedBacktestData()`，将返回值持久化为 JSON 文件
- 若返回 `error`、`counts` 为空，或三类数据量均为 0，降级到 9b

### 9b. 页面标签补抽与 DOM 降级

- API 成功时：用 DOM 补抽 `logs`、`profile` 和静态指标标签（alpha、beta、sharpe 等）
- API 不可用时：用 DOM 降级抓取 `transactioninfo`、`positioninfo`、`logs` 等标签
- 执行 `collectBacktestTabTexts()` 收集标签文本
- **注意**：DOM 方式抓取 `transactioninfo`、`positioninfo`、`logs` 会受虚拟滚动限制；只有在 API 失败时才接受这种不完整结果
- 发生 DOM 降级时，在 metadata 中记录警告

## 10. 提取收益概述

- 继续使用 [../snippets/extract.js](../snippets/extract.js)
- 从 `#tab-summaryinfo` 抽取结构化指标面板
- 输出形如：
  - 指标名称 -> 指标值
- 该结果单独保存，后续写入 `summary_metrics.json`

## 11. 结果落盘

回测产物目录遵循仓库根目录 `path_aliases.json` 中的语义别名：`backtest_run` 表示单次回测根目录，`backtest_report_dir` 表示报告目录，`backtest_tabs_dir` 表示原始标签 Markdown 目录。流程中出现的 `<run_dir>` 应由这些语义目录解析得到，避免在多处硬编码物理目录结构。

根据数据来源选择不同落盘方式：

**API 方式（优先）**：
- 将 `dumpFetchedBacktestData()` 返回的 JSON 保存到 `<run_dir>/api_export.json`
- 运行：
  ```bash
  python "${CLAUDE_SKILL_DIR}/scripts/save_backtest_data.py" --api "<run_dir>/api_export.json" "<run_dir>"
  ```
- 该脚本负责将 API JSON 转为 `tabs_raw/transactioninfo.md`、`tabs_raw/positioninfo.md`、`tabs_raw/daily_returns.md`，并生成 `all_data.json` 索引文件
- 需要 `logs`、`profile` 或静态指标标签时，再按 9b 用 DOM 文本补抽相应标签并写入 `tabs_raw/`

**DOM 方式（降级）**：
- 运行：
  ```bash
  python "${CLAUDE_SKILL_DIR}/scripts/save_backtest_data.py" "<persisted_json_path>" "<run_dir>"
  ```
- 该脚本负责解析持久化 JSON → `tabs_raw/*.md`

然后补写：
- `metadata.json`：回测参数、实际日期、回测 ID、详情页 URL、时间戳、是否 API 提取
- `summary_metrics.json`：第 10 步提取的收益概述

产物细节见 [output-contract.md](output-contract.md)。

## 12. 生成策略分析报告（必做）

- 使用 [../templates/analysis-report.md](../templates/analysis-report.md) 作为策略分析报告骨架
- 写入路径：`<strategy_dir>/backtest_runs/<run_id>/report/strategy-analysis.md`
- 报告需要覆盖：
  - 核心指标摘要
  - 风格与稳定性评估
  - 优势与风险
  - 适用场景
  - 后续优化建议

## 13. 生成性能分析报告（必做）

执行条件：`need_performance=true`（默认开启）或策略包含 `enable_profile()`。

- `need_performance=true`
- 策略中已包含 `enable_profile()`

执行规则：

- 读取 [../snippets/extract.js](../snippets/extract.js) 中的性能分析相关函数
- 打开 `#tab-profile`
- 轮询直到：
  - `#tab-profile` 存在
  - 文本命中 `Total time` 或 `总耗时`
  - 表格 `tr` 数量大于 1
- 提取完整文本后分析：
  - 函数名
  - 总耗时
  - 占比
  - 调用次数
  - 主要瓶颈代码
- 写入路径：`<strategy_dir>/backtest_runs/<run_id>/report/performance-analysis.md`

## 14. 校验完成条件

完成前至少确认以下结果已经齐备：

- `<strategy_dir>/backtest_runs/<run_id>/report/strategy-analysis.md`
- `<strategy_dir>/backtest_runs/<run_id>/report/performance-analysis.md`
- `<strategy_dir>/backtest_runs/<run_id>/report/backtest_report.md`
- `backtest_runs/<run_id>/tabs_raw/` 下的结构化 Markdown 文件
- `metadata.json`、`summary_metrics.json`、`all_data.json`

出现异常时，按 [troubleshooting.md](troubleshooting.md) 处理。
