"""실전 자동매매 모듈 — Phase 6 승인 전까지 비활성.

이 파일은 사용자가 Phase 5(모의투자 검증) 결과에 만족하고 "실전 전환"을
명시적으로 승인하기 전까지 어떤 함수도 실제로 동작해서는 안 된다.
아래 가드는 실수로 이 모듈을 호출하더라도 항상 실패하도록 만든 안전장치이며,
Phase 6 승인 시 사용자와 함께 리스크 관리 로직(종목당 최대 비중, 일일 손실
한도, 포트폴리오 MDD 한도 도달 시 자동 중단)을 구현한 뒤에만 이 가드를
해제한다.
"""

from __future__ import annotations

LIVE_TRADING_APPROVED = False


class LiveTradingNotApprovedError(RuntimeError):
    """실전매매가 아직 사용자 승인을 받지 못했을 때 발생시키는 예외."""


def run_live_trading(*args, **kwargs):
    if not LIVE_TRADING_APPROVED:
        raise LiveTradingNotApprovedError(
            "실전 자동매매는 아직 승인되지 않았습니다. "
            "Phase 5(모의투자 검증) 결과를 확인하고 명시적으로 승인한 뒤에만 "
            "LIVE_TRADING_APPROVED를 True로 바꾸고 리스크 관리 로직을 구현합니다."
        )
