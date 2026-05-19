---
name: agent-doc-add
description: 当用户要求把新增提示词、规则或项目约定加入 AGENTS.md、CLAUDE.md 或仓库文档，并希望遵循渐进式披露、避免重复冲突、必要时更新索引和治理扫描时使用。
---

# Agent Doc Add

把新增内容放到最合适的位置：根入口只保留每次任务都需要看到的内容，细节放进主题文档或已有 skill。

## 流程

1. 先读 [AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->、[CLAUDE.md](../../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->、[indexes.md](../../../indexes.md) <!-- pathref: repo/indexes.md --> 和相关规则文档；用 `rg` 查相同主题。
2. 查找矛盾、重复、过于模糊、过于显然的内容；发现后先问用户，不直接替用户选择。
3. 判断新增内容归属：
   - 根 [AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->：项目描述、非标准构建/检查命令、每个任务都相关的通用规则、根索引指针。
   - 根 [CLAUDE.md](../../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->：项目描述、Claude Code 专属内容、指向 AGENTS.md 的一句话。
   - 其他内容：按主题更新已有 markdown；没有合适文件时，按仓库文档结构新建主题文件。
4. 仅在新增或移动文档入口时更新 [indexes.md](../../../indexes.md) <!-- pathref: repo/indexes.md -->。
5. Markdown 内部链接使用“可点击链接 + `pathref` 注释”。
6. 收尾运行仓库级治理扫描；如果无法运行，明确说明阻断原因和替代检查。

## 边界

- 不在 AGENTS.md、CLAUDE.md 和规则文档之间重复同一条细则。
- 不加入无法执行的笼统要求，也不加入“写干净代码”这类显然规则。
- 不借新增内容重构无关文件。
- 不删除现有治理要求，除非用户明确要求并同步更新验证规则。
