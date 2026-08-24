"""[Phase 4 준비] DART OpenAPI로 ROE/부채비율/영업이익을 받아올 수 있는지 확인.

DART_API_KEY가 .env에 있어야 한다 (opendart.fss.or.kr에서 이메일로 즉시 발급).
삼성전자(005930)의 2023년 사업보고서 기준 ROE/부채비율과, 2023년 분기별
영업이익 흑자 여부를 조회해본다.

주의: 이 리포지토리가 올라가 있는 클라우드 세션은 DART 서버로 나가는
외부 네트워크가 막혀 있어 여기서는 실행해도 항상 실패한다. 반드시 본인
컴퓨터(로컬)에서 실행해서 결과를 확인해달라.

실행:
    python test_dart_connection.py
"""

from __future__ import annotations

from src.config import get_dart_api_key
from src.dart_client import DartAPIError, DartClient


def main() -> int:
    api_key = get_dart_api_key()
    if not api_key:
        print("[실패] .env에 DART_API_KEY가 비어 있습니다.")
        return 1

    client = DartClient(api_key)
    code = "005930"  # 삼성전자
    year = "2023"  # 이미 사업보고서가 확정 공시된 완료 연도로 테스트

    try:
        corp_code = client.get_corp_code(code)
        print(f"[성공] {code} -> DART 고유번호 {corp_code}")

        ratios = client.get_roe_and_debt_ratio(corp_code, year)
        print(f"[성공] {year}년 사업보고서 기준 ROE={ratios['roe']:.2f}%, 부채비율={ratios['debt_ratio']:.2f}%")

        profits = client.get_quarterly_operating_profits(corp_code, year)
        print(f"[정보] {year}년 분기별 영업이익(단독, 원): {profits}")
        streak = all(v > 0 for v in profits.values())
        print(f"[정보] 4개 분기 연속 흑자 여부: {streak}")

    except DartAPIError as exc:
        print(f"[실패] {exc}")
        return 1

    print("\n[성공] DART로 재무 데이터 조회 확인 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
