# ETF Factor Rotation 云端测试执行计划

设计日期：2026-05-05
测试对象：[etf_factor_rotation.py](../../etf_factor_rotation.py)
测试设计：[测试方案设计文档.md](../测试方案设计文档.md)

## 1. 硬约束

1. **60 分钟/日 = 聚宽云端 CPU 计算时间**，浏览器操作、数据抓取、本地分析不占额度
2. **性能优先**：若首次编译或短回测耗时异常，立即中断并 `jq-fix` 优化，不继续消耗额度
3. **本地不通过不上云**：每次 `jq-run` 前先执行 `py_compile` + `pytest`
4. **一次确认只跑批准的场景**：每批次开始前输出计划等用户确认

## 2. 回测运行合并方案

将 61 个云端用例合并为 **7 次回测运行** + **1 次纯分析**：

| 运行 | 参数 | 区间 | 预计计算 | 覆盖用例数 | 覆盖范围 |
|------|------|------|----------|-----------|----------|
| R0 冒烟 | 默认 | 1 个月 | ~5 min | 8 | C0 全部 + C3-PERF-001 |
| R1 默认基线 | 默认 | 1 年 | ~20 min | 30+ | C1-DATA/SIG/EXEC 全部 + C1-FQ-A + C2-REGIME 部分 |
| R2 复权B | `use_real_price=False, fq=None` | 同 R1 | ~20 min | 2 | C1-FQ-B |
| R3 测试参数 | MaxWeight=0.30, MinWeight=0.20, TargetVol=0.05 | 6 个月 | ~8 min | 4 | C1-SIG-009~010, 边界压力 |
| R4 长周期基线 | 默认 | 5~8 年 | ~35 min | 15+ | C2-LONG 全部 + C2-REGIME 全部 + C3-PERF-002/005/008 |
| R5 无 profile | 默认（移除 enable_profile） | 同 R4 | ~35 min | 1 | C3-PERF-003 |
| R6 高窗口压力 | RSRS_M=800, CrowdWindow=700 | 3 个月 | ~10 min | 1 | C3-PERF-006 |
| R7 扩展资产池 | 临时扩展 5~8 ETF | 3 个月 | ~8 min | 1 | C3-PERF-007 |

> C3-PERF-004（日志量压力）从 R1/R4 的日志中直接评估，不单独跑回测。

## 3. 多日调度计划

### Day 1 — 性能闸门 + 默认基线

**预算**：~25 min 计算 / 60 min

| 步骤 | 动作 | 技能 | 预计计算 |
|------|------|------|----------|
| 1 | 本地 `py_compile` + `pytest` 确认通过 | 直接执行 | 0 |
| 2 | `strip_comments.py` 生成上传版 | 直接执行 | 0 |
| 3 | 上传、编译、**1 个月冒烟回测** (R0) | `jq-run` | ~5 min |
| 4 | 抓取 R0 数据、落盘 | `jq-run` | 0 |
| 5 | R0 分析：检查编译耗时和回测耗时 | `jq-analyze` | 0 |

> **闸门**：编译 >10s 或 1 个月回测明显过慢 → 中断，`jq-fix` 优化后重新 Day 1。

| 6 | 若闸门通过，启动 **1 年默认基线回测** (R1) | `jq-run` | ~20 min |
| 7 | 抓取 R1 数据、落盘 | `jq-run` | 0 |
| 8 | R1 初步分析：抽查调仓日志、信号链路 | `jq-analyze` | 0 |

**Day 1 交付物**：R0/R1 完整回测产物 + 策略分析 + 性能分析

### Day 2 — 复权 A/B + 测试参数

**预算**：~28 min 计算 / 60 min

| 步骤 | 动作 | 技能 | 预计计算 |
|------|------|------|----------|
| 1 | 启动 **FQ-B 回测** (R2) | `jq-run` | ~20 min |
| 2 | 启动 **测试参数回测** (R3) | `jq-run` | ~8 min |
| 3 | FQ A/B 对比分析 (R1 vs R2) | `jq-analyze` | 0 |
| 4 | R3 策略分析 | `jq-analyze` | 0 |

> **闸门**：若 FQ A/B 信号差异显著且无合理解释 → 暂停，不进入长周期回测。

### Day 3 — 长周期基线 + 市场场景回归

**预算**：~35 min 计算 / 60 min

| 步骤 | 动作 | 技能 | 预计计算 |
|------|------|------|----------|
| 1 | 启动 **长周期基线回测** (R4) | `jq-run` | ~35 min |
| 2 | R4 策略分析 + 性能分析 | `jq-analyze` | 0 |
| 3 | 结合 R1+R4 完成 C2-REGIME 场景分析 | `jq-analyze` | 0 |
| 4 | C3-PERF-004 日志量评估 | `jq-analyze` | 0 |

### Day 4 — Profile 对比 + 压力测试

**预算**：~53 min 计算 / 60 min（根据前 3 天余量调整）

| 步骤 | 动作 | 技能 | 预计计算 |
|------|------|------|----------|
| 1 | 启动 **无 profile 长回测** (R5) | `jq-run` | ~35 min |
| 2 | 启动 **高窗口压力回测** (R6) | `jq-run` | ~10 min |
| 3 | 启动 **扩展资产池回测** (R7) | `jq-run` | ~8 min |
| 4 | R5 vs R4 profile 对比 | `jq-analyze` | 0 |
| 5 | R6/R7 性能分析 | `jq-analyze` | 0 |

### Day 5 — 汇总归档（纯本地，零计算）

