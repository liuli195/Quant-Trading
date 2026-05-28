# 命令和本地环境规则

通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

## MUST

- Python 命令默认走项目 `.venv`，不改用系统 Python。
- setup script 只负责 bootstrap `.venv` 并配置 hooks。
- Windows 本地默认入口：`.\.venv\Scripts\python.exe`。
- Codex Cloud/Linux/POSIX 默认入口：`.venv/bin/python`。
- Git hooks 内部仍通过 `.githooks/run-python.sh` 选择当前平台虚拟环境；日常命令不走该脚本。
- 中文输出由环境变量层处理：`PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。
- `gh` CLI 默认提权执行，否则无法获取沙箱外的登录状态。

## 初始化

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
git config core.hooksPath .githooks
```

```bash
bash .githooks/setup-python.sh
.venv/bin/python -c "import sys; print(sys.executable); print('中文')"
```

## 常用命令

Windows 示例：

```powershell
.\.venv\Scripts\python.exe -m py_compile strategies\<strategy>\<strategy>.py
.\.venv\Scripts\python.exe -m pytest strategies\<strategy>\tests -q
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation compile-check strategies\<strategy>\<strategy>.py
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
.\.venv\Scripts\python.exe -m scripts.research.docs index
.\.venv\Scripts\python.exe -m scripts.research.governance gate
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow ready --title "<PR标题>"
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
| `scripts.research.governance.pr_flow` | `prepare`、`sync`、`wait`、`ready` |

POSIX 示例把 Windows Python 路径替换为 `.venv/bin/python`。

## 参考

- [local-python-env.md](../guides/local-python-env.md) <!-- pathref: docs/guides/local-python-env.md -->
- [jq_automation/README.md](../../scripts/tools/jq_automation/README.md) <!-- pathref: scripts/tools/jq_automation/README.md -->
- [path_tools/README.md](../../scripts/tools/path_tools/README.md) <!-- pathref: scripts/tools/path_tools/README.md -->
