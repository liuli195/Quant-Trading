本仓库是基于 Python 的 A 股/场内基金量化策略仓库，交易与回测环境为聚宽 JoinQuant。

开始任何任务前，必须先读取并遵守 [AGENTS.md](AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

仓库级 Skill 的唯一来源是 `.agents/skills/`。Claude Code 通过 `.claude/skills` Windows Junction 读取同一份 Skill 内容；如 Junction 缺失，运行：

```powershell
.\.githooks\ensure-skill-junction.ps1
```
