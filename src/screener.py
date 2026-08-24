"""1차 필터(재무지표 스크리닝) + 전체 스크리닝 파이프라인 오케스트레이션.

- `load_universe`: 스크리닝 대상 종목 목록을 CSV에서 읽어온다.
- `FundamentalFilter`: PER/PBR/ROE/부채비율/시가총액 기준 적용.
- `Screener`: 재무 필터를 통과한 종목만 골라 기술적 필터(src/technical.py)로
  타이밍까지 확인하는 전체 흐름을 담당한다.

KIS API는 "코스피/코스닥 전체 종목 목록"을 REST로 제공하지 않으므로,
종목코드/업종 정보는 `config/universe.csv` 파일로 관리한다. (KRX
상장종목 목록이나 KIS 종목마스터 파일을 내려받아 이 형식으로 변환해
사용하면 된다.)
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from src.config import Criteria, FundamentalCriteria
from src.dart_client import DartAPIError, DartClient
from src.kis_client import KISAPIError, KISClient
from src.models import FilterOutcome, FinancialSnapshot, ScreeningResult
from src.technical import TechnicalFilter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UniverseEntry:
    code: str
    name: str
    market: str
    industry: str


def load_universe(path: str | Path) -> list[UniverseEntry]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"유니버스 파일을 찾을 수 없습니다: {path}")

    entries: list[UniverseEntry] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                UniverseEntry(
                    code=row["code"].strip(),
                    name=row.get("name", "").strip(),
                    market=row.get("market", "").strip(),
                    industry=row.get("industry", "").strip(),
                )
            )
    return entries


class FundamentalFilter:
    """1차 필터: 재무지표 스크리닝.

    기준 (2026-08-16 확정, 4-1절):
    - PER: 업종 평균 대비 20% 이상 저평가
    - PBR: 1.5배 이하
    - ROE: 10% 이상
    - 부채비율: 100% 이하
    - 시가총액: 2000억원 이상
    """

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

        profit_streak_ok = snapshot.operating_profit_streak_ok
        details["operating_profit_streak"] = {"passed": profit_streak_ok}

        passed = per_ok and pbr_ok and roe_ok and debt_ok and cap_ok and profit_streak_ok
        return FilterOutcome(passed=passed, details=details)


class Screener:
    """1차(재무) + 2차(기술) 필터를 순서대로 적용하는 전체 파이프라인.

    재무 스냅샷은 두 소스를 합쳐서 만든다:
    - KIS(client): 현재가 기준 PER/PBR/시가총액/업종 PER
    - DART(dart_client): ROE/부채비율/영업이익 연속흑자 (직전 완결 회계연도
      사업보고서 + 분기보고서 기준)
    """

    def __init__(
        self,
        client: KISClient,
        dart_client: DartClient,
        criteria: Criteria,
        fiscal_year: str,
    ):
        self._client = client
        self._dart_client = dart_client
        self._fiscal_year = fiscal_year
        self._fundamental_filter = FundamentalFilter(criteria.fundamental)
        self._technical_filter = TechnicalFilter(criteria.technical)

    def run(self, universe: list[UniverseEntry]) -> list[ScreeningResult]:
        results: list[ScreeningResult] = []

        for entry in universe:
            try:
                result = self._screen_one(entry)
            except (KISAPIError, DartAPIError) as exc:
                logger.warning("종목 %s(%s) 조회 실패: %s", entry.code, entry.name, exc)
                continue
            results.append(result)

        return results

    def _screen_one(self, entry: UniverseEntry) -> ScreeningResult:
        price_snapshot = self._client.get_price_snapshot(entry.code, industry=entry.industry)

        corp_code = self._dart_client.get_corp_code(entry.code)
        ratios = self._dart_client.get_roe_and_debt_ratio(corp_code, self._fiscal_year)
        profit_streak_ok = self._dart_client.has_four_consecutive_profitable_quarters(
            corp_code, self._fiscal_year
        )

        snapshot = FinancialSnapshot(
            code=entry.code,
            name=price_snapshot["name"],
            market=entry.market,
            industry=entry.industry,
            per=price_snapshot["per"],
            industry_per=price_snapshot["industry_per"],
            pbr=price_snapshot["pbr"],
            roe=ratios["roe"],
            debt_ratio=ratios["debt_ratio"],
            market_cap=price_snapshot["market_cap"],
            operating_profit_streak_ok=profit_streak_ok,
        )
        fundamental_outcome = self._fundamental_filter.evaluate(snapshot)

        if not fundamental_outcome.passed:
            return ScreeningResult(
                code=entry.code, name=entry.name, fundamental=fundamental_outcome
            )

        price_df = self._client.get_daily_price_df(entry.code, count=60)
        technical_outcome = self._technical_filter.evaluate(price_df)

        return ScreeningResult(
            code=entry.code,
            name=entry.name,
            fundamental=fundamental_outcome,
            technical=technical_outcome,
        )

    @staticmethod
    def final_candidates(results: list[ScreeningResult]) -> list[ScreeningResult]:
        """재무 + 기술 필터를 모두 통과한 최종 매수 후보."""

        return [r for r in results if r.passed]

    @staticmethod
    def fundamental_only_candidates(results: list[ScreeningResult]) -> list[ScreeningResult]:
        """재무 필터만 통과하고 기술적 타이밍을 기다리는 관심종목."""

        return [
            r
            for r in results
            if r.fundamental.passed and (r.technical is None or not r.technical.passed)
        ]
