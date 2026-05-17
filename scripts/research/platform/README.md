# platform — 本地优先研究平台核心

研究平台的核心引擎层，提供插件契约、特征缓存、候选漏斗、数据集管理和 4 个内置研究插件。依赖 `research_core`。

无 CLI 入口，通过 `scripts.research.cli` 和 `scripts.research.engine` 间接调用。

## 模块概览

| 模块 | 用途 | 关键符号 |
|---|---|---|
| `contracts.py` | 插件接口与数据类型 | `FidelityLevel`, `PluginCapabilities`, `ResearchPlugin`, `ResearchRunContext` |
| `engine.py` | 研究编排引擎 | `create_project`, `run_project`, `promote_run`, `handoff_cloud`, `resume_run` |
| `features.py` | 特征缓存 | `FeatureStore`, `FeatureBundle`, `stable_hash` |
| `funnel.py` | 候选漏斗 | `CandidateFunnel`, `build_fast_funnel`, `promote_full_funnel` |
| `datasets.py` | 数据集快照管理 | `DatasetSnapshot`, `load_snapshot`, `import_joinquant_price_json`, `import_audit_log_jsonl`, `load_price_frames` |
| `plugins.py` | 内置研究插件 | `FactorScanPlugin`, `ParameterFollowupPlugin`, `RobustnessCheckPlugin`, `GenericPlugin`, `get_plugin` |

---

## contracts.py — 插件契约

```python
from scripts.research.platform.contracts import (
    FidelityLevel, PluginCapabilities, ResearchRunContext, validate_baseline_exports,
    BASELINE_REQUIRED_EXPORTS,
)
```

### FidelityLevel (StrEnum)

本地研究可信度三级：

| 级别 | 含义 |
|---|---|
| `LOCAL_EXACT` | 本地可精确复现（如同因子扫描、稳健性检查） |
| `LOCAL_REPLAYABLE` | 本地可近似回放（参数跟随研究） |
| `CLOUD_ONLY` | 必须云端确认 |

### PluginCapabilities

插件能力声明 dataclass：

```python
PluginCapabilities(
    local_capabilities=("factor_windows", "thresholds", ...),  # 本地可判断的能力
    replayable_params=("weight_shape", "tilt_strength", ...),   # 可本地回放的参数
    required_exports=("daily_returns", "signals", ...),          # 依赖的云端导出
    unsupported_changes=("order_execution", ...),                # 不支持的改动类型
    fidelity_level=FidelityLevel.LOCAL_EXACT,
)
```

### ResearchRunContext

单次运行上下文 dataclass，聚合 `project_dir`、`project`（配置 dict）、`run`（ResearchRunLayout）、`mode`、`top_k`、`cloud_top_k`、`source_run_id`。

### ResearchPlugin (Protocol)

插件最小协议。任何插件需实现：

| 方法 | 说明 |
|---|---|
| `build_feature_spec(project)` | 返回特征规格（用于缓存键） |
| `dataset_fingerprint(project)` | 返回输入数据指纹（不构建特征） |
| `build_features(project)` | 构建可复用衍生特征 |
| `run_fast(context, features)` | 快速筛选 → `{grid, funnel, decision}` |
| `run_full(context, features, shortlist)` | 精细评估 → `{reviewed, funnel, decision}` |
| `build_cloud_handoff(context, cloud_candidates)` | 生成云端交接材料 |

### validate_baseline_exports(bundle) → list[str]

检查基线导出包中缺少哪些必需字段。返回缺失字段列表。

---

## engine.py — 编排引擎

```python
from scripts.research.platform.engine import (
    create_project, run_project, promote_run, handoff_cloud, resume_run, load_project,
)
```

完整的 research project 生命周期管理。由 `scripts.research.cli` 直接调用，详细参数见 [scripts/research/README.md](../README.md)。

### create_project(*, project_dir, strategy, project, template, plugin=None, datasets=None, ...) → Path

创建研究项目骨架：`project.json` + `README.md` + `docs/` 下 6 个模板文件。

### run_project(*, project_dir, run_id, mode, top_k=None, cloud_top_k=None, ...) → dict

执行 fast 或 full 运行。自动处理特征缓存（FeatureStore）、调用插件、写入产物（grid/shortlist/cloud_candidates/decision/benchmark/manifest/status）。

### promote_run(*, project_dir, fast_run_id, full_run_id, top_k=None, cloud_top_k=None) → dict

将 fast 运行的 shortlist 升级为 full 运行（直接读取 `shortlist.csv` 传入 `run_project(mode="full")`）。

### handoff_cloud(*, project_dir, run_id) → dict

为 full 运行生成云端交接 payload（`cloud_handoff.json`）。

### resume_run(*, project_dir, run_id) → dict

读取 `request.json` 恢复中断的运行。full 模式自动通过 source_run_id 重新 promote。

### load_project(project_dir) → dict

读取 `project.json` 返回配置字典。

---

## features.py — 特征缓存

```python
from scripts.research.platform.features import FeatureStore, FeatureBundle, stable_hash
```

### stable_hash(payload) → str

对 JSON 兼容对象做确定性 SHA256 哈希（`sort_keys=True`）。

### FeatureStore(root=".local/research-cache")

持久化特征缓存管理器。

```python
store = FeatureStore()

# 生成缓存键
key = store.cache_key(
    dataset_fingerprint="sha256:abc123",
    feature_spec={"plugin": "factor_scan", ...},
    code_version="factor_scan:v1",
)

# 加载或构建
bundle = store.load_or_build(key, lambda: expensive_computation())
# bundle.payload      → 特征数据
# bundle.cache_hit    → 是否命中缓存
# bundle.build_seconds → 构建耗时（缓存命中时为 0）
```

