"""Filesystem layout helpers shared by local research projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResearchProjectLayout:
    """Stable directory layout for one research project."""

    root: Path

    @classmethod
    def from_path(cls, path: str | Path) -> "ResearchProjectLayout":
        return cls(Path(path))

    @property
    def docs_dir(self) -> Path:
        return self.root / "docs"

    @property
    def raw_inputs_dir(self) -> Path:
        return self.root / "inputs" / "raw"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    def raw_input_path(self, filename: str) -> Path:
        return self.raw_inputs_dir / filename

    def run(self, run_id: str) -> "ResearchRunLayout":
        if not run_id.strip():
            raise ValueError("run_id must not be empty")
        return ResearchRunLayout(project_root=self.root, run_id=run_id)

    def ensure_project_dirs(self) -> None:
        for directory in (self.docs_dir, self.raw_inputs_dir, self.exports_dir, self.runs_dir):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ResearchRunLayout:
    """Directory layout for one persisted analysis run."""

    project_root: Path
    run_id: str

    @property
    def root(self) -> Path:
        return self.project_root / "runs" / self.run_id

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def tables_dir(self) -> Path:
        return self.root / "tables"

    @property
    def curves_dir(self) -> Path:
        return self.root / "curves"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def ensure_dirs(self) -> None:
        for directory in (self.reports_dir, self.tables_dir, self.curves_dir):
            directory.mkdir(parents=True, exist_ok=True)
