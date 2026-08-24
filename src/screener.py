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

        # NOTE: 영업이익 4개 분기 연속 흑자 기준(4-1절)은 아직 KIS API 응답
        # 필드 매핑을 확인하지 못해 "확인 필요" 상태로 보류했다. 실제 계좌로
        # 재무비율 API를 호출해 응답을 확인한 뒤 추가할 예정.

        passed = per_ok and pbr_ok and roe_ok and debt_ok and cap_ok
        return FilterOutcome(passed=passed, details=details)


class Screener:
    """1차(재무) + 2차(기술) 필터를 순서대로 적용하는 전체 파이프라인."""

    def __init__(self, client: KISClient, criteria: Criteria):
        self._client = client
        self._fundamental_filter = FundamentalFilter(criteria.fundamental)
        self._technical_filter = TechnicalFilter(criteria.technical)

    def run(self, universe: list[UniverseEntry]) -> list[ScreeningResult]:
        results: list[ScreeningResult] = []

        for entry in universe:
            try:
                result = self._screen_one(entry)
            except KISAPIError as exc:
                logger.warning("종목 %s(%s) 조회 실패: %s", entry.code, entry.name, exc)
                continue
            results.append(result)

        return results

    def _screen_one(self, entry: UniverseEntry) -> ScreeningResult:
        snapshot = self._client.get_financial_snapshot(
            entry.code, market=entry.market, industry=entry.industry
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
