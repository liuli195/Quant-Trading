# 治理审计

`governance/` 用来防止本地研究平台继续扩展后发生入口漂移、文档漂移和目录漂移。

## 命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

`gate` is the enforced entry for hooks and CI. It runs governance audit plus
the pathref checker. The tracked hooks are `.githooks/pre-commit` and
`.githooks/pre-push`; enable them with:

```powershell
git config core.hooksPath .githooks
```

`.githooks/pre-push` calls:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.branch_protection pre-push
```

It blocks direct pushes to `main` / `master` when remote rulesets are unavailable.

审计范围：

- 仓库级规则文档 [docs/rules/index.md](../../../docs/rules/index.md) <!-- pathref: docs/rules/index.md --> 是否存在，ADR 目录 [docs/adr](../../../docs/adr) <!-- pathref: docs/adr --> 是否连续编号。
- `.githooks/pre-push` 是否仍调用代码化主干保护门禁。
- `CODEOWNERS` 是否覆盖关键治理路径，`.github/pull_request_template.md` 是否包含规则同步、检查、waiver 和证据项。
- `docs/exceptions/active-waivers.yaml` 中的 waiver 是否有 owner、批准人、过期时间和迁移计划。
- 工具是否登记在中央 registry。
- README、文档入口、测试文件是否存在。
- 主要 CLI 的 `--help` 是否可运行。
- `CLAUDE.md` 与 `jq-research` Skill 是否同步到新入口。
- `research_datasets/catalog.json` 是否和目录一致。
- `docs/indexes/docs_catalog.json`、`reports_catalog.json`、`datasets_catalog.json`、`variants_catalog.json` 是否存在，并和实际报告文件一致。
- `scripts/research/workflows/templates/*.json` 是否符合模板 schema。
- Markdown `pathref` 是否通过校验。

开发单测可用：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit --skip-cli-help --skip-pathrefs
```
