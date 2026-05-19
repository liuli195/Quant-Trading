## 改动目标

-

## 影响范围

-

## 规则同步

- [ ] 不涉及规则入口、Skill、README、workflow、registry、catalog 或 pathref
- [ ] 已同步 `CLAUDE.md`、`docs/rules/`、`docs/adr/`、Skill 或 README

## 已运行检查

- [ ] `.\.venv\Scripts\python.exe -m scripts.research.governance gate --skip-cli-help`
- [ ] `.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check`
- [ ] 相关 pytest / py_compile

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review 按 AGENTS.md 和 docs/rules/review-guidelines.md 审；逐条检查 docs/rules/*.md`
- 结论: 未执行
- 阻断问题: 未确认
- 关键证据:
  - Codex review 链接：https://github.com/<owner>/<repo>/pull/<number>#pullrequestreview-<id>
  - `.\.venv\Scripts\python.exe -m scripts.research.governance gate`

## waiver

- [ ] 不需要 waiver
- [ ] 已在 `docs/exceptions/active-waivers.yaml` 登记 owner、批准人、过期时间和迁移计划

## 证据

- 报告、manifest、run、catalog 或其他证据链接：
