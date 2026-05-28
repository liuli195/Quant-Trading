# PR Flow Handsfree Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `make pr-ready TITLE="<PR标题>"` 做成尽量一键到底的 PR 流程；只有异常处理、任务分发、问题回复三类情况才停止。

**Architecture:** 保持仓库规则不变：`pr_flow` 只编排、等待、同步结构化证据，不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review。新增一个显式状态机，把“无问题路径”自动推进，把“需要判断路径”稳定归类并输出可执行下一步。

**Tech Stack:** Python 3.12, pytest, GitHub CLI `gh`, existing `scripts.research.governance.pr_flow`, `ai_review_gate`, `pr_review_evidence`, `Codex Review Monitor`, Makefile `pr-ready`, `.githooks/run-python.ps1`.

---

## 不违反规则的自动化边界

| 场景 | 自动化策略 | 是否允许继续 |
| --- | --- | --- |
| 本地 AI review evidence 已存在且 schema 合法 | 自动校验、渲染 PR body、同步 PR | 允许 |
| 本地 AI review evidence 缺失或不完整 | 输出 `DISPATCH_REQUIRED`，列出需要交给 agents 的 review 项 | 停止 |
| 官方 Codex review 无 P0/P1 | 自动读取当前 head 的有效 review/comment，写入 `official_codex_review`，同步 PR body | 允许 |
| 官方 Codex review 报 P0/P1 或 unresolved thread | 输出 `REPLY_OR_FIX_REQUIRED`，列出链接和阻断原因 | 停止 |
| required checks 出现旧失败、新成功重复项 | 自动按最新 run 结果去重 | 允许 |
| required checks 最新结果失败 | 输出 `EXCEPTION_REQUIRED`，附 run/job 链接和失败摘要 | 停止 |
| PR head 在等待期间变化 | 输出 `EXCEPTION_REQUIRED`，禁止把旧证据写到新 head | 停止 |
| GitHub auth / network / API 失败 | 输出 `EXCEPTION_REQUIRED`，保留可重跑状态 | 停止 |

## 目标命令行为

主入口保持不变：

```powershell
make pr-ready TITLE="<PR标题>"
```

成功路径：

```text
prepare local checks
sync PR body and labels
trigger @codex review if required
wait for current-head Codex review
auto-record passing Codex evidence
resync PR body
wait required checks
exit 0
```

停止路径只允许三类：

```text
DISPATCH_REQUIRED       # 缺本地 AI review / 需要子 agent review
REPLY_OR_FIX_REQUIRED   # Codex 或 reviewer 报出 P0/P1，需要修复或回复
EXCEPTION_REQUIRED      # auth、网络、CI 失败、head 变化、超时等异常
```

## File Structure

**Modify: `scripts/research/governance/pr_flow.py`**

职责：
- 增加 PR flow 状态枚举和机器可读摘要。
- 自动等待并采集当前 head 的官方 Codex 通过证据。
- 自动重渲染 `.local/ai-review/pr-body.md` 并同步 PR 托管区。
- 对 required checks 采用最新 run 去重。
- 只在允许自动推进的状态继续。

**Modify: `scripts/research/governance/tests/test_pr_flow.py`**

职责：
- 覆盖无问题路径自动推进。
- 覆盖三类停止状态。
- 覆盖 head 变化、Codex P0/P1、重复 required checks、pending timeout。

**Modify: `docs/rules/pr-workflow.md`**

职责：
- 把 `pr-ready` 描述为一键状态机。
- 保留“不得伪造 review、不得本地合入 main、官方 review 证据必须来自当前 head”的规则。

**Modify: `docs/rules/review-guidelines.md`**

职责：
- 说明自动补证据只适用于官方 Codex 无 P0/P1 的当前 head 结果。
- 明确 P0/P1、unresolved thread、context invalid 仍阻断。

**Modify: `docs/rules/governance.md`**

职责：
- 同步 required checks 和 PR body 证据要求。
- 说明 `Codex Review Monitor` success 不替代 PR body evidence，但可作为自动采集依据之一。

