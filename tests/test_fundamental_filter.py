from quant.config import FundamentalCriteria
from quant.models import FinancialSnapshot
from quant.screener.fundamental import FundamentalFilter

CRITERIA = FundamentalCriteria(
    per_industry_discount=0.20,
    pbr_max=1.5,
    roe_min=10.0,
    debt_ratio_max=100.0,
    market_cap_min=200_000_000_000,
)


def _snapshot(**overrides) -> FinancialSnapshot:
    base = dict(
        code="000000",
        name="테스트종목",
        market="KOSPI",
        industry="전기전자",
        per=8.0,  # industry_per(10.0) * 0.8 = 8.0 -> 정확히 경계값(통과)
        industry_per=10.0,
        pbr=1.2,
        roe=12.0,
        debt_ratio=80.0,
        market_cap=300_000_000_000,
    )
    base.update(overrides)
    return FinancialSnapshot(**base)


def test_all_criteria_pass():
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot())
    assert outcome.passed
    assert all(item["passed"] for item in outcome.details.values())


def test_per_above_industry_discount_threshold_fails():
    # per=9.0 > industry_per(10.0)*0.8=8.0 -> 저평가 기준 미달
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot(per=9.0))
    assert not outcome.passed
    assert not outcome.details["per"]["passed"]


def test_pbr_above_max_fails():
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot(pbr=1.6))
    assert not outcome.passed
    assert not outcome.details["pbr"]["passed"]


def test_roe_below_min_fails():
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot(roe=9.9))
    assert not outcome.passed
    assert not outcome.details["roe"]["passed"]


def test_debt_ratio_above_max_fails():
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot(debt_ratio=100.1))
    assert not outcome.passed
    assert not outcome.details["debt_ratio"]["passed"]


def test_market_cap_below_min_fails():
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot(market_cap=199_999_999_999))
    assert not outcome.passed
    assert not outcome.details["market_cap"]["passed"]


def test_zero_per_treated_as_missing_data_and_fails():
    outcome = FundamentalFilter(CRITERIA).evaluate(_snapshot(per=0.0))
    assert not outcome.passed
    assert not outcome.details["per"]["passed"]
