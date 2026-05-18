"""Schemas used by the central research tool registry."""

from __future__ import annotations

from dataclasses import dataclass, field


TOOL_LAYERS = {
    "strategy_library",
    "data_center",
    "workflow_orchestration",
    "research_toolkit",
    "docs_reports",
    "governance",
}


TOOL_KINDS = {
    "cli",
    "library",
    "workflow_template",
    "automation",
}

LIFECYCLE_STATES = {"active", "superseded", "archived"}


@dataclass(frozen=True)
class ToolDefinition:
    """One discoverable research tool."""

    tool_id: str
    layer: str
    entry_module: str
    description: str
    library: str = ""
    kind: str = "library"
    cli: str | None = None
    readme_path: str | None = None
    docs_path: str | None = None
    tests: tuple[str, ...] = field(default_factory=tuple)
    inputs: tuple[str, ...] = field(default_factory=tuple)
    outputs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = "research-platform"
    lifecycle: str = "active"
    permissions: tuple[str, ...] = ("registered_cli_or_library",)

    def validate_schema(self) -> list[str]:
        errors: list[str] = []
        if not self.tool_id.strip():
            errors.append("tool_id is required")
        if self.layer not in TOOL_LAYERS:
            errors.append(f"{self.tool_id}: unknown layer {self.layer}")
        if not self.library.strip():
            errors.append(f"{self.tool_id}: library is required")
        if self.kind not in TOOL_KINDS:
            errors.append(f"{self.tool_id}: unknown kind {self.kind}")
        if not self.entry_module.strip():
            errors.append(f"{self.tool_id}: entry_module is required")
        if not self.description.strip():
            errors.append(f"{self.tool_id}: description is required")
        if not self.owner.strip():
            errors.append(f"{self.tool_id}: owner is required")
        if self.lifecycle not in LIFECYCLE_STATES:
            errors.append(f"{self.tool_id}: unknown lifecycle {self.lifecycle}")
        for field_name in ("tests", "inputs", "outputs", "permissions"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                errors.append(f"{self.tool_id}: {field_name} must be a tuple")
            elif any(not isinstance(item, str) or not item.strip() for item in value):
                errors.append(f"{self.tool_id}: {field_name} must contain non-empty strings")
        return errors
