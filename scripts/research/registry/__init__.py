"""Central registry for local research tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tool_registry import ToolRegistry

__all__ = ["ToolRegistry", "default_tool_registry"]


def default_tool_registry():
    from .tool_registry import default_tool_registry as _default_tool_registry

    return _default_tool_registry()


def __getattr__(name: str):
    if name == "ToolRegistry":
        from .tool_registry import ToolRegistry

        return ToolRegistry
    raise AttributeError(name)
