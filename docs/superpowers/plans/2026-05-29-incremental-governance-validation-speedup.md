# 日常增量验证提速 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 repo-native affected 验证层，让日常小改默认跑 `verify-fast`；本地 PR 提交走 `pr-submit`，push、CI 和最终交付仍跑完整 `verify-full`。

**Architecture:** 保留 `scripts.research.governance gate` 的强门禁语义，新增 `verify` 编排层负责 affected 选择、解释输出和本地缓存。每个检查都有稳定 `check_id`、输入文件、配置依赖和命令边界；fast 只证明“可继续开发”，PR/合并证据来自 GitHub required check，full 保留为 push/CI/final 完整验证。

**Tech Stack:** Python 3.12, argparse, pytest, existing `scripts.research.governance`, existing `scripts.tools.path_tools.refactor`, Makefile, `.githooks`, GitHub Actions.

---

## Design Inputs

- 方案设计：[日常增量验证提速方案设计.md](../../design/日常增量验证提速方案设计.md) <!-- pathref: docs/design/日常增量验证提速方案设计.md -->
- 通用入口：[AGENTS.md](../../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->
- 命令规则：[commands.md](../../rules/commands.md) <!-- pathref: docs/rules/commands.md -->
- 治理规则：[governance.md](../../rules/governance.md) <!-- pathref: docs/rules/governance.md -->
- Pathref 规则：[docs-and-pathref.md](../../rules/docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->
- 现有治理入口：[governance/README.md](../../../scripts/research/governance/README.md) <!-- pathref: scripts/research/governance/README.md -->

## Tracer Bullet Rules

每个切片必须是一条可单独验证的窄路径：

| 层 | 本计划中的含义 | 每片交付 |
| --- | --- | --- |
| 架构 | affected 规则、缓存键、fast/full 合同 | 有明确选择规则和降级边界 |
| API | Python 函数、CLI 参数、返回结构 | 测试可直接调用，CLI 可演示 |
| 界面 | 命令输出、Makefile、hook、CI、规则文档 | 用户知道跑了什么、跳过了什么 |
| 测试 | 单测、hook/governance 断言、pathref 检查 | 切片可独立跑通 |

AFK 表示实现和合并不需要新的人工判断；HITL 表示需要先确认策略或删除窗口。本计划主路径全部按 AFK 设计；旧入口删除作为可选 HITL 收尾。

## Slice Tracker

- [x] S01 [AFK] Pathref scoped check：给 Markdown 小改第一条快路径。
- [x] S02 [AFK] Affected explain：只解释命中的检查，不执行命令。
- [x] S03 [AFK] Docs fast path：`verify fast` 能验证普通文档改动并声明 full 未运行。
- [x] S04 [AFK] Skill fast path：Skill 改动触发 owner/adapter scoped 检查。
- [x] S05 [AFK] Governance fast path：治理代码改动触发静态扫描和治理单测。
- [x] S06 [AFK] Strategy/dependency fast path：策略与依赖改动触发对应局部检查。
- [x] S07 [AFK] Passing-result cache：只缓存通过结果，并在 explain/fast 中展示命中。
- [x] S08 [AFK] Full contract and entrypoints：`verify full`、Makefile、hooks、CI parity 全部接入。
- [x] S09 [AFK] Rules and registry sync：规则、README、工具注册表、层索引同步。
- [x] S10 [HITL] Legacy and CI shape decision：人工已确认 CI 收敛为单命令。

## File Structure

**Create: `scripts/research/governance/affected.py`**

职责：
- 收集 staged/worktree diff、`--base`、`--files` 和 `.local/ai-review/latest.json.changed_files`。
- 把文件路径映射为 `CheckSpec` 列表。
- 明确 `full_required=False`，不自动把 fast 升级为 full。

**Create: `scripts/research/governance/verify.py`**

职责：
- 提供 `fast`、`full`、`explain` 三个 CLI 子命令。
- 执行 affected 检查、渲染 checked/skipped/cache-hit/full-not-run。
- `full` 调用现有完整门禁和全局检查。

**Create: `scripts/research/governance/verify_cache.py`**

职责：
- 在 `.local/governance-cache/` 保存通过结果。
- 缓存键包含 check id、命令参数、输入文件哈希、配置哈希、Python 版本和工具版本。
- 失败结果不缓存。

**Modify: `scripts/tools/path_tools/refactor.py`**

职责：
- 扩展 `check --files <paths...>`。
- 无 `--files` 时保持现有全仓行为。

**Modify: `scripts/research/governance/__main__.py`**

职责：
- 挂载 `verify` 子命令，保持 `audit` 和 `gate` 兼容。

**Modify: `scripts/research/governance/pr_flow.py`**

职责：
- 复用 `affected.py` 的路径分类，避免 `pr_flow.select_local_checks()` 与 `verify` 各维护一套矩阵。
- PR evidence 路径仍可要求完整治理证据，不继承 fast 的“可继续开发”语义。

**Modify: `scripts/research/governance/rules.py`**

职责：
- 更新 hook、Makefile、workflow、文档 token 检查。
- `pre-commit` 期待 `verify fast --staged`，`pre-push` 和 CI 期待 `verify full`。

**Modify tests**

- `scripts/research/governance/tests/test_governance.py`
- 新增可选拆分文件：`scripts/research/governance/tests/test_verify.py`

**Modify interface/docs**

- `Makefile`
- `.githooks/pre-commit`
- `.githooks/pre-push`
- `.github/workflows/research-governance.yml`
- `scripts/research/governance/README.md`
- `docs/rules/commands.md`
- `docs/rules/governance.md`
- `docs/rules/review-guidelines.md`
- `AGENTS.md`
- `scripts/research/registry/tool_registry.py`

## Integration Risks

- 旧 `.githooks/pre-commit` 的 fast-gate 入口只是跳过 CLI help/pathref，仍会跑完整 `run_audit()`；它不是本设计里的 affected fast。
- 现有 `pr_flow.select_local_checks()` 已按 changed files 选择检查，但 docs 改动也会落到 `governance-full`；新 planner 必须被 `pr_flow` 复用或替换，避免两套矩阵漂移。
- CI 第一轮可分步展示 ruff、bandit、mypy、pip-audit、pytest 和 gate；S10 由人工决定是否收敛为单一 `verify full`。
- 缓存必须晚于 check id、输入范围和 explain 输出稳定后再加。

## S01 [AFK]: Pathref Scoped Check

**Demo:** 普通文档小改只检查该 Markdown 文件内的 pathref。

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check --files docs/design/日常增量验证提速方案设计.md
```

**Files:**
- Modify: `scripts/tools/path_tools/refactor.py`
- Test: `scripts/research/governance/tests/test_governance.py`
- Modify: `scripts/tools/path_tools/README.md`

- [ ] 写失败测试：两个 Markdown 文件中只有传入 `--files` 的坏 pathref 会报错，未传入文件不扫描。
- [ ] 将 `check_markdown_pathrefs()` 改为接收 `files: Sequence[Path] | None`。
- [ ] CLI 增加 `check --files <paths...>`；路径必须留在 repo 内，非 Markdown 文件给出清晰错误。
- [ ] 更新 path_tools README，说明 `--files` 是日常增量入口，全量仍用无参数 `check`。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py -q
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check --files docs/design/日常增量验证提速方案设计.md
```

**Vertical path:** 架构收窄 pathref 合同；API 暴露 `--files`；界面给出 checked file 数；测试证明不会扫描全仓。

## S02 [AFK]: Affected Explain

**Demo:** 不执行检查，只说明一次文档改动会命中什么。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files docs/design/日常增量验证提速方案设计.md
```

**Files:**
- Create: `scripts/research/governance/affected.py`
- Create: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/__main__.py`
- Test: `scripts/research/governance/tests/test_verify.py`

- [ ] 写失败测试：`docs/**/*.md` 映射到 `pathref.changed-files`，并输出 `full_not_run=true`。
- [ ] 定义 `ChangedFileSource`、`CheckSpec`、`AffectedPlan`。
- [ ] 实现 `collect_changed_files(repo_root, staged, base, files, ai_review_report)`。
- [ ] 实现 `plan_checks(changed_files)`，先覆盖 docs、skills、governance、requirements、strategies 五类。
- [ ] 让 `pr_flow.select_local_checks()` 复用 `plan_checks()` 的分类结果；PR evidence 仍可追加完整治理检查。
- [ ] `verify explain` 输出 JSON 和默认人类可读文本；默认文本必须包含 checked、skipped、full-not-run。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_verify.py -q
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files docs/design/日常增量验证提速方案设计.md
```

**Vertical path:** 架构建立 affected 模型；API 给出可测 Python 对象；界面先可解释；测试锁定路径矩阵。

## S03 [AFK]: Docs Fast Path

**Demo:** 文档小改跑 `verify fast`，只执行 changed-file pathref，并明确不是 PR 证据。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs/design/日常增量验证提速方案设计.md
```

**Files:**
- Modify: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/tests/test_verify.py`
- Modify: `docs/rules/commands.md`

- [ ] 写失败测试：docs-only fast 不调用 `scripts.research.governance gate`。
- [ ] 实现命令 runner，先支持 `pathref.changed-files`。
- [ ] `verify fast` 返回结构包含 `ok`、`checked`、`skipped`、`full_not_run`。
- [ ] 文档命令区新增 `verify fast` / `verify explain`，并声明 fast 只代表可继续开发。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_verify.py -q
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs/design/日常增量验证提速方案设计.md
```

**Vertical path:** 架构落地 fast 合同；API 执行一个真实 check；界面输出覆盖范围；测试防止误跑 full。

## S04 [AFK]: Skill Fast Path

**Demo:** Skill 目录变更只跑 owner/adapter scoped 检查，不跑完整 gate。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files .codex/skills/repo-python-env/SKILL.md
```

**Files:**
- Modify: `scripts/research/governance/affected.py`
- Modify: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/tests/test_verify.py`
- Modify: `docs/rules/skills.md`

- [ ] 写失败测试：`.codex/skills/**` 和 `.claude/skills/**` 命中 `skill-ownership.scoped`。
- [ ] 让 `skill-ownership.scoped` 调用现有 `scripts.research.governance.skill_ownership check`；如当前 CLI 不支持 scoped 参数，先跑 owner 全量，不升级 full gate。
- [ ] 输出中列出命中的 skill 名称和跳过的 full gate。
- [ ] 更新 Skill 规则，说明 Skill 小改的日常检查入口。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_verify.py -q
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files .codex/skills/repo-python-env/SKILL.md
```

**Vertical path:** 架构保留 owner 边界；API 选择 skill check；界面展示 skill scope；测试证明不触发 full。

## S05 [AFK]: Governance Fast Path

**Demo:** 治理代码改动触发治理相关 ruff、bandit、mypy、pytest，但不跑 pathref 全量。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files scripts/research/governance/verify.py
```

**Files:**
- Modify: `scripts/research/governance/affected.py`
- Modify: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/tests/test_verify.py`
- Modify: `scripts/research/governance/README.md`

- [ ] 写失败测试：`scripts/research/governance/**` 命中 `ruff.governance`、`bandit.governance`、`mypy.governance`、`pytest.governance`。
- [ ] 实现治理检查命令，复用 Makefile 中现有路径和 bandit skip 列表。
- [ ] 输出中把这些检查标为 `scoped`，并显示 full gate 未运行。
- [ ] README 加入 fast/full/explain 三个入口的区别。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_verify.py -q
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files scripts/research/governance/verify.py
```

**Vertical path:** 架构限定高风险路径；API 复用静态扫描命令；界面显示 scoped 检查；测试覆盖命令矩阵。

## S06 [AFK]: Strategy And Dependency Fast Path

**Demo:** 策略改动只跑对应策略的语法和测试；依赖改动跑 pip-audit。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files strategies/etf_factor_rotation/etf_factor_rotation.py
```

**Files:**
- Modify: `scripts/research/governance/affected.py`
- Modify: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/tests/test_verify.py`

- [ ] 写失败测试：`strategies/<name>/<name>.py` 命中 `py_compile.strategy` 和 `pytest.strategy`。
- [ ] 写失败测试：`requirements.txt`、`requirements-dev.txt` 命中 `pip-audit.dependencies`。
- [ ] 实现策略路径解析：优先编译 `strategies/<name>/<name>.py`，测试目录存在时跑 `strategies/<name>/tests -q`。
- [ ] 缺少测试目录时输出 `skipped`，但不把 fast 标为失败；PR 前仍由 full 兜底。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_verify.py -q
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files strategies/etf_factor_rotation/etf_factor_rotation.py
```

**Vertical path:** 架构按策略目录切 scope；API 生成策略命令；界面解释 skipped；测试覆盖存在/缺失测试目录。

## S07 [AFK]: Passing-Result Cache

**Demo:** 同一输入第二次 fast 命中 `.local/governance-cache/`，失败不缓存。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs/design/日常增量验证提速方案设计.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs/design/日常增量验证提速方案设计.md
```

**Files:**
- Create: `scripts/research/governance/verify_cache.py`
- Modify: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/tests/test_verify.py`

- [ ] 写失败测试：相同 check/input/config/python/tool 版本二次运行 `cache_hit=true`。
- [ ] 写失败测试：文件内容变更后缓存失效。
- [ ] 写失败测试：失败结果不写入缓存。
- [ ] 缓存目录固定为 `.local/governance-cache/`，不进入 Git。
- [ ] explain 输出缓存键摘要，不输出长哈希噪音。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_verify.py -q
```

**Vertical path:** 架构定义缓存键；API 提供 load/store；界面显示 cache-hit；测试覆盖命中、失效和失败不缓存。

## S08 [AFK]: Full Contract And Entrypoints

**Demo:** 日常入口变快，本地 PR 提交不重复跑完整门禁，push/CI 仍跑完整门禁。

```powershell
make verify-fast
make verify-full
```

**Files:**
- Modify: `Makefile`
- Modify: `.githooks/pre-commit`
- Modify: `.githooks/pre-push`
- Modify: `.github/workflows/research-governance.yml`
- Modify: `scripts/research/governance/verify.py`
- Modify: `scripts/research/governance/pr_flow.py`
- Modify: `scripts/research/governance/rules.py`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] 写失败测试：Makefile 必须包含 `verify-fast`、`verify-full`，`pre-pr` 调用或等价覆盖 `verify-full`。
- [ ] 写失败测试：pre-commit 使用 `scripts.research.governance verify fast --staged`。
- [ ] 写失败测试：pre-push 和 CI 不使用 fast，仍覆盖完整治理门禁。
- [ ] 实现 `verify full`：复用现有 ruff、bandit、mypy、pip-audit、pytest、pathref、governance gate。
- [ ] CI 第一轮保留现有分步诊断；如增加 `verify full`，只作为 parity 或最终 gate，不替换可读性更好的分步 job。
- [ ] 旧 fast-gate 入口暂保留兼容；可内部委托 `verify fast` 或保持旧语义，但新文档不再推荐它。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py -q
make verify-fast
make verify-full
```

**Vertical path:** 架构完成 fast/full 合同；API 提供 full；界面接入 Makefile/hook/CI parity；测试锁住不能把 full 降级。

## S09 [AFK]: Rules And Registry Sync

**Demo:** 工具注册表、规则文档和层索引都能发现新验证入口。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry validate
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry write-layers
```

**Files:**
- Modify: `scripts/research/registry/tool_registry.py`
- Modify: `scripts/research/layers/*.md`
- Modify: `AGENTS.md`
- Modify: `docs/rules/commands.md`
- Modify: `docs/rules/governance.md`
- Modify: `docs/rules/review-guidelines.md`
- Modify: `scripts/research/governance/README.md`
- Modify: `indexes.md` if docs index requires it

- [ ] 登记 `research.governance_verify` 或更新 `research.governance` 描述，使 `verify fast/full/explain` 可见。
- [ ] 规则文档写清：日常小改默认 `verify fast`；本地 PR 提交走 `pr-submit`；push 前、CI、最终交付证据必须 `verify full`。
- [ ] AGENTS.md 只保留入口级规则，避免复制实现细节。
- [ ] 重新生成层索引和 docs index。
- [ ] 运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry validate
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry write-layers
.\.venv\Scripts\python.exe -m scripts.research.docs index
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
.\.venv\Scripts\python.exe -m scripts.research.governance gate
git diff --check
```

**Vertical path:** 架构同步注册表；API 进入工具目录；界面同步规则入口；测试/门禁证明无漂移。

## S10 [HITL]: Legacy And CI Shape Decision

**Demo:** 人工已决定删除旧入口，CI 收敛为单一 `verify full`。

**Files:**
- Potential Modify: `scripts/research/governance/gate.py`
- Potential Modify: `scripts/research/governance/__main__.py`
- Potential Modify: `docs/rules/governance.md`
- Potential Modify: `.githooks/pre-commit`
- Potential Modify: `.github/workflows/research-governance.yml`

- [x] S01-S09 先完成，不被旧入口删除阻断。
- [x] 人工确认删除旧 fast-gate，不做 deprecation warning 或长期别名。
- [x] 人工确认 CI 收敛为单命令 `verify full`。
- [x] 测试必须证明所有文档、hooks、Makefile、CI 不再引用旧入口。

**Vertical path:** 架构确认兼容策略；API 处理旧参数；界面避免用户命令断裂和 CI 诊断退化；测试防止旧入口半删半留。

## Acceptance

- `verify fast` 对普通 Markdown 小改不运行完整 `scripts.research.governance gate`。
- `verify fast` 输出包含 checked、skipped、cache-hit、full-not-run。
- `verify explain` 可在不执行命令的情况下说明命中检查。
- `verify full` 与现有完整 pre-push/CI 覆盖等价；PR 合并证据来自 GitHub required check。
- `.githooks/pre-commit` 走 fast；`.githooks/pre-push` 和 GitHub Actions 仍走 full。
- 缓存只保存通过结果，输入、配置、Python 或工具版本变化后失效。
- 文档、工具注册表、层索引、pathref、governance gate 全部同步。

## Final Verification Bundle

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests -q
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry validate
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry write-layers
.\.venv\Scripts\python.exe -m scripts.research.docs index
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs/design/日常增量验证提速方案设计.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
git diff --check
```
