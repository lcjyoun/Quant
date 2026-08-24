"""여러 모듈에서 공유하는 데이터 구조.

kis_client.py가 만들어서 screener.py/technical.py가 소비하는 값들이라
공용 파일로 분리했다 (문서 초안에는 없던 파일이지만 중복 정의를 피하기
위해 추가함).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FinancialSnapshot:
    """1차(재무지표) 필터에 사용되는 종목 스냅샷."""

    code: str
    name: str
    market: str  # "KOSPI" | "KOSDAQ"
    industry: str
    per: float
    industry_per: float
    pbr: float
    roe: float
    debt_ratio: float
    market_cap: float  # 원(KRW) 단위


@dataclass
class PriceBar:
    """일봉 1개 데이터."""

    date: str  # YYYYMMDD
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class FilterOutcome:
    """단일 필터(재무 또는 기술)의 판정 결과."""

    passed: bool
    details: dict = field(default_factory=dict)


@dataclass
class ScreeningResult:
    """종목 1개에 대한 최종 스크리닝 결과."""

    code: str
    name: str
    fundamental: FilterOutcome
    technical: FilterOutcome | None = None

    @property
    def passed(self) -> bool:
        if self.technical is None:
            return False
        return self.fundamental.passed and self.technical.passed
