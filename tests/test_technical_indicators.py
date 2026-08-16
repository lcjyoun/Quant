import pandas as pd
import pytest

from quant.indicators.technical import (
    is_golden_cross,
    is_volume_surge,
    latest_rsi,
    rsi,
    volume_surge_ratio,
)


def _make_df(closes, volumes=None):
    volumes = volumes or [1000] * len(closes)
    return pd.DataFrame({"close": closes, "volume": volumes})


def test_golden_cross_detected_on_recovery():
    # 20일간 하락 후 마지막 구간에서 급반등 -> 단기(5) 이평선이 장기(20) 이평선을 상향 돌파
    decline = [120 - i for i in range(20)]  # 120 -> 101
    recovery = [105, 112, 120, 128, 136, 144, 152]
    closes = decline + recovery

    assert is_golden_cross(_make_df(closes), short_window=5, long_window=20, lookback_days=3)


def test_golden_cross_not_detected_on_pure_downtrend():
    closes = [200 - i for i in range(40)]  # 계속 하락
    assert not is_golden_cross(_make_df(closes), short_window=5, long_window=20, lookback_days=3)


def test_golden_cross_insufficient_data_returns_false():
    closes = [100, 101, 102]
    assert not is_golden_cross(_make_df(closes), short_window=5, long_window=20)


def test_rsi_all_gains_approaches_100():
    closes = [100 + i for i in range(30)]  # 계속 상승 (손실 없음)
    value = latest_rsi(_make_df(closes), period=14)
    assert value == pytest.approx(100.0)


def test_rsi_all_losses_approaches_0():
    closes = [200 - i for i in range(30)]  # 계속 하락 (이익 없음)
    value = latest_rsi(_make_df(closes), period=14)
    assert value == pytest.approx(0.0)


def test_rsi_bounded_between_0_and_100():
    closes = [100, 102, 99, 105, 101, 108, 103, 110, 107, 115, 112, 120, 118, 125, 122, 130]
    values = rsi(pd.Series(closes), period=14).dropna()
    assert not values.empty
    assert values.between(0, 100).all()


def test_rsi_insufficient_data_returns_none():
    closes = [100, 101, 102]
    assert latest_rsi(_make_df(closes), period=14) is None


def test_volume_surge_detected():
    volumes = [1000] * 20 + [2000]  # 마지막 날 평균 대비 2배
    closes = [100] * 21
    ratio = volume_surge_ratio(_make_df(closes, volumes), avg_window=20)
    assert ratio == pytest.approx(2.0)
    assert is_volume_surge(_make_df(closes, volumes), avg_window=20, surge_ratio=1.5)


def test_volume_surge_not_detected_when_flat():
    volumes = [1000] * 21
    closes = [100] * 21
    assert not is_volume_surge(_make_df(closes, volumes), avg_window=20, surge_ratio=1.5)


def test_volume_surge_insufficient_data_returns_none():
    volumes = [1000] * 5
    closes = [100] * 5
    assert volume_surge_ratio(_make_df(closes, volumes), avg_window=20) is None
