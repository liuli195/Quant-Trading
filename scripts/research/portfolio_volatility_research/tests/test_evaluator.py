from __future__ import annotations

import gzip
import json

from scripts.research.portfolio_volatility_research.evaluator import (
    _parse_cloud_summary,
)


def test_parse_cloud_summary_reads_data_center_pointer(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    snapshot = tmp_path / "research_datasets" / "demo" / "run"
    (snapshot / "raw").mkdir(parents=True)
    summary = {
        "策略年化收益": "12.50%",
        "策略波动率": 0.22,
        "夏普比率": "1.350",
        "最大回撤": "-8.20%",
    }
    (snapshot / "raw" / "summary_metrics.json.gz").write_bytes(
        gzip.compress(json.dumps(summary, ensure_ascii=False).encode("utf-8"))
    )
    summary_path = run_dir / "summary_metrics.json"
    summary_path.write_text(
        json.dumps(
            {
                "kind": "data_center_pointer",
                "dataset_snapshot": snapshot.as_posix(),
                "dataset_file": "raw/summary_metrics.json.gz",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = _parse_cloud_summary(summary_path)

    assert result["annual_return"] == 0.125
    assert result["volatility"] == 0.22
    assert result["sharpe"] == 1.35
    assert abs(result["max_drawdown"] - 0.082) < 1e-12

