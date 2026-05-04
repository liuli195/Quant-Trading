# AGENTS.md

## 1. 项目定位与边界

本项目是基于 Python 的 A 股/场内基金量化交易策略仓库，交易与回测环境为 **聚宽 (JoinQuant)**。

- 策略运行边界：策略代码仅在聚宽云端可运行，本地不能直接执行完整策略。
- 本地职责边界：本地用于编写代码、静态检查、单元测试、文档维护、回测结果分析。
- 目标：以可复用、可测试、可审计的方式持续迭代策略。

## 2. 核心文档与入口

- 聚宽 API 在线文档：<https://www.joinquant.com/help/api/help#name:api>
- 聚宽 API 离线文档：`docs/joinquant-api.md`（优先查阅）
- 聚宽回测入口：<https://www.joinquant.com/algorithm/index/list>
- 聚宽模拟交易入口：<https://www.joinquant.com/algorithm/trade/list>

## 3. 仓库结构约定

- `strategies/`：策略主目录
- `strategies/<strategy_name>/<strategy_name>.py`：策略代码文件
- `strategies/<strategy_name>/tests/`：本地单元测试（pytest）与测试文档
- `strategies/<strategy_name>/reports/`：专题分析报告（跨回测对比、深度归因）
- `strategies/<strategy_name>/backtest_runs/<run_id>/`：单次回测的完整产物
  - `report/backtest_report.md`：回测数据汇总
  - `report/strategy-analysis.md`：本次回测策略分析（每次回测必须产出）
  - `report/performance-analysis.md`：本次回测性能分析（每次回测必须产出）
- `docs/`：聚宽文档镜像与研究资料
- `scripts/`：文档转换、辅助脚本

### 3.1 路径别名与引用治理

- `path_aliases.json`：仓库级目录别名配置，是策略、报告、回测产物、文档图片等语义目录的唯一来源。
- `scripts/path_tools/`：路径治理工具目录。
  - `aliases.py`：解析 `path_aliases.json` 中的目录别名。
  - `refactor.py`：移动/改名文件并批量重写仓库内部引用。
- 新增脚本写入结果目录时，优先通过目录别名解析，不直接硬编码 `strategies/<strategy>/backtest_runs/...` 等结构。
- 重要 Markdown 内部文件引用采用“双轨格式”：普通路径负责可点击，`pathref` 注释负责机器校验和重写。

示例：

```md
[阈值对比](strategies/etf_dynamic_rebalance/reports/01-threshold-comparison.md) <!-- pathref: strategy_reports(strategy=etf_dynamic_rebalance)/01-threshold-comparison.md -->
```

常用命令：

```bash
# 解析目录别名
python -m scripts.path_tools.aliases resolve backtest_report_dir strategy=etf_dynamic_rebalance run_id=xxx

# 检查 Markdown pathref 引用
python -m scripts.path_tools.refactor check

# 移动/改名并重写引用
python -m scripts.path_tools.refactor move old/path.md new/path.md
```

## 4. 开发与验证流程

推荐流程：

1. 在本地修改策略与测试代码。
2. 执行本地校验（语法/单测）。
3. 通过浏览器上传到聚宽，执行云端回测。
4. 分析回测结果，记录在策略目录文档中。
5. 必要时进入模拟交易观察，再进行下一轮迭代。

说明：上传与回测环节依赖浏览器登录态，请先在 Chrome 中手动登录聚宽。

## 5. 本地检查命令

示例命令（在仓库根目录执行）：

```bash
# 语法检查（按需替换为目标策略文件）
python -m py_compile strategies/etf_dynamic_rebalance/etf_dynamic_rebalance.py

# 单元测试（示例）
pytest strategies/etf_dynamic_rebalance/tests -q
```

如果新增策略，建议同步补齐 `tests/` 目录并至少覆盖：

- 参数初始化正确性
- 核心权重/信号函数
- 调仓流程关键分支

## 6. 策略代码规范

### 6.1 生命周期函数

- `initialize(context)`：集中完成环境选项、参数初始化、费用/滑点设置、定时任务注册。
- `handle_data(context, data)` 或 `run_daily/run_weekly`：实现调仓主逻辑。

### 6.2 参数管理

- 策略参数统一在初始化阶段集中定义（如 `set_parameter`）。
- 避免魔法数字散落在交易逻辑中。
- 参数命名需要体现含义与单位（如窗口长度、阈值、权重上限）。

### 6.3 数据与性能

- 先筛选后计算，避免全市场全量重复查询。
- 同一周期内可复用的数据应缓存到局部变量。
- 优先批量接口、向量化计算，减少逐条循环调用 API。
- 明确处理缺失值、停牌、上市时长不足等边界情况。

### 6.4 风险与执行约束

- 明确仓位上下限与调仓步长限制。
- 对关键风控参数（最大回撤、单次换手、仓位漂移）保留日志。
- 下单前后记录目标权重、当前权重、实际成交偏差。

## 7. 注释与文档规范

- 注释目标是解释“为什么”，而不是逐行翻译“做了什么”。
- 推荐三层注释结构：
  - 模块头注释：策略思想、适用标的、核心公式与约束
  - 函数注释：输入、输出、关键副作用
  - 关键语句注释：复杂计算、风控裁剪、边界处理
- 研究结论、参数变更理由应写入对应策略目录的分析文档，而不是留在代码注释里。

## 8. 提交前检查清单

- 代码是否通过语法检查与相关单元测试？
- 是否避免引入未来函数或隐式未来数据？
- 参数、手续费、滑点、调仓频率是否与策略设计一致？
- 新增/修改逻辑是否同步更新分析文档与性能分析？
- 是否可以被他人根据文档复现回测流程？
