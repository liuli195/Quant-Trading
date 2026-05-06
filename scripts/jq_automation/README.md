# JoinQuant Cloud Automation

`scripts/jq_automation` 是本仓库的聚宽云端回测自动化工具。它负责把本地策略代码上传到聚宽策略编辑器，执行云端编译和正式回测，抓取回测详情页数据，并把结果按仓库约定落盘到 `backtest_runs/`、`test_batches/` 和 quota ledger 中。

策略本身仍然只在聚宽云端运行；本地只做语法检查、参数改写、浏览器自动化、产物归档和结果对比。

## 能力边界

工具覆盖的工作：

- 本地 `py_compile` 检查策略文件。
- 生成去注释后的 `<strategy>__upload.py` 上传文件。
- 使用 Playwright 持久化 Chrome profile，复用聚宽登录态。
- 自动打开聚宽策略编辑器、写入 Ace editor、设置回测参数、触发编译、启动正式回测。
- 等待回测完成，优先通过只读 JSON 接口抓取完整数据；失败时 fallback 到 DOM tab 文本抓取。
- 将回测结果保存为 `api_export.json`、`metadata.json`、`summary_metrics.json`、`all_data.json`、`tabs_raw/*.md` 和 `report/backtest_report.md`。
- 维护每日云端用时账本，防止免费额度被意外打满。
- 批量执行 `manifest.json` 中的 pending/failed 场景。
- 支持基于 Git ref + 参数组合的 A/B 实验扩展、运行和对比报告。

工具不会做的事：

- 不在本地执行完整聚宽策略逻辑。
- 不自动创建聚宽策略；首次需要你在聚宽侧已有策略，或通过 `--edit-url` 指向策略编辑页。
- 不自动登录聚宽；首次需要非 headless 浏览器里手动登录一次。
- 不自动提交 Git、不 checkout 分支、不把 A/B winner 写回策略文件。
- 不自动产出每个 run 的深度 `strategy-analysis.md` / `performance-analysis.md`；A/B 报告只检查并引用这些产物。

## 目录速览

```text
scripts/jq_automation/
  __main__.py              # python -m scripts.jq_automation 入口
  cli.py                   # jq-auto CLI 与 run/batch/fetch/upload 编排
  browser.py               # Playwright + 聚宽页面操作封装
  config.py                # scenario.json / YAML 解析与 sweep 展开
  local.py                 # py_compile、上传文件生成、params_diff 改写
  artifacts.py             # API/DOM 产物落盘入口
  manifest.py              # batch manifest 与 A/B manifest 更新
  quota.py                 # 每日云端用时账本
  abtest.py                # A/B 配置、expand、run、report
  git_versioning.py        # Git ref 冻结与源码物化
  metrics.py               # A/B 指标抽取与归一化
  snippets/*.js            # 注入聚宽页面的浏览器脚本
  scripts/
    strip_comments.py      # 上传前去注释
    save_backtest_data.py  # 回测数据转 Markdown/JSON
  tests/                   # 本地单元测试
```

## 环境准备

本仓库约定本地 Python 命令必须使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m scripts.jq_automation --help
```

依赖记录在 `requirements.txt`，关键依赖包括 `playwright`、`pyyaml`、`pytest`。如果 Playwright 浏览器尚未安装，需要先安装 Chromium 运行时：

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

首次使用云端命令时不要加 `--headless`。工具会打开持久化浏览器 profile，默认目录为：

```text
.local/chrome-jq/
```

在弹出的浏览器中完成聚宽登录后，工具会保存 cookies 到该 profile，后续运行可复用登录态。`.local/` 已被 Git 忽略。

## CLI 总览

入口有两个等价形式：

```powershell
.\.venv\Scripts\python.exe -m scripts.jq_automation <command> ...
.\.venv\Scripts\python.exe scripts\jq-auto.py <command> ...
```

常用命令：

```powershell
# 只做本地语法检查；可选生成 __upload.py
.\.venv\Scripts\python.exe -m scripts.jq_automation compile-check strategies\etf_factor_rotation\etf_factor_rotation.py --write-upload

# 上传到已有聚宽策略编辑器；默认上传后做云端编译
.\.venv\Scripts\python.exe -m scripts.jq_automation upload strategies\etf_factor_rotation\etf_factor_rotation.py --strategy-name etf_factor_rotation

