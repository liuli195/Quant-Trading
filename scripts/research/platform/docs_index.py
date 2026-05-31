"""Markdown report indexing and evidence-link helpers."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_ROOT_PATTERNS = (
    "strategies/*/reports/**/*.md",
    "strategies/*/backtest_runs/*/report/*.md",
    "strategies/*/test_batches/*/report/*.md",
    "docs/**/*.md",
)
PATHREF_RE = re.compile(r"<!--\s*pathref:\s*(?P<pathref>[^>]+?)\s*-->")
DATE_RE = re.compile(r"(?P<date>20\d{2}-\d{2}-\d{2})")
TAGS_RE = re.compile(r"^\s*tags\s*:\s*(?P<tags>.+)$", re.IGNORECASE | re.MULTILINE)
ADR_FILE_RE = re.compile(r"^(?P<number>\d{4})-.+\.md$")


@dataclass(frozen=True)
class ReportRecord:
    """One indexed Markdown document."""

    path: str
    title: str
    category: str
    strategy: str | None
    date: str | None
    tags: tuple[str, ...]
    pathrefs: tuple[str, ...]
    updated_at: str


class DocsIndexer:
    """Build a lightweight repository Markdown index."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()

    def scan(self) -> list[ReportRecord]:
        records: dict[str, ReportRecord] = {}
        for pattern in REPORT_ROOT_PATTERNS:
            for path in self.repo_root.glob(pattern):
                if not path.is_file():
                    continue
                rel = path.relative_to(self.repo_root).as_posix()
                if "/__pycache__/" in rel:
                    continue
                if rel.startswith("docs/indexes/"):
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                record = ReportRecord(
                    path=rel,
                    title=_first_heading(text) or path.stem,
                    category=_category_for(rel),
                    strategy=_strategy_for(rel),
                    date=_date_for(text, rel),
                    tags=_tags_for(text),
                    pathrefs=tuple(match.group("pathref").strip() for match in PATHREF_RE.finditer(text)),
                    updated_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                )
                records[rel] = record
        return [records[key] for key in sorted(records)]

    def write(self, output_dir: str | Path = "docs/indexes") -> dict[str, Any]:
        if scan_adr_records(self.repo_root):
            write_adr_index(self.repo_root)
        records = self.scan()
        docs = [record for record in records if record.category == "docs"]
        reports = [record for record in records if record.category != "docs"]
        out_dir = self.repo_root / output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload = _catalog_payload(records, "documents", generated_at)
        docs_payload = _catalog_payload(docs, "docs", generated_at)
        reports_payload = _catalog_payload(reports, "reports", generated_at)
        datasets_payload = self._datasets_catalog(generated_at)
        variants_payload = self._variants_catalog(generated_at)

        (out_dir / "docs_catalog.json").write_text(
            json.dumps(docs_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "reports_catalog.json").write_text(
            json.dumps(reports_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "datasets_catalog.json").write_text(
            json.dumps(datasets_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / "variants_catalog.json").write_text(
            json.dumps(variants_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Backwards-compatible aliases for older scripts and existing docs.
        (out_dir / "reports.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "reports.md").write_text(_render_reports_markdown(records), encoding="utf-8")
        (out_dir / "reports_catalog.md").write_text(_render_reports_markdown(reports), encoding="utf-8")
        return payload

    def stale_entries(self, index_path: str | Path = "docs/indexes/reports_catalog.json") -> list[str]:
        """Return indexed report paths that no longer exist on disk."""

        path = self.repo_root / index_path
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return sorted(
            row["path"]
            for row in payload.get("reports", [])
            if not (self.repo_root / row["path"]).is_file()
        )

    def _datasets_catalog(self, generated_at: str) -> dict[str, Any]:
        source = self.repo_root / "research_datasets" / "catalog.json"
        datasets: list[dict[str, Any]] = []
        if source.is_file():
            datasets = json.loads(source.read_text(encoding="utf-8"))
        return {
            "schema_version": 1,
            "generated_at": generated_at,
            "count": len(datasets),
            "datasets": datasets,
        }

    def _variants_catalog(self, generated_at: str) -> dict[str, Any]:
        variants: list[dict[str, Any]] = []
        for index_path in sorted(self.repo_root.glob("strategies/*/variants/variants.json")):
            strategy = index_path.parts[-3]
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            for row in payload.get("variants", []):
                variants.append({"strategy": strategy, **row})
        return {
            "schema_version": 1,
            "generated_at": generated_at,
            "count": len(variants),
            "variants": variants,
        }


class ReportRegistry:
    """Read the generated report index."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        index_path: str | Path = "docs/indexes/reports_catalog.json",
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.index_path = self.repo_root / index_path

    def load(self) -> dict[str, Any]:
        path = self.index_path
        if not path.is_file() and path.name == "reports_catalog.json":
            legacy = path.with_name("reports.json")
            if legacy.is_file():
                path = legacy
        if not path.is_file():
            raise FileNotFoundError(f"report index not found: {self.index_path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def find_by_strategy(self, strategy: str) -> list[dict[str, Any]]:
        payload = self.load()
        return [row for row in payload.get("reports", []) if row.get("strategy") == strategy]


class EvidenceLinker:
    """Build small, machine-checkable evidence blocks for reports."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()

    def render_block(self, evidence: dict[str, str]) -> str:
        lines = ["## 证据链接", ""]
        for label, rel_path in evidence.items():
            target = (self.repo_root / rel_path).resolve()
            if not target.exists():
                raise FileNotFoundError(f"evidence path not found: {rel_path}")
            lines.append(f"- **{label}**: [{target.name}]({rel_path}) <!-- pathref: repo/{rel_path} -->")
        lines.append("")
        return "\n".join(lines)


class PathrefValidator:
    """Run the repository pathref checker without rewriting files."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()

    def check(self, *, strict: bool = False) -> int:
        command = [sys.executable, "-m", "scripts.tools.path_tools.refactor", "check"]
        if strict:
            command.append("--strict")
        result = subprocess.run(command, cwd=self.repo_root, check=False)
        return int(result.returncode)


@dataclass(frozen=True)
class AdrRecord:
    """One numbered ADR document."""

    number: str
    filename: str
    title: str


def scan_adr_records(repo_root: str | Path = ".") -> list[AdrRecord]:
    root = Path(repo_root).resolve()
    adr_root = root / "docs" / "adr"
    records: list[AdrRecord] = []
    if not adr_root.is_dir():
        return records
    for path in sorted(adr_root.glob("*.md")):
        match = ADR_FILE_RE.match(path.name)
        if not match:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        records.append(
            AdrRecord(
                number=match.group("number"),
                filename=path.name,
                title=_adr_title(_first_heading(text), path.stem),
            )
        )
    return records


def render_adr_index(repo_root: str | Path = ".") -> str:
    lines = [
        "# ADR 索引",
        "",
        "本目录记录重大规则、架构和治理决策。阅读当前入口规则时优先看状态仍有效或被后续 ADR 更新的记录。",
        "",
        "| ADR | 标题 |",
        "| --- | --- |",
    ]
    for record in scan_adr_records(repo_root):
        lines.append(
            f"| [{record.number}]({record.filename}) <!-- pathref: docs/adr/{record.filename} --> | {record.title} |"
        )
    return "\n".join(lines) + "\n"


def write_adr_index(
    repo_root: str | Path = ".",
    index_path: str | Path = "docs/adr/index.md",
) -> Path:
    root = Path(repo_root).resolve()
    path = root / index_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_adr_index(root), encoding="utf-8")
    return path


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _adr_title(heading: str, fallback: str) -> str:
    if not heading:
        return fallback
    match = re.match(r"ADR\s+\d{4}\s*[:：]\s*(?P<title>.+)", heading)
    if match:
        return match.group("title").strip()
    return heading


def _date_for(text: str, path: str) -> str | None:
    match = DATE_RE.search(text) or DATE_RE.search(path)
    return match.group("date") if match else None


def _tags_for(text: str) -> tuple[str, ...]:
    match = TAGS_RE.search(text)
    if not match:
        return ()
    return tuple(tag.strip() for tag in re.split(r"[,， ]+", match.group("tags")) if tag.strip())


def _catalog_payload(records: list[ReportRecord], catalog_type: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "catalog_type": catalog_type,
        "generated_at": generated_at,
        "count": len(records),
        "reports": [asdict(record) for record in records],
    }


def _strategy_for(path: str) -> str | None:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] == "strategies":
        return parts[1]
    return None


def _category_for(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/backtest_runs/" in normalized:
        return "backtest_run"
    if "/test_batches/" in normalized:
        return "test_batch"
    if "/reports/research/" in normalized:
        return "research"
    if "/reports/design/" in normalized:
        return "design"
    if normalized.startswith("docs/"):
        return "docs"
    return "report"


def _render_reports_markdown(records: list[ReportRecord]) -> str:
    lines = [
        "# 报告索引",
        "",
        "| category | strategy | title | path | pathrefs |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for record in records:
        lines.append(
            f"| {record.category} | {record.strategy or ''} | {record.title} | "
            f"`{record.path}` | {len(record.pathrefs)} |"
        )
    lines.append("")
    return "\n".join(lines)
