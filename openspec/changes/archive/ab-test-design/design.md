# jq_automation A/B 测试能力方案设计文档

## 摘要

为 `scripts/tools/jq_automation` 增加声明式 A/B 测试能力：用户通过一个实验配置声明 baseline、多个 controls、variants、参数差异和 Git 策略版本；工具把每个候选项生成一份最终上传的完整策略 `.py` 快照，在一次聚宽策略编辑器上传会话中顺序覆盖上传、编译、回测、抓取结果，并生成 A/B 对比报告。

v1 定位为“可复现的回测变体对比工具”，首要交付物是对比报告，而不是自动改策略或自动筛参。

本仓库当前策略参数直接保存在策略 `.py` 内部，因此 A/B candidate 的真实执行体不是“外部参数 + 代码”的抽象组合，而是“Git 策略源码 + 扫描确认参数组合”生成后的完整 `.py`。聚宽正式回测启动后，会在云端回测列表中保存当次代码快照，因此同一个编辑器后续覆盖代码不影响已启动回测的追溯。

## 目标

- 支持同一策略的参数 A/B，例如 `fq_mode='pre'` vs `fq_mode=None`。
- 支持 Git 管理的代码版本 A/B，例如 `main`、历史 tag、实验 branch、指定 commit 之间的对比。
- 支持多个对照版本：一个 `baseline` 作为主 delta 参照，多个 `controls` 用于横向校准。
- 支持“参数扫描后确认组合”的工作流：`main_best`、`branch_best`、旧版本 control 都可以记录各自的 `scan_source`。
- 支持一次上传会话内完成 A/B：一次打开浏览器和策略编辑器，顺序上传多个最终 `.py` 快照。
- 输出可复现、可审计的 A/B 对比报告。
- 继续遵守 path alias、manifest、`backtest_runs` 目录约定。

## 非目标

- v1 不做统计显著性检验。
- v1 不替代现有 `sweep` 参数扫描能力。
- v1 不并行启动多个 JoinQuant 云端回测，避免编辑器状态和每日额度冲突。
- v1 不自动创建 Git branch、tag、commit、merge，也不自动把 winner 写回策略默认参数。
- v1 不改变策略参数保存在 `.py` 内的现状；A/B 只负责从已确认参数组合生成最终上传代码。
- v1 不自动生成每个 run 的深度策略分析，只检查并链接已有分析产物。

## A/B 配置设计

新增 A/B 配置文件，建议放在：

```text
strategies/<strategy>/test_batches/<batch_id>/abtests/<experiment_id>.json
```

示例：

