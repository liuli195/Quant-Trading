# 本地 Python 环境说明

本文档约定仓库本地开发、静态检查和单元测试统一使用当前 checkout 的项目虚拟环境 `.venv`。

## 两阶段模型

- setup script：创建或修复当前 checkout 的 `.venv`，安装 [requirements-dev.txt](../../requirements-dev.txt) <!-- pathref: repo/requirements-dev.txt -->，并配置 `git config core.hooksPath .githooks`。
- run 阶段：日常命令直接调用当前 checkout 的 `.venv`；UTF-8 由用户级或机器级环境变量处理，不再由 run-python wrapper 注入。

推荐入口：

- Windows setup：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1`
- Windows run：`.\.venv\Scripts\python.exe`
- Codex Cloud / Linux setup：`bash .githooks/setup-python.sh`
- Codex Cloud / Linux run：`.venv/bin/python`
- Git hook 内部入口：`.githooks/run-python.sh`

不建议直接使用系统 `python` 执行业务命令。系统 Python 只允许 setup script 用来 bootstrap `.venv`。

## 本地或 worktree 初始化

如果 `.venv` 丢失、损坏，或你新建了一个 worktree，在该 checkout 根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
```

手动新建 worktree 的完整示例：

```powershell
git worktree add ..\Quant-Trading-<name> -b <branch> <base-branch-or-commit>
Set-Location ..\Quant-Trading-<name>
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable); print('中文')"
```

Codex App 创建的 Windows worktree 中，也使用同一条初始化命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
```

## Codex Cloud Environment setup script

Codex Cloud 环境设置页中可粘贴：

```bash
set -eu

bash .githooks/setup-python.sh
.venv/bin/python -c "import sys; print(sys.executable); print('中文')"
```

官方依据：Codex Cloud 会先 checkout repo，再运行 setup script；setup 阶段可联网安装依赖，agent 阶段再执行命令。参考 <https://developers.openai.com/codex/cloud/environments>。

## Codex App Local Environment

Codex App Local Environment 的 Linux/macOS setup script 示例：

```bash
set -eu

bash .githooks/setup-python.sh
.venv/bin/python -m scripts.research.governance gate
```

Windows Local Environment 示例：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\setup-python.ps1
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

官方依据：Codex Local Environments 可为 worktree 配置 setup script，配置可由 Codex App 生成到仓库根目录 `.codex`。参考 <https://developers.openai.com/codex/app/local-environments>。

Codex worktree 是独立 checkout，每个 worktree 都应该运行 setup script 并拥有自己的 `.venv`。参考 <https://developers.openai.com/codex/app/worktrees>。

## 常用命令

语法检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile strategies\etf_dynamic_rebalance\etf_dynamic_rebalance.py
.\.venv\Scripts\python.exe -m py_compile strategies\etf_factor_rotation\etf_factor_rotation.py
```

运行单元测试：

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_dynamic_rebalance\tests -q
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests -q
```

路径引用检查：

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

## 依赖说明

[requirements-dev.txt](../../requirements-dev.txt) <!-- pathref: repo/requirements-dev.txt --> 是本地治理、测试和 review gate 的 setup 入口。它包含 [requirements.txt](../../requirements.txt) <!-- pathref: repo/requirements.txt -->，并额外安装 `pre-commit`、`ruff`、`bandit`、`mypy`、`pip-audit` 等检查工具。

`jqlib` 不作为本地依赖安装要求；相关测试通过 stub 或 monkeypatch 隔离。