# 执行单个 scenario.json：上传、编译、正式回测、抓取并落盘
.\.venv\Scripts\python.exe -m scripts.jq_automation run strategies\etf_factor_rotation\test_batches\<batch_id>\scenarios\<scenario_id>\scenario.json --yes --backtest-timeout 240

# 只读抓取已有回测详情页
.\.venv\Scripts\python.exe -m scripts.jq_automation fetch <backtestId-or-detail-url> --strategy etf_factor_rotation --run-id <run_id>

# 执行 manifest 中所有 pending/failed runs
.\.venv\Scripts\python.exe -m scripts.jq_automation batch strategies\etf_factor_rotation\test_batches\<batch_id>\manifest.json --yes --backtest-timeout 240

# 只执行某几个 scenario，可重复指定
.\.venv\Scripts\python.exe -m scripts.jq_automation batch strategies\etf_factor_rotation\test_batches\<batch_id>\manifest.json --scenario s01-smoke --yes
```

浏览器相关参数在 `upload`、`run`、`fetch`、`batch`、`ab run` 中通用：

- `--user-data-dir <dir>`：指定 Chrome profile，默认 `.local/chrome-jq/`。
- `--headless`：无头模式。首次登录不能使用。
- `--slow-mo <ms>`：每步浏览器动作延迟，调试页面适配时有用。
- `--edit-url <url>`：绕过策略列表查找，直接打开指定聚宽编辑页。

## 三条主线

这套工具最常用的三条主线是：

1. 走完整个云端测试流程：从本地策略文件到聚宽正式回测，再到本地产物和分析文档。
2. 使用参数扫描：用 `sweep` 把一个场景展开成多个参数组合，批量跑完后人工选择候选。
3. 使用 A/B 测试：把不同 Git 版本或不同已确认参数组合放进同一批次里做对照报告。

### 1. 怎么走完整个云端测试流程

完整流程建议按下面顺序走。

1. 修改策略代码。

   策略文件放在：

   ```text
   strategies/<strategy>/<strategy>.py
   ```

   参数建议集中写在 `set_parameter()` 或初始化阶段，后续 `params_diff` 只能安全改写 `set_parameter()` 里的单行 `g.<param> = ...`。

2. 做本地检查。

   ```powershell
   .\.venv\Scripts\python.exe -m py_compile strategies\<strategy>\<strategy>.py
   .\.venv\Scripts\python.exe -m pytest strategies\<strategy>\tests -q
   ```

   如果只是想验证 jq automation 能否生成上传版代码：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation compile-check strategies\<strategy>\<strategy>.py --write-upload
   ```

3. 准备 batch 目录。

   ```text
   strategies/<strategy>/test_batches/<batch_id>/
     manifest.json
     scenarios/
       <scenario_id>/
         scenario.json
   ```

   `batch_id` 建议带日期和目的，例如 `20260507-rsrs-window-scan`。`scenario_id` 建议短而稳定，例如 `s01-smoke`、`s02-param-scan`。

4. 写 `scenario.json`。

   单次正式回测最小配置：

   ```json
   {
     "strategy_file": "d:/My Project/Quant Trading/strategies/etf_factor_rotation/etf_factor_rotation.py",
     "strategy": "etf_factor_rotation",
     "scenario_id": "s01-smoke",
     "start_date": "2026-03-01",
     "end_date": "2026-03-31",
     "capital": 100000,
     "frequency": "1d",
     "py_version": "Python3",
     "estimated_minutes": 5,
     "batch_id": "20260507-smoke"
   }
   ```

5. 写 `manifest.json`。

   ```json
   {
     "batch_id": "20260507-smoke",
     "strategy": "etf_factor_rotation",
     "scenarios": {
       "s01-smoke": { "status": "pending" }
     }
   }
   ```

6. 首次登录聚宽。

   第一次不要加 `--headless`。如果工具能在策略列表里找到 `strategy_name`，直接运行；如果找不到，把聚宽编辑器 URL 写入 `scenario.json` 的 `edit_url`，或命令行传 `--edit-url`。