## Task 1: 状态模型和退出码

**Files:**
- Modify: `scripts/research/governance/pr_flow.py`
- Test: `scripts/research/governance/tests/test_pr_flow.py`

- [ ] **Step 1: 写失败测试：缺本地 review evidence 时停止为任务分发**

新增测试：

```python
def test_ready_stops_with_dispatch_required_when_review_evidence_missing(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    runner = FakeRunner(existing_pr=True)
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.DISPATCH_REQUIRED_EXIT_CODE
    assert "DISPATCH_REQUIRED" in capsys.readouterr().err
```

运行：

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py::test_ready_stops_with_dispatch_required_when_review_evidence_missing -q
```

预期：失败，因为当前没有 `DISPATCH_REQUIRED_EXIT_CODE` 和显式状态输出。

- [ ] **Step 2: 实现状态常量**

在 `pr_flow.py` 顶部常量区加入：

```python
SUCCESS_EXIT_CODE = 0
GENERAL_FAILURE_EXIT_CODE = 1
CODEX_REVIEW_PENDING_EXIT_CODE = 3
DISPATCH_REQUIRED_EXIT_CODE = 4
REPLY_OR_FIX_REQUIRED_EXIT_CODE = 5
EXCEPTION_REQUIRED_EXIT_CODE = 6
```

新增小工具：

```python
def _print_state(state: str, message: str, *, details: Sequence[str] = ()) -> None:
    print(f"{state}: {message}", file=sys.stderr)
    for detail in details:
        print(f"- {detail}", file=sys.stderr)
```

- [ ] **Step 3: 缺 evidence 时不进入 sync / wait**

在 `ready()` 读取 `.local/ai-review/latest.json` 后增加：

```python
if payload is None:
    _print_state(
        "DISPATCH_REQUIRED",
        "missing .local/ai-review/latest.json; local AI review must be produced by humans or agents",
        details=[
            "run the required local AI review",
            "record two independent reviewers",
            "record security_review with codex-security evidence",
        ],
    )
    return DISPATCH_REQUIRED_EXIT_CODE
```

规则理由：仓库要求本地 AI review 和两个独立 reviewer，`pr_flow` 不能伪造。

- [ ] **Step 4: 跑测试**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py::test_ready_stops_with_dispatch_required_when_review_evidence_missing -q
```

预期：通过。

## Task 2: 官方 Codex 无问题路径自动推进

**Files:**
- Modify: `scripts/research/governance/pr_flow.py`
- Test: `scripts/research/governance/tests/test_pr_flow.py`

- [ ] **Step 1: 写失败测试：触发 Codex 后自动写入当前 head 通过证据**

新增测试：

```python
def test_ready_auto_records_current_head_codex_completion_comment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True)
    runner.api_issue_comments.append(
        {
            "id": 99,
            "user": {"login": "chatgpt-codex-connector"},
            "body": "Codex Review: Didn't find any major issues.",
            "created_at": "2026-05-28T10:00:00Z",
            "updated_at": "2026-05-28T10:00:00Z",
            "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-99",
        }
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == 0
    payload = json.loads((tmp_path / ".local/ai-review/latest.json").read_text(encoding="utf-8"))
    assert payload["official_codex_review"]["evidence"][0].endswith("#issuecomment-99")
    assert "## Codex Code Review" in runner.edited_bodies[-1]
```

预期：失败，直到 `ready()` 能自动写证据并重新同步 PR body。

- [ ] **Step 2: 实现 current-head Codex evidence 查找**

在 `pr_flow.py` 保留当前 head 校验，逻辑必须同时满足：
- comment/review 来自 `chatgpt-codex-connector` 或 bot。
- PR URL 匹配当前 PR。
- head SHA 匹配当前 head 或 trigger time 晚于当前 head 创建时间。
- 内容是无 P0/P1 的通过结果。
- 不存在当前 head 未解决 P0/P1 thread。

核心接口：

