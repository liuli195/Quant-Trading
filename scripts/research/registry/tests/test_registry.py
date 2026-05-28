from __future__ import annotations

from pathlib import Path

from scripts.research.registry import default_tool_registry


def test_default_tool_registry_has_unique_valid_tools() -> None:
    registry = default_tool_registry()
    tool_ids = [tool["tool_id"] for tool in registry.list()]
    assert len(tool_ids) == len(set(tool_ids))
    assert registry.get("research.governance").layer == "governance"
    assert registry.get("tools.jq_automation").library == "scripts.tools.jq_automation"
    assert registry.get("research.portfolio_volatility").kind == "library"
    assert all(
        tool["cli"].startswith(r".\.venv\Scripts\python.exe -m ")
        for tool in registry.list()
        if tool["kind"] == "cli"
    )
    assert all(
        tool["cli_windows"].startswith(r".\.venv\Scripts\python.exe -m ")
        for tool in registry.list()
        if tool["kind"] == "cli"
    )
    assert all(
        tool["cli_posix"].startswith(".venv/bin/python -m ")
        for tool in registry.list()
        if tool["kind"] == "cli"
    )
    assert "scripts.research.research_core" in registry.by_library()
    assert "research_toolkit" in registry.by_layer()
    assert not registry.validate(".")


def test_registry_generates_layer_docs(tmp_path: Path) -> None:
    registry = default_tool_registry()
    docs = registry.render_layer_docs()
    assert "README.md" in docs
    assert "strategy_library.md" in docs
    assert "`research.strategy_variants`" in docs["strategy_library.md"]
    assert ".venv/bin/python -m scripts.research.variants" in docs["strategy_library.md"]
    assert "第四层：研究工具库" in docs["research_toolkit.md"]

    written = registry.write_layer_docs(tmp_path)
    assert tmp_path / "README.md" in written
    assert (tmp_path / "strategy_library.md").is_file()
