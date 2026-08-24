"""[Phase 4 준비] pykrx로 과거 데이터를 실제로 받아올 수 있는지 확인.

가입/API 키가 전혀 필요 없다. 삼성전자(005930)의 특정 기간 시세와
PER/PBR/시가총액을 받아와 출력해본다. 표가 정상적으로 출력되면 성공.

주의: 이 리포지토리가 올라가 있는 클라우드 세션(Claude Code 원격 실행
환경)은 KRX 서버로 나가는 외부 네트워크가 막혀 있어 여기서는 실행해도
항상 실패한다. 반드시 본인 컴퓨터(로컬)에서 실행해서 결과를 확인해달라.

실행:
    python test_pykrx_connection.py
"""

from __future__ import annotations

from src.market_data import (
    get_fundamental_history,
    get_market_cap_history,
    get_price_history,
)


def main() -> int:
    code = "005930"  # 삼성전자
    start, end = "20240102", "20240115"

    print(f"[조회] {code} 시세 ({start} ~ {end})")
    price_df = get_price_history(code, start, end)
    print(price_df)

    print(f"\n[조회] {code} PER/PBR ({start} ~ {end})")
    fundamental_df = get_fundamental_history(code, start, end)
    print(fundamental_df)

    print(f"\n[조회] {code} 시가총액 ({start} ~ {end})")
    cap_df = get_market_cap_history(code, start, end)
    print(cap_df)

    if price_df.empty or fundamental_df.empty or cap_df.empty:
        print("\n[실패] 데이터가 비어 있습니다. 인터넷 연결이나 pykrx 버전을 확인하세요.")
        return 1

    print("\n[성공] pykrx로 과거 데이터 조회 확인 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
