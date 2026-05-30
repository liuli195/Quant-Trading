# PR #25 流程问题复盘

本文记录 PR #25 `整理规则入口并忽略本地数据目录` 从工作区整理、分支创建、本地 review、PR 自动化、required checks、合并到 cleanup 的流程问题。结论来自本次会话、`pr_flow` 输出、GitHub PR 状态、本地验证和两路子 agent review。

关联规则和实现入口：

- [pr-workflow.md](../rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->：PR、主干同步、分支清理规则。
- [review-guidelines.md](../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->：本地 AI review、官方 Codex Review 和 PR 证据规则。
- [governance.md](../rules/governance.md) <!-- pathref: docs/rules/governance.md -->：required checks、hooks 和治理门禁。
- [docs-and-pathref.md](../rules/docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->：文档链接和索引规则。
- [pr_flow.py](../../scripts/research/governance/pr_flow.py) <!-- pathref: scripts/research/governance/pr_flow.py -->：本地 PR 自动化状态机。
- [ai_review_gate.py](../../scripts/research/governance/ai_review_gate.py) <!-- pathref: scripts/research/governance/ai_review_gate.py -->：本地 AI review evidence 校验和 PR body 渲染。

最终状态：

- PR：<https://github.com/liuli195/Quant-Trading/pull/25>
- 分支：`codex/agents-rules-sync`
- 业务提交：`5502f00 整理规则入口并忽略本地数据目录`
- 合并提交：`ffa197c8be61edc7f699dfcdbe446605aadf6d41`
- 合并时间：2026-05-30 08:52:40 UTC
- cleanup：已完成，本地 `main...origin/main = 0 0`，本地和远端功能分支均已清理。

## 1. 阻断性质问题

| 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- |
| 根目录 `data/` 未被仓库忽略，污染 PR 工作区 | 初始工作区在 `main` 上有未跟踪 `data/`，`pr_flow` / `ai_review_gate` 的 changed-files 发现会把未跟踪文件纳入证据范围。先用 `.git/info/exclude` 临时规避，后续按用户要求改为 tracked `.gitignore` 规则。 | 是。PR #25 已把根目录本地数据目录加入 [.gitignore](../../.gitignore) <!-- pathref: repo/.gitignore -->，规则为 `/data/`。 | 无。 |
| `.gitignore` 初始写成 `data/`，会隐藏嵌套数据中心文件 | 两路 reviewer 补审发现 `data/` 会匹配任意层级 `data/` 目录，可能隐藏未来应提交的 `research_datasets/**/data/*.parquet` 或策略目录下的结构化数据文件。这是 P1，必须修复后才能继续。 | 部分。本次已改成 `/data/` 并合入，当前问题解决；但还没有治理规则阻止以后再次加入过宽 ignore 模式。 | 在治理审计中增加 `.gitignore` 规则检查：禁止裸 `data/`、`**/data/` 这类会命中嵌套数据目录的模式；允许 `/data/`。 |
| review 范围变化后需要补审 | 两个子 agent 最初只审了 `AGENTS.md` 和 `indexes.md`，后来用户要求把 `data/` 加入 `.gitignore`，实际 PR 范围变成 `.gitignore`、`AGENTS.md`、`indexes.md`。原 review 结论明确排除了 `.gitignore`，必须追加补审。 | 否。这次靠人工发现并补审。 | `pr_flow prepare/ready` 比较当前 `git diff --name-only origin/main...HEAD` 与 `.local/ai-review/latest.json.changed_files`、review evidence 覆盖范围；发现新增文件未被 reviewer 覆盖时输出 `DISPATCH_REQUIRED`。 |
| `.local/ai-review/latest.json` 残留上一次 PR 的 evidence | 本次开始时 `.local/ai-review/latest.json` 仍记录上一轮大 PR 的 changed files、findings 和官方 review 链接。它能通过 schema 校验，但不代表当前 PR。必须手工重写为 PR #25 的真实 evidence。 | 否。`.local/ai-review` 是本地临时目录，当前没有持久防呆。 | 在 evidence schema 中加入 `base_ref`、`head_sha`、`diff_files_hash`；`ai_review_gate validate` 发现 head 或文件集不匹配时直接失败。 |
| GitHub GraphQL 读取 review threads 时 EOF | 第一次 `pr_flow complete` 已触发官方 review，但读取 review threads 时 `gh api graphql` 返回 EOF；流程按 fail-closed 停止，需要重新以提权 GitHub CLI 路径运行。 | 否。fail-closed 行为正确，但网络/API 临时错误仍会中断流程。 | 对 GitHub REST/GraphQL 读取增加有限重试和退避；重试耗尽后保留 `EXCEPTION_REQUIRED`，并在输出中明确这是网络/API 异常，不是 review blocker。 |
| GitHub base branch policy 要求 `--auto` 合并 | `pr_flow complete` 在 required checks 和 Codex Review 都通过后执行 head-locked merge，但 GitHub 返回 base branch policy prohibits merge，并提示加 `--auto`。需要手工运行 `gh pr merge --merge --auto --match-head-commit <sha>`，再执行 cleanup。 | 否。PR #25 已合并，但 `pr_flow merge` 仍不支持这个 policy 分支。 | `pr_flow merge` 在状态 `CLEAN`、required checks 全绿、head SHA 匹配时自动使用 `--auto --match-head-commit`；禁止使用 `--admin`。同时更新规则文档说明 auto-merge 是 GitHub policy 路径，不是 bypass。 |

## 2. 效率性质问题

| 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- |
| 完整验证重复运行多次 | 本次跑了本地 `verify full`、修复 `.gitignore` 后再次 `verify full`、pre-push `verify full`、CI required checks。质量上合理，但等待时间明显。 | 部分。PR 准备和 push 前必须有 `verify full`，不能取消；但本地重复可以更少。 | `pr_flow prepare` 记录当前 head/diff 的验证证据；如果后续 diff 未变化，避免重复本地 full，只在 push/CI 保留强验证。 |
| 官方 Codex Review 等待时间长 | 因 `AGENTS.md` 属于规则入口，本次按 high risk 触发官方 Codex Review。等待 review evidence 和 `Codex Review Monitor` 是正确流程，但耗时较高。 | 部分。当前已有 `Codex Review Monitor` 和 evidence 自动采集，但等待本身仍存在。 | 对规则入口保持官方 review；对低风险非关键路径 PR 继续允许 monitor 空跑。进一步优化只应做 evidence 复用和状态提示，不应跳过必要 review。 |
| 子 agent review 先审错范围，导致二次补审 | 初始子 agent review 在 `.gitignore` 加入前发起，后续 PR scope 扩大，两个 reviewer 都声明 `.gitignore` 不在结论范围内，必须补审和复核。 | 否。 | 冻结 diff 后再派 review；或者在每次新增文件后自动生成补审任务，只审新增文件和受影响规则。 |
| PR body 更新触发新一轮 required checks | `pr_flow complete` 同步 PR body evidence 后，GitHub 又触发一轮 `Research Governance`，导致前一轮已经通过的 check 旁边出现新 pending run，需要额外等待。 | 部分。状态机能等待，但仍可能造成重复等待。 | `pr_flow ready` 先完成 PR body/evidence 同步，再进入唯一一轮 required-check wait；如果 body 更新后产生新 run，明确输出“等待最新 run”，不要混杂旧 run。 |
| `gh pr checks --watch` 文本输出混杂旧 run 和新 run | 手工排障时 `gh pr checks` 同时显示旧成功 run 和新 pending run，阅读成本高。此前 JSON 去重逻辑主要在 `pr_flow` 内，手工命令仍容易误判。 | 部分。`pr_flow` 内部已有更可靠的状态判断；手工输出仍嘈杂。 | 日常排障默认用 `pr_flow diagnose --pr <PR号>`；如必须用 `gh pr checks`，用 JSON 输出并按 workflow/job/latest run 去重。 |
| cleanup 前后状态确认较多 | 合并后需要确认 PR merged、执行受控 cleanup、再确认本地 `main`、`origin/main`、本地分支和远端分支。步骤正确，但人工检查项多。 | 是。`pr_flow cleanup --pr 25` 已完成受控同步和分支清理。 | 无。可继续把最终状态摘要固化到 `pr_flow cleanup` 输出中。 |

## 3. PR 流程规则冲突问题

| 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- |
| 仓库规则要求 `gh` 默认提权，但第一次 `pr_flow complete` 非提权运行 | `AGENTS.md` 规定 GitHub CLI 默认提权执行，避免丢失沙箱外登录态。本次第一次 `pr_flow complete` 非提权运行，虽然能触发 review，但在 GraphQL review threads 读取处 EOF 后才改为提权重跑。 | 否。 | Codex 工作流中把所有会调用 `gh` 的 `pr_flow` 命令视为需要提权；必要时在 `pr_flow` 启动时检测 `gh auth status` 和 GitHub API 可读性，失败时直接提示按提权路径重跑。 |
| `pr-complete` 规则承诺完成 merge/cleanup，但实际卡在 GitHub auto-merge policy | [pr-workflow.md](../rules/pr-workflow.md) 和 [governance.md](../rules/governance.md) 都描述 `pr-complete` 在无阻断路径上继续 ready-for-review、head-locked merge 和 cleanup。本次无阻断后仍因 GitHub policy 需要 `--auto` 手工介入。 | 否。 | 更新 `pr_flow merge` 支持 head-locked auto-merge；或者把规则改为“如果远端 policy 要求 auto-merge，`pr_flow` 自动设置 auto-merge 并等待 merge 完成后 cleanup”。 |
| 临时 `.git/info/exclude` 处理不符合“持久化忽略规则”的实际需求 | 初始只把 `data/` 放入本地 exclude，能临时清理工作区，但无法解决仓库其他工作区反复出现根目录 `data/` 的问题。用户随后明确要求加入 Git 忽略列表，才转为 tracked `.gitignore`。 | 是。本次已用 tracked [.gitignore](../../.gitignore) 持久化。 | 无。后续遇到可重复产生的项目级本地目录，应优先判断是否需要 repo-level ignore，而不是只做本地 exclude。 |
| 本地 AI review evidence 依赖手工拼装 | 规则希望先由 Skills / agents 产出 `.local/ai-review/latest.json`，再让 `pr_flow` 渲染 PR body。本次 review 结论来自真实子 agent，但 `latest.json` 仍由主会话手工重写。过程合规性可接受，但不够自动化，容易漏字段或使用旧 evidence。 | 否。 | 增加一个 evidence builder：读取当前 diff、子 agent review 输出、验证结果，生成 `latest.json`、`latest.md`、`codex-review-scope.md` 和 `pr-body.md`，并校验 head/diff 一致性。 |

## 后续建议

| 优先级 | 建议 | 目标 |
| --- | --- | --- |
| P1 | 给 `pr_flow merge` 增加 head-locked `--auto` 分支 | 消除 PR #25 这类远端 policy 下的手工合并步骤。 |
| P1 | 给 `ai_review_gate` 增加 head/diff 文件集一致性校验 | 防止旧 `.local/ai-review/latest.json` 被误用于新 PR。 |
| P1 | 给 `.gitignore` 增加治理检查，禁止裸 `data/` | 防止再次隐藏 `research_datasets/**/data/*`。 |
| P2 | 给 `pr_flow` 增加 GitHub API/GraphQL 有限重试 | 减少 EOF/TLS 这类临时错误导致的中断。 |
| P2 | 把子 agent 输出自动转成 PR evidence | 减少手工拼装证据和补字段成本。 |
