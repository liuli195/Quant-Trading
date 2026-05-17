from __future__ import annotations

from dataclasses import dataclass
from datetime import date


ETF_CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")
ETF_LABELS = {
    "159819.XSHE": "AI_ETF",
    "513100.XSHG": "NASDAQ_ETF",
    "518880.XSHG": "GOLD_ETF",
}

SCORE_START = date(2021, 1, 1)
SCORE_END = date(2026, 4, 30)
DISCOVERY_END = date(2024, 12, 31)
HORIZONS = (5, 10, 20, 40)
PRIMARY_HORIZON = 5
CROWD_WINDOW = 500
CROWD_THRESHOLD = 0.60
BOOTSTRAP_REPS = 400
BOOTSTRAP_BLOCK_SIZE = 4

TREND_MOMENTUM_WINDOWS = (10, 20, 30, 40, 60, 80, 100, 120, 160)
CROWD_RETURN_WINDOWS = (10, 20, 30, 40, 60, 80, 120)
CROWD_SHAPE_WINDOWS = (10, 20, 30, 40, 60)

SEGMENTS = {
    "discovery": (date(2021, 1, 1), date(2024, 12, 31)),
    "holdout": (date(2025, 1, 1), date(2026, 4, 30)),
    "segment_2021_2022": (date(2021, 1, 1), date(2022, 12, 31)),
    "segment_2023_2024": (date(2023, 1, 1), date(2024, 12, 31)),
    "segment_2025_2026": (date(2025, 1, 1), date(2026, 4, 30)),
}


@dataclass(frozen=True)
class FactorSpec:
    factor: str
    family: str
    windows: tuple[int, ...]
    description: str


FACTOR_SPECS = (
    FactorSpec("trend_gate", "trend", TREND_MOMENTUM_WINDOWS, "close above moving average"),
    FactorSpec("momentum_return", "momentum", TREND_MOMENTUM_WINDOWS, "rolling close return"),
    FactorSpec("crowd_ret_short", "crowding", CROWD_RETURN_WINDOWS, "rolling return percentile"),
    FactorSpec("crowd_ret_mid", "crowding", CROWD_RETURN_WINDOWS, "rolling return percentile"),
    FactorSpec("crowd_amount", "crowding", CROWD_SHAPE_WINDOWS, "rolling money mean percentile"),
    FactorSpec("crowd_deviation", "crowding", CROWD_SHAPE_WINDOWS, "close / moving average deviation percentile"),
    FactorSpec("crowd_volatility", "crowding", CROWD_SHAPE_WINDOWS, "rolling volatility percentile"),
)


def window_band(window: int) -> str:
    if window <= 30:
        return "short"
    if window <= 80:
        return "mid"
    return "long"