```json
{
  "experiment_id": "factor-v2-ab",
  "strategy": "etf_factor_rotation",
  "batch_id": "20260506-factor-v2-ab",
  "baseline": "main_best",
  "controls": ["main_best", "prod_20260501"],
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
    "frequency": "每天",
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
        "run_label": "TopK=2_TargetVol=0.12",
        "selection_note": "main 参数扫描后人工确认的最佳组合"
      },
      "note": "当前主分支最佳参数组合，作为主 baseline。"
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
      "scan_source": {
        "batch_id": "20260506-factor-v2-sweep",
        "scenario_id": "s01-branch-grid",
        "run_label": "TopK=3_TargetVol=0.10",
        "selection_note": "新分支参数扫描后人工确认的最佳组合"
      },
      "note": "新策略结构在自身最佳参数组合下的表现。"
    },
    {
      "label": "prod_20260501",
      "role": "control",
      "code_source": {
        "type": "git",
        "ref": "prod/2026-05-01",
        "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
      },
      "params_mode": "baked_in_git",
      "params_diff": {
        "TopK": 2,
        "TargetVol": 0.12
      },
      "note": "旧生产确认版本，用于判断新旧策略是否相对历史稳定版本退化。"
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

配置约束：

- `experiment_id` 在同一个 batch 内唯一。
- `baseline` 必须匹配一个 `variants[].label`，但该 label 可以指向任何 Git 版本，包括 `main`、历史 tag、实验 branch 或 commit SHA。
- `controls` 是可选数组，表示多个对照版本；每个 control label 也必须匹配一个 `variants[].label`。
- `baseline` 自动视为 control，即使没有显式写入 `controls`。
- `variants[].label` 在同一实验内必须唯一。
- `variants[].role` 可取 `control` 或 `variant`；缺省为 `variant`。
- `params_diff` 只允许真实 `set_parameter()` 中的 `g.<param>` 覆盖。
- `note` 必须放在 variant 顶层，不能放入 `params_diff`，避免现有 `apply_params_overrides()` 把备注误当策略参数注入。
- `code_source.type=git` 是代码版本管理的默认方式；variant 级 `code_source` 覆盖 `base.code_source`。
- `code_source.ref` 可以是 branch、tag 或 commit SHA；`ab expand` 必须把它冻结成 commit SHA。
- `ab run` 使用 manifest 中冻结的 commit SHA，不重新解析 branch，保证实验复现。
- `params_mode` 可取 `params_diff` 或 `baked_in_git`；缺省为 `params_diff`。
- `params_mode=params_diff` 表示工具把扫描确认的参数注入策略 `.py`，生成最终上传代码。
- `params_mode=baked_in_git` 表示 Git ref 中已经提交最终参数；此时 `params_diff` 可省略，若保留则仅作为报告中的参数快照说明。
- `scan_source` 可选，用于记录该候选参数组合来自哪次 `sweep/batch`，不参与自动选优。
- `uploaded_code_sha256` 不在配置中手写，由 `ab run` 对最终上传 `.py` 自动计算并写入 manifest/report。
- 未声明 `metrics` 时使用默认指标：`annual_return`、`excess_return`、`max_drawdown`、`sharpe`、`actual_minutes`。

## Git 版本工作流与实际意义

Git 在本方案中负责定义“策略代码版本”，`jq_automation` 负责把这些版本拿去云端回测并做对比。

- 在 `main` 上设计策略的实际意义：`main` 表示当前主开发线，是默认可信参照，但它本身还不是 A/B 的最终执行体。
- 在 `main` 上做参数扫描的实际意义：用现有 `sweep/batch` 找到主分支策略在当前假设下的最佳参数组合，形成 `main_best`。
- 开 Git 分支调整策略的实际意义：分支表达“策略结构或逻辑变化”，例如新增信号、调整风控、关闭 profile，而不是临时覆盖当前工作区。
- 在新分支上再次做参数扫描的实际意义：让新策略结构也使用自己确认后的最佳参数，A/B 比较的是 `main_best` vs `branch_best`，不是“主分支最佳参数”硬套到新分支。
- 引入旧版本 control 的实际意义：把历史生产版本或已确认 tag 放进同一张表，判断新旧策略是否相对稳定版本退化。
- 使用 commit SHA 的实际意义：把 branch/tag 固定成不可变版本，最适合归档后的复跑和审计。

工具执行时不做 `git checkout`，而是在 `expand` 阶段把 ref 解析为 commit SHA，在 `run` 阶段用 `git show <commit>:<path>` 读取策略文件内容。这样不会改变当前工作区，也不会覆盖用户未提交的本地修改。

由于参数当前保存在策略 `.py` 内，`params_diff` 的意义不是外部运行参数，而是对 Git 源码中的 `set_parameter()` 做受控改写，得到最终上传到聚宽的完整 `.py`。这个最终代码会计算 `uploaded_code_sha256`，用于把本地候选项、聚宽回测记录和分析报告三者绑定起来。

## CLI 设计

新增 `ab` 子命令：

```powershell
python -m scripts.tools.jq_automation ab expand <ab_config> [--force-reset-pending]
python -m scripts.tools.jq_automation ab run <ab_config> --yes [--backtest-timeout 180]
python -m scripts.tools.jq_automation ab report <ab_config-or-manifest> --experiment <id> [--allow-partial]
```

命令行为：

- `ab expand`：读取 A/B 配置，生成或更新对应 `scenario.json`，并写入 manifest 的 `ab_experiments` 映射。
- `ab run`：先执行 `expand`，再启动一次浏览器和一次策略编辑器会话，在该会话内按候选项顺序覆盖上传最终 `.py` 并启动正式回测。
- `ab report`：读取已完成 run 的产物，生成 Markdown 对比报告和 JSON 摘要。

返回码约定：

- `0`：命令成功。
- `1`：用户取消或实验未满足报告条件。
- `2`：配置、manifest、路径或本地校验错误。

## Manifest 扩展

在现有 `manifest.json` 顶层新增 `ab_experiments`，作为实验索引层。已有 `scenarios` 和 `runs[]` 结构不破坏。

示例：

```json
{
  "ab_experiments": {
    "factor-v2-ab": {
      "status": "completed",
      "baseline": "main_best",
      "controls": ["main_best", "prod_20260501"],
      "config_hash": "sha256:...",
      "upload_session": {
        "session_started_at": "2026-05-06T10:00:00",
        "session_finished_at": "2026-05-06T10:38:00",
        "strategy_name": "etf_factor_rotation",
        "edit_url": "https://www.joinquant.com/algorithm/index/edit?algorithmId=...",
        "candidate_order": ["main_best", "branch_best", "prod_20260501"]
      },
      "variants": [
        {
          "label": "main_best",
          "scenario_id": "ab-factor-v2-ab-main-best",
          "run_label": "main_best",
          "run_id": "20260505-0933-bt...",
          "role": "control",
          "is_baseline": true,
          "upload_index": 1,
          "code_source": {
            "type": "git",
            "ref": "main",
            "commit": "8f3c1a9...",
            "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
          },
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
          "uploaded_code_sha256": "sha256:...",
          "backtest_id": "7a98269d2440d36f387fb95085dfb39d",
          "backtest_url": "https://www.joinquant.com/algorithm/backtest/detail?backtestId=...",
          "status": "completed"
        },
        {
          "label": "branch_best",
          "scenario_id": "ab-factor-v2-ab-branch-best",
          "run_label": "branch_best",
          "run_id": "20260505-2215-bt...",
          "role": "variant",
          "upload_index": 2,
          "code_source": {
            "type": "git",
            "ref": "feature/factor-v2",
            "commit": "c91b0e2...",
            "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
          },
          "params_mode": "params_diff",
          "params_diff": {
            "TopK": 3,
            "TargetVol": 0.10
          },
          "scan_source": {
            "batch_id": "20260506-factor-v2-sweep",
            "scenario_id": "s01-branch-grid",
            "run_label": "TopK=3_TargetVol=0.10"
          },
          "uploaded_code_sha256": "sha256:...",
          "backtest_id": "149cf2096d978f58083820813960d145",
          "backtest_url": "https://www.joinquant.com/algorithm/backtest/detail?backtestId=...",
          "status": "completed"
        },
        {
          "label": "prod_20260501",
          "scenario_id": "ab-factor-v2-ab-prod-20260501",
          "run_label": "prod_20260501",
          "run_id": "20260505-1742-bt...",
          "role": "control",
          "upload_index": 3,
          "code_source": {
            "type": "git",
            "ref": "prod/2026-05-01",
            "commit": "4a28d5b...",
            "path": "strategies/etf_factor_rotation/etf_factor_rotation.py"
          },
          "params_mode": "baked_in_git",
          "uploaded_code_sha256": "sha256:...",
          "backtest_id": "old-prod-backtest-id",
          "backtest_url": "https://www.joinquant.com/algorithm/backtest/detail?backtestId=...",
          "status": "completed"
        }
      ],
      "reports": {
        "markdown": "report/ab-factor-v2-ab-comparison.md",
        "json": "report/ab-factor-v2-ab-summary.json"
      }
    }
  }
}
```

状态聚合规则：

- 任一 control 或 variant `failed`：experiment `status=failed`。
- 任一 control 或 variant `pending` 或 `in_progress`：experiment `status=in_progress`。
- 全部 control 和 variant `completed`：experiment `status=completed`。
- 缺少 run 产物但 manifest 标记完成：报告阶段标记为 `artifact_missing`，不直接改 manifest 状态。

## 目录与 path alias 设计

新增 path aliases：

```json
{
  "test_batch_abtests": "{test_batch}/abtests",
  "test_batch_abtest": "{test_batch_abtests}/{experiment_id}"
}
```

报告继续使用现有 alias：

```json
{
  "test_batch_report_dir": "{test_batch}/report"
}
```

输出目录：

```text
strategies/<strategy>/test_batches/<batch_id>/abtests/<experiment_id>.json
strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-comparison.md
strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-summary.json
```

Markdown 内部文件引用遵守项目双轨格式：正常可点击路径加 `pathref` 注释。A/B 报告中链接 run 产物时应使用 `backtest_report_dir`、`backtest_run` 等现有 alias。

## 实现模块拆分

新增 `scripts/tools/jq_automation/abtest.py`：

- `ABExperimentConfig`：实验配置 dataclass。
- `ABVariantSpec`：单个 variant 配置 dataclass。
- `load_ab_config(path)`：读取 JSON/YAML 配置并校验。
- `resolve_ab_code_sources(config)`：解析每个 Git ref，冻结为 commit SHA。
- `prepare_candidate_upload_code(candidate)`：读取 Git 源码、按 `params_mode` 处理参数、生成最终上传 `.py`。
- `compute_uploaded_code_sha256(path_or_text)`：对最终上传代码计算 hash。
- `expand_ab_experiment(config)`：生成 scenario 文件并更新 manifest。
- `run_ab_experiment(args, config)`：执行 expand 后，使用一次上传会话顺序运行全部待执行 candidate。
- `write_ab_report(config_or_manifest, experiment_id, allow_partial=False)`：生成 Markdown 和 JSON 报告。

新增 `scripts/tools/jq_automation/git_versioning.py`：

- `resolve_git_ref(ref)`：把 branch、tag 或 SHA 解析成完整 commit SHA。
- `assert_file_at_commit(commit, path)`：确认指定策略文件存在于 commit 中。
- `read_file_at_commit(commit, path)`：读取 commit 中的策略源码，不 checkout 工作区。
- `materialize_strategy_source(commit, path, experiment_id, label)`：把源码写到 `.local/jq-automation` 临时目录供参数注入和上传流程使用。
- `git_code_fingerprint(commit, path)`：生成报告和 manifest 使用的代码指纹。

新增 `scripts/tools/jq_automation/metrics.py`：

- 从 `summary_metrics.json` 提取核心指标。
- 从 `metadata.json` 提取回测区间、本金、回测 ID、参数快照。
- 必要时从 `api_export.json` 的 `stats` fallback。
- 从 quota ledger 提取 `actual_minutes`。
- 规范化百分比、浮点数、缺失值。
- 提供稳定英文指标 key 到中文字段的映射。

修改 `scripts/tools/jq_automation/cli.py`：

- 增加 `ab` subparser。
- 将现有 `cmd_batch()` 的可复用执行逻辑抽出，供 `ab run` 按 scenario filter 调用。
- 保持 `run`、`batch`、`fetch`、`upload` 现有接口兼容。

修改 `scripts/tools/jq_automation/manifest.py`：

- 增加 `update_ab_experiment()`。
- 增加 `get_ab_experiment()`。
- 增加 `sync_ab_experiment_status()`。
- 保持 `update_manifest()` 现有行为不变。

修改 `path_aliases.json`：

- 增加 `test_batch_abtests`。
- 增加 `test_batch_abtest`。

## 执行流程

### 1. expand

`ab expand` 读取实验配置后，为每个 variant 生成一个 scenario：

```text
scenario_id = ab-<experiment_id>-<sanitized_label>
run_label = <variant.label>
```

每个 scenario 的 `scenario.json` 来自 `base` 和 variant 覆盖：

- 参数变体：沿用 `base.code_source`，写入 `params_diff`。
- 代码变体：使用 variant `code_source`，同时可叠加 `params_diff`。
- `batch_id`、`strategy`、日期、本金、频率、Python 版本继承自 `base`。
- 所有 `code_source.ref` 在 expand 阶段冻结为 commit SHA，并写入 manifest。
- `scan_source`、`params_mode`、候选项顺序一并写入 manifest，便于后续报告追溯。

### 2. run

`ab run` 在一次上传会话中串行执行该实验下的 pending 或 failed candidates：

1. 创建一个 `JoinQuantBrowser`，打开一次目标聚宽策略编辑器。
2. 从 manifest 读取候选项顺序和每个候选项已冻结的 commit SHA。
3. 对当前 candidate 用 `git show <commit>:<path>` 读取策略源码，不 checkout 工作区。
4. 将源码物化到 `.local/jq-automation` 临时目录。
5. 按 `params_mode` 生成最终上传 `.py`：
   - `params_diff`：对 `set_parameter()` 中的 `g.<param>` 单行赋值应用扫描确认参数。
   - `baked_in_git`：不改写源码，直接使用 Git ref 中已经提交的参数。
6. 对最终上传 `.py` 运行本地 `py_compile`，生成 upload 文件并计算 `uploaded_code_sha256`。
7. 将最终代码写入同一个 JoinQuant 编辑器，覆盖上一个 candidate 的代码。
8. 编译、设置回测参数、启动正式回测。
9. 等待回测完成，抓取 API bundle 或 DOM tabs，落盘到 `backtest_runs/<run_id>/`。
10. 记录 `backtest_id`、`backtest_url`、`upload_index`、`uploaded_code_sha256`，更新 quota ledger、manifest、`ab_experiments`。
11. 导航回同一策略编辑器，继续下一个 candidate。

不并行执行，避免多个 candidate 争用同一个 JoinQuant 编辑器状态。聚宽正式回测启动后会在回测列表中保存当次代码快照，因此同一编辑器后续覆盖代码不会影响已启动回测的追溯。

### 3. report

`ab report` 汇总每个 variant：

- role：`control` 或 `variant`。
- baseline 标记。
- Git ref、冻结 commit SHA、策略文件 path。
- `params_mode`、`params_diff` 或参数已 baked in Git 的说明。
- `scan_source`。
- `uploaded_code_sha256`。
- `backtest_id` 和 `backtest_url`。
- 单上传会话中的 `upload_index`。
- run 状态。
- `run_id`。
- `summary_metrics.json` 核心指标。
- `metadata.json` 参数快照。
- quota ledger 实际耗时。
- `report/backtest_report.md` 是否存在。
- `report/strategy-analysis.md` 是否存在。
- `report/performance-analysis.md` 是否存在。

然后输出对比报告和机器可读 JSON 摘要。

## 指标规范化

建议使用稳定英文 key，报告中再显示中文名称。

| key | 中文名称 | 来源 | 方向 |
| --- | --- | --- | --- |
| `total_return` | 策略收益 | `summary_metrics.json` | maximize |
| `annual_return` | 策略年化收益 | `summary_metrics.json` | maximize |
| `benchmark_return` | 基准收益 | `summary_metrics.json` | maximize |
| `excess_return` | 超额收益 | `summary_metrics.json` | maximize |
| `max_drawdown` | 最大回撤 | `summary_metrics.json` | minimize |
| `sharpe` | 夏普比率 | `summary_metrics.json` | maximize |
| `information_ratio` | 信息比率 | `summary_metrics.json` | maximize |
| `volatility` | 策略波动率 | `summary_metrics.json` | minimize |
| `win_ratio` | 胜率 | `summary_metrics.json` | maximize |
| `actual_minutes` | 实际计算耗时 | quota ledger/API runtime | minimize |

解析规则：

- `"18.06%"` 转为 `0.1806`。
- `"4.29%"` 转为 `0.0429`。
- `"-1.841"` 转为 `-1.841`。
- 空字符串、缺失字段、无法解析值转为 `null`。
- 中文字段存在 mojibake 时，优先通过已知 key 映射兼容；后续可修复编码后再收窄兼容逻辑。

## 报告输出格式

Markdown 报告路径：

```text
strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-comparison.md
```

JSON 摘要路径：

```text
strategies/<strategy>/test_batches/<batch_id>/report/ab-<experiment_id>-summary.json
```

Markdown 报告章节：

1. 实验摘要。
2. baseline、controls 与 variants 配置差异。
3. 核心指标对比表。
4. 相对 baseline 的 delta 表。
5. controls 横向校准表。
6. 每个指标的最优 variant。
7. Git 版本、扫描来源、参数组合和最终上传代码 hash。
8. 聚宽回测列表记录映射：`upload_index`、`backtest_id`、`backtest_url`、`uploaded_code_sha256`。
9. run 状态与产物完整性。
10. 已有分析文档链接。
11. 缺失项和人工决策备注。

v1 默认不输出最终 winner，只输出“按单项指标最优”和“可选推荐”。后续可加入 `decision` 权重评分：

```json
{
  "decision": {
    "weights": {
      "annual_return": 0.35,
      "max_drawdown": 0.30,
      "sharpe": 0.25,
      "actual_minutes": 0.10
    },
    "min_requirements": {
      "max_drawdown": "<=0.12"
    }
  }
}
```

## 异常处理

- baseline 未完成：`ab report` 默认返回非 0；加 `--allow-partial` 时生成 partial 报告并返回 0。
- 任一 control 未完成：报告标记 control 缺失；默认返回非 0，`--allow-partial` 时返回 0。
- 配置 hash 变化且已有 completed run：拒绝覆盖，提示新建 `experiment_id` 或手动归档旧实验。
- pending/failed run 可通过 `--force-reset-pending` 重置。
- 同名 scenario 已存在：仅当属于同一 experiment 且 config hash 一致时幂等复用。
- Git ref 不存在：`expand` 阶段直接失败。
- 指定策略文件不存在于 commit：`expand` 阶段直接失败。
- 找不到策略参数：沿用 `apply_params_overrides()` 报错。
- 参数赋值为多行：沿用 `apply_params_overrides()` 报错，要求手动改为单行或使用代码变体。
- `params_mode=baked_in_git` 且仍提供 `params_diff`：允许作为报告参数快照，但不得再次注入源码。
- 单上传会话中途失败：当前 candidate 标记 `failed`，已完成 candidate 保持 `completed`，未开始 candidate 保持 `pending`，默认 fail-fast 终止本次 session。
- 再次运行 `ab run`：开启新的上传会话，只执行 pending/failed candidate，不重跑 completed candidate，除非显式 reset。
- 聚宽未返回 `backtest_id` 或回测 URL：本地 run 产物仍可落盘，但 manifest/report 标记 `backtest_record_missing`。
- 报告缺少某个 run 产物：写入缺失项，不伪造指标。
- JoinQuant API 抓取失败：沿用现有 DOM fallback。
- 每日额度不足：沿用现有 quota guardrail，中止后续 variant。

## 测试计划

### 配置解析

- baseline 缺失或未匹配任何 variant 时报错。
- `controls` 中的 label 未匹配任何 variant 时报错。
- variant label 重复时报错。
- `params_diff.note` 报错。
- variant 级 `code_source` 正确覆盖 base。
- `params_mode` 只接受 `params_diff` 或 `baked_in_git`。
- `scan_source` 可选；存在时必须保留到 manifest 和报告。
- 未声明 `metrics` 时使用默认指标。

### Git 版本解析

- `main`、tag、branch、commit SHA 都能解析为完整 commit SHA。
- 不存在的 ref 报错。
- 指定 path 不存在于 commit 时报错。
- `run` 阶段使用 manifest 中的 commit SHA，不重新解析 branch。
- 读取 Git 文件不改变当前工作区。

### expand

- 生成 expected `scenario.json`。
- 写入 manifest `ab_experiments`。
- 写入 `scan_source`、`params_mode`、候选项顺序。
- 重复执行保持幂等。
- config hash 变化且已有 completed run 时拒绝。
- `--force-reset-pending` 只重置 pending/failed，不重置 completed。

### run/upload session

- `ab run` 只创建一个 `JoinQuantBrowser`，只打开一次策略编辑器。
- 每个 candidate 都按 `upload_index` 顺序覆盖上传、编译、启动回测。
- `params_mode=params_diff` 会把扫描确认参数注入最终 `.py`。
- `params_mode=baked_in_git` 不改写源码。
- 每个 candidate 都记录独立 `uploaded_code_sha256`、`backtest_id`、`backtest_url`。
- 中途失败后已完成 candidate 不重跑，pending/failed 可在新 session 中继续。

### metrics

- 正确解析百分比、负数、空值。
- 中文 summary key 映射到英文 key。
- `api_export.json` stats fallback 生效。
- quota ledger 中 `actual_minutes` 优先于 estimated minutes。

### report

- 完整实验生成 Markdown 和 JSON。
- partial 实验在 `--allow-partial` 下生成报告。
- 缺 baseline 默认返回非 0。
- 缺 control 默认返回非 0。
- 缺 `strategy-analysis.md` 或 `performance-analysis.md` 时写入缺失项。
- delta 表以 baseline 为参照。
- controls 表展示多个对照版本与 baseline 的关系。
- 报告展示 `scan_source`、`params_mode`、`uploaded_code_sha256` 和聚宽回测记录映射。

### 回归

- 现有 `batch` 行为不变。
- 现有 `sweep` 行为不变。
- 现有 `manifest.runs[]` 迁移行为不变。
- 现有 `run`、`fetch`、`upload` CLI 行为不变。

## 验证命令

本地验证必须使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\jq_automation\__init__.py scripts\jq_automation\__main__.py scripts\jq_automation\config.py scripts\jq_automation\local.py scripts\jq_automation\manifest.py scripts\jq_automation\artifacts.py scripts\jq_automation\quota.py scripts\jq_automation\paths.py scripts\jq_automation\browser.py scripts\jq_automation\cli.py
.\.venv\Scripts\python.exe -m pytest scripts\jq_automation\tests -q
python -m scripts.tools.path_tools.refactor check
```