| 步骤 | 动作 | 技能 | 预计计算 |
|------|------|------|----------|
| 1 | 全批次对比：汇总 R0~R7 | `jq-analyze` | 0 |
| 2 | 写入 issue-log：未触发用例、异常发现 | `jq-analyze` | 0 |
| 3 | FQ 口径最终决策文档 | `jq-analyze` | 0 |
| 4 | 确认所有退出标准满足 | 人工审查 | 0 |

## 4. Scenario → Run 映射

| Scenario ID | 运行 | 参数组 | 说明 |
|-------------|------|--------|------|
| s01-smoke | R0 | 默认, 1 月 | C0 冒烟 + 性能闸门 |
| s02-default-baseline | R1 | 默认, 1 年 | C1 全部 + FQ-A 基线 |
| s03-fq-b | R2 | 不复权, 1 年 | FQ-B 对比 |
| s04-test-params | R3 | 测试参数, 6 月 | 边界约束验证 |
| s05-long-baseline | R4 | 默认, 全区间 | C2 全部 |
| s06-profile-off | R5 | 无 profile, 全区间 | profile 开销对比 |
| s07-high-window | R6 | 高窗口, 3 月 | RSRS/拥挤度压力 |
| s08-extended-pool | R7 | 扩展池, 3 月 | 资产池伸缩性 |

## 5. 各回测运行详细配置

### R0 — 冒烟（C0 全部 + C3-PERF-001）

- 参数：默认（与 etf_factor_rotation.py 完全一致）
- 区间：近 1 个月
- 初始资金：100,000
- 基准：000300.XSHG
- 验证：C0-001~005, C3-PERF-001

### R1 — 默认基线（C1 主体验）

- 参数：默认
- 区间：近期 1 年（避开 ETF 上市初期）
- 初始资金：100,000
- 验证：C1-DATA-001~005, C1-SIG-001~008, C1-EXEC-001~007, C1-FQ-001, C3-PERF-005/008

### R2 — 复权 B 组

```python
g.use_real_price = False
g.fq_mode = None
# 其余默认，区间与 R1 完全一致
```

### R3 — 测试参数

```python
g.MaxWeight = 0.30
g.MinWeight = 0.20
g.TargetVol = 0.05
# 其余默认，区间近 6 个月
```

### R4 — 长周期基线

- 参数：默认
- 区间：ETF 数据可用的最长时间范围
- 初始资金：100,000

### R5 — 无 Profile

- 删除或注释 enable_profile()，其余同 R4

### R6 — 高窗口压力

```python
g.RSRS_M = 800
g.CrowdWindow = 700
# 其余默认，区间近 3 个月
```

### R7 — 扩展资产池

```python
g.etf_pool = [
    '159819.XSHE',   # AI ETF
    '513100.XSHG',   # 纳指100 ETF
    '518880.XSHG',   # 黄金 ETF
    '510050.XSHG',   # 50ETF
    '510300.XSHG',   # 300ETF
    '159915.XSHE',   # 创业板ETF
]
g.TopK = 3
# 其余默认，区间近 3 个月
```

## 6. 技能调用时机

```
修改代码 → py_compile + pytest → jq-run → jq-analyze
                ↓ 失败                  ↓ 失败     ↓ 发现问题
             jq-fix                  jq-fix     jq-fix
```

| 阶段 | 主要技能 | 触发条件 |
|------|----------|----------|
| 上传、编译、回测、抓取、落盘 | `jq-run` | 本地校验通过后 |
| 编译失败 / 回测异常 | `jq-fix` | jq-run 遇到错误时 |
| 策略分析、性能分析、批次对比 | `jq-analyze` | jq-run 落盘完成后 |
| 分析发现信号/logic 问题 | `jq-fix` | jq-analyze 标记 needs_cloud_verification |

## 7. 风险与回退

| 风险 | 应对 |
|------|------|
| R0 编译 >10s 或回测异常慢 | 中断，`jq-fix` 排查取数/滚动计算，优化后重新 Day 1 |
| R1 中途发现未来数据问题 | 立即停止，`jq-fix` 修复 end_date 逻辑，重跑 R1 |
| 某天计算预算提前用尽 | 未完成场景延至次日，更新计划 |
| C1 关键用例失败（非性能） | `jq-fix` 本地修复 → pytest 验证 → `jq-run` 重跑 |
| FQ A/B 差异无法解释 | 暂停 C2/C3，先补充数据口径分析 |
| 聚宽接口变更 / 不可用 | 等待恢复，不强制执行；记录在 issue-log |
| 某场景未触发（如停牌） | 记录为 "未触发" + 原因，不阻塞后续流程 |

## 8. 退出标准

- [ ] C0 全部通过
- [ ] C1-DATA 全部通过
- [ ] C1-SIG 关键用例全部通过，未触发项有解释
- [ ] C1-EXEC 成功路径通过，未触发异常路径有本地覆盖或云端说明
- [ ] FQ A/B 完成对比，口径决策明确
- [ ] C2-LONG 默认参数长周期回测完成
- [ ] C2-REGIME 核心场景覆盖（至少 5/8）
- [ ] C3 关键性能用例通过，云端耗时和日志量无异常退化
- [ ] 每 run_id 下 backtest_report + strategy-analysis + performance-analysis 齐全
- [ ] batch-comparison.md + issue-log.md 生成
- [ ] 本计划可被他人复现

## 9. 验证方法

```powershell
# 每次 jq-run 后
python -m py_compile strategies/etf_factor_rotation/etf_factor_rotation.py
pytest strategies/etf_factor_rotation/tests -q

# 全部完成后
python -m py_compile strategies/etf_factor_rotation/etf_factor_rotation.py
pytest strategies/etf_factor_rotation/tests -q
python -m scripts.path_tools.refactor check
```
