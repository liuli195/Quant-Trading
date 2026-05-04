# JoinQuant 回测完整流程

本文档只描述执行编排与决策点。DOM 选择器、等待条件、内部数据 API、提取函数和 bundle 字段契约统一见 [browser-contracts.md](browser-contracts.md) <!-- pathref: joinquant_skill/reference/browser-contracts.md -->；产物结构见 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md -->。

## 1. 解析参数与模式

- 解析 `strategy_file`、`start_date`、`end_date`、`capital`。
- 若用户要求抓取已有回测详情，或当前页面已经是回测详情页，进入”已有详情页抓取模式”，直接跳到第 9 步。
- 其余情况进入”上传并新跑回测模式”，从第 2 步开始。
- 已有详情页抓取模式仍需确定 `strategy` 与 `run_id`；若不能从用户请求、页面标题或回测 ID 推断，先停下确认。
- 若 `start_date > end_date`，直接停下并要求用户确认，不自动交换。

## 2. 读取并预检查策略

- 读取 `strategy_file`，确认文件存在且可读。
- 若未传 `strategy_file`，先从用户请求中推断；若仅给策略名，优先用路径别名解析 `strategy_dir(strategy=<name>)`，再尝试 `<strategy_dir>/<name>.py`。
- 计算并记录：
  - `strategy_name`：文件名去掉 `.py`
  - `strategy_dir`：策略所在目录
  - `strategy`：`path_aliases.json` 中使用的策略目录变量，通常等于 `strategies/<strategy>/` 的目录名

## 3. 生成上传版本

- 推荐输出文件：`<strategy_dir>/<strategy_name>__upload.py`。
- 调用技能自带脚本：

```bash
python "<skill_dir>/scripts/strip_comments.py" "<src_file>" "<dst_file>"
```

- 读取上传版本到内存，作为网页写入内容。
- 优先使用技能目录内脚本，不依赖仓库根目录同名脚本。

## 4. 进入策略列表或编辑页

- 导航到：`https://www.joinquant.com/algorithm/index/list`
- 若跳转到登录页，提示用户手动登录；登录完成后再次进入列表页。
- 以 `strategy_name` 作为聚宽策略名：
  - 若列表中存在同名策略，优先进入最近更新的一条
  - 若不存在，点击“新建策略”，将新策略命名为 `strategy_name`
- 进入编辑页后，确认 URL 已包含 `/algorithm/index/edit`。

## 5. 写入 Ace 编辑器代码

- 读取 [../snippets/editor.js](../snippets/editor.js) <!-- pathref: joinquant_skill/snippets/editor.js -->。
- 调用编辑器写入逻辑，将上传版本写入 Ace，并同步隐藏代码框。
- 写入完成后，确认返回值包含 `ok=true` 且 `length > 0`。

## 6. 编译校验

- 点击“编译运行”。
- 编译日期范围设置为 1 周，只做语法与最小可运行性检查。
- 读取 [../snippets/compile.js](../snippets/compile.js) <!-- pathref: joinquant_skill/snippets/compile.js -->。
- 等待与失败判定按 [browser-contracts.md](browser-contracts.md) <!-- pathref: joinquant_skill/reference/browser-contracts.md --> 的“编译完成”规则执行。
- 若失败，打开错误日志、提取证据、修复本地策略后从第 3 步重新执行；证据保留要求见 [troubleshooting.md](troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md -->。

## 7. 设置并启动正式回测

- 读取 [../snippets/backtest.js](../snippets/backtest.js) <!-- pathref: joinquant_skill/snippets/backtest.js -->。
- 设置开始日期、结束日期和初始资金。
- 日期归一化规则：
  - 若用户未指定 `end_date`，默认取最近一个交易日
  - 若用户给定日期是非交易日，回退到该日期之前最近的交易日
  - 归一化优先级：聚宽交易日历或 API、页面日期组件可选值、手工按天向前回退最多 15 天
- 参数写入后立即回读页面值，保存为实际生效日期。
- 点击正式回测按钮，期望跳转到 `/algorithm/backtest/detail?backtestId=...`。

## 8. 等待回测完成

- 按 [browser-contracts.md](browser-contracts.md) <!-- pathref: joinquant_skill/reference/browser-contracts.md --> 的“正式回测完成”规则等待。
- 若超时，按 [troubleshooting.md](troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md --> 的回测超时流程处理。

## 9. 提取数据

- 读取 [../snippets/extract.js](../snippets/extract.js) <!-- pathref: joinquant_skill/snippets/extract.js -->。
- 已有详情页抓取模式：按 [browser-contracts.md](browser-contracts.md) <!-- pathref: joinquant_skill/reference/browser-contracts.md --> 的“API bundle 主路径”执行，只读抓取详情页数据，禁止点击会消耗积分的页面“导出”。
- 上传并新跑回测模式：优先按 [browser-contracts.md](browser-contracts.md) <!-- pathref: joinquant_skill/reference/browser-contracts.md --> 的“新跑回测 API 路径”提取；不可用时按“DOM 降级路径”提取。
- 保存浏览器返回的原始 JSON：
  - API 路径保存为 `backtest_run(strategy=<strategy>, run_id=<run_id>)/api_export.json`
  - DOM 降级路径保存为临时 `persisted_json`，后续传给落盘脚本
- 记录本次提取方式，后续写入索引与完整度信息。

## 10. 结果落盘

路径、文件职责和完整度标记以 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md --> 为准。需要绝对路径时，先解析并记录本次别名：

```bash
python -m scripts.path_tools.aliases resolve backtest_run strategy=<strategy> run_id=<run_id> --absolute
python -m scripts.path_tools.aliases resolve backtest_report_dir strategy=<strategy> run_id=<run_id> --absolute
python -m scripts.path_tools.aliases resolve backtest_tabs_dir strategy=<strategy> run_id=<run_id> --absolute
```

API 路径落盘：

```bash
python "<skill_dir>/scripts/save_backtest_data.py" --api "<api_export_json_path>" --strategy "<strategy>" --run-id "<run_id>"
```

DOM 降级路径落盘：

```bash
python "<skill_dir>/scripts/save_backtest_data.py" "<persisted_json_path>" --strategy "<strategy>" --run-id "<run_id>"
```

落盘脚本负责生成 `tabs_raw/`、`metadata.json`、`summary_metrics.json`、`all_data.json` 和 `report/backtest_report.md`。策略分析与性能分析报告不在本技能流程内，基于落盘数据单独运行。

## 11. 校验完成条件

完成前按 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md --> 校验产物；出现异常时，按 [troubleshooting.md](troubleshooting.md) <!-- pathref: joinquant_skill/reference/troubleshooting.md --> 处理。
