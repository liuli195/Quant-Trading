---
name: agent-doc-refactor
description: 当用户要求重构 AGENTS.md、CLAUDE.md 或 AI 助手入口文档，使其符合渐进式披露、拆分冗余规则、创建主题文档结构、更新索引并运行治理检查时使用。
---

# Agent Doc Refactor

把根入口压缩成导航层，把细节拆到主题文档；先解决矛盾，再移动内容。

## 流程

1. 读取 [AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->、[CLAUDE.md](../../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->、[indexes.md](../../../indexes.md) <!-- pathref: repo/indexes.md -->、[docs/rules](../../../docs/rules) <!-- pathref: docs/rules --> 和相关治理规则。
2. 找出互相冲突的指令；每个冲突都先问用户保留哪个版本。
3. 提取根 [AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 的极简内容：
   - 一句话项目描述。
   - 非标准构建、类型检查或测试命令的入口指针。
   - 每个任务都必须知道的通用规则。
   - 指向 [indexes.md](../../../indexes.md) <!-- pathref: repo/indexes.md --> 的一句话。
4. 提取根 [CLAUDE.md](../../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 的极简内容：
   - 一句话项目描述。
   - Claude Code 专属内容。
   - 指向 [AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 和 `.claude/skills` 的一句话。
5. 将剩余规则按逻辑主题拆到独立 markdown。优先更新已有文件；需要新建时使用仓库现有文档目录。
6. 更新根文档索引，确保每个新主题文档能从 [indexes.md](../../../indexes.md) <!-- pathref: repo/indexes.md --> 或规则索引抵达。
7. 删除重复、不可执行、过于显然的内容。
8. 收尾运行 pathref 检查和仓库级治理扫描；如治理规则要求保留根入口 token，先同步规则或说明无法继续。

## 边界

- 不替用户决定冲突版本。
- 不把细则留在 AGENTS.md 或 CLAUDE.md 里，只保留入口级内容。
- 不创建脱离仓库文档体系的临时说明文件。
- 不做 Git 分支、合并或 PR 操作，除非用户另行要求。
