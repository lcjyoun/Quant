"""[Phase 4 준비] DART OpenAPI로 ROE/부채비율/영업이익을 받아올 수 있는지 확인.

DART_API_KEY가 필요하다 (opendart.fss.or.kr에서 이메일로 즉시 발급, 증권계좌
불필요). 삼성전자(005930)의 2023년 사업보고서 기준 ROE/부채비율과, 2023년
분기별 영업이익 흑자 여부를 조회해본다.

키 설정 방법 (아무거나 하나만 하면 됨):
- 로컬: `.env` 파일에 `DART_API_KEY=발급받은키` 한 줄 추가
- Colab: 셀에서 직접 `import os; os.environ["DART_API_KEY"] = "발급받은키"`
  실행하거나, 왼쪽 열쇠 아이콘(보안 비밀)에 이름 `DART_API_KEY`로 저장하고
  "노트북 액세스" 토글을 켜두면 자동으로 읽어온다.

실행 (로컬):
    python test_dart_connection.py

실행 (Colab, 저장소를 클론한 뒤):
    !python test_dart_connection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Colab의 %run/작업 디렉터리가 이 파일 위치와 다를 때도 src를 찾을 수 있도록
# 이 스크립트 자신의 폴더를 import 경로에 추가한다.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import get_dart_api_key  # noqa: E402
from src.dart_client import DartAPIError, DartClient  # noqa: E402


def main() -> int:
    api_key = get_dart_api_key()
    if not api_key:
        print(
            "[실패] DART_API_KEY를 찾을 수 없습니다. "
            ".env 파일이나 환경변수, 또는 Colab 보안 비밀(Secrets)에 "
            "DART_API_KEY를 설정했는지 확인하세요."
        )
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
