## Purpose

TBD

## Requirements

### Requirement: 项目虚拟环境

环境管理系统 SHALL 以项目 `.venv` 作为默认 Python 执行环境，禁止日常命令使用系统 Python。

#### Scenario: 命令执行

- **WHEN** 用户或 AI agent 执行 Python 命令
- **THEN** 系统使用 `.\.venv\Scripts\python.exe` (Windows) 或 `.venv/bin/python` (Linux/macOS)，UTF-8 编码由环境变量 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8` 保障

### Requirement: 本地/聚宽平台差异

环境管理系统 SHALL 明确区分本地开发环境和聚宽云端环境的边界：策略代码仅在聚宽回测/模拟运行，本地负责开发、测试和分析。

#### Scenario: 平台兼容检查

- **WHEN** 策略代码准备上传聚宽
- **THEN** 系统通过 `scripts.tools.jq_automation compile-check` 检查 Python 3.6 兼容性、禁用语法和 API 可用性
