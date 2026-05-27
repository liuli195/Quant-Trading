## 改动目标

-

## 影响范围

-

## 规则同步

- [ ] 不涉及规则入口、Skill、README、workflow、registry、catalog 或 pathref
- [ ] 已同步 `CLAUDE.md`、`docs/rules/`、`docs/adr/`、Skill 或 README

## 已运行检查

- [ ] `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate --skip-cli-help`
- [ ] `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor check`
- [ ] 相关 pytest / py_compile

## AI Review 风险分级

- 风险等级: low / high / unknown
- 是否需要官方 Codex Review: 是 / 否（低风险无需 / 用户授权跳过）
- high/unknown PR label: `ai-risk-review` / 不适用
- 官方 Codex Review 跳过授权: 无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex / claude；tool=codex-security / security-guidance；evidence=<安全 review 证据>
- 本地 AI review 模式: complete / partial
- 不完全 Review 模式授权: 无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>
- 子 agent 交叉评审: 填写 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` + `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`；reviewers: <规格评审子agent>, <代码质量评审子agent>；见 `.local/ai-review/latest.md`
- 任务分发说明: 填写已分发任务；未分发时写原因
- Codex Review Scope: `.local/ai-review/codex-review-scope.md`
- P0/P1 未关闭项: 无

## P2 保留项

- 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review`
- 标准触发评论: 按 `docs/rules/review-guidelines.md` 的固定模板填写当前 PR、当前 head SHA、Review Scope（可为空）和审查重点；不得写模板外文案。
- 结论: 未要求 / 未执行 / 通过
- 阻断问题: 无 / 未确认
- 关键证据:
  - Codex review 链接：
  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate`

## waiver

- [ ] 不需要 waiver
- [ ] 已在 `docs/exceptions/active-waivers.yaml` 登记 owner、批准人、过期时间和迁移计划

## 证据

- 报告、manifest、run、catalog 或其他证据链接：
