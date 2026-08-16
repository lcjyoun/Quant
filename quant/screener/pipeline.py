"""전체 스크리닝 파이프라인: 1차(재무) 필터 통과 종목만 2차(기술) 필터로 타이밍 확인."""

from __future__ import annotations

import logging

from quant.config import Criteria
from quant.kis.client import KISAPIError, KISClient
from quant.models import ScreeningResult
from quant.screener.fundamental import FundamentalFilter
from quant.screener.technical import TechnicalFilter
from quant.universe.loader import UniverseEntry

logger = logging.getLogger(__name__)


class Screener:
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