```python
def _current_head_codex_review_evidence(
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
) -> str | None:
    evidence = _current_head_codex_review_evidence_from_reviews(
        pr_url=pr_url,
        head_sha=head_sha,
        root=root,
        runner=runner,
    )
    if evidence:
        return evidence
    return _current_head_codex_review_evidence_from_comments(
        pr_url=pr_url,
        head_sha=head_sha,
        root=root,
        runner=runner,
    )
```

- [ ] **Step 3: 自动写入 evidence**

实现：

```python
def _payload_with_official_codex_review_evidence(
    payload: dict[str, Any],
    *,
    evidence: str,
) -> dict[str, Any]:
    updated = dict(payload)
    updated["official_codex_review"] = {
        "reviewer": "Codex",
        "trigger": "@codex review",
        "conclusion": "通过",
        "blocking_issues": "无",
        "evidence": [
            evidence,
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\.githooks\\run-python.ps1 -m scripts.research.governance gate",
        ],
    }
    return updated
```

注意：这里记录真实 evidence，不替代本地 AI review。

- [ ] **Step 4: 自动重渲染 PR body**

在写入 `.local/ai-review/latest.json` 后调用现有 `sync()`：

```python
code = sync(repo_root=repo_root, title=title, runner=runner)
if code != 0:
    return code
```

`sync()` 继续负责：
- `ai_review_gate markdown`
- `ai_review_gate scope`
- `ai_review_gate pr-body`
- `gh pr edit --body-file`

- [ ] **Step 5: 跑测试**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py::test_ready_auto_records_current_head_codex_completion_comment -q
```

预期：通过。

## Task 3: Codex P0/P1 和 unresolved thread 阻断

**Files:**
- Modify: `scripts/research/governance/pr_flow.py`
- Test: `scripts/research/governance/tests/test_pr_flow.py`

- [ ] **Step 1: 写失败测试：Codex P1 不自动推进**

新增测试：

```python
def test_ready_stops_when_codex_reports_blocking_finding(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True)
    runner.api_issue_comments.append(
        {
            "id": 100,
            "user": {"login": "chatgpt-codex-connector"},
            "body": "P1 Badge: required check can be bypassed.",
            "created_at": "2026-05-28T10:00:00Z",
            "updated_at": "2026-05-28T10:00:00Z",
            "html_url": "https://github.com/liuli195/Quant-Trading/pull/7#issuecomment-100",
        }
    )
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.REPLY_OR_FIX_REQUIRED_EXIT_CODE
    assert "REPLY_OR_FIX_REQUIRED" in capsys.readouterr().err
```

- [ ] **Step 2: 实现阻断分类**

新增：

```python
def _current_head_codex_blocking_findings(
    *,
    pr_url: str,
    head_sha: str,
    root: Path,
    runner: Runner,
) -> tuple[str, ...]:
    comments = _current_head_codex_issue_comments(
        pr_url=pr_url,
        head_sha=head_sha,
        root=root,
        runner=runner,
    )
    review_comments = _current_head_codex_review_comments(
        pr_url=pr_url,
        head_sha=head_sha,
        root=root,
        runner=runner,
    )
    findings: list[str] = []
    for item in [*comments, *review_comments]:
        body = str(item.get("body") or "")
        if BLOCKING_CODEX_FINDING_PATTERN.search(body):
            findings.append(f"{_single_line_text(item.get('html_url'))} {_single_line_text(body)}")
    return tuple(findings)
```

返回内容示例：

```text
https://github.com/liuli195/Quant-Trading/pull/19#issuecomment-100 P1 Badge: required check can be bypassed.
```

- [ ] **Step 3: `ready()` 在发现阻断项时停止**

在等待 Codex 通过证据前先检查阻断项：

```python
blocking = _current_head_codex_blocking_findings(
    pr_url=pr_url,
    head_sha=head_sha,
    root=root,
    runner=runner,
)
if blocking:
    _print_state(
        "REPLY_OR_FIX_REQUIRED",
        "Codex review reported blocking current-head findings",
        details=blocking,
    )
    return REPLY_OR_FIX_REQUIRED_EXIT_CODE
