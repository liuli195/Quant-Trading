# PR #25/#26 流程问题复盘

本文合并记录 PR #25 `整理规则入口并忽略本地数据目录` 和 PR #26 `补齐 Agent 配置治理文档` 的 PR 自动化流程问题。结论来自本次会话、`pr_flow` 输出、GitHub PR 状态、required checks、本地验证、官方 Codex Review 和两路子 agent review。

关联规则和实现入口：

- [pr-workflow.md](../rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->：PR、主干同步、分支清理规则。
- [review-guidelines.md](../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->：本地 AI review、官方 Codex Review 和 PR 证据规则。
- [governance.md](../rules/governance.md) <!-- pathref: docs/rules/governance.md -->：required checks、hooks 和治理门禁。
- [docs-and-pathref.md](../rules/docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->：文档链接和索引规则。
- [pr_flow.py](../../scripts/research/governance/pr_flow.py) <!-- pathref: scripts/research/governance/pr_flow.py -->：本地 PR 自动化状态机。
- [ai_review_gate.py](../../scripts/research/governance/ai_review_gate.py) <!-- pathref: scripts/research/governance/ai_review_gate.py -->：本地 AI review evidence 校验和 PR body 渲染。

最终状态：

- PR #25：<https://github.com/liuli195/Quant-Trading/pull/25>
  - 分支：`codex/agents-rules-sync`
  - 业务提交：`5502f00 整理规则入口并忽略本地数据目录`
  - 合并提交：`ffa197c8be61edc7f699dfcdbe446605aadf6d41`
  - 合并时间：2026-05-30 08:52:40 UTC
- PR #26：<https://github.com/liuli195/Quant-Trading/pull/26>
  - 分支：`codex/agent-docs-pr25-followup`
  - 业务提交：`8b500c9 补齐 Agent 配置治理文档`
  - 合并提交：`dd1a6a10077fb7452ba7cd1ff8ed0d39b5fbac22`
  - 合并时间：2026-05-30 12:18:45 UTC
- cleanup：两次 PR 均已完成，本地 `main...origin/main = 0 0`，本地和远端功能分支均已清理。

排序规则：未解决项按 P1、P2、P3 排序；同优先级内按对合并流程影响排序。已持久化解决的问题放在对应表格后部。

## 1. 阻断性质问题

| 编号 | 优先级 | 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- | --- | --- |
| B-01 | P1 | review evidence 与当前 diff 不一致 | PR #25 中 `.local/ai-review/latest.json` 残留上一轮 PR 证据；PR #26 中新增 `CODEOWNERS`、`docs/rules/governance.md`、`rules.py`、治理测试后，review evidence 仍一度只覆盖旧范围。该问题会让 `pr-review-evidence` 或人工 review 使用过期文件集。 | 否。两次都靠人工发现并重写 evidence；工具还没有强制校验 head、base 和文件集。 | 给 evidence schema 增加 `base_ref`、`head_sha`、`diff_files_hash`；`ai_review_gate validate` 比较当前 `git diff --name-only origin/main...HEAD` 与 evidence 文件集，不一致直接失败并输出 `DISPATCH_REQUIRED`。 |
| B-02 | P1 | review 范围变化后缺少自动补审 | PR #25 先审 `AGENTS.md` 和 `indexes.md`，后续加入 `.gitignore`；PR #26 又加入 `docs/agents/**`、`CODEOWNERS` 和治理代码。每次 scope 扩大后都需要人工识别并追加子 agent 复审。 | 否。流程依赖主会话发现 diff 变化。 | `pr_flow prepare/ready` 在每次同步 PR 前冻结 diff；若新增文件未被 `.local/ai-review/latest.json.changed_files` 覆盖，自动停止并给出补审文件列表，只允许补审完成后继续。 |
| B-03 | P1 | `.gitignore` 宽匹配风险没有治理规则兜底 | PR #25 初始把根目录数据忽略写成 `data/`，会匹配任意层级 `data/`，可能隐藏 `research_datasets/**/data/*` 或策略目录内应治理的数据文件。当前 PR 已改为 `/data/`，但没有持久规则阻止未来再次加入宽匹配。 | 部分。具体错误已修复并合入；防回归规则未实现。 | 在 governance audit 中增加 `.gitignore` 检查：禁止裸 `data/`、`**/data/` 等会命中嵌套数据目录的模式；允许 `/data/`。增加对应治理测试。 |
| B-04 | P2 | GitHub GraphQL/API EOF 多次中断流程 | PR #25 和 PR #26 都出现 `gh api graphql` 或 `gh pr view/edit` EOF，发生在 review threads、head SHA、label 同步等步骤。`pr_flow` 正确 fail-closed，但用户必须反复诊断和重跑。 | 否。fail-closed 已持久化；临时网络/API 错误仍会中断无问题路径。 | 对 GitHub REST/GraphQL 读取增加有限重试和退避；可用 REST 替代 GraphQL 的字段优先走 REST；重试耗尽后保留 `EXCEPTION_REQUIRED`，并明确标注为网络/API 异常。 |
| B-05 | P2 | 当前 `main` 有未提交后续改动时无法直接“合并主干” | 用户要求“使用 PR 自动化流程合并主干”时，PR #25 已合并且没有 open PR，但本地 `main` 有未提交的后续文档改动。必须先把脏工作区移到新功能分支，再重新提交、push、建 PR。 | 否。当前靠人工检查 `git status` 和新建分支处理。 | 给 `pr_flow complete` 增加 preflight：若当前在 `main` 且工作区非空，输出 `BRANCH_REQUIRED`，建议分支名并阻止继续；可选提供 `prepare-branch` 子命令只做安全分支切换，不提交。 |
| B-06 | P2 | `.codex/environments/environment.toml` 被纳入 PR 范围 | Codex App 自动生成的本地环境配置一度作为未跟踪文件进入 `ai_review_gate draft` 的 changed_files，污染 PR #26 scope。 | 是。PR #26 已在 `.gitignore` 中加入 `.codex/environments/`，该文件不再进入 review evidence。 | 无。后续如果要提交 Codex Local Environment 配置，应单独作为受治理配置变更评审。 |
| B-07 | P2 | `docs/agents/**` 未纳入关键治理路径 | PR #26 新增 `docs/agents/*` 并由 `AGENTS.md` 引用为 agent 行为配置入口，但初始未同步 `CODEOWNERS`、`governance.md`、`rules.py` 和治理测试。 | 是。PR #26 已把 `docs/agents/**` 加入 CODEOWNERS、治理关键路径、`REQUIRED_CODEOWNER_PATTERNS` 和测试 fixture。 | 无。 |
| B-08 | P3 | 复盘文档重复 pathref 造成 catalog 噪声 | PR #26 review 发现同一文档后文重复使用 pathref 注释，导致生成 catalog 中同一目标重复计数。 | 是。已移除重复 pathref 注释并重新生成 docs index。 | 无。 |

## 2. 效率性质问题

| 编号 | 优先级 | 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- | --- | --- |
| E-01 | P1 | PR body/evidence 更新触发多轮 required checks | `pr_flow complete` 同步 PR body、采集 Codex Review 证据、重新写 PR body 后，GitHub 多次触发 `Research Governance`。PR #26 中旧 run 失败、新 run 成功并存，等待和判断成本明显增加。 | 部分。`pr_flow` 能等待 required checks，但仍会产生重复 run。 | `pr_flow ready` 先完成本地 evidence、官方 review 触发/采集和 PR body 最终同步，再进入唯一一轮 required-check wait；如果 body 更新后产生新 run，只展示最新 run。 |
| E-02 | P1 | `gh pr checks --required` 输出混杂旧失败和新成功 | 手工观察时，同一个 required check 会显示旧失败、旧成功和新 pending/success 多行。PR #26 曾出现 `mergeStateStatus=BLOCKED`，但 JSON 中最新 required check 已接近全绿，阅读成本高。 | 部分。`pr_flow` 已有 JSON 去重逻辑；手工命令仍容易误判。 | 默认排障入口改为 `pr_flow diagnose --pr <PR号>`；补一个 `pr_flow checks --latest` 或增强 diagnose，把 required checks 按 workflow/job/latest run 去重后展示。 |
| E-03 | P2 | 官方 Codex Review 等待和采集需要多轮重跑 | 高风险 PR 必须触发官方 Codex Review。PR #26 中 Codex 结果以 issue comment 返回，之后还要重跑 `pr_flow complete` 才能采集证据、更新 PR body，并等待新 checks。 | 部分。Codex Review Monitor 和现有证据采集能工作，但状态提示和自动续跑不够顺滑。 | `pr_flow ready/complete` 在检测到当前 head 已有 Codex completion comment 后，直接采集并更新 PR body；在输出中区分“已触发等待中”“已完成待同步”“已同步待 checks”。 |
| E-04 | P2 | 本地和 CI 完整验证重复运行 | 两次 PR 都有本地 `verify full`、pre-push `verify full`、CI `Research Governance`；scope 修复后还会再次运行。质量上正确，但耗时高。 | 部分。PR 和 push 前必须保留 full 证据；重复运行尚未减少。 | `pr_flow prepare` 记录当前 head/diff 对应的本地 full 证据；如果 diff 未变化，后续本地阶段复用证据，只保留 pre-push 和 CI 的强验证。 |
| E-05 | P3 | cleanup 后状态确认步骤多 | 合并后需要确认 PR merged、本地 `main` fast-forward、`main...origin/main = 0 0`、本地/远端分支消失。步骤正确，但人工检查项较多。 | 部分。`pr_flow cleanup` 已执行主要动作；最终摘要仍靠人工组合多条命令。 | 在 `pr_flow cleanup` 成功输出中固化最终摘要：merge commit、base sync 状态、本地分支删除状态、远端分支删除状态。 |

## 3. PR 流程规则冲突问题

| 编号 | 优先级 | 问题 | 详细解释 | 是否已持久化解决 | 未解决时的解决方案 |
| --- | --- | --- | --- | --- | --- |
| C-01 | P1 | `pr-complete` 承诺合并收尾，但远端 merge policy 仍需人工介入 | 规则写明 `pr-complete` 在无阻断路径上继续 ready-for-review、head-locked merge 和 cleanup。PR #25 在全绿后提示必须加 `--auto`；PR #26 加 `--auto` 又因仓库未启用 auto-merge 被拒，最后等最新 checks 后用 head-locked 标准 merge 才成功。这说明 `pr_flow merge` 没覆盖远端策略分支。 | 否。两次都靠人工切换 merge 命令完成。 | `pr_flow merge` 捕获 base branch policy 错误后读取 repo auto-merge 开关和 PR `mergeable_state`；若 auto-merge 可用则 head-locked `--auto`，不可用且状态为 `clean` 时重试标准 `--match-head-commit` merge；禁止使用 `--admin`。同步更新规则文档。 |
| C-02 | P1 | 本地 AI review evidence 依赖手工拼装，不符合规则期望 | 规则期望 Skills / agents 产出 `.local/ai-review/latest.json`，再由 `pr_flow` 渲染 PR body。两次 PR 都需要主会话手工拼装或重写 JSON，容易漏字段、复用旧 PR 证据或忘记最终 reviewer 结论。 | 否。当前 schema 能校验结构，但不能自动从子 agent 输出构建真实 evidence。 | 增加 evidence builder：读取当前 diff、子 agent review 输出、验证结果、Codex review scope，生成 `latest.json`、`latest.md`、`codex-review-scope.md` 和 `pr-body.md`，并强制 head/diff 一致性校验。 |
| C-03 | P2 | 仓库要求 `gh` 默认提权，但流程仍可能非提权启动 | `AGENTS.md` 要求 `gh` CLI 默认提权执行，避免丢失沙箱外登录态。PR #25 初次 `pr_flow complete` 非提权后在 GraphQL 读取处失败；PR #26 已按提权执行，但工具本身没有启动前检查。 | 部分。本次后续操作已按提权路径执行；自动化入口未强制。 | `pr_flow` 启动时执行轻量 `gh auth status` / API 可读性检查；失败时明确输出“按提权路径重跑”，不要进入半完成状态。 |
| C-04 | P2 | 本地临时 exclude 与持久化忽略需求容易混淆 | PR #25 初始用 `.git/info/exclude` 临时处理根目录 `data/`，能清理工作区但不能解决其他工作区重复出现同类本地数据目录的问题。后续按用户要求才改成 tracked `.gitignore`。 | 是。根目录 `/data/` 已进入 `.gitignore`；PR #26 也把 `.codex/environments/` 持久忽略。 | 无。后续遇到可重复产生的项目级本地目录，应优先判断是否需要 repo-level ignore；只对纯个人路径使用 `.git/info/exclude`。 |

## 未解决项优先级汇总

| 优先级 | 编号 | 建议 |
| --- | --- | --- |
| P1 | B-01 | 给 review evidence 增加 head/base/diff 文件集一致性校验。 |
| P1 | B-02 | 在 `pr_flow prepare/ready` 中自动发现新增未审文件并输出补审任务。 |
| P1 | B-03 | 增加 `.gitignore` 治理规则，禁止宽匹配 `data/`。 |
| P1 | C-01 | 完善 `pr_flow merge` 对 GitHub auto-merge policy 和标准 merge fallback 的处理。 |
| P1 | C-02 | 增加本地 AI review evidence builder，减少手工拼装。 |
| P1 | E-01 | 让 PR body 最终同步先于唯一一轮 required-check wait。 |
| P1 | E-02 | 增加 latest required-check 去重展示入口。 |
| P2 | B-04 | 为 GitHub API/GraphQL 读写增加有限重试和 REST fallback。 |
| P2 | B-05 | `pr_flow` 检测 `main` 脏工作区并输出 `BRANCH_REQUIRED`。 |
| P2 | C-03 | `pr_flow` 启动前检查 `gh` 登录态/API 可读性。 |
| P2 | E-03 | 改善官方 Codex Review completion 采集和状态提示。 |
| P2 | E-04 | 记录并复用当前 diff 的本地 full 验证证据。 |
| P3 | E-05 | 在 `pr_flow cleanup` 输出最终状态摘要。 |