7. 跑云端正式回测。

   单场景：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation run strategies\<strategy>\test_batches\<batch_id>\scenarios\<scenario_id>\scenario.json --yes --backtest-timeout 240
   ```

   整批 pending/failed 场景：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation batch strategies\<strategy>\test_batches\<batch_id>\manifest.json --yes --backtest-timeout 240
   ```

   只跑某个场景：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation batch strategies\<strategy>\test_batches\<batch_id>\manifest.json --scenario s01-smoke --yes --backtest-timeout 240
   ```

8. 检查落盘产物。

   成功后 manifest 会写入 `run_id`，对应目录为：

   ```text
   strategies/<strategy>/backtest_runs/<run_id>/
   ```

   必看文件：

   ```text
   metadata.json
   summary_metrics.json
   report/backtest_report.md
   tabs_raw/
   ```

   如果有 `api_export.json`，说明结构化 API bundle 抓取成功；如果只有 `dom_tabs_persisted.json`，说明走了 DOM fallback。

9. 补分析文档。

   每次正式回测完成后，应补齐：

   ```text
   report/strategy-analysis.md
   report/performance-analysis.md
   ```

   `jq_automation` 负责产物抓取和指标归档，不替代策略解释、失败归因、参数变更理由和下一步决策。

10. 失败后重跑或抓取已有回测。

   `batch` 会自动选择 pending/failed run，修复配置后重新跑同一个 manifest 即可。若聚宽已经完成回测但本地抓取失败，可以用 `fetch` 补拉：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation fetch <backtestId-or-detail-url> --strategy <strategy> --run-id <run_id>
   ```

### 2. 怎么使用参数扫描

参数扫描用 `scenario.json` 里的 `sweep` 声明，一定通过 `batch` 执行。`run` 命令要求一个 scenario 只能展开成一个 run，所以不能直接跑含有多组合 `sweep` 的 scenario。

使用步骤：

1. 确认可扫描参数。

   每个参数必须是策略 `set_parameter()` 里的单行赋值，例如：

   ```python
   def set_parameter(context):
       g.TopK = 2
       g.TargetVol = 0.12
       g.RSRS_M = 600
   ```

2. 创建扫描场景。

   ```text
   strategies/<strategy>/test_batches/<batch_id>/scenarios/s01-param-scan/scenario.json
   ```

3. 写 grid sweep。

   grid 会计算笛卡尔积，适合小规模网格：

   ```json
   {
     "strategy_file": "d:/My Project/Quant Trading/strategies/etf_factor_rotation/etf_factor_rotation.py",
     "strategy": "etf_factor_rotation",
     "scenario_id": "s01-param-scan",
     "start_date": "2025-05-01",
     "end_date": "2026-04-30",
     "capital": 100000,
     "frequency": "1d",
     "py_version": "Python3",
     "estimated_minutes": 8,
     "batch_id": "20260507-rsrs-scan",
     "sweep": {
       "strategy": "grid",
       "dimensions": {
         "TopK": [2, 3],
         "TargetVol": [0.10, 0.12],
         "RSRS_M": [600, 800]
       }
     }
   }
   ```

   上面会展开 2 x 2 x 2 = 8 个 run，label 类似：

   ```text
   TopK=2_TargetVol=0.1_RSRS_M=600
   ```

4. 或写 list sweep。

   list 适合只跑人工挑选的组合，也适合从前一轮扫描结果中提炼候选：

   ```json
   {
     "sweep": {
       "strategy": "list",
       "combinations": [
         {
           "label": "low-vol",
           "params": { "TopK": 2, "TargetVol": 0.08, "RSRS_M": 600 }
         },
         {
           "label": "balanced",
           "params": { "TopK": 3, "TargetVol": 0.12, "RSRS_M": 800 }
         }
       ]
     }
   }
   ```

5. 在 manifest 中登记场景。

   ```json
   {
     "batch_id": "20260507-rsrs-scan",
     "strategy": "etf_factor_rotation",
     "scenarios": {
       "s01-param-scan": { "status": "pending" }
     }
   }
   ```