```

- [ ] **Step 4: 跑测试**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py::test_ready_stops_when_codex_reports_blocking_finding -q
```

预期：通过。

## Task 4: required checks 等待去重和异常摘要

**Files:**
- Modify: `scripts/research/governance/pr_flow.py`
- Test: `scripts/research/governance/tests/test_pr_flow.py`

- [ ] **Step 1: 写测试：同名旧失败、新成功时通过**

```python
def test_wait_uses_latest_duplicate_required_check_result(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DuplicateRequiredChecksRunner()

    code = pr_flow.wait(repo_root=tmp_path, pr="7", runner=runner)

    assert code == 0
    assert "required checks passed" in capsys.readouterr().out
```

- [ ] **Step 2: 写测试：同名旧成功、新失败时阻断**

```python
def test_wait_blocks_latest_duplicate_required_check_failure(
    tmp_path: Path,
    capsys,
) -> None:
    runner = DuplicateRequiredChecksRunner(
        [
            {
                "name": "pr-review-evidence",
                "state": "FAILURE",
                "bucket": "fail",
                "workflow": "Research Governance",
                "link": "https://github.com/o/r/actions/runs/20/job/200",
            },
            {
                "name": "pr-review-evidence",
                "state": "SUCCESS",
                "bucket": "pass",
                "workflow": "Research Governance",
                "link": "https://github.com/o/r/actions/runs/10/job/100",
            },
        ]
    )

    code = pr_flow.wait(repo_root=tmp_path, pr="7", runner=runner)

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "Research Governance / pr-review-evidence" in capsys.readouterr().err
```

- [ ] **Step 3: 实现 JSON 去重**

使用：

```python
CHECKS_JSON_FIELDS = "name,state,bucket,link,workflow"
ACTIONS_CHECK_URL_PATTERN = re.compile(r"/actions/runs/(?P<run_id>\d+)/job/(?P<job_id>\d+)")
```

按 `(workflow, name)` 分组，优先取最大 `run_id/job_id`。非 Actions check 使用返回顺序作为低优先级。

- [ ] **Step 4: 失败时输出异常状态**

将纯文本：

```text
failing required checks:
```

升级为：

```text
EXCEPTION_REQUIRED: failing required checks
- Research Governance / pr-review-evidence https://github.com/liuli195/Quant-Trading/actions/runs/26566295200/job/78261721930
```

成功仍输出：

```text
required checks passed
```

