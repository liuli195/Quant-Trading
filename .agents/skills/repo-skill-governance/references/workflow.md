# Workflow

1. 读取 `docs/rules/skills.md` 和相关规则。
2. 更新 `.agents/skills/<skill>/` 下的 Skill 内容与 `ownership.yaml`。
3. 确认 `.claude/skills` Junction 指向 `.agents/skills`。
4. 增加或更新发现测试。
5. 运行 Skill ownership 检查、治理 gate 和文档索引。
