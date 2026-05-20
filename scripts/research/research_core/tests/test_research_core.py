from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.research_core.audit import load_rebalance_events, load_run_start_params
from scripts.research.research_core.calendar import (
    build_weekly_anchor_frame,
    first_trading_days_by_week,
    forward_return_frame,
)
from scripts.research.research_core.layout import ResearchProjectLayout
from scripts.research.research_core.metrics import (
    paired_block_bootstrap,
    parse_cumulative_returns_md,
    performance_metrics,
    rolling_sharpe,
    yearly_metrics,
)
from scripts.research.research_core.pointers import read_text_file
from scripts.research.research_core.prices import load_price_bundle


def test_load_price_bundle_normalizes_frames(tmp_path) -> None:
    payload = {
        "calendar": ["2026-01-02", "2026-01-05"],
        "prices": {
            "AAA": [
                {"date": "2026-01-02", "open": 0.95, "close": 1.0, "high": 1.1, "low": 0.9, "money": 10},
                {"date": "2026-01-05", "open": 1.05, "close": 1.1, "high": 1.2, "low": 1.0, "money": 11},
            ]
        },
    }
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    frames = load_price_bundle(path, codes=("AAA", "BBB"))
    assert frames.open.loc[pd.Timestamp("2026-01-05"), "AAA"] == 1.05
    assert list(frames.close.columns) == ["AAA", "BBB"]
    assert frames.close.loc[pd.Timestamp("2026-01-05"), "AAA"] == 1.1
    assert pd.isna(frames.close.loc[pd.Timestamp("2026-01-05"), "BBB"])


def test_load_price_bundle_reads_data_center_pointer(tmp_path) -> None:
    payload = {
        "calendar": ["2026-01-02"],
        "prices": {
            "AAA": [
                {"date": "2026-01-02", "open": 0.95, "close": 1.0, "high": 1.1, "low": 0.9, "money": 10},
            ]
        },
    }
    snapshot = tmp_path / "research_datasets" / "prices" / "snap"
    (snapshot / "raw").mkdir(parents=True)
    (snapshot / "raw" / "prices.json.gz").write_bytes(
        gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    )
    pointer = tmp_path / "prices.json"
    pointer.write_text(
        json.dumps(
            {
                "kind": "data_center_pointer",
                "dataset_snapshot": snapshot.as_posix(),
                "dataset_file": "raw/prices.json.gz",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    frames = load_price_bundle(pointer)

    assert frames.close.loc[pd.Timestamp("2026-01-02"), "AAA"] == 1.0


def test_load_price_bundle_reads_repo_relative_pointer_from_strategy_cwd(tmp_path, monkeypatch) -> None:
    payload = {
        "calendar": ["2026-01-02"],
        "prices": {
            "AAA": [
                {"date": "2026-01-02", "open": 0.95, "close": 1.0, "high": 1.1, "low": 0.9, "money": 10},
            ]
        },
    }
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    strategy_dir = repo / "strategies" / "demo_strategy"
    run_dir = strategy_dir / "backtest_runs" / "run-1"
    snapshot = repo / "research_datasets" / "demo_strategy_backtest_runs" / "run-1"
    (run_dir).mkdir(parents=True)
    (snapshot / "raw").mkdir(parents=True)
    (snapshot / "raw" / "prices.json.gz").write_bytes(
        gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    )
    (run_dir / "prices.json").write_text(
        json.dumps(
            {
                "kind": "data_center_pointer",
                "dataset_snapshot": "research_datasets/demo_strategy_backtest_runs/run-1",
                "dataset_file": "raw/prices.json.gz",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(strategy_dir)

    frames = load_price_bundle(Path("backtest_runs/run-1/prices.json"))

    assert frames.close.loc[pd.Timestamp("2026-01-02"), "AAA"] == 1.0


def test_read_text_file_resolves_relative_pointer_snapshot_next_to_pointer(tmp_path, monkeypatch) -> None:
    pointer_dir = tmp_path / "run"
    snapshot = pointer_dir / "snapshot"
    (snapshot / "raw").mkdir(parents=True)
    (snapshot / "raw" / "payload.txt").write_text("hello", encoding="utf-8")
    pointer = pointer_dir / "payload.txt"
    pointer.write_text(
        json.dumps(
            {
                "kind": "data_center_pointer",
                "dataset_snapshot": "snapshot",
                "dataset_file": "raw/payload.txt",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert read_text_file(pointer) == "hello"


def test_calendar_helpers_build_forward_returns() -> None:
    calendar = pd.bdate_range("2026-01-01", "2026-01-20")
    anchors = build_weekly_anchor_frame(calendar, date(2026, 1, 1), date(2026, 1, 20), (5,))
    close = pd.DataFrame({"AAA": np.arange(1, len(calendar) + 1, dtype=float)}, index=calendar)
    forward = forward_return_frame(close, anchors, (5,), codes=("AAA",))
    assert len(first_trading_days_by_week(calendar, date(2026, 1, 1), date(2026, 1, 20))) == len(anchors) + 1
    assert forward["forward_5d"].notna().any()


def test_audit_helpers_extract_expected_rows(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"event": "run_start", "params": {"x": 1}}),
                json.dumps({"event": "rebalance_signals", "seq": 2}),
                json.dumps({"event": "rebalance_order", "seq": 3}),
            ]
        ),
        encoding="utf-8",
    )
    assert load_run_start_params(path) == {"x": 1}
    assert [row["seq"] for row in load_rebalance_events(path)] == [2]


def test_metrics_helpers_cover_return_workflow(tmp_path) -> None:
    path = tmp_path / "daily_returns.md"
    path.write_text(
        "\n".join(
            [
                "| 日期 | 策略收益 |",
                "| --- | --- |",
                "| 2026-01-02 | 0.01 |",
                "| 2026-01-05 | 0.0201 |",
            ]
        ),
        encoding="utf-8",
    )
    returns = parse_cumulative_returns_md(path)
    assert np.allclose(returns.to_numpy(), [0.01, 0.01])
    metrics = performance_metrics(returns)
    assert metrics["total_return"] > 0
    boot = paired_block_bootstrap(returns, returns + 0.001, n_boot=20, block=1, seed=7)
    assert boot["observed"] > 0
    roll = rolling_sharpe(pd.Series(np.repeat(0.001, 300)), window=252)
    assert roll.notna().sum() == 49
    yearly = yearly_metrics(pd.Series([0.01, -0.01], index=pd.to_datetime(["2025-01-02", "2026-01-02"])))
    assert set(yearly["year"]) == {2025, 2026}


def test_project_layout_creates_expected_dirs(tmp_path) -> None:
    project = ResearchProjectLayout.from_path(tmp_path / "demo")
    project.ensure_project_dirs()
    run = project.run("r1")
    run.ensure_dirs()
    assert run.reports_dir.exists()
    assert run.tables_dir.exists()
    assert run.curves_dir.exists()
