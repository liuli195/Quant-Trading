## Purpose

TBD

## Requirements

### Requirement: 聚宽兼容性

代码标准系统 SHALL 要求策略代码兼容聚宽 Python 3.6 环境，禁用新语法（`f"{x=}"`、`X | Y`、`match/case`）和本地专属库（`matplotlib`、`seaborn`、`cvxpy`）。

#### Scenario: 语法检查

- **WHEN** 策略代码发生变更
- **THEN** 系统运行语法检查，拒绝包含 Python 3.6+ 新语法或不兼容 API 调用的代码

### Requirement: 策略参数集中定义

策略代码 SHALL 将参数集中定义，避免魔法数字，`initialize` 集中配置与注册，`handle_data` 或 `run_daily` 承载调仓逻辑。

#### Scenario: 策略结构校验

- **WHEN** 新策略代码提交审查
- **THEN** 系统校验参数定义集中、调仓逻辑清晰、停牌/缺失值/仓位上下限有明确处理