缓存存储为 `.local/research-cache/<key>/features.pkl` + `metadata.json`。

### FeatureBundle

不可变 dataclass：`payload`, `cache_key`, `cache_hit`, `build_seconds`, `cache_dir`。

---

## funnel.py — 候选漏斗

```python
from scripts.research.platform.funnel import CandidateFunnel, build_fast_funnel, promote_full_funnel
```

### CandidateFunnel

三阶段候选漏斗产物 dataclass：

```python
funnel = CandidateFunnel(
    ranked=pd.DataFrame(...),       # 全部候选（按分数排序）
    discarded=pd.DataFrame(...),     # 淘汰候选（含 discard_reason）
    shortlist=pd.DataFrame(...),     # 入围候选（含 funnel_stage）
    cloud_candidates=pd.DataFrame(...), # 云端候选
)
```

### build_fast_funnel(candidates, *, score_column, top_k) → CandidateFunnel

按 `score_column` 降序排列，取前 `top_k` 进入 shortlist，其余进入 discarded。

### promote_full_funnel(reviewed, *, cloud_top_k, eligible_column="eligible_for_cloud", score_column="refinement_score") → CandidateFunnel

从 reviewed 中按 `eligible_column` 筛选，取前 `cloud_top_k` 进入 cloud_candidates。

---

## datasets.py — 数据集管理

```python
from scripts.research.platform.datasets import (
    DatasetSnapshot, load_snapshot, import_joinquant_price_json,
    import_audit_log_jsonl, load_price_frames,
)
```

### DatasetSnapshot

不可变 dataclass，代表一个数据集快照。

```python
snapshot = load_snapshot("my_dataset", "2026-05-17T...")
snapshot.root          # Path
snapshot.dataset_id    # str
snapshot.snapshot_id   # str
snapshot.fingerprint   # str (sha256:...)
snapshot.raw_path      # Path → 原始文件
snapshot.parquet_path  # Path → Parquet 主存储
```

### import_joinquant_price_json(source, *, dataset_id, snapshot_id=None) → DatasetSnapshot

将聚宽价格导出 JSON 转为不可变快照。自动生成 `raw/source.json.gz`、`data/data.parquet`、`views/` 和 `dataset.json`。更新 `research_datasets/catalog.json`。

### import_audit_log_jsonl(source, *, dataset_id, snapshot_id=None) → DatasetSnapshot

将聚宽审计日志 JSONL 转为不可变快照。自动：
- 解析 `run_start` 中的 ETF 池、基准等参数
- 从 `rebalance_signals` 事件中展平所有数组字段（趋势门槛、权重、惩罚、缩放）
- 写入 `data/data.parquet`

### load_snapshot(dataset_id, snapshot_id, *, datasets_root="research_datasets") → DatasetSnapshot

读取已有数据集快照的元数据。

### load_price_frames(snapshot, codes=None) → PriceFrames

从 Parquet 加载价格数据，回退到原始 JSON 解析。

---

## plugins.py — 内置插件

```python
from scripts.research.platform.plugins import (
    get_plugin, BUILTIN_PLUGINS,
    FactorScanPlugin, ParameterFollowupPlugin, RobustnessCheckPlugin, GenericPlugin,
)
```

### get_plugin(name) → ResearchPlugin

按名称获取插件实例。内置 4 个：

| 插件 | 模板 | 可信度 | 用途 |
|---|---|---|---|
| `FactorScanPlugin` | `factor_scan` | `LOCAL_EXACT` | 因子窗口组合扫描，本地可精确计算 |
| `ParameterFollowupPlugin` | `parameter_followup` | `LOCAL_REPLAYABLE` | 参数跟随研究，通过策略特定 adapter 回放 |
| `RobustnessCheckPlugin` | `robustness_check` | `LOCAL_EXACT` | 事后稳健性验证（bootstrap + 滚动窗 + 年度分解） |
| `GenericPlugin` | `generic` | `LOCAL_EXACT` | 最小脚手架，不预设漏斗流程，供诊断/探索用 |

### FactorScanPlugin

对 ETF 因子窗口组合做快速扫描，包含：
- **fast**：`build_factor_window_grid` → 按 benefit 排序 → top_k shortlist
- **full**：shortlist 逐候选 review（holdout 验证 + 分段稳定性 + bootstrap）

### ParameterFollowupPlugin

通过 `ParameterReplayAdapter` 适配不同策略的参数回放研究。当前唯一 adapter：`MomentumTiltReplayAdapter`（动量倾斜参数回放）。

- **fast**：逐变体 `replay_variant` → 按 sharpe_delta 排序
- **full**：逐候选 `review_full` → 含校准门禁 + bootstrap

### RobustnessCheckPlugin

对已有回测收益路径做事后稳健性检查。

- **fast**：对齐 baseline/variant 收益 → 按 sharpe_delta 排序
- **full**：逐变体深度对比（bootstrap + 滚动 Sharpe 胜率 + 年度稳定性）

full 模式门禁（5 条全部通过才算 eligible）：
1. `sharpe > baseline`
2. `annual_return >= baseline - 0.003`
3. `bootstrap ci_low >= 0`
4. `rolling_sharpe_win_rate > 0.55`
5. 超过半数年份 variant Sharpe 更优

### GenericPlugin

不执行任何分析逻辑的最小插件。生成空漏斗，供用户在 `runs/<run_id>/` 下手动运行分析脚本。

---

## 依赖关系

```
research_core (零依赖)
    ↑
platform (依赖 research_core + etf_window_research + momentum_tilt_research)
    ↑
cli.py (依赖 platform.engine)
```

`platform` 层依赖 `research_core`，且 plugins.py 会 import `etf_window_research.analysis` 和 `momentum_tilt_research` 作为具体分析实现。
