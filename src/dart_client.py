"""DART(전자공시시스템) OpenAPI 클라이언트 — ROE/부채비율/영업이익 조회.

pykrx는 시세/PER/PBR/시가총액은 주지만 ROE·부채비율·분기별 영업이익은
주지 않는다. 이 세 지표는 기업의 재무제표 원본이 있어야 계산할 수 있고,
DART OpenAPI(https://opendart.fss.or.kr)가 무료로 이 데이터를 제공한다.
DART는 KIS와 달리 증권계좌 없이 이메일만으로 즉시 API 키를 받을 수 있다.

이 파일이 하는 일:
1. 종목코드(예: "005930") -> DART 내부 고유번호(corp_code) 매핑을
   내려받아 캐싱한다. (DART API는 고유번호로만 조회 가능하기 때문)
2. 특정 연도/분기의 재무제표에서 부채총계/자본총계/당기순이익/영업이익을
   찾아 ROE, 부채비율을 계산한다.
3. 최근 4개 분기의 영업이익이 모두 흑자인지 확인한다.

NOTE (확인 필요): DART 분기 보고서의 영업이익은 "분기 단독" 금액이 아니라
"연초부터 해당 분기까지의 누적" 금액으로 공시되는 경우가 많다
(1분기보고서=1분기 단독, 반기보고서=상반기 누적, 3분기보고서=1~3분기 누적,
사업보고서=연간 누적). 그래서 분기 단독 영업이익은 누적값을 서로 빼서
구해야 한다 (아래 `get_quarterly_operating_profits` 참고). 이 방식이
일반적인 계산법이지만, 실제 공시 데이터로 검증하기 전까지는 "확인 필요"로
취급하고 결과를 사람이 한 번 더 확인할 것을 권장한다.
"""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
FINANCIAL_STATEMENT_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

# 분기보고서 종류별 코드. 값은 "연초 ~ 해당 분기까지 누적" 금액이 찍힌다.
REPORT_CODE_Q1 = "11013"  # 1분기보고서 (1분기 단독, 누적이 아님)
REPORT_CODE_H1 = "11012"  # 반기보고서 (1~2분기 누적)
REPORT_CODE_Q3 = "11014"  # 3분기보고서 (1~3분기 누적)
REPORT_CODE_ANNUAL = "11011"  # 사업보고서 (1~4분기 연간 누적)

_DEFAULT_CORP_CODE_CACHE = Path("corp_code_cache.json")


class DartAPIError(RuntimeError):
    """DART API 호출 실패."""


class DartClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        corp_code_cache_path: str | Path = _DEFAULT_CORP_CODE_CACHE,
    ):
        if not api_key:
            raise ValueError("DART_API_KEY가 비어 있습니다")

        self._api_key = api_key
        self._session = session or requests.Session()
        self._corp_code_cache_path = Path(corp_code_cache_path)
        self._stock_to_corp_code: dict[str, str] | None = None

    # -- 종목코드 -> DART 고유번호 매핑 -----------------------------------

    def _load_corp_code_map(self) -> dict[str, str]:
        if self._stock_to_corp_code is not None:
            return self._stock_to_corp_code

        if self._corp_code_cache_path.exists():
            cached = json.loads(self._corp_code_cache_path.read_text(encoding="utf-8"))
            self._stock_to_corp_code = cached
            return cached

        mapping = self._download_corp_code_map()
        try:
            self._corp_code_cache_path.write_text(
                json.dumps(mapping, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass  # 캐시 저장 실패는 치명적이지 않음
        self._stock_to_corp_code = mapping
        return mapping

    def _download_corp_code_map(self) -> dict[str, str]:
        response = self._session.get(
            CORP_CODE_URL, params={"crtfc_key": self._api_key}, timeout=30
        )
        if response.status_code != 200:
            raise DartAPIError(
                f"corp_code 다운로드 실패 ({response.status_code}): {response.text[:200]}"
            )

        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                xml_bytes = zf.read("CORPCODE.xml")
        except zipfile.BadZipFile as exc:
            # DART는 키가 잘못되면 zip이 아니라 에러 메시지를 담은 xml을 준다.
            raise DartAPIError(
                f"corp_code 응답이 zip 파일이 아닙니다. API 키를 확인하세요. "
                f"응답 일부: {response.content[:200]!r}"
            ) from exc

        root = ET.fromstring(xml_bytes)
        mapping: dict[str, str] = {}
        for item in root.findall("list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            if stock_code:  # 상장사만 (비상장은 stock_code가 빈 문자열)
                mapping[stock_code] = corp_code
        return mapping

    def get_corp_code(self, stock_code: str) -> str:
        mapping = self._load_corp_code_map()
        corp_code = mapping.get(stock_code)
        if not corp_code:
            raise DartAPIError(f"종목코드 {stock_code}에 대한 DART 고유번호를 찾을 수 없습니다")
        return corp_code

    # -- 재무제표 조회 ----------------------------------------------------

    def get_financial_statement(
        self, corp_code: str, year: str, report_code: str, fs_div: str = "CFS"
    ) -> list[dict]:
        """단일회사 전체 재무제표 조회. fs_div: CFS=연결, OFS=별도."""

        response = self._session.get(
            FINANCIAL_STATEMENT_URL,
            params={
                "crtfc_key": self._api_key,
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": report_code,
                "fs_div": fs_div,
            },
            timeout=15,
        )
        if response.status_code != 200:
            raise DartAPIError(
                f"재무제표 조회 실패 ({response.status_code}): {response.text[:200]}"
            )

        data = response.json()
        status = data.get("status")
        if status != "000":
            raise DartAPIError(f"재무제표 조회 오류 (status={status}): {data.get('message')}")

        return data.get("list", [])

    @staticmethod
    def _find_amount(items: list[dict], account_name: str) -> float:
        for item in items:
            if item.get("account_nm") == account_name:
                raw = (item.get("thstrm_amt") or "0").replace(",", "")
                try:
                    return float(raw)
                except ValueError:
                    return 0.0
        return 0.0

    def get_roe_and_debt_ratio(
        self, corp_code: str, year: str, report_code: str = REPORT_CODE_ANNUAL
    ) -> dict:
        """연간 사업보고서 기준 ROE(%), 부채비율(%)을 계산한다."""

        items = self.get_financial_statement(corp_code, year, report_code)
        equity = self._find_amount(items, "자본총계")
        liabilities = self._find_amount(items, "부채총계")
        net_income = self._find_amount(items, "당기순이익")

        roe = (net_income / equity * 100) if equity else 0.0
        debt_ratio = (liabilities / equity * 100) if equity else 0.0
        return {"roe": roe, "debt_ratio": debt_ratio}

    def get_quarterly_operating_profits(self, corp_code: str, year: str) -> dict[str, float]:
        """분기별 "단독" 영업이익 4개를 반환한다 (누적 공시값을 서로 빼서 계산)."""

        q1_items = self.get_financial_statement(corp_code, year, REPORT_CODE_Q1)
        h1_items = self.get_financial_statement(corp_code, year, REPORT_CODE_H1)
        q3_cum_items = self.get_financial_statement(corp_code, year, REPORT_CODE_Q3)
        annual_items = self.get_financial_statement(corp_code, year, REPORT_CODE_ANNUAL)

        q1 = self._find_amount(q1_items, "영업이익")
        h1_cum = self._find_amount(h1_items, "영업이익")
        q3_cum = self._find_amount(q3_cum_items, "영업이익")
        annual_cum = self._find_amount(annual_items, "영업이익")

        return {
            "Q1": q1,
            "Q2": h1_cum - q1,
            "Q3": q3_cum - h1_cum,
            "Q4": annual_cum - q3_cum,
        }

    def has_four_consecutive_profitable_quarters(self, corp_code: str, year: str) -> bool:
        profits = self.get_quarterly_operating_profits(corp_code, year)
        return all(value > 0 for value in profits.values())
