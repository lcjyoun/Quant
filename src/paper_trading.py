"""모의투자(paper trading) 실행 모듈 (Phase 5에서 구현 예정).

Phase 4 백테스트 검증이 끝난 뒤, src/screener.py + src/technical.py가
만든 매수 신호를 KISClient(모의투자 계좌, env=mock)로 실제 주문까지
자동화하고 판단 근거를 logs/에 남기는 로직이 여기에 들어간다.
"""
