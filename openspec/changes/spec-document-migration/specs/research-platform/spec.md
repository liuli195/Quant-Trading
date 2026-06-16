## ADDED Requirements

### Requirement: 本地优先研究流程

研究平台 SHALL 支持本地优先研究流程，通过统一的 CLI 入口管理研究项目的完整生命周期。

#### Scenario: 创建研究项目

- **WHEN** 用户运行 `scripts.research.cli init` 创建研究项目
- **THEN** 系统生成标准项目骨架，包含 `docs/research_spec.md`、`docs/data_contract.md`、`docs/execution_plan.md` 等文档模板

#### Scenario: fast mode 粗筛

- **WHEN** 用户运行 fast mode 进行大规模候选扫描
- **THEN** 系统在热启动条件下于 3 秒内完成粗筛并输出初步排名

### Requirement: 候选漏斗与云端交接

研究平台 SHALL 支持多层候选漏斗（fast → full → handoff-cloud），只在本地精筛通过后将少量候选送往云端确认。

#### Scenario: 候选提升

- **WHEN** fast mode 输出的候选列表通过 `promote` 进入 full mode
- **THEN** 系统对提升候选执行留出集、分段时间段和 bootstrap 精筛

#### Scenario: 云端交接

- **WHEN** full mode 验证通过的候选触发 `handoff-cloud`
- **THEN** 系统生成云端确认请求，不将未通过本地门槛的候选送往云端
