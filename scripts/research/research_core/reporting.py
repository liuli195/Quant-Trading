"""Lightweight persistence helpers for research outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact markdown table."""

    if frame.empty:
        return "_无可用记录。_"
    display = frame.copy().fillna("")
    headers = [str(column) for column in display.columns]
    rows = [[str(value) for value in row] for row in display.itertuples(index=False, name=None)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_json(path: str | Path, payload: object) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ReportPrimitives:
    """Reusable Markdown report fragments."""

    @staticmethod
    def table(frame: pd.DataFrame) -> str:
        return markdown_table(frame)

    @staticmethod
    def conclusion_block(*, directional_support: str, writeback_readiness: str) -> str:
        return "\n".join(
            [
                "## 结论边界",
                "",
                f"- **方向性支持**: {directional_support}",
                f"- **准备写回默认参数**: {writeback_readiness}",
                "",
            ]
        )

    @staticmethod
    def evidence_link(label: str, rel_path: str) -> str:
        return f"- **{label}**: [{rel_path}]({rel_path}) <!-- pathref: repo/{rel_path} -->"
