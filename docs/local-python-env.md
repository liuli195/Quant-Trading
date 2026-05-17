# 本地 Python 环境说明

本文档约定仓库本地开发、静态检查和单元测试统一使用项目虚拟环境 [`.venv`](../.venv) <!-- pathref: repo/.venv -->。

## 推荐解释器

- Windows PowerShell：`.\.venv\Scripts\python.exe`
- 不建议直接使用系统 `python`，因为本机可能同时存在多个 Python 发行版，且默认 `python` 不一定带有 `pip`。
- Codex/自动化执行本项目 Python 命令时，默认应请求/使用提权执行项目虚拟环境；不提权可能无法访问 `.venv` 或正确解析项目目录。

## 当前约定

- 本地策略检查：使用 `.venv` 中的 Python 3.12
- 自动化代理执行：优先提权调用 `.venv\Scripts\python.exe` 或 `.venv\Scripts\pytest.exe`，避免退回系统 Python
- JoinQuant 云端运行：仍以聚宽环境为准，本地仅做编写、静态检查、单元测试和文档分析
- `jqlib` 不作为本地依赖安装要求；相关测试通过 stub 或 monkeypatch 隔离

## 首次安装或修复

如果 `.venv` 丢失或损坏，可在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果已有 `.venv` 但入口损坏，可尝试：

```powershell
py -3.12 -m venv --upgrade .venv
```

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

仓库根目录的 [`requirements.txt`](../requirements.txt) <!-- pathref: repo/requirements.txt --> 覆盖当前本地开发和文档脚本所需的基础依赖：

- 策略和测试：`numpy`、`pandas`、`pytest`
- 文档脚本：`requests`、`beautifulsoup4`、`markdownify`、`python-docx`

如后续新增本地脚本依赖，请同步更新 `requirements.txt`。
