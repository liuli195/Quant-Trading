# ADR 0008: Skill 使用 `.agents/skills/` 单一来源

## 状态

Accepted

## 背景

仓库级 Skill 原来分成两份维护：`.codex/skills/` 保存完整 owner Skill，`.claude/skills/` 保存 Claude adapter。每次改 Skill 都要同步两处文件，治理脚本还要校验 owner 与 adapter 是否等价。

这个模式增加了维护成本，也让 Skill 来源不清晰。Codex 的仓库级标准路径是 `.agents/skills/`，因此需要把仓库 Skill 收敛到一个事实来源。

## 决策

- `.agents/skills/` 是仓库级 Skill 的唯一事实来源，并进入版本控制。
- Codex 直接读取 `.agents/skills/`。
- Claude Code 通过 `.claude/skills` Windows Junction 指向 `.agents/skills`，读取同一份内容。
- `.claude/skills/` 是生成产物，写入 `.gitignore`，不得双重追踪。
- `.codex/skills/` 删除；`.codex/environments/environment.toml` 保留。
- `ownership.yaml` 删除 `adapters` 字段，改用 `tools: [claude-code, codex]` 表示使用方。
- `skill-system` 改名为 `repo-skill-governance`，避免继续表达旧 owner/adapter 架构。

## 后果

修改一个 Skill 只需要改 `.agents/skills/<skill>/` 一处。治理检查从 adapter 等价性改为 `.agents/skills` 完整性和 `.claude/skills` Junction 有效性检查。

这个决策只覆盖当前 Windows 本地仓库工作流；跨操作系统替代方案不在本次范围内。
