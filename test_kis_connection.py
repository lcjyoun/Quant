"""[Phase 1] KIS API 연결 확인용 테스트 스크립트.

이 스크립트가 하는 일 (초보자용 설명):
1. `.env`에 적어둔 앱키/시크릿으로 KIS 서버에 "접근토큰"(임시 출입증)을
   요청한다. 이게 실패하면 이후 모든 API 호출이 불가능하므로 가장 먼저
   확인해야 한다.
2. 발급받은 토큰으로 모의투자 계좌의 잔고(예수금, 총평가금액)를 조회한다.
   이게 성공하면 "인증 -> 실제 요청"까지 정상 동작한다는 뜻이다.

실행:
    python test_kis_connection.py

주의: KIS_ENV=real로 되어 있어도 이 스크립트는 조회(잔고 확인)만 하고
주문은 절대 넣지 않는다. 다만 real로 설정된 상태에서 실행하면 실제
계좌 정보가 조회되니, 처음에는 반드시 .env의 KIS_ENV=mock 상태에서
실행할 것.
"""

from __future__ import annotations

import sys

from src.config import KISSettings
from src.kis_client import KISAPIError, KISAuthError, KISClient


def main() -> int:
    settings = KISSettings.from_env()

    if not settings.app_key or not settings.app_secret:
        print("[실패] .env에 KIS_APP_KEY / KIS_APP_SECRET이 비어 있습니다.")
        print("      .env.example을 복사해 .env를 만들고 값을 채워주세요.")
        return 1

    if not settings.account_no:
        print("[실패] .env에 KIS_ACCOUNT_NO가 비어 있습니다. (예: 12345678-01)")
        return 1

    print(f"[정보] KIS_ENV = {settings.env} (base_url = {settings.base_url})")

    client = KISClient(settings)

    try:
        client.check_auth()
    except KISAuthError as exc:
        print(f"[실패] 인증 토큰 발급에 실패했습니다: {exc}")
        return 1

    print("[성공] 인증 토큰 발급 성공")

    try:
        balance = client.get_account_balance()
    except KISAPIError as exc:
        print(f"[실패] 잔고 조회에 실패했습니다: {exc}")
        print("      (인증은 됐지만 계좌번호나 요청 파라미터가 잘못됐을 수 있습니다)")
        return 1

    print("[성공] 계좌 잔고 조회 성공")
    print(f"  - 예수금: {balance['cash']:,.0f}원")
    print(f"  - 총평가금액: {balance['total_eval_amount']:,.0f}원")
    print(f"  - 보유 종목 수: {balance['holding_count']}개")

    return 0


if __name__ == "__main__":
    sys.exit(main())
