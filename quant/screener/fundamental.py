"""1차 필터: 재무지표 스크리닝.

기준 (2026-08-16 확정):
- PER: 업종 평균 대비 20% 이상 저평가
- PBR: 1.5배 이하
- ROE: 10% 이상
- 부채비율: 100% 이하
- 시가총액: 2000억원 이상
"""

from __future__ import annotations

from quant.config import FundamentalCriteria
from quant.models import FilterOutcome, FinancialSnapshot


class FundamentalFilter:
    def __init__(self, criteria: FundamentalCriteria):
        self._criteria = criteria

    def evaluate(self, snapshot: FinancialSnapshot) -> FilterOutcome:
        c = self._criteria
        details: dict = {}

        per_threshold = snapshot.industry_per * (1 - c.per_industry_discount)
        per_ok = snapshot.industry_per > 0 and snapshot.per > 0 and snapshot.per <= per_threshold
        details["per"] = {
            "value": snapshot.per,
            "industry_per": snapshot.industry_per,
            "threshold": per_threshold,
            "passed": per_ok,
        }

        pbr_ok = snapshot.pbr > 0 and snapshot.pbr <= c.pbr_max
        details["pbr"] = {"value": snapshot.pbr, "threshold": c.pbr_max, "passed": pbr_ok}

        roe_ok = snapshot.roe >= c.roe_min
        details["roe"] = {"value": snapshot.roe, "threshold": c.roe_min, "passed": roe_ok}

        debt_ok = snapshot.debt_ratio <= c.debt_ratio_max
        details["debt_ratio"] = {
            "value": snapshot.debt_ratio,
            "threshold": c.debt_ratio_max,
            "passed": debt_ok,
        }

        cap_ok = snapshot.market_cap >= c.market_cap_min
        details["market_cap"] = {
            "value": snapshot.market_cap,
            "threshold": c.market_cap_min,
            "passed": cap_ok,
        }

        passed = per_ok and pbr_ok and roe_ok and debt_ok and cap_ok
        return FilterOutcome(passed=passed, details=details)
