## ADDED Requirements

### Requirement: 单一来源管理

Skill 管理系统 SHALL 以 `.agents/skills/<skill>/` 作为仓库级 Skill 的唯一事实来源（SSOT），Codex 直接读取，Claude Code 通过 `.claude/skills` Directory Symlink 指向同一份内容。

#### Scenario: Skill 创建

- **WHEN** 新增仓库级 Skill
- **THEN** 系统在 `.agents/skills/<skill>/` 下创建完整的 `SKILL.md`、`agents/openai.yaml` 和 `references/*`，同步更新 `ownership.yaml`

### Requirement: 自然语言发现

Skill SHALL 支持通过自然语言请求唯一命中目标 Skill，命中后先读取 `read_rules` 列出的规则文件再执行推荐命令。

#### Scenario: 自然语言匹配

- **WHEN** 用户发起符合某 Skill 触发语义的自然语言请求
- **THEN** 系统唯一命中目标 Skill，加载对应的规则文件和操作指令
