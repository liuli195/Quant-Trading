---
name: joinquant-cloud-run
description: 处理 JoinQuant 上传、云端回测 run、fetch、batch、结果落盘和配额保护时使用。
---

# JoinQuant Cloud Run

本技能负责 JoinQuant 上传、云端回测 run、fetch、batch、结果落盘和额度保护。

## 必读规则

- `docs/rules/environments.md`
- `docs/rules/research-workflow.md`

## 执行规则

- 正式 run 或 batch 前必须展示计划并确认额度。
- `--yes` 只表示确认已经完成。
- 云端结果必须保留 run、manifest、audit log 或报告路径。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation run <场景配置.json> --yes
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation fetch <回测URL或ID> --strategy <策略名>
```
