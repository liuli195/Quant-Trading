---
name: joinquant-cloud-run
description: 处理 JoinQuant 上传、云端回测 run、fetch、batch、结果落盘和配额保护时使用。
---

# JoinQuant Cloud Run Adapter

对应 Codex owner Skill：`.codex/skills/joinquant-cloud-run/SKILL.md`。

## 必读规则

- `docs/rules/environments.md`
- `docs/rules/research-workflow.md`

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation run <场景配置.json> --yes
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation fetch <回测URL或ID> --strategy <策略名>
```
