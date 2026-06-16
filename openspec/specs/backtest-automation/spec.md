## Purpose

TBD

## Requirements

### Requirement: A/B 实验配置与执行

回测自动化系统 SHALL 支持通过声明式 JSON 配置定义 A/B 实验，支持参数对比和 Git 版本对比，在一次上传会话内完成全部候选的覆盖上传和回测。

#### Scenario: 参数 A/B 对比

- **WHEN** 用户配置 baseline 与 variants 的参数差异（如 `fq_mode='pre'` vs `fq_mode=None`）
- **THEN** 系统为每个候选生成完整策略快照，顺序上传至聚宽编辑器并触发回测

### Requirement: 数据源选择

回测数据获取 SHALL 支持 `--result-source auto|research|detail` 三种模式，auto 优先使用聚宽研究环境 `get_backtest()`，失败后回退到详情页 API。

#### Scenario: auto 模式数据获取

- **WHEN** 用户以 `--result-source auto` 获取回测结果
- **THEN** 系统先尝试研究环境 API，失败后自动回退到详情页接口，两种都失败时记录错误并报告
