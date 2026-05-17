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
