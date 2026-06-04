# ADR 0005: AI 入口采用渐进式披露

## 状态

Accepted

## 背景

根目录的 `AGENTS.md` 和 `CLAUDE.md` 同时承载大量规则，导致入口重复、职责不清，并且不利于不同 AI 工具按需读取规则。

## 决策

- [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 是所有 AI 编码助手的通用入口。
- 根目录不再保留重复文档索引；规则索引归 [docs/rules/index.md](../rules/index.md) <!-- pathref: docs/rules/index.md -->，ADR 入口归 [docs/adr/index.md](index.md) <!-- pathref: docs/adr/index.md -->。
- [CLAUDE.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 是 File Symlink 指向 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->，内容即 `AGENTS.md`，无需独立维护。
- 仓库级规则正文继续放在 [docs/rules](../rules) <!-- pathref: docs/rules -->。
- 命令和本地环境规则独立为 [commands.md](../rules/commands.md) <!-- pathref: docs/rules/commands.md -->。
- 沙箱/权限提权规则暂时上提到 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->，不放入 `CLAUDE.md`。
- `scripts.research.governance gate` 必须检查新的入口模型，避免 `AGENTS.md`、`CLAUDE.md`、规则正文、ADR 索引和 review 入口漂移。

## 删除或合并的指令

- 删除重复入口表述：`CLAUDE.md 是权威规则源`、`AGENTS.md 只保留 review 指向`。
- 合并重复 Python 环境规则到 [commands.md](../rules/commands.md) <!-- pathref: docs/rules/commands.md -->，根入口不重复命令细节。
- 将 Python 环境规则收敛为默认必须提权使用项目 `.venv`，不改用系统 Python。
- 删除“CLAUDE.md 包含全部目录结构、工具入口、代码规范、提交清单”的根文件承诺，改由 [docs/rules/index.md](../rules/index.md) <!-- pathref: docs/rules/index.md --> 分组披露。

## 影响

新增或修改 AI 规则时，先判断是否属于根入口。只有每次任务都相关的内容进入 `AGENTS.md`；工具专属内容进入对应工具入口；细则进入 `docs/rules/*.md`。