实现 A/B 模块后，验证命令应扩展为：

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\jq_automation\abtest.py scripts\jq_automation\git_versioning.py scripts\jq_automation\metrics.py
.\.venv\Scripts\python.exe -m pytest scripts\jq_automation\tests -q
python -m scripts.tools.path_tools.refactor check
```

## 默认决策

- A/B v1 同时支持参数变体和代码变体。
- 代码版本默认通过 Git ref 管理。
- baseline 可以是任意 Git ref，包括 `main`、tag、branch 或 commit SHA。
- 一个实验可以配置多个 controls；baseline 是主参照，controls 是额外对照版本。
- 参数当前保存在策略 `.py` 内；A/B candidate 的最终执行体是完整上传 `.py` 快照。
- 参数扫描仍由现有 `sweep/batch` 完成，A/B 只记录人工确认后的 `scan_source` 和参数组合。
- `ab run` 必须在一次浏览器/编辑器上传会话中顺序执行候选项。
- 聚宽回测列表保存每次正式回测的代码快照；本地用 `uploaded_code_sha256` 绑定候选项与云端回测记录。
- A/B v1 首要产物是对比报告。
- 云端回测串行执行。
- 不 checkout 工作区，不自动创建 Git 分支、tag、commit 或 merge。
- 不自动修改策略代码。
- 不自动选择最终 winner。
- A/B 结果沉淀在 batch report 中，单次 run 产物仍保存在 `backtest_runs/<run_id>/`。
- 每个 run 的深度 `strategy-analysis.md` 和 `performance-analysis.md` 仍由既有分析流程产出；A/B 报告只校验并链接它们。
