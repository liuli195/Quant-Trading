"""Workflow template loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkflowTemplateError(ValueError):
    """Raised when a workflow template is incomplete or invalid."""


@dataclass(frozen=True)
class WorkflowTemplate:
    """One reusable research workflow declaration."""

    schema_version: int
    template: str
    inputs: tuple[str, ...]
    stages: tuple[str, ...]
    outputs: tuple[str, ...]
    gates: tuple[str, ...]

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "WorkflowTemplate":
        required = ("schema_version", "template", "inputs", "stages", "outputs", "gates")
        missing = [field for field in required if field not in payload]
        if missing:
            raise WorkflowTemplateError(f"workflow template missing field(s): {', '.join(missing)}")
        template = cls(
            schema_version=int(payload["schema_version"]),
            template=str(payload["template"]),
            inputs=tuple(str(item) for item in payload["inputs"]),
            stages=tuple(str(item) for item in payload["stages"]),
            outputs=tuple(str(item) for item in payload["outputs"]),
            gates=tuple(str(item) for item in payload["gates"]),
        )
        template.validate()
        return template

    @classmethod
    def load(cls, path: str | Path) -> "WorkflowTemplate":
        return cls.from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))

    def validate(self) -> None:
        if self.schema_version != 1:
            raise WorkflowTemplateError(f"unsupported workflow template schema_version: {self.schema_version}")
        if not self.template:
            raise WorkflowTemplateError("workflow template name is required")
        if not self.inputs:
            raise WorkflowTemplateError(f"{self.template}: inputs must not be empty")
        if not self.stages:
            raise WorkflowTemplateError(f"{self.template}: stages must not be empty")
        if not self.outputs:
            raise WorkflowTemplateError(f"{self.template}: outputs must not be empty")
        unknown_stages = set(self.stages) - {"init", "fast", "full", "handoff", "cloud_confirmation", "report"}
        if unknown_stages:
            raise WorkflowTemplateError(f"{self.template}: unknown stage(s): {', '.join(sorted(unknown_stages))}")


def load_workflow_templates(root: str | Path = "scripts/research/workflows/templates") -> list[WorkflowTemplate]:
    """Load and validate all workflow templates under a directory."""

    template_root = Path(root)
    if not template_root.is_dir():
        raise WorkflowTemplateError(f"workflow template directory not found: {template_root}")
    return [WorkflowTemplate.load(path) for path in sorted(template_root.glob("*.json"))]
