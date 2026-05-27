# 命令和本地环境规则

本文件承接 AI 入口中的命令细节。通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

## MUST

- Python 环境分为 setup script 和 run-python wrapper 两阶段。
- Windows 本地 / worktree 初始化使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1`。
- Codex Cloud / Linux / POSIX worktree 初始化使用 `bash .githooks/setup-python.sh`。
- Windows 本地 Python 命令默认使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1`，由 wrapper 设置 UTF-8 并调用项目 `.venv`。
- Codex Cloud/Linux Python 命令使用 `.githooks/run-python.sh`，由 wrapper 设置 UTF-8 并调用 `.venv/bin/python`。
- `.\.venv\Scripts\python.exe -m ...` 仍可用于临时排障；若命令输出中文，需先设置 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。
- Git hook 和自动化入口统一通过 `.githooks/run-python.sh` 选择当前平台的项目虚拟环境。
- run-python wrapper 找不到 `.venv` 时必须失败，不回退系统 Python；系统 Python 只允许 setup script 用来 bootstrap `.venv`。

## 环境初始化

当前 checkout 初始化：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
```

手动 worktree 初始化：

```powershell
git worktree add ..\Quant-Trading-<name> -b <branch> <base-branch-or-commit>
Set-Location ..\Quant-Trading-<name>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
```

Codex Cloud Environment setup script：

```bash
set -eu

bash .githooks/setup-python.sh
.githooks/run-python.sh -c "import sys; print(sys.executable); print('中文')"
```

Codex App Local Environment setup script：

```bash
set -eu

bash .githooks/setup-python.sh
.githooks/run-python.sh -m scripts.research.governance gate
```

## 常用命令

以下示例默认使用 Windows 本地入口；Codex Cloud / Linux / POSIX 环境把命令前缀替换为 `.githooks/run-python.sh -m`。

```powershell
# 语法检查
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m py_compile strategies\<strategy>\<strategy>.py

# 单元测试
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m pytest strategies\<strategy>\tests -q

# 云端回测，完整参考 scripts/tools/jq_automation/README.md
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.jq_automation compile-check|upload|run|fetch|batch|ab

# 路径引用校验
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor check

# 本地研究
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.cli init|run|promote|resume|handoff-cloud|status

# 数据中心
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.datasets import-price-json|import-audit-log|import-backtest-run|migrate-backtest-runs|inspect

# 批量迁移并瘦身历史回测 run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.datasets migrate-backtest-runs --compact-source

# 文档报告索引
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.docs index

# 策略变体登记、快照和 Git 计划
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.variants list|register|materialize|branch-plan|branch-create|merge-plan|merge-apply

# 中央工具注册与治理审计
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry list|validate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance audit
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate

# 启用本地治理 hooks
git config core.hooksPath .githooks
```

## 参考文档

- [local-python-env.md](../guides/local-python-env.md) <!-- pathref: docs/guides/local-python-env.md -->
- [jq_automation/README.md](../../scripts/tools/jq_automation/README.md) <!-- pathref: scripts/tools/jq_automation/README.md -->
- [path_tools/README.md](../../scripts/tools/path_tools/README.md) <!-- pathref: scripts/tools/path_tools/README.md -->
- [research-workflow.md](../guides/research-workflow.md) <!-- pathref: docs/guides/research-workflow.md -->
