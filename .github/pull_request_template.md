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

## 评审治理 Agent 结论

- Agent: `pr-governance-review`
- 结论: 未执行
- 阻断问题: 未确认
- 关键证据:
  -

## waiver

- [ ] 不需要 waiver
- [ ] 已在 `docs/exceptions/active-waivers.yaml` 登记 owner、批准人、过期时间和迁移计划

## 证据

- 报告、manifest、run、catalog 或其他证据链接：