6. 执行 batch。

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation batch strategies\etf_factor_rotation\test_batches\20260507-rsrs-scan\manifest.json --yes --backtest-timeout 240
   ```

   第一次执行时，工具会把 `sweep` 展开为 `manifest.scenarios["s01-param-scan"].runs[]`。之后重跑同一个 batch 时，只会继续执行 pending/failed 的组合。

7. 查看扫描结果。

   每个组合都有独立 `run_id`。先看 manifest 找到映射关系，再看各 run 的：

   ```text
   summary_metrics.json
   report/backtest_report.md
   report/strategy-analysis.md
   report/performance-analysis.md
   ```

   当前工具不自动选最优参数。建议人工比较年化收益、最大回撤、夏普、换手、日志异常和策略解释，把选中的组合记录到后续报告或 A/B 配置的 `scan_source` 里。

8. 二次确认。

   扫描出的“最好组合”通常不要直接改成生产默认值。推荐把它放进 A/B 测试，与 baseline、旧生产版本或另一个分支的最佳组合对比。

### 3. 怎么使用 A/B 测试

A/B 测试用于比较多个最终上传代码快照。它比普通参数扫描更强调可复现：每个候选的代码来源会在 `ab expand` 阶段冻结到 Git commit SHA。

使用步骤：

1. 准备 Git 版本。

   A/B 的 `code_source` 读取的是 Git ref 中的文件，不读取未提交工作区。要比较当前改动，先提交到 branch 或创建可解析的 commit/tag。工具不会执行 `git checkout`。

2. 准备 A/B 配置目录。

   ```text
   strategies/<strategy>/test_batches/<batch_id>/abtests/<experiment_id>.json
   ```

3. 写 A/B 配置。

   ```json
   {
     "experiment_id": "rsrs-window-ab",
     "strategy": "etf_factor_rotation",
     "batch_id": "20260507-rsrs-ab",
     "baseline": "main_best",
     "controls": ["main_best"],
     "base": {
       "code_source": {
         "type": "git",
         "ref": "main",
         "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
       },
       "start_date": "2025-05-01",
       "end_date": "2026-04-30",
       "capital": 100000,
       "estimated_minutes": 12,
       "frequency": "1d",
       "py_version": "Python3"
     },
     "variants": [
       {
         "label": "main_best",
         "role": "control",
         "params_mode": "params_diff",
         "params_diff": {
           "TopK": 2,
           "TargetVol": 0.12,
           "RSRS_M": 600
         },
         "scan_source": {
           "batch_id": "20260507-rsrs-scan",
           "scenario_id": "s01-param-scan",
           "run_label": "TopK=2_TargetVol=0.12_RSRS_M=600"
         }
       },
       {
         "label": "feature_best",
         "role": "variant",
         "code_source": {
           "type": "git",
           "ref": "feature/rsrs-window",
           "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
         },
         "params_mode": "params_diff",
         "params_diff": {
           "TopK": 3,
           "TargetVol": 0.10,
           "RSRS_M": 800
         },
         "scan_source": {
           "batch_id": "20260507-feature-rsrs-scan",
           "scenario_id": "s01-param-scan",
           "run_label": "TopK=3_TargetVol=0.1_RSRS_M=800"
         }
       }
     ],
     "metrics": [
       { "key": "annual_return", "direction": "maximize" },
       { "key": "max_drawdown", "direction": "minimize" },
       { "key": "sharpe", "direction": "maximize" },
       { "key": "actual_minutes", "direction": "minimize" }
     ]
   }
   ```

4. expand。

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation ab expand strategies\etf_factor_rotation\test_batches\20260507-rsrs-ab\abtests\rsrs-window-ab.json
   ```

   这一步会：

   - 解析并校验配置。
   - 把每个 `code_source.ref` 冻结为完整 commit SHA。
   - 用 `git show <commit>:<path>` 读取源码并物化到 `.local/jq-automation/ab/<experiment_id>/`。
   - 生成每个 variant 对应的 `scenarios/ab-<experiment>-<label>/scenario.json`。
   - 写入 `manifest.json` 的 `ab_experiments.<experiment_id>`。

