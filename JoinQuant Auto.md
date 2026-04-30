# 聚宽量化项目自动化

采用 mcp-chrome（开源 MCP Server + Chrome 扩展）实现浏览器自动化。Claude Code 通过MCP 协议操控 Chrome，直接复用聚宽登录会话，完成「上传策略 → 运行回测 → 提取结果 →分析错误 → 修复代码」的自动化循环。无需编写任何自动化代码。

## 当前状态

CLAUDE.md 开发环境已更新，指向 /setup-mcp-chrome skill
~/.claude/skills/setup-mcp-chrome.md — 通用 mcp-chrome 安装指引
~/.claude/plans/egde-bug-optimized-turtle.md — 完整设计方案

## 待办

  1. 安装 mcp-chrome 扩展 + 配置 MCP Server（运行 /setup-mcp-chrome）
  2. Chrome 中登录聚宽
  3. 编写首个策略文件
  4. 端到端验证
