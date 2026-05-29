"""Central registry for local research tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .schemas import ToolDefinition


WINDOWS_PYTHON_CLI = r".\.venv\Scripts\python.exe"
POSIX_PYTHON_CLI = ".venv/bin/python"
PYTHON_CLI = WINDOWS_PYTHON_CLI


LAYER_ORDER = (
    "strategy_library",
    "data_center",
    "workflow_orchestration",
    "research_toolkit",
    "docs_reports",
    "governance",
)

LAYER_TITLES = {
    "strategy_library": "第一层：策略库",
    "data_center": "第二层：数据中心",
    "workflow_orchestration": "第三层：流程编排层",
    "research_toolkit": "第四层：研究工具库",
    "docs_reports": "第五层：文档报告库",
    "governance": "横向治理：注册与审计",
}

LAYER_DESCRIPTIONS = {
    "strategy_library": "策略结构、变体定义、物化和合并计划。",
    "data_center": "本地不可变数据集、快照、目录和数据导入。",
    "workflow_orchestration": "研究项目生命周期、流程模板、插件调度和聚宽自动化。",
    "research_toolkit": "可复用研究计算库和专题研究工具。",
    "docs_reports": "报告、索引、证据链接和文档产出。",
    "governance": "跨层注册、审计、路径引用和提交门禁。",
}

LAYER_FILENAMES = {
    "strategy_library": "strategy_library.md",
    "data_center": "data_center.md",
    "workflow_orchestration": "workflow_orchestration.md",
    "research_toolkit": "research_toolkit.md",
    "docs_reports": "docs_reports.md",
    "governance": "governance.md",
}


def _cli(module: str, suffix: str = "") -> str:
    command = f"{PYTHON_CLI} -m {module}"
    return f"{command} {suffix}".strip()


def _posix_cli(command: str | None) -> str:
    if not command:
        return ""
    return command.replace(
        WINDOWS_PYTHON_CLI,
        POSIX_PYTHON_CLI,
        1,
    )


def _tool_record(tool: ToolDefinition) -> dict[str, Any]:
    record = dict(tool.__dict__)
    if tool.kind == "cli":
        record["cli_windows"] = tool.cli or ""
        record["cli_posix"] = _posix_cli(tool.cli)
    else:
        record["cli_windows"] = ""
        record["cli_posix"] = ""
    return record


def _markdown_values(values: tuple[str, ...]) -> str:
    return "<br>".join(f"`{value}`" for value in values)


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        tool_id="research.cli",
        layer="workflow_orchestration",
        library="scripts.research",
        kind="cli",
        entry_module="scripts.research.cli",
        cli=_cli("scripts.research.cli"),
        description="Local-first research project lifecycle CLI.",
        readme_path="scripts/research/README.md",
        docs_path="docs/guides/research-workflow.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("project.json", "dataset snapshots", "raw research exports"),
        outputs=("runs/<run_id>/manifest.json", "candidate funnel tables", "cloud_handoff.json"),
    ),
    ToolDefinition(
        tool_id="research.datasets",
        layer="data_center",
        library="scripts.research",
        kind="cli",
        entry_module="scripts.research.datasets",
        cli=_cli("scripts.research.datasets"),
        description="Immutable dataset snapshot import and inspection CLI.",
        readme_path="scripts/research/README.md",
        docs_path="research_datasets/README.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("JoinQuant price JSON", "audit_log.jsonl", "backtest_runs/<run_id>"),
        outputs=("research_datasets/<dataset_id>/<snapshot_id>", "catalog.json", "catalog.md"),
    ),
    ToolDefinition(
        tool_id="research.docs_index",
        layer="docs_reports",
        library="scripts.research",
        kind="cli",
        entry_module="scripts.research.docs",
        cli=_cli("scripts.research.docs"),
        description="Markdown report index, report registry and evidence-link helpers.",
        readme_path="scripts/research/platform/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("Markdown reports", "pathref comments"),
        outputs=(
            "docs/indexes/docs_catalog.json",
            "docs/indexes/reports_catalog.json",
            "docs/indexes/datasets_catalog.json",
            "docs/indexes/variants_catalog.json",
        ),
    ),
    ToolDefinition(
        tool_id="research.strategy_variants",
        layer="strategy_library",
        library="scripts.research",
        kind="cli",
        entry_module="scripts.research.variants",
        cli=_cli("scripts.research.variants"),
        description="Variant registry, materializer, branch plan and merge plan helpers.",
        readme_path="scripts/research/platform/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("strategy.json", "variants/<variant_id>.json"),
        outputs=("variants/variants.json", ".local/research-materialized"),
    ),
    ToolDefinition(
        tool_id="research.registry",
        layer="governance",
        library="scripts.research.registry",
        kind="cli",
        entry_module="scripts.research.registry.tool_registry",
        cli=_cli("scripts.research.registry.tool_registry"),
        description="Central research tool registry.",
        readme_path="scripts/research/registry/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/registry/tests/test_registry.py",),
        inputs=("ToolDefinition entries",),
        outputs=("registry validation report",),
    ),
    ToolDefinition(
        tool_id="research.governance",
        layer="governance",
        library="scripts.research.governance",
        kind="cli",
        entry_module="scripts.research.governance",
        cli=_cli("scripts.research.governance", "audit"),
        description="Governance audit and gate for registry, docs, catalogs, pathrefs and tests.",
        readme_path="scripts/research/governance/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/governance/tests/test_governance.py",),
        inputs=("tool registry", "CLAUDE.md", ".claude/skills", "catalogs"),
        outputs=("audit result JSON/stdout", "gate result JSON/stdout"),
    ),
    ToolDefinition(
        tool_id="research.governance_verify",
        layer="governance",
        library="scripts.research.governance",
        kind="cli",
        entry_module="scripts.research.governance",
        cli=_cli("scripts.research.governance", "verify"),
        description="Affected fast/explain verification and full governance verification.",
        readme_path="scripts/research/governance/README.md",
        docs_path="docs/rules/governance.md",
        tests=("scripts/research/governance/tests/test_verify.py",),
        inputs=("changed files", "staged diff", ".local/ai-review/latest.json"),
        outputs=("checked/skipped/cache-hit/full-not-run verification report",),
    ),
    ToolDefinition(
        tool_id="research.pr_flow",
        layer="governance",
        library="scripts.research.governance",
        kind="cli",
        entry_module="scripts.research.governance.pr_flow",
        cli=_cli("scripts.research.governance.pr_flow", "ready"),
        description="Local PR preparation, draft PR synchronization, Codex review trigger, diagnostics and required-check waiting.",
        readme_path="scripts/research/governance/README.md",
        docs_path="docs/rules/pr-workflow.md",
        tests=("scripts/research/governance/tests/test_pr_flow.py",),
        inputs=(".local/ai-review/latest.json", "git diff", "gh authenticated session"),
        outputs=(".local/ai-review/pr-body.md", "draft pull request", "required check summary"),
    ),
    ToolDefinition(
        tool_id="research.workflow_templates",
        layer="workflow_orchestration",
        library="scripts.research.workflows",
        kind="workflow_template",
        entry_module="scripts.research.platform.workflows",
        description="Schema validation for reusable local research workflow templates.",
        readme_path="scripts/research/workflows/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("scripts/research/workflows/templates/*.json",),
        outputs=("validated WorkflowTemplate objects",),
    ),
    ToolDefinition(
        tool_id="research.platform.plugins",
        layer="workflow_orchestration",
        library="scripts.research.platform",
        kind="library",
        entry_module="scripts.research.platform.plugins",
        description="Built-in research plugins and plugin registry.",
        readme_path="scripts/research/platform/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("project.json", "ResearchRunContext", "feature bundles"),
        outputs=("fast/full result tables", "cloud handoff payloads"),
    ),
    ToolDefinition(
        tool_id="research.core.metrics",
        layer="research_toolkit",
        library="scripts.research.research_core",
        kind="library",
        entry_module="scripts.research.research_core.metrics",
        description="Shared performance metrics.",
        readme_path="scripts/research/research_core/README.md",
        tests=("scripts/research/research_core/tests/test_research_core.py",),
        inputs=("daily returns",),
        outputs=("annual return, drawdown, Sharpe, volatility, rolling/yearly metrics",),
    ),
    ToolDefinition(
        tool_id="research.core.robustness",
        layer="research_toolkit",
        library="scripts.research.research_core",
        kind="library",
        entry_module="scripts.research.research_core.robustness",
        description="Reusable robustness checks.",
        readme_path="scripts/research/research_core/README.md",
        tests=("scripts/research/research_core/tests/test_research_core.py",),
        inputs=("baseline returns", "variant returns"),
        outputs=("bootstrap, rolling win rate, yearly split",),
    ),
    ToolDefinition(
        tool_id="research.core.replay",
        layer="research_toolkit",
        library="scripts.research.research_core",
        kind="library",
        entry_module="scripts.research.research_core.replay",
        description="Standard replay adapter contract for local counterfactual research.",
        readme_path="scripts/research/research_core/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/research/research_core/tests/test_research_core.py",),
        inputs=("cloud baseline artifacts", "variant definitions"),
        outputs=("ReplayResult diagnostics and tables",),
    ),
    ToolDefinition(
        tool_id="research.core.data_io",
        layer="research_toolkit",
        library="scripts.research.research_core",
        kind="library",
        entry_module="scripts.research.research_core",
        description="Shared layout, price, calendar, audit and reporting helpers.",
        readme_path="scripts/research/research_core/README.md",
        tests=("scripts/research/research_core/tests/test_research_core.py",),
        inputs=("price bundles", "audit logs", "project paths"),
        outputs=("PriceFrames", "ResearchProjectLayout", "Markdown/JSON artifacts"),
    ),
    ToolDefinition(
        tool_id="research.etf_window",
        layer="research_toolkit",
        library="scripts.research.etf_window_research",
        kind="cli",
        entry_module="scripts.research.etf_window_research.cli",
        cli=_cli("scripts.research.etf_window_research.cli"),
        description="ETF factor/window heterogeneity local research workflow.",
        readme_path="scripts/research/etf_window_research/README.md",
        tests=("scripts/research/etf_window_research/tests/test_analysis.py",),
        inputs=("JoinQuant price exports", "audit logs"),
        outputs=("window grids", "holdout validation", "research reports"),
    ),
    ToolDefinition(
        tool_id="research.momentum_tilt",
        layer="research_toolkit",
        library="scripts.research.momentum_tilt_research",
        kind="cli",
        entry_module="scripts.research.momentum_tilt_research",
        cli=_cli("scripts.research.momentum_tilt_research"),
        description="Momentum tilt replay calibration, local analysis and cloud robustness report workflow.",
        readme_path="scripts/research/momentum_tilt_research/README.md",
        tests=("scripts/research/momentum_tilt_research/tests/test_analysis.py",),
        inputs=("price bundle", "audit logs", "baseline returns", "cloud run summaries"),
        outputs=("calibration reports", "candidate scans", "cloud robustness reports"),
    ),
    ToolDefinition(
        tool_id="research.execution_timing",
        layer="research_toolkit",
        library="scripts.research.execution_timing_research",
        kind="cli",
        entry_module="scripts.research.execution_timing_research.cli",
        cli=_cli("scripts.research.execution_timing_research.cli"),
        description="Execution timing local impact study workflow.",
        readme_path="scripts/research/execution_timing_research/README.md",
        tests=("scripts/research/execution_timing_research/tests/test_analysis.py",),
        inputs=("price bundle with open/close", "audit logs"),
        outputs=("timing path compare tables", "signal shift reports", "local decision report"),
    ),
    ToolDefinition(
        tool_id="research.portfolio_volatility",
        layer="research_toolkit",
        library="scripts.research.portfolio_volatility_research",
        kind="library",
        entry_module="scripts.research.portfolio_volatility_research",
        description="Portfolio volatility scale domain builder and evaluator used by the portfolio_volatility plugin.",
        readme_path="scripts/research/portfolio_volatility_research/README.md",
        tests=("scripts/research/portfolio_volatility_research/tests/test_domain_builder.py",),
        inputs=("baseline audit logs", "price bundles", "scan domains"),
        outputs=("domain grids", "variant evaluation tables", "smoke/full reports"),
    ),
    ToolDefinition(
        tool_id="research.cash_decomposition",
        layer="research_toolkit",
        library="scripts.research.cash_decomposition",
        kind="library",
        entry_module="scripts.research.cash_decomposition.analysis",
        description="Cash utilization decomposition from registered audit datasets.",
        readme_path="scripts/research/cash_decomposition/README.md",
        tests=("scripts/research/platform/tests/test_platform.py",),
        inputs=("audit dataset snapshots",),
        outputs=("cash decomposition tables", "summary reports"),
    ),
    ToolDefinition(
        tool_id="tools.jq_automation",
        layer="workflow_orchestration",
        library="scripts.tools.jq_automation",
        kind="cli",
        entry_module="scripts.tools.jq_automation",
        cli=_cli("scripts.tools.jq_automation"),
        description="JoinQuant cloud compile/upload/run/fetch/batch/AB automation.",
        readme_path="scripts/tools/jq_automation/README.md",
        docs_path="docs/architecture/research-platform-architecture.md",
        tests=("scripts/tools/jq_automation/tests/test_core.py", "scripts/tools/jq_automation/tests/test_ab.py"),
        inputs=("scenario.json", "AB config", "browser profile", "JoinQuant run pages"),
        outputs=("backtest_runs/<run_id>", "test_batches/<batch_id>", "research_datasets snapshots"),
    ),
    ToolDefinition(
        tool_id="tools.path_tools.refactor",
        layer="governance",
        library="scripts.tools.path_tools",
        kind="cli",
        entry_module="scripts.tools.path_tools.refactor",
        cli=_cli("scripts.tools.path_tools.refactor"),
        description="Markdown pathref checking and reference rewrite helpers.",
        readme_path="scripts/tools/path_tools/README.md",
        tests=("scripts/research/governance/tests/test_governance.py",),
        inputs=("Markdown pathrefs", "move maps"),
        outputs=("pathref validation result", "rewritten references"),
    ),
    ToolDefinition(
        tool_id="tools.path_tools.aliases",
        layer="governance",
        library="scripts.tools.path_tools",
        kind="cli",
        entry_module="scripts.tools.path_tools.aliases",
        cli=_cli("scripts.tools.path_tools.aliases"),
        description="Repository path alias resolver.",
        readme_path="scripts/tools/path_tools/README.md",
        tests=("scripts/research/governance/tests/test_governance.py",),
        inputs=("path_aliases.json", "alias variables"),
        outputs=("resolved repository paths",),
    ),
)


class ToolRegistry:
    """In-memory registry with validation helpers."""

    def __init__(self, tools: tuple[ToolDefinition, ...] = TOOL_DEFINITIONS) -> None:
        self.tools = tools

    def list(self) -> list[dict[str, Any]]:
        return [_tool_record(tool) for tool in self.tools]

    def by_library(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tool in self.tools:
            grouped.setdefault(tool.library, []).append(_tool_record(tool))
        return {library: grouped[library] for library in sorted(grouped)}

    def by_layer(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tool in self.tools:
            grouped.setdefault(tool.layer, []).append(_tool_record(tool))
        ordered_layers = [layer for layer in LAYER_ORDER if layer in grouped]
        ordered_layers.extend(sorted(set(grouped) - set(ordered_layers)))
        return {
            layer: sorted(grouped[layer], key=lambda item: (item["library"], item["tool_id"]))
            for layer in ordered_layers
        }

    def get(self, tool_id: str) -> ToolDefinition:
        for tool in self.tools:
            if tool.tool_id == tool_id:
                return tool
        raise KeyError(f"unknown tool_id: {tool_id}")

    def validate(self, repo_root: str | Path = ".") -> list[str]:
        root = Path(repo_root)
        errors: list[str] = []
        seen: set[str] = set()
        for tool in self.tools:
            errors.extend(tool.validate_schema())
            if tool.tool_id in seen:
                errors.append(f"duplicate tool_id: {tool.tool_id}")
            seen.add(tool.tool_id)
            if tool.kind == "cli":
                cli_windows = tool.cli or ""
                cli_posix = _posix_cli(tool.cli)
                if not cli_windows.startswith(f"{WINDOWS_PYTHON_CLI} -m "):
                    errors.append(
                        f"{tool.tool_id}: cli_windows must use {WINDOWS_PYTHON_CLI}"
                    )
                if not cli_posix.startswith(f"{POSIX_PYTHON_CLI} -m "):
                    errors.append(
                        f"{tool.tool_id}: cli_posix must use {POSIX_PYTHON_CLI}"
                    )
            for label, rel_path in (("README", tool.readme_path), ("docs", tool.docs_path)):
                if rel_path and not (root / rel_path).is_file():
                    errors.append(f"{tool.tool_id}: missing {label}: {rel_path}")
            for test_path in tool.tests:
                if not (root / test_path).is_file():
                    errors.append(f"{tool.tool_id}: missing test: {test_path}")
        return errors

    def to_markdown(self) -> str:
        lines = [
            "# Research Tool Registry",
            "",
            "| library | tool_id | owner | lifecycle | layer | kind | cli_windows | cli_posix | README | tests |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |",
        ]
        for tool in sorted(self.list(), key=lambda item: (item["library"], item["tool_id"])):
            lines.append(
                f"| `{tool['library']}` | `{tool['tool_id']}` | {tool['owner']} | "
                f"{tool['lifecycle']} | {tool['layer']} | {tool['kind']} | "
                f"`{tool['cli_windows']}` | `{tool['cli_posix']}` | "
                f"{tool['readme_path'] or ''} | {len(tool['tests'])} |"
            )
        lines.append("")
        return "\n".join(lines)

    def render_layer_docs(self) -> dict[str, str]:
        docs = {"README.md": self.layer_index_markdown()}
        for layer in LAYER_ORDER:
            docs[LAYER_FILENAMES[layer]] = self.layer_markdown(layer)
        return docs

    def write_layer_docs(self, output_dir: str | Path = "scripts/research/layers") -> list[Path]:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for filename, content in self.render_layer_docs().items():
            path = target / filename
            path.write_text(content, encoding="utf-8")
            written.append(path)
        return written

    def layer_index_markdown(self) -> str:
        grouped = self.by_layer()
        lines = [
            "# 本地研究平台工具分层索引",
            "",
            "本目录按平台5层核心整理工具视图，内容由工具注册表生成。",
            "",
            "生成命令：",
            f"- Windows：`{WINDOWS_PYTHON_CLI} -m scripts.research.registry.tool_registry write-layers`",
            f"- POSIX：`{POSIX_PYTHON_CLI} -m scripts.research.registry.tool_registry write-layers`",
            "",
            "| 层 | 文件 | 职责 | 工具数 |",
            "| --- | --- | --- | ---: |",
        ]
        for layer in LAYER_ORDER:
            filename = LAYER_FILENAMES[layer]
            lines.append(
                f"| {LAYER_TITLES[layer]} | [{filename}]({filename}) "
                f"<!-- pathref: scripts/research/layers/{filename} --> | "
                f"{LAYER_DESCRIPTIONS[layer]} | {len(grouped.get(layer, []))} |"
            )
        lines.extend(
            [
                "",
                "源码仍按库维护，分层目录只提供结构化索引，避免同一工具在物理目录和库目录之间重复实现。",
                "",
            ]
        )
        return "\n".join(lines)

    def layer_markdown(self, layer: str) -> str:
        tools = self.by_layer().get(layer, [])
        lines = [
            f"# {LAYER_TITLES.get(layer, layer)}",
            "",
            LAYER_DESCRIPTIONS.get(layer, ""),
            "",
            "本页由工具注册表生成，不手工维护。",
            "",
            "| tool_id | owner | lifecycle | library | kind | entry_module | cli_windows | cli_posix | README | tests | inputs | outputs |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for tool in tools:
            tests = _markdown_values(tuple(tool["tests"]))
            inputs = _markdown_values(tuple(tool["inputs"]))
            outputs = _markdown_values(tuple(tool["outputs"]))
            lines.append(
                f"| `{tool['tool_id']}` | {tool['owner']} | {tool['lifecycle']} | "
                f"`{tool['library']}` | `{tool['kind']}` | "
                f"`{tool['entry_module']}` | `{tool['cli_windows']}` | "
                f"`{tool['cli_posix']}` | "
                f"`{tool['readme_path'] or ''}` | {tests} | {inputs} | {outputs} |"
            )
        lines.append("")
        return "\n".join(lines)


def default_tool_registry() -> ToolRegistry:
    return ToolRegistry()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="print registered tools")
    list_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    list_parser.add_argument("--group-by-library", action="store_true")
    list_parser.add_argument("--group-by-layer", action="store_true")
    list_parser.set_defaults(func=_cmd_list)

    validate_parser = subparsers.add_parser("validate", help="validate registered tool metadata")
    validate_parser.add_argument("--repo-root", default=".")
    validate_parser.set_defaults(func=_cmd_validate)

    layers_parser = subparsers.add_parser("write-layers", help="generate 5-layer tool index docs")
    layers_parser.add_argument("--output-dir", default="scripts/research/layers")
    layers_parser.set_defaults(func=_cmd_write_layers)
    return parser


def _cmd_list(args: argparse.Namespace) -> int:
    registry = default_tool_registry()
    if args.format == "markdown":
        print(registry.to_markdown())
    elif args.group_by_layer:
        print(json.dumps(registry.by_layer(), ensure_ascii=False, indent=2))
    elif args.group_by_library:
        print(json.dumps(registry.by_library(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(registry.list(), ensure_ascii=False, indent=2))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    errors = default_tool_registry().validate(args.repo_root)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def _cmd_write_layers(args: argparse.Namespace) -> int:
    written = default_tool_registry().write_layer_docs(args.output_dir)
    print(json.dumps({"ok": True, "files": [str(path) for path in written]}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