5. run。

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation ab run strategies\etf_factor_rotation\test_batches\20260507-rsrs-ab\abtests\rsrs-window-ab.json --yes --backtest-timeout 240
   ```

   `ab run` 会先执行一次幂等 expand，然后在同一个浏览器/编辑器 session 中按 `upload_index` 顺序运行 pending/failed variants。每个 variant 都会覆盖上传代码、编译、启动正式回测、抓取产物，并在 manifest 中记录 `run_id`、`backtest_id`、`backtest_url`、`uploaded_code_sha256`。

6. report。

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation ab report strategies\etf_factor_rotation\test_batches\20260507-rsrs-ab\abtests\rsrs-window-ab.json --experiment rsrs-window-ab
   ```

   输出：

   ```text
   strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-comparison.md
   strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-summary.json
   ```

   baseline 未完成时默认返回非 0。需要看部分结果时加：

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.jq_automation ab report strategies\etf_factor_rotation\test_batches\20260507-rsrs-ab\abtests\rsrs-window-ab.json --experiment rsrs-window-ab --allow-partial
   ```

7. 重跑失败候选。

   修复问题后再次执行 `ab run`。completed variants 会保留，pending/failed variants 会继续跑。若配置变化且已有 completed run，工具会因 config hash 改变而拒绝覆盖；这时应新建 `experiment_id`。

## 单场景配置

`run` 和 `batch` 的基本单位是 `scenario.json`。推荐路径：

```text
strategies/<strategy>/test_batches/<batch_id>/scenarios/<scenario_id>/scenario.json
```

最小示例：

```json
{
  "strategy_file": "d:/My Project/Quant Trading/strategies/etf_factor_rotation/etf_factor_rotation.py",
  "strategy": "etf_factor_rotation",
  "scenario_id": "s01-smoke",
  "start_date": "2026-04-01",
  "end_date": "2026-04-30",
  "capital": 100000,
  "frequency": "1d",
  "py_version": "Python3",
  "estimated_minutes": 5,
  "batch_id": "20260505-0000-etf-factor-rotation-full-test"
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `strategy_file` | 是 | 本地策略文件。相对路径按 `scenario.json` 所在目录解析。 |
| `scenario_id` | 是 | 场景 ID，通常等于目录名。 |
| `start_date` / `end_date` | 是 | 回测区间，格式 `YYYY-MM-DD`。 |
| `capital` | 是 | 初始资金，支持数字或带逗号字符串。 |
| `strategy` | 否 | 策略目录名；未提供时尝试从 `strategies/<name>/...` 推断。 |
| `batch_id` | 否 | 存在时用于回写对应 `manifest.json`。 |
| `strategy_name` | 否 | 聚宽策略列表中的策略名；默认用策略文件 stem。 |
| `edit_url` | 否 | 聚宽策略编辑页 URL；列表查找失败时建议显式提供。 |
| `frequency` | 否 | 支持 `1d`、`1m`、`tick`、`5m`、`15m`、`30m`、`60m` 及部分英文别名。 |
| `py_version` | 否 | 聚宽侧 Python 版本，默认 `Python3`。 |
| `estimated_minutes` | 否 | 用于 quota guardrail 的预计云端耗时。 |
| `run_id` | 否 | 指定本地 run 目录名；默认由回测 ID 生成。 |
| `params_base` | 否 | batch 场景的基础参数覆盖。 |
| `params_diff` | 否 | 单次 run 的参数覆盖。 |
| `sweep` | 否 | 在 batch 中展开为多个参数组合。 |

### 参数覆盖

`params_diff` 会改写策略源码中 `set_parameter()` 函数内的 `g.<name> = <value>` 赋值，再把改写后的临时代码上传到聚宽。它不是聚宽运行时外部参数。

支持的值类型：

- `int`、`float`、`bool`、`str`、`null`
- 上述标量组成的 list

限制：

- 目标参数必须在 `set_parameter()` 中存在。
- 同一参数不能在 `set_parameter()` 中赋值多次。
- 目标赋值必须是单行。
- 如果同名 `g.<name>` 只在其他函数中出现，工具会拒绝改写，避免误伤运行态变量。
- 不建议把说明文字放进 `params_diff.note`；manifest 里可以有 note，但参数改写时 `note` 会被当作真实参数名。

示例：

```json
{
  "params_diff": {
    "TopK": 3,
    "TargetVol": 0.10,
    "fq_mode": null
  }
}
```

### 参数扫描配置细节

`sweep` 只在 `batch` 流程中展开。`run` 命令要求一个 `scenario.json` 只能展开成一个 run。

网格扫描：

```json
{
  "sweep": {
    "strategy": "grid",
    "dimensions": {
      "TopK": [1, 2, 3],
      "TargetVol": [0.10, 0.12]
    }
  }
}
```

列表扫描：

```json
{
  "sweep": {
    "strategy": "list",
    "combinations": [
      { "label": "conservative", "params": { "TopK": 1, "TargetVol": 0.08 } },
      { "label": "baseline", "params": { "TopK": 2, "TargetVol": 0.12 } }
    ]
  }
}
```

网格扫描的默认 run label 形如 `TopK=2_TargetVol=0.12`。

## Batch Manifest

批量测试目录推荐结构：

```text
strategies/<strategy>/test_batches/<batch_id>/
  manifest.json
  scenarios/
    <scenario_id>/
      scenario.json
  report/
```

最小 manifest：

```json
{
  "batch_id": "20260505-0000-etf-factor-rotation-full-test",
  "strategy": "etf_factor_rotation",
  "scenarios": {
    "s01-smoke": { "status": "pending" },
    "s02-baseline": { "status": "pending" }
  }
}
```

`batch` 会读取 manifest 中所有非 completed 的 run：

- `status=pending` 且没有 `runs[]`：先读取对应 `scenario.json`，根据 `sweep` 展开 run entry。
- `runs[].status` 不是 `completed`：执行该 run。
- run 成功后写入 `run_id`、`status=completed`、`params_diff`。
- run 失败后写入 `status=failed` 和 `error`。
- scenario 顶层状态由 `runs[]` 汇总得到：有 failed 则 failed，有 in_progress/started 则 in_progress，全 completed 则 completed。

## 正式回测底层步骤

`run` 和 batch 中的单个 run 大致执行以下步骤：

1. 对策略文件执行本地 `py_compile`。
2. 生成 `<strategy>__upload.py`，内容为去注释后的上传版源码。
3. 打开聚宽策略编辑器。若没有传 `--edit-url`，会进入策略列表并按 `strategy_name` 查找编辑链接。
4. 读取聚宽页面上的今日用时与免费额度；读取失败时使用本地 quota ledger。
5. 写入 Ace editor。
6. 使用短区间做一次云端编译检查，短区间默认为最近约 30 天，并且不超过配置的 `end_date`。
7. 设置正式回测参数并启动正式回测。
8. 根据聚宽详情页 URL 里的 `backtestId` 生成本地 `run_id`，格式类似 `20260507-0343-bt<backtestId>`。
9. 等待详情页显示回测完成。
10. 优先调用页面内只读 JSON 接口抓取 API bundle；失败时抓取 DOM tabs。
11. 保存产物、更新 quota ledger、回写 manifest。

`--backtest-timeout` 只控制等待正式回测完成的秒数，不影响聚宽实际已经启动的云端任务。

## 产物目录

单次回测产物保存到：

```text
strategies/<strategy>/backtest_runs/<run_id>/
```

常见文件：

| 路径 | 说明 |
| --- | --- |
| `api_export.json` | 只读 JSON 接口抓到的原始 bundle。API 抓取成功时存在。 |
| `dom_tabs_persisted.json` | DOM fallback 的原始 tab 文本。fallback 时存在。 |
| `metadata.json` | 回测 ID、URL、区间、资金、频率、Python 版本、抓取方式等。 |
| `summary_metrics.json` | 核心绩效指标。 |
| `all_data.json` | tabs/report 索引。 |
| `tabs_raw/transactioninfo.md` | 交易明细。 |
| `tabs_raw/positioninfo.md` | 持仓与收益。 |
| `tabs_raw/daily_returns.md` | 每日收益。 |
| `tabs_raw/*.md` | 风险指标、日志、profile 等其他标签页。 |
| `report/backtest_report.md` | 回测数据汇总。 |
| `report/strategy-analysis.md` | 策略分析，应由后续分析流程补齐。 |
| `report/performance-analysis.md` | 性能分析，应由后续分析流程补齐。 |

quota ledger 保存到：

```text
docs/joinquant-data/quota_ledger/<YYYYMMDD>.json
```

账本会优先记录聚宽 `runTimeInfo` 返回的实际耗时 `needSeconds / 60`；如果拿不到实际耗时，则用 `estimated_minutes` 估算。失败/取消 run 若已有实际耗时，也会计入消耗。

## 抓取机制

API 抓取路径优先级最高。`browser.py` 会向回测详情页注入 `snippets/extract.js`，调用页面内只读接口汇总：

- stats / summary metrics
- transactions
- positions
- result rows / daily returns
- risk tabs
- logs
- profile
- runtime info

如果 API bundle 抓取失败，工具会调用 DOM fallback，读取页面上可见 tab 文本并转换为 Markdown。fallback 可保留关键数据，但结构化程度和完整性通常不如 API bundle。

## A/B 配置字段细节

A/B 实验用于对比多个“最终上传代码快照”。每个候选可以来自不同 Git ref，也可以在同一 Git ref 上叠加不同 `params_diff`。

推荐配置路径：

```text
strategies/<strategy>/test_batches/<batch_id>/abtests/<experiment_id>.json
```

命令：

```powershell
# 将 A/B 配置展开为 scenario.json 和 manifest.ab_experiments
.\.venv\Scripts\python.exe -m scripts.jq_automation ab expand strategies\<strategy>\test_batches\<batch_id>\abtests\<experiment_id>.json

# 在同一浏览器/编辑器 session 中顺序运行 pending/failed variants
.\.venv\Scripts\python.exe -m scripts.jq_automation ab run strategies\<strategy>\test_batches\<batch_id>\abtests\<experiment_id>.json --yes --backtest-timeout 240

# 生成对比报告
.\.venv\Scripts\python.exe -m scripts.jq_automation ab report strategies\<strategy>\test_batches\<batch_id>\abtests\<experiment_id>.json --experiment <experiment_id>
```

配置示例：

```json
{
  "experiment_id": "factor-v2-ab",
  "strategy": "etf_factor_rotation",
  "batch_id": "20260506-factor-v2-ab",
  "baseline": "main_best",
  "controls": ["main_best"],
  "base": {
    "code_source": {
      "type": "git",
      "ref": "main",
      "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
    },
    "start_date": "2025-05-01",
    "end_date": "2026-04-30",
    "capital": 100000,
    "estimated_minutes": 20,
    "frequency": "1d",
    "py_version": "Python3"
  },
  "variants": [
    {
      "label": "main_best",
      "role": "control",
      "params_mode": "params_diff",
      "params_diff": {
        "TopK": 2,
        "TargetVol": 0.12
      },
      "scan_source": {
        "batch_id": "20260506-main-sweep",
        "scenario_id": "s01-main-grid",
        "run_label": "TopK=2_TargetVol=0.12"
      },
      "note": "main 参数扫描后人工确认的最佳组合"
    },
    {
      "label": "branch_best",
      "role": "variant",
      "code_source": {
        "type": "git",
        "ref": "feature/factor-v2",
        "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
      },
      "params_mode": "params_diff",
      "params_diff": {
        "TopK": 3,
        "TargetVol": 0.10
      },
      "note": "新分支参数扫描后的候选组合"
    }
  ],
  "metrics": [
    { "key": "annual_return", "direction": "maximize" },
    { "key": "max_drawdown", "direction": "minimize" },
    { "key": "sharpe", "direction": "maximize" },
    { "key": "actual_minutes", "direction": "minimize" }
  ]
}
```

A/B 关键语义：

- `baseline` 必须匹配一个 `variants[].label`，用于 delta 对比。
- `controls` 可选，用于记录额外对照组；baseline 本身通常也写进 controls。
- `base.code_source.type` 当前只支持 `git`。
- `ab expand` 会把 branch/tag/short SHA 冻结成完整 commit SHA，并写入 manifest。后续 `ab run` 使用 manifest 中冻结的 commit，不重新解析 branch。
- `params_mode=params_diff`：从冻结 commit 读取策略源码，再用 `params_diff` 改写 `set_parameter()`。
- `params_mode=baked_in_git`：不改写源码，认为参数已经提交在对应 Git ref 中。
- `scan_source` 只用于记录该候选来自哪次参数扫描，不参与自动选优。
- `uploaded_code_sha256` 由 `ab run` 对最终上传文件计算，用于绑定候选、上传代码和云端回测记录。
- `ab run` 串行执行候选，不并发启动多个聚宽回测，避免同一个编辑器状态互相覆盖。

A/B 报告输出到：

```text
strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-comparison.md
strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-summary.json
```

报告会汇总各 variant 的指标、相对 baseline 的变化、run 状态和关键产物完整性。默认 baseline 缺失或未完成时返回非 0；加 `--allow-partial` 可以生成部分报告。

## 路径别名

工具落盘路径不直接拼接硬编码目录，而是通过 `path_aliases.json` 中的 alias 解析：

| alias | 用途 |
| --- | --- |
| `backtest_run` | `strategies/<strategy>/backtest_runs/<run_id>` |
| `backtest_report_dir` | 单次 run 的 `report/` |
| `backtest_tabs_dir` | 单次 run 的 `tabs_raw/` |
| `test_batch` | `strategies/<strategy>/test_batches/<batch_id>` |
| `test_batch_scenarios` | batch 下的 `scenarios/` |
| `test_batch_abtests` | batch 下的 `abtests/` |
| `test_batch_report_dir` | batch 下的 `report/` |
| `joinquant_quota_ledger` | `docs/joinquant-data/quota_ledger/` |

脚本中新增任何结果目录引用时，应优先调用 `scripts.path_tools.aliases.resolve_path()` 或 `ensure_dir()`。

## 状态与返回码

常见返回码：

- `0`：成功。
- `1`：用户取消、run 失败、A/B 不满足报告条件。
- `2`：配置、路径、本地校验或自动化前置条件错误。

常见状态：

- `pending`：等待执行。
- `in_progress` / `started`：已进入执行流程。
- `completed`：本地产物已保存且 manifest 已回写。
- `failed`：执行失败，可修复后重新运行 batch 或 A/B。
- `cancelled`：用户取消或外部标记取消。

## 故障排查

找不到聚宽策略编辑页：

- 首次运行不要使用 `--headless`，确认已经登录聚宽。
- 如果策略列表无法按名称匹配，手动打开策略编辑页，把 URL 传给 `--edit-url`。

云端编译超时或失败：

- 先运行 `compile-check` 排除本地语法问题。
- 查看命令输出中的 JoinQuant compile error / Traceback。
- 如果页面按钮或文案变化，优先检查 `browser.py` 和 `snippets/compile.js`。

额度不足：

- 工具会优先读取聚宽页面上的今日已用/免费额度。
- 读取失败时使用 `docs/joinquant-data/quota_ledger/<YYYYMMDD>.json`。
- 调小 `estimated_minutes` 前先确认实际回测耗时，避免 guardrail 失效。

`params_diff` 报错：

- 确认目标参数在 `set_parameter()` 中是单行 `g.<name> = ...`。
- 确认参数没有在 `set_parameter()` 中重复赋值。
- 不要把说明字段混入 `params_diff`。

抓取结果不完整：

- 优先检查 `api_export.json` 是否存在。
- 若只存在 `dom_tabs_persisted.json`，说明 API bundle 失败并已走 fallback。
- `summary_metrics.json` 缺字段时，A/B 指标会尝试从 `api_export.json` 的 stats fallback。

A/B expand 报 Git 错误：

- `code_source.ref` 必须能被 `git rev-parse` 解析。
- `code_source.path` 必须存在于该 commit。
- 已完成实验的配置 hash 改变时，工具会拒绝覆盖；请新建 `experiment_id` 或归档旧实验。

## 验证

改动工具代码后建议执行：

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\jq-auto.py scripts\jq_automation\__init__.py scripts\jq_automation\__main__.py scripts\jq_automation\config.py scripts\jq_automation\local.py scripts\jq_automation\manifest.py scripts\jq_automation\artifacts.py scripts\jq_automation\quota.py scripts\jq_automation\paths.py scripts\jq_automation\browser.py scripts\jq_automation\cli.py scripts\jq_automation\abtest.py scripts\jq_automation\git_versioning.py scripts\jq_automation\metrics.py
.\.venv\Scripts\python.exe -m pytest scripts\jq_automation\tests -q
.\.venv\Scripts\python.exe -m scripts.path_tools.refactor check
```

只改 README 时通常不需要跑云端回测；最多执行 pathref 检查即可。

## 临时产物清理

工具会自动删除 `apply_params_overrides()` 产生的 `__sweep_tmp.py` 临时文件。

以下产物通常会保留，且已被 `.gitignore` 忽略：

- `.local/chrome-jq/`
- `.local/jq-automation/`
- `*__upload.py`

它们用于复用登录态、审计最终上传代码或排查 A/B 候选来源。确认不再需要时可以手动清理。
