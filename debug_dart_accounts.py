"""[진단용] DART 응답에서 실제 계정과목 이름을 확인하는 임시 스크립트.

ROE/부채비율/영업이익 계산이 0으로 나오는 원인을 추측하지 않고 실제
응답을 눈으로 확인하기 위한 것. 확인이 끝나면 이 파일은 지워도 된다.

실행:
    python debug_dart_accounts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import get_dart_api_key
from src.dart_client import REPORT_CODE_ANNUAL, DartClient

KEYWORDS = ["자본총계", "부채총계", "당기순이익", "영업이익", "자산총계"]


def main() -> int:
    api_key = get_dart_api_key()
    if not api_key:
        print("[실패] DART_API_KEY를 찾을 수 없습니다.")
        return 1

    client = DartClient(api_key)
    corp_code = client.get_corp_code("005930")
    items = client.get_financial_statement(corp_code, "2023", REPORT_CODE_ANNUAL)

    print(f"[정보] 전체 항목 수: {len(items)}\n")

    print("=== 키워드로 필터링한 항목 (기대하는 이름과 실제 이름 비교용) ===")
    matched = False
    for item in items:
        name = item.get("account_nm", "")
        if any(k in name for k in KEYWORDS):
            matched = True
            print(
                f"sj_div={item.get('sj_div')!r:>6} | account_nm={name!r} | "
                f"fs_div={item.get('fs_div')!r} | thstrm_amt={item.get('thstrm_amt')!r}"
            )
    if not matched:
        print("(키워드에 걸리는 항목이 하나도 없습니다)")

    print("\n=== 전체 계정과목 이름 목록 (처음 40개) ===")
    for item in items[:40]:
        print(f"- {item.get('sj_div')} | {item.get('account_nm')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
