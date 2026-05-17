"""Static configuration for the momentum-tilt follow-up research project."""

from __future__ import annotations

from datetime import date


STRATEGY = "etf_factor_rotation"
ETF_CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")
ETF_LABELS = {
    "159819.XSHE": "AI",
    "513100.XSHG": "NASDAQ",
    "518880.XSHG": "GOLD",
}

SCORE_START = date(2021, 1, 1)
SCORE_END = date(2026, 4, 30)
DISCOVERY = (date(2021, 1, 1), date(2023, 12, 31))
HOLDOUT = (date(2024, 1, 1), date(2026, 4, 30))
YEAR_SEGMENTS = (
    ("2021", date(2021, 1, 1), date(2021, 12, 31)),
    ("2022", date(2022, 1, 1), date(2022, 12, 31)),
    ("2023", date(2023, 1, 1), date(2023, 12, 31)),
    ("2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("2025", date(2025, 1, 1), date(2025, 12, 31)),
    ("2026YTD", date(2026, 1, 1), date(2026, 4, 30)),
)

HORIZONS = (5, 10, 20, 40)
PRIMARY_HORIZON = 20
SCORE_BIN_WIDTH = 0.05

LINEAR_STRENGTHS = (0.50, 0.45, 0.40, 0.35, 0.25)

BASELINE_RUN_ID = "20260517-1611-bt9b67f2f9a034bb7d3d7a044cf3e0d4e9"
EXTREME_090_RUN_ID = "20260517-1624-btac3499f8d6b8bf0f5ee81147b6bd0da1"
LINEAR_025_RUN_ID = "20260517-1629-bt13a13155cdf761ba85550d3987fd22c4"

CALIBRATION_TOLERANCES = {
    "annual_return_abs": 0.0025,
    "sharpe_abs": 0.03,
    "max_drawdown_abs": 0.0025,
}
