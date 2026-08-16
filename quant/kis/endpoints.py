"""KIS Developers API 경로 및 TR_ID 상수.

NOTE: TR_ID 및 응답 필드명은 한국투자증권 Open API 공식 문서
(https://apiportal.koreainvestment.com) 기준으로 작성했다. 문서 개정이나
실제 응답이 다를 경우 이 파일과 `quant/kis/client.py`의 파싱 부분만
수정하면 되도록 한곳에 모아둔다.
"""

from __future__ import annotations

# 인증
TOKEN_PATH = "/oauth2/tokenP"

# 국내주식 현재가 시세 (현재가/PER/PBR/시가총액 등)
INQUIRE_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
TR_INQUIRE_PRICE = "FHKST01010100"

# 국내주식 일별/기간별 시세 (일봉 - 골든크로스/RSI/거래량 계산용)
INQUIRE_DAILY_PRICE_PATH = (
    "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
)
TR_INQUIRE_DAILY_PRICE = "FHKST03010100"

# 국내주식 수익성비율 (ROE 등)
FINANCIAL_RATIO_PATH = "/uapi/domestic-stock/v1/finance/profit-ratio"
TR_FINANCIAL_RATIO = "FHKST66430400"

# 국내주식 안정성비율 (부채비율 등)
STABILITY_RATIO_PATH = "/uapi/domestic-stock/v1/finance/stability-ratio"
TR_STABILITY_RATIO = "FHKST66430600"

# 업종 현재가 (업종 평균 PER 비교용)
INDUSTRY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
TR_INDUSTRY_PRICE = "FHPUP02100000"

# 주식 현금 주문 (매수/매도)
ORDER_CASH_PATH = "/uapi/domestic-stock/v1/trading/order-cash"

# 모의투자와 실전투자는 tr_id가 다르다.
TR_ORDER_BUY_REAL = "TTTC0802U"
TR_ORDER_BUY_MOCK = "VTTC0802U"
TR_ORDER_SELL_REAL = "TTTC0801U"
TR_ORDER_SELL_MOCK = "VTTC0801U"
