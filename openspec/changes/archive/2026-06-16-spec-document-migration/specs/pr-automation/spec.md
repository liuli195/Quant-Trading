## ADDED Requirements

### Requirement: 统一 PR 提交流程

PR 自动化系统 SHALL 提供 `pr-submit` 作为唯一推荐入口，编排从本地检查到 GitHub auto-merge 的完整自动化流程。

#### Scenario: 标准 PR 提交

- **WHEN** 用户运行 `make pr-submit TITLE="<PR标题>"`
- **THEN** 系统依次执行：校验 review fragments → 创建/更新 draft PR → 刷新 PR Evidence → ready-for-review → 等待 required checks → head-locked auto-merge → 本地收尾

### Requirement: PR Flow 状态机契约

系统 SHALL 通过 `pr-flow-interface-contract.yaml` 定义 PR Flow 的机器接口，包括 required checks、artifact 路径和规则约束。

#### Scenario: Required checks 校验

- **WHEN** `pr-submit` 等待 GitHub checks 完成
- **THEN** 系统校验 `PR Flow / review-status`、`Research Governance / verify-full`、`PR Flow / evidence` 三个 required checks 全部通过后才触发 auto-merge
