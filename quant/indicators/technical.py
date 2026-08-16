"""기술적 지표 계산 (골든크로스 / RSI / 거래량 급증).

모든 함수는 `date` 오름차순(과거 -> 최근)으로 정렬된 DataFrame을
입력으로 받는다. 최소한 `close`, `volume` 컬럼이 있어야 한다.
"""

from __future__ import annotations

import pandas as pd


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
    """Wilder's smoothing 방식의 RSI."""

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
