# CLAUDE.md

## 项目概述

这是一个量化交易项目，基于 python ，主要用于A股股票和场内基金。整个开发、回测、模拟交易均运行在**聚宽 (JoinQuant) 云平台**上，无法在本地运行。

- 聚宽 API 文档：<https://www.joinquant.com/help/api/help#name:api>
- 策略回测系统：<https://www.joinquant.com/algorithm/index/list>
- 模拟交易系统：<https://www.joinquant.com/algorithm/trade/list>

## 开发环境

### Python 本地环境（静态检查）

代码在本地编写，随后通过浏览器自动化上传到聚宽平台运行和测试。本地无法直接执行策略代码，但可以搭建 Python 环境用于静态检查或代码格式化。

### 浏览器自动化（mcp-chrome）

通过 [mcp-chrome](https://github.com/hangwin/mcp-chrome) 开源 MCP Server 操控 Chrome 浏览器，实现「上传策略 → 运行回测 → 提取结果」的自动化。Claude Code 通过 MCP 协议调用浏览器工具，所有操作在真实浏览器中可见。

使用 `/setup-mcp-chrome` 查看完整的安装和配置步骤。

**关键提示：**

- 需先在 Chrome 中手动登录聚宽（微信扫码/手机验证码），mcp-chrome 直接复用该登录会话

## 聚宽策略代码结构

聚宽策略文件遵循固定的生命周期函数模式：

- `initialize(context)` — 策略初始化，设置参数、股票池、定时任务
- `handle_data(context, data)` — 按分钟/日调用的主逻辑（或自定义 `run_daily`/`run_weekly` 等定时函数）

## 注意事项

- 对claude code本身进行操作时，包括配置MCP，skill等，优先采用Claude code自带命令。
- 所有策略代码依赖聚宽API，这些API仅在聚宽云端可用，本地无法运行。
- jqdata为本地数据下载服务，本项目不采用本地数据，不使用jqdata。
- 聚宽平台对 API 调用频率有限制，策略中需注意避免过于频繁的请求。
- 回测和模拟交易均需要绑定聚宽账号，策略文件不与账号凭证关联。
