# 命令和本地环境规则

通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

## MUST

- Python 命令默认走项目 `.venv`，在本地/Codex 需要权限时按提权执行，不改用系统 Python。
- setup script 只负责 bootstrap `.venv`；run-python wrapper 找不到 `.venv` 必须失败。
- Windows 本地默认 wrapper：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1`。
- Codex Cloud/Linux/POSIX 默认 wrapper：`.githooks/run-python.sh`。
- Git hooks 通过 `.githooks/run-python.sh` 选择当前平台虚拟环境；Windows 交互命令可直接用 `run-python.ps1`。
- 临时排障可直用 `.\.venv\Scripts\python.exe -m ...` 或 `.venv/bin/python -m ...`；中文输出需设置 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。
- `gh` CLI 默认提权执行，否则无法获取沙箱外的登录状态。

## 初始化

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
git config core.hooksPath .githooks
```

```bash
bash .githooks/setup-python.sh
.githooks/run-python.sh -c "import sys; print(sys.executable); print('中文')"
```

## 常用命令

Windows 示例：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m py_compile strategies\<strategy>\<strategy>.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m pytest strategies\<strategy>\tests -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.jq_automation compile-check strategies\<strategy>\<strategy>.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.docs index
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate
gh pr checks <PR号或URL> --required --watch --interval 10
gh pr checks <PR号或URL> --required
```

可用 CLI：

| 模块 | 子命令 |
| --- | --- |
| `scripts.tools.jq_automation` | `compile-check`、`upload`、`run`、`fetch`、`batch`、`ab expand/run/report` |
| `scripts.research.cli` | `init`、`run`、`promote`、`resume`、`handoff-cloud`、`status` |
| `scripts.research.datasets` | `import-price-json`、`import-audit-log`、`import-backtest-run`、`migrate-backtest-runs`、`inspect` |
| `scripts.research.variants` | `list`、`register`、`materialize`、`branch-plan`、`branch-create`、`merge-plan`、`merge-apply` |
| `scripts.research.registry.tool_registry` | `list`、`validate` |
| `scripts.research.governance` | `audit`、`gate` |

POSIX 示例把 Windows wrapper 替换为 `.githooks/run-python.sh`。

## 参考

- [local-python-env.md](../guides/local-python-env.md) <!-- pathref: docs/guides/local-python-env.md -->
- [jq_automation/README.md](../../scripts/tools/jq_automation/README.md) <!-- pathref: scripts/tools/jq_automation/README.md -->
- [path_tools/README.md](../../scripts/tools/path_tools/README.md) <!-- pathref: scripts/tools/path_tools/README.md -->
