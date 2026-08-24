"""KIS Developers API 인증 및 요청 래퍼.

이 파일 하나로 다음을 처리한다:
- OAuth 접근토큰(=API 호출용 임시 출입증) 발급 및 캐싱
- 시세/재무 조회, 계좌 잔고 조회, 주문 실행

모의투자(mock)/실전투자(real)는 `KISSettings.env` 값에 따라 base_url과
주문/잔고조회의 tr_id(=요청 종류를 구분하는 코드)만 달라지고 나머지는
동일하게 동작한다.

NOTE: TR_ID 및 응답 필드명은 한국투자증권 Open API 공식 문서
(https://apiportal.koreainvestment.com) 기준으로 작성했다. 실제 응답이
다르면 이 파일의 필드명만 고치면 되도록 파싱 로직을 한곳에 모아뒀다.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config import KISSettings
from src.models import FinancialSnapshot, PriceBar

# -- API 경로 및 TR_ID -------------------------------------------------

TOKEN_PATH = "/oauth2/tokenP"

INQUIRE_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
TR_INQUIRE_PRICE = "FHKST01010100"

INQUIRE_DAILY_PRICE_PATH = (
    "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
)
TR_INQUIRE_DAILY_PRICE = "FHKST03010100"

FINANCIAL_RATIO_PATH = "/uapi/domestic-stock/v1/finance/profit-ratio"
TR_FINANCIAL_RATIO = "FHKST66430400"

STABILITY_RATIO_PATH = "/uapi/domestic-stock/v1/finance/stability-ratio"
TR_STABILITY_RATIO = "FHKST66430600"

INDUSTRY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
TR_INDUSTRY_PRICE = "FHPUP02100000"

INQUIRE_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
TR_BALANCE_REAL = "TTTC8434R"
TR_BALANCE_MOCK = "VTTC8434R"

ORDER_CASH_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
TR_ORDER_BUY_REAL = "TTTC0802U"
TR_ORDER_BUY_MOCK = "VTTC0802U"
TR_ORDER_SELL_REAL = "TTTC0801U"
TR_ORDER_SELL_MOCK = "VTTC0801U"

# 접근토큰은 발급 후 24시간 유효. 만료 경계에서 요청이 실패하지 않도록
# 만료 전 여유시간을 두고 미리 갱신한다.
_EXPIRY_SAFETY_MARGIN_SECONDS = 300


class KISAuthError(RuntimeError):
    """토큰 발급/조회 실패."""


class KISAPIError(RuntimeError):
    """KIS API 호출 실패."""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class _TokenManager:
    """접근토큰 발급/파일 캐싱 담당 (KISClient 내부에서만 사용)."""

    def __init__(self, settings: KISSettings, session: requests.Session):
        self._settings = settings
        self._session = session
        self._cache_path = Path(settings.token_cache_path)
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_access_token(self) -> str:
        if self._access_token and time.time() < self._expires_at:
            return self._access_token

        if self._load_from_cache():
            return self._access_token  # type: ignore[return-value]

        return self._issue_new_token()

    def _load_from_cache(self) -> bool:
        if not self._cache_path.exists():
            return False
        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False

        if cached.get("app_key") != self._settings.app_key:
            return False

        expires_at = cached.get("expires_at", 0)
        if time.time() >= expires_at - _EXPIRY_SAFETY_MARGIN_SECONDS:
            return False

        self._access_token = cached.get("access_token")
        self._expires_at = expires_at
        return bool(self._access_token)

    def _issue_new_token(self) -> str:
        url = self._settings.base_url + TOKEN_PATH
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._settings.app_key,
            "appsecret": self._settings.app_secret,
        }

        response = self._session.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            raise KISAuthError(
                f"토큰 발급 실패 ({response.status_code}): {response.text}"
            )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 86400)
        if not access_token:
            raise KISAuthError(f"토큰 발급 응답에 access_token이 없습니다: {data}")

        self._access_token = access_token
        self._expires_at = time.time() + int(expires_in)
        self._save_to_cache()
        return access_token

    def _save_to_cache(self) -> None:
        cache = {
            "app_key": self._settings.app_key,
            "access_token": self._access_token,
            "expires_at": self._expires_at,
        }
        try:
            self._cache_path.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass  # 캐시 저장 실패는 치명적이지 않으므로 무시한다.


class KISClient:
    def __init__(self, settings: KISSettings, session: requests.Session | None = None):
        self._settings = settings
        self._session = session or requests.Session()
        self._auth = _TokenManager(settings, session=self._session)

    # -- 내부 유틸 -----------------------------------------------------

    def _account_parts(self) -> tuple[str, str]:
        parts = self._settings.account_no.split("-")
        cano = parts[0]
        acnt_prdt_cd = parts[1] if len(parts) > 1 else "01"
        return cano, acnt_prdt_cd

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

    # -- Phase 1: 인증 확인 ----------------------------------------------

    def check_auth(self) -> str:
        """접근토큰 발급이 실제로 되는지 확인한다. 성공 시 토큰 문자열 반환."""

        return self._auth.get_access_token()

    def get_account_balance(self) -> dict:
        """계좌 잔고 조회 (예수금, 총평가금액, 보유종목 수 요약)."""

        cano, acnt_prdt_cd = self._account_parts()
        tr_id = TR_BALANCE_MOCK if self._settings.is_mock else TR_BALANCE_REAL

        data = self._get(
            INQUIRE_BALANCE_PATH,
            tr_id,
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

        holdings = data.get("output1", [])
        summary_rows = data.get("output2", [{}])
        summary = summary_rows[0] if summary_rows else {}

        return {
            "cash": _safe_float(summary.get("dnca_tot_amt")),
            "total_eval_amount": _safe_float(summary.get("tot_evlu_amt")),
            "holding_count": len(holdings),
            "holdings": holdings,
        }

    # -- 시세/재무 조회 --------------------------------------------------

    def get_financial_snapshot(
        self, code: str, market: str = "KOSPI", industry: str = ""
    ) -> FinancialSnapshot:
        """현재가/PER/PBR/시가총액 + 수익성/안정성 비율을 합쳐 스냅샷을 만든다."""

        price = self._get(
            INQUIRE_PRICE_PATH,
            TR_INQUIRE_PRICE,
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        ).get("output", {})

        profit = self._get(
            FINANCIAL_RATIO_PATH,
            TR_FINANCIAL_RATIO,
            params={
                "FID_DIV_CLS_CODE": "0",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": code,
            },
        ).get("output", [{}])
        profit_row = profit[0] if profit else {}

        stability = self._get(
            STABILITY_RATIO_PATH,
            TR_STABILITY_RATIO,
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
            INDUSTRY_PRICE_PATH,
            TR_INDUSTRY_PRICE,
            params={"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": industry_code},
        ).get("output", {})
        return _safe_float(output.get("per"))

    def get_daily_prices(self, code: str, count: int = 60) -> list[PriceBar]:
        """일봉 데이터를 오래된 순(과거 -> 최근)으로 반환한다."""

        output = self._get(
            INQUIRE_DAILY_PRICE_PATH,
            TR_INQUIRE_DAILY_PRICE,
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
    # Phase 6(실전 자동매매) 전까지는 이 메서드를 실전 계좌(env=real)로
    # 호출하는 코드를 어디에서도 작성하지 마라. 모의투자 검증(Phase 5)까지만
    # 사용한다.

    def place_order(
        self, code: str, quantity: int, price: int, side: str = "buy"
    ) -> dict:
        """현금 매수/매도 주문. price=0이면 시장가 주문."""

        if side not in ("buy", "sell"):
            raise ValueError("side는 'buy' 또는 'sell'이어야 합니다")

        if side == "buy":
            tr_id = TR_ORDER_BUY_MOCK if self._settings.is_mock else TR_ORDER_BUY_REAL
        else:
            tr_id = TR_ORDER_SELL_MOCK if self._settings.is_mock else TR_ORDER_SELL_REAL

        cano, acnt_prdt_cd = self._account_parts()
        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": code,
            "ORD_DVSN": "01" if price == 0 else "00",  # 01=시장가, 00=지정가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price),
        }

        url = self._settings.base_url + ORDER_CASH_PATH
        response = self._session.post(
            url, headers=self._headers(tr_id, extra={"hashkey": ""}), json=body, timeout=10
        )
        if response.status_code != 200:
            raise KISAPIError(f"주문 실패 ({response.status_code}): {response.text}")
        return response.json()
