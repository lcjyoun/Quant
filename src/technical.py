"""기술적 지표 계산 + 2차 필터(타이밍) 판정.

- 골든크로스: 단기 이평선이 장기 이평선을 최근 며칠 이내 상향 돌파했는지
- RSI(14): 과매수/과매도가 아닌 중립 구간(40~60)에 있는지
- 거래량: 평소 대비 급증했는지 (매수세 유입 신호로 사용)

모든 지표 계산 함수는 `date` 오름차순(과거 -> 최근)으로 정렬된
DataFrame을 입력으로 받는다. 최소 `close`, `volume` 컬럼이 필요하다.
"""

from __future__ import annotations

import pandas as pd

from src.config import TechnicalCriteria
from src.models import FilterOutcome


def moving_average(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def is_golden_cross(
    df: pd.DataFrame,
    short_window: int = 5,
    long_window: int = 20,
    lookback_days: int = 3,
) -> bool:
    """최근 `lookback_days`일 이내에 단기 이평선이 장기 이평선을
    상향 돌파했고, 현재도 단기 > 장기 상태이면 True.
    """

    if len(df) < long_window + lookback_days:
        return False

    close = df["close"]
    diff = (moving_average(close, short_window) - moving_average(close, long_window)).dropna()

    if len(diff) < 2:
        return False

    # 교차가 일어난 시점을 확인하려면 lookback 구간 시작 "직전" 값까지 봐야 하므로
    # lookback_days + 2개를 가져온다 (오늘 1개 + lookback_days개 + 교차 판별용 1개).
    recent = diff.tail(lookback_days + 2)
    if recent.iloc[-1] <= 0:
        return False  # 현재 단기 이평선이 장기 이평선 아래에 있으면 골든크로스 아님

    return bool((recent.iloc[:-1] <= 0).any())


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's smoothing 방식의 RSI(상대강도지수, 0~100 사이 값으로
    과매수/과매도 정도를 나타냄)."""

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    # 손실이 전혀 없었던 구간은 RS가 무한대이므로 RSI를 100으로 처리한다.
    result = result.where(avg_loss != 0, 100.0)
    return result


def latest_rsi(df: pd.DataFrame, period: int = 14) -> float | None:
    if len(df) < period + 1:
        return None
    values = rsi(df["close"], period=period).dropna()
    if values.empty:
        return None
    return float(values.iloc[-1])


def volume_surge_ratio(df: pd.DataFrame, avg_window: int = 20) -> float | None:
    """최근 거래량 / 직전 `avg_window`일 평균 거래량."""

    if len(df) < avg_window + 1:
        return None

    volume = df["volume"]
    baseline = volume.iloc[-(avg_window + 1) : -1].mean()
    today = volume.iloc[-1]

    if baseline <= 0:
        return None

    return float(today / baseline)


def is_volume_surge(
    df: pd.DataFrame, avg_window: int = 20, surge_ratio: float = 1.5
) -> bool:
    ratio = volume_surge_ratio(df, avg_window=avg_window)
    if ratio is None:
        return False
    return ratio >= surge_ratio


class TechnicalFilter:
    """2차 필터: 재무지표를 통과한 종목에 타이밍 신호를 적용한다."""

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
