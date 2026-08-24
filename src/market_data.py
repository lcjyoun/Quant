"""pykrx 기반 과거 시세/PER/PBR/시가총액 조회 (백테스트용, 가입 불필요).

Phase 4 백테스트는 "그날 그 시점" 기준 데이터가 필요하다. KIS API는
계좌 인증이 있어야 호출 가능하지만, pykrx는 KRX가 공개한 데이터를
그대로 가져오는 라이브러리라 회원가입 없이 바로 쓸 수 있다. 실시간
조회나 주문에는 쓸 수 없고 어디까지나 "과거 데이터 조회"용이다.

주의: pykrx는 KRX 사이트를 스크래핑하는 방식이라 요청이 너무 잦으면
느려지거나 일시적으로 막힐 수 있다. 종목 수가 많아지면 요청 사이에
약간의 대기시간을 두는 것을 권장한다.
"""

from __future__ import annotations

import pandas as pd
from pykrx import stock


def get_price_history(code: str, start: str, end: str) -> pd.DataFrame:
    """일별 시세(OHLCV)를 과거 -> 최근 순으로 반환한다.

    start/end는 'YYYYMMDD' 형식.
    """

    df = stock.get_market_ohlcv(start, end, code)
    df = df.sort_index()
    df = df.rename(
        columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        }
    )
    df = df.reset_index().rename(columns={"날짜": "date"})
    return df[["date", "open", "high", "low", "close", "volume"]]


def get_fundamental_history(code: str, start: str, end: str) -> pd.DataFrame:
    """일별 PER/PBR/EPS/BPS를 과거 -> 최근 순으로 반환한다."""

    df = stock.get_market_fundamental(start, end, code)
    df = df.sort_index()
    return df.reset_index().rename(columns={"날짜": "date"})


def get_market_cap_history(code: str, start: str, end: str) -> pd.DataFrame:
    """일별 시가총액(원)을 과거 -> 최근 순으로 반환한다."""

    df = stock.get_market_cap(start, end, code)
    df = df.sort_index()
    df = df.reset_index().rename(columns={"날짜": "date", "시가총액": "market_cap"})
    return df[["date", "market_cap"]]


def get_snapshot_as_of(code: str, date: str) -> dict:
    """특정 날짜 기준 PER/PBR/시가총액 스냅샷.

    해당 날짜가 휴장일일 수 있으므로 며칠 전부터 조회해 가장 최근
    영업일 값을 사용한다.
    """

    lookback_start = (pd.Timestamp(date) - pd.Timedelta(days=10)).strftime("%Y%m%d")

    fundamental = get_fundamental_history(code, lookback_start, date)
    market_cap = get_market_cap_history(code, lookback_start, date)

    if fundamental.empty or market_cap.empty:
        raise ValueError(f"{code} 기준일({date}) 근처 데이터가 없습니다")

    latest_fundamental = fundamental.iloc[-1]
    latest_cap = market_cap.iloc[-1]

    return {
        "per": float(latest_fundamental.get("PER", 0.0)),
        "pbr": float(latest_fundamental.get("PBR", 0.0)),
        "market_cap": float(latest_cap["market_cap"]),
    }


def average_industry_per(codes: list[str], date: str) -> float:
    """같은 업종 종목들의 PER 평균을 업종 평균 PER의 근사값으로 사용한다.

    NOTE: 이건 KRX 공식 업종 지수 PER이 아니라, `config/universe.csv`에서
    같은 industry로 묶인 종목들의 개별 PER을 평균낸 근사값이다. 유니버스에
    해당 업종 종목이 적으면 부정확할 수 있다. 공식 업종 지수 PER이 필요하면
    이 함수만 교체하면 되도록 분리해뒀다.
    """

    pers = []
    for code in codes:
        try:
            snapshot = get_snapshot_as_of(code, date)
        except ValueError:
            continue
        if snapshot["per"] > 0:
            pers.append(snapshot["per"])

    if not pers:
        return 0.0
    return sum(pers) / len(pers)
