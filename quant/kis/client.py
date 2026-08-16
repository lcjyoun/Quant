"""KIS Developers API 클라이언트.

시세/재무/주문 조회를 위한 얇은 REST 래퍼. 모의투자(mock)/실전투자(real)는
`KISSettings.env`에 따라 base_url과 주문 tr_id만 달라지고 나머지 조회
API는 동일하게 동작한다.

응답 필드명은 공식 문서 기준으로 매핑했으나, 실제 응답과 다를 경우
아래 `*_FIELD` 딕셔너리만 수정하면 되도록 분리해두었다.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from quant.config import KISSettings
from quant.kis import endpoints as ep
from quant.kis.auth import TokenManager
from quant.models import FinancialSnapshot, PriceBar


class KISAPIError(RuntimeError):
    """KIS API 호출 실패."""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class KISClient:
    def __init__(self, settings: KISSettings, session: requests.Session | None = None):
        self._settings = settings
        self._session = session or requests.Session()
        self._auth = TokenManager(settings, session=self._session)

    # -- 내부 유틸 -----------------------------------------------------

    def _headers(self, tr_id: str, extra: dict | None = None) -> dict:
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._auth.get_access_token()}",
            "appkey": self._settings.app_key,
            "appsecret": self._settings.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }
        if extra:
            headers.update(extra)
        return headers

    def _get(self, path: str, tr_id: str, params: dict) -> dict:
        url = self._settings.base_url + path
        response = self._session.get(
            url, headers=self._headers(tr_id), params=params, timeout=10
        )
        if response.status_code != 200:
            raise KISAPIError(f"GET {path} 실패 ({response.status_code}): {response.text}")

        data = response.json()
        if data.get("rt_cd") not in (None, "0"):
            raise KISAPIError(f"GET {path} 오류 응답: {data.get('msg1')} ({data})")
        return data

    # -- 시세/재무 조회 --------------------------------------------------

    def get_financial_snapshot(
        self, code: str, market: str = "KOSPI", industry: str = ""
    ) -> FinancialSnapshot:
        """현재가/PER/PBR/시가총액 + 수익성/안정성 비율을 합쳐 스냅샷을 만든다."""

        price = self._get(
            ep.INQUIRE_PRICE_PATH,
            ep.TR_INQUIRE_PRICE,
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        ).get("output", {})

        profit = self._get(
            ep.FINANCIAL_RATIO_PATH,
            ep.TR_FINANCIAL_RATIO,
            params={
                "FID_DIV_CLS_CODE": "0",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": code,
            },
        ).get("output", [{}])
        profit_row = profit[0] if profit else {}

        stability = self._get(
            ep.STABILITY_RATIO_PATH,
            ep.TR_STABILITY_RATIO,
            params={
                "fid_div_cls_code": "0",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": code,
            },
        ).get("output", [{}])
        stability_row = stability[0] if stability else {}

        name = price.get("hts_kor_isnm", code)
        per = _safe_float(price.get("per"))
        pbr = _safe_float(price.get("pbr"))
        # hts_avls: 시가총액(억원 단위) -> 원 단위로 환산
        market_cap = _safe_float(price.get("hts_avls")) * 100_000_000

        roe = _safe_float(profit_row.get("self_cptl_ntin_inrt"))
        debt_ratio = _safe_float(stability_row.get("lblt_rate"))

        industry_per = self.get_industry_per(industry) if industry else per

        return FinancialSnapshot(
            code=code,
            name=name,
            market=market,
            industry=industry,
            per=per,
            industry_per=industry_per,
            pbr=pbr,
            roe=roe,
            debt_ratio=debt_ratio,
            market_cap=market_cap,
        )

    def get_industry_per(self, industry_code: str) -> float:
        """업종 평균 PER 조회. 업종 코드가 없으면 0을 반환한다."""

        if not industry_code:
            return 0.0

        output = self._get(
            ep.INDUSTRY_PRICE_PATH,
            ep.TR_INDUSTRY_PRICE,
            params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": industry_code},
        ).get("output", {})
        return _safe_float(output.get("per"))

    def get_daily_prices(self, code: str, count: int = 60) -> list[PriceBar]:
        """일봉 데이터를 오래된 순(과거 -> 최근)으로 반환한다."""

        output = self._get(
            ep.INQUIRE_DAILY_PRICE_PATH,
            ep.TR_INQUIRE_DAILY_PRICE,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": "",
                "FID_INPUT_DATE_2": "",
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "1",
            },
        ).get("output2", [])

        bars = [
            PriceBar(
                date=row.get("stck_bsop_date", ""),
                open=_safe_float(row.get("stck_oprc")),
                high=_safe_float(row.get("stck_hgpr")),
                low=_safe_float(row.get("stck_lwpr")),
                close=_safe_float(row.get("stck_clpr")),
                volume=_safe_float(row.get("acml_vol")),
            )
            for row in output[:count]
        ]
        bars.reverse()  # KIS는 최신순으로 내려주므로 뒤집어 과거->최근 순으로 맞춘다.
        return bars

    def get_daily_price_df(self, code: str, count: int = 60) -> pd.DataFrame:
        bars = self.get_daily_prices(code, count=count)
        return pd.DataFrame(
            [
                {
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars
            ]
        )

    # -- 주문 -----------------------------------------------------------

    def place_order(
        self, code: str, quantity: int, price: int, side: str = "buy"
    ) -> dict:
        """현금 매수/매도 주문. price=0이면 시장가 주문."""

        if side not in ("buy", "sell"):
            raise ValueError("side는 'buy' 또는 'sell'이어야 합니다")

        if side == "buy":
            tr_id = ep.TR_ORDER_BUY_MOCK if self._settings.is_mock else ep.TR_ORDER_BUY_REAL
        else:
            tr_id = ep.TR_ORDER_SELL_MOCK if self._settings.is_mock else ep.TR_ORDER_SELL_REAL

        account_parts = self._settings.account_no.split("-")
        cano = account_parts[0]
        acnt_prdt_cd = account_parts[1] if len(account_parts) > 1 else "01"

        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": code,
            "ORD_DVSN": "01" if price == 0 else "00",  # 01=시장가, 00=지정가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price),
        }

        url = self._settings.base_url + ep.ORDER_CASH_PATH
        response = self._session.post(
            url, headers=self._headers(tr_id, extra={"hashkey": ""}), json=body, timeout=10
        )
        if response.status_code != 200:
            raise KISAPIError(
                f"주문 실패 ({response.status_code}): {response.text}"
            )
        return response.json()