- [ ] **Step 5: 跑测试**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py -q
```

预期：全部通过。

## Task 5: head 变化和超时保护

**Files:**
- Modify: `scripts/research/governance/pr_flow.py`
- Test: `scripts/research/governance/tests/test_pr_flow.py`

- [ ] **Step 1: 写失败测试：等待期间 PR head 变化**

```python
def test_ready_stops_when_pr_head_changes_during_codex_wait(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    _write_valid_report(
        tmp_path,
        risk_level="high",
        requires_official=True,
        changed_files=["scripts/research/governance/pr_flow.py"],
    )
    runner = FakeRunner(existing_pr=True)
    runner.pr_head_sha_after_wait = "2" * 40
    monkeypatch.setattr(pr_flow, "prepare", lambda **_kwargs: 0)

    code = pr_flow.ready(
        repo_root=tmp_path,
        title="治理自动化",
        runner=runner,
        codex_review_timeout_seconds=0,
        codex_review_poll_seconds=0,
    )

    assert code == pr_flow.EXCEPTION_REQUIRED_EXIT_CODE
    assert "head changed" in capsys.readouterr().err
```

- [ ] **Step 2: 每轮轮询校验 head**

在 `_wait_for_current_head_codex_review_evidence()` 每轮读取 PR metadata：

```python
metadata = _current_pr_metadata(root, runner)
current_head = _single_line_text(metadata.get("headRefOid") or metadata.get("headRefOid"))
if current_head and current_head != head_sha:
    _print_state(
        "EXCEPTION_REQUIRED",
        "head changed during Codex review wait",
        details=[f"expected={head_sha}", f"actual={current_head}"],
    )
    return None
```

- [ ] **Step 3: 超时保持可续跑**

超时返回：

```text
EXCEPTION_REQUIRED: official Codex review still pending
- rerun: make pr-ready TITLE="<same title>"
```

退出码使用 `CODEX_REVIEW_PENDING_EXIT_CODE` 或 `EXCEPTION_REQUIRED_EXIT_CODE` 二选一。推荐保留 `CODEX_REVIEW_PENDING_EXIT_CODE` 兼容现有流程，但输出状态名。

- [ ] **Step 4: 跑测试**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py -q
```

预期：全部通过。

## Task 6: 规则文档同步

**Files:**
- Modify: `docs/rules/pr-workflow.md`
- Modify: `docs/rules/review-guidelines.md`
- Modify: `docs/rules/governance.md`

- [ ] **Step 1: 更新 `docs/rules/pr-workflow.md`**

加入精简描述：

```markdown
- `pr-ready` / `pr_flow ready` 是一键 PR 状态机：准备本地 evidence、同步 PR、触发必要的 `@codex review`、在当前 head 的官方 review 无 P0/P1 时自动记录证据并继续等待 required checks。
- `pr_flow` 不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review；缺失本地 review evidence 时必须停止并进入任务分发。
- 只有异常处理、任务分发、问题回复三类情况需要人工或 agents 介入。
```

- [ ] **Step 2: 更新 `docs/rules/review-guidelines.md`**

加入：

```markdown
- 官方 Codex Review 无 P0/P1 且匹配当前 head 时，`pr_flow` 可以自动把真实 review/comment 链接写入 PR body evidence。
- 自动写入不等于跳过 review；证据必须来自当前 PR、当前 head、当前 trigger 之后的 Codex 结果。
```

- [ ] **Step 3: 更新 `docs/rules/governance.md`**

加入：

```markdown
- `Codex Review Monitor` success 可作为 `pr_flow` 自动采集官方 Codex 通过证据的信号之一，但不能替代 PR body 的 `Codex Code Review 结论`。
```

- [ ] **Step 4: 跑 pathref / governance**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate
```

预期：

```json
{
  "ok": true
}
```

## Task 7: 端到端验证

**Files:**
- Modify: none

- [ ] **Step 1: 跑治理测试**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_pr_flow.py scripts\research\governance\tests\test_ai_review_gate.py -q
```

预期：全部通过。

- [ ] **Step 2: 跑静态检查**

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\research\governance\pr_flow.py
.\.venv\Scripts\python.exe -m ruff check scripts\research\governance
.\.venv\Scripts\python.exe -m mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports scripts\research\governance
.\.venv\Scripts\python.exe -m bandit -q -r scripts\research\governance -x scripts\research\governance\tests -s B310,B404,B603,B607
```

预期：
- `py_compile` 无输出且退出 0。
- `ruff` 输出 `All checks passed!`。
- `mypy` 输出 `Success: no issues found`。
- `bandit` 退出 0。

- [ ] **Step 3: 跑完整治理门禁**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate
```

预期：

```json
{
  "ok": true
}
```

- [ ] **Step 4: 真实 PR dry run**

在一个已有 PR 分支上运行：

```powershell
make pr-ready TITLE="<PR标题>"
```

预期无问题路径：

```text
required checks passed
```

预期需要介入路径只出现以下状态之一：

```text
DISPATCH_REQUIRED
REPLY_OR_FIX_REQUIRED
EXCEPTION_REQUIRED
```

## Execution Handoff

执行时优先使用 `superpowers:subagent-driven-development`：每个 task 一个独立 worker，主会话负责 review、集成、跑验证。若当前分支已有未提交代码，执行前先确认哪些改动属于当前任务，避免覆盖用户或其他 agent 的工作。
