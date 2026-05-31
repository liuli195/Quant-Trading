# 命令和本地环境规则

通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

## MUST

<a id="python-env"></a>

### Python 环境

- Python 命令默认必须提权使用项目 `.venv`，不改用系统 Python。
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
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files docs\rules\commands.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs\rules\commands.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow ready --title "<PR标题>"
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow diagnose --pr <PR号>
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow resolve-threads <thread-id> [<thread-id>...]
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow complete --title "<PR标题>" --pr <PR号>
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow complete --title "<PR标题>" --resolve-thread <thread-id>
gh pr checks <PR号或URL> --required --watch --interval 10
gh pr checks <PR号或URL> --required
```

`verify explain` 只说明会命中哪些检查，不执行命令。`verify fast` 是日常小改入口，只表示当前改动可继续开发；PR 准备、push 前、CI 和最终交付证据必须使用 `verify full`。

可用 CLI：

| 模块 | 子命令 |
| --- | --- |
| `scripts.tools.jq_automation` | `compile-check`、`upload`、`run`、`fetch`、`batch`、`ab expand/run/report` |
| `scripts.research.cli` | `init`、`run`、`promote`、`resume`、`handoff-cloud`、`status` |
| `scripts.research.datasets` | `import-price-json`、`import-audit-log`、`import-backtest-run`、`migrate-backtest-runs`、`inspect` |
| `scripts.research.variants` | `list`、`register`、`materialize`、`branch-plan`、`branch-create`、`merge-plan`、`merge-apply` |
| `scripts.research.registry.tool_registry` | `list`、`validate` |
| `scripts.research.governance` | `audit`、`gate`、`verify explain/fast/full` |
| `scripts.research.governance.pr_flow` | `prepare`、`sync`、`wait`、`ready`、`diagnose`、`resolve-threads`、`ready-for-review`、`merge`、`cleanup`、`complete` |

POSIX 示例把 Windows Python 路径替换为 `.venv/bin/python`。

## 参考

- [local-python-env.md](../guides/local-python-env.md) <!-- pathref: docs/guides/local-python-env.md -->
- [jq_automation/README.md](../../scripts/tools/jq_automation/README.md) <!-- pathref: scripts/tools/jq_automation/README.md -->
- [path_tools/README.md](../../scripts/tools/path_tools/README.md) <!-- pathref: scripts/tools/path_tools/README.md -->

## PR Flow Intent Commands

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent stage --issue 54:reference
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent stage --issue 55:closes --issue 54:reference
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent stage --issue 60:closes --ac-review-mode user_required
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent stage --no-issue-reason "<reason>" --no-issue-authorized-by "<user>" --no-issue-evidence "<evidence>"
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent pre-commit
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent post-commit
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow intent check-coverage
```

`pr_flow intent stage` 必须在 `git add` 之后、`git commit` 之前运行；`pr_flow intent pre-commit` 和 `pr_flow intent post-commit` 由 hooks 调用；`pr_flow intent check-coverage` 用于 PR readiness/CI 发现 rewritten commits 缺少 branch intent。
`--ac-review-mode user_required` 表示该 branch intent 要求人工确认 AC，不自动勾选 Issue checkbox。
