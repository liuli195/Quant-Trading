# Skill 系统精简重构方案

## Why
每条规则和命令都应该能被 AI 通过 Skill 的自然语言触发语义发现，避免每次都全量扫描命令和规则文档。所有 owner Skill 先设计成 Codex 标准 Skill，再为 Claude 生成同名 adapter。

## What Changes
- 按四个逻辑组管理：Skill System、Repo Governance、Strategy Research、JoinQuant Automation
- 所有 Codex owner Skill 使用一层目录 .codex/skills/
- Claude 侧只保留同名 adapter
- ownership.yaml 作为结构化 SSOT
- 新增 10 条发现性测试样例

## Impact
Skill 名称、description 都要让 agent 从自然语言请求中准确识别用途。禁止把多个弱相关流程塞进一个语义模糊的大 Skill。Claude adapter 不声明第二 owner，不复制规则正文。

---
source: docs/design/skill-system-refactor.md
