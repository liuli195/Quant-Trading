## Purpose

TBD

## Requirements

### Requirement: 参数变体管理

策略变体系统 SHALL 通过 `VariantRegistry` 登记参数变体（params diff）和结构变体（Git 代码差异），参数变体默认不使用 Git 分支。

#### Scenario: 登记参数变体

- **WHEN** 用户通过 `variant_id` 登记一组参数差异（如 `TopK=2, TargetVol=0.12`）
- **THEN** 系统生成 `variants/<variant_id>.json` 配置文件，不创建 Git 分支

### Requirement: 结构变体状态流转

结构变体 SHALL 遵循标准状态流转：`candidate → in_research → cloud_confirmed → merge_ready → merged_pending_validation → merged_confirmed`。

#### Scenario: 结构变体合并

- **WHEN** 结构变体通过云端确认后进入 `merge_ready` 状态
- **THEN** `VariantMergeManager` 生成合并计划，仅在用户显式授权后执行合并
