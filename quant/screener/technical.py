"""2차 필터: 기술적 지표(타이밍) 스크리닝.

기준 (2026-08-16 확정):
- 골든크로스 (단기 이평선이 장기 이평선을 상향 돌파)
- RSI 40~60 구간
- 거래량 직전 평균 대비 150% 이상
"""

from __future__ import annotations

import pandas as pd

from quant.config import TechnicalCriteria
from quant.indicators.technical import is_golden_cross, latest_rsi, volume_surge_ratio
from quant.models import FilterOutcome


class TechnicalFilter:
    def __init__(self, criteria: TechnicalCriteria):
        self._criteria = criteria

    def evaluate(self, price_df: pd.DataFrame) -> FilterOutcome:
        c = self._criteria
        details: dict = {}

        golden_cross = is_golden_cross(
            price_df,
            short_window=c.short_ma_window,
            long_window=c.long_ma_window,
            lookback_days=c.golden_cross_lookback_days,
        )
        details["golden_cross"] = {"passed": golden_cross}

        rsi_value = latest_rsi(price_df, period=c.rsi_period)
        rsi_ok = rsi_value is not None and c.rsi_min <= rsi_value <= c.rsi_max
        details["rsi"] = {
            "value": rsi_value,
            "min": c.rsi_min,
            "max": c.rsi_max,
            "passed": rsi_ok,
        }

        surge_ratio = volume_surge_ratio(price_df, avg_window=c.volume_avg_window)
        volume_ok = surge_ratio is not None and surge_ratio >= c.volume_surge_ratio
        details["volume_surge"] = {
            "ratio": surge_ratio,
            "threshold": c.volume_surge_ratio,
            "passed": volume_ok,
        }

        passed = golden_cross and rsi_ok and volume_ok
        return FilterOutcome(passed=passed, details=details)
