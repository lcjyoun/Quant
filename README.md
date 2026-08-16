# Quant — 국내 주식 스크리너

코스피/코스닥 종목을 **재무지표 1차 필터**로 걸러낸 뒤, **기술적 지표로
매수 타이밍**을 확인하는 스크리닝 파이프라인. 시세/재무 데이터는 한국투자증권
KIS Developers API를 사용하며, 모의투자 계좌로 개발 후 실전투자로 전환할 수
있다.

## 스크리닝 기준값 (2026-08-16 확정)

### 1차 필터 — 재무지표

| 지표 | 기준 |
| --- | --- |
| PER | 업종 평균 대비 20% 이상 저평가 |
| PBR | 1.5배 이하 |
| ROE | 10% 이상 |
| 부채비율 | 100% 이하 |
| 시가총액 | 2,000억원 이상 |

### 2차 필터 — 기술적 지표 (타이밍)

| 지표 | 기준 |
| --- | --- |
| 골든크로스 | 단기(5일) 이평선이 장기(20일) 이평선을 상향 돌파 |
| RSI | 40 ~ 60 구간 |
| 거래량 | 직전 20일 평균 대비 150% 이상 |

기준값은 `config/criteria.yaml`에서 조정할 수 있다.

## 프로젝트 구조

```
quant/
├── config.py              # .env / criteria.yaml 로딩
├── models.py               # 공용 데이터 모델
├── kis/
│   ├── auth.py              # OAuth 토큰 발급/캐싱
│   ├── endpoints.py          # API 경로 및 TR_ID 상수
│   └── client.py             # 시세/재무/주문 REST 클라이언트
├── indicators/
│   └── technical.py          # 골든크로스 / RSI / 거래량 급증 계산
├── screener/
│   ├── fundamental.py        # 1차 필터
│   ├── technical.py          # 2차 필터
│   └── pipeline.py           # 전체 파이프라인 오케스트레이션
└── universe/
    └── loader.py              # 스크리닝 대상 종목 목록 로딩

config/
├── criteria.yaml            # 기준값
└── universe.csv              # 스크리닝 대상 종목 (code,name,market,industry)

main.py                      # CLI 진입점
tests/                        # 지표/필터 단위 테스트
```

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## KIS API 설정

1. [KIS Developers 포털](https://apiportal.koreainvestment.com)에서 앱키/시크릿을
   발급받는다. 실전투자 계좌와 모의투자 계좌 각각 별도로 발급해야 한다.
2. `.env.example`을 복사해 `.env`를 만들고 값을 채운다.

```bash
cp .env.example .env
```

```
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ACCOUNT_NO=12345678-01
KIS_ENV=mock   # mock=모의투자, real=실전투자
```

`KIS_ENV`만 `real`로 바꾸면 base URL과 주문 TR_ID가 자동으로 실전투자용으로
전환된다 (`quant/config.py`, `quant/kis/endpoints.py` 참고).

> **참고:** KIS API는 코스피/코스닥 "전체 종목 목록"을 REST로 제공하지
> 않으므로, 스크리닝 대상 종목은 `config/universe.csv`에 직접 관리한다.
> KRX 상장종목 목록이나 KIS 종목마스터 파일을 내려받아 이 형식으로 변환해
> 사용하면 된다.

## 실행

```bash
python main.py --universe config/universe.csv --output output/candidates.csv
```

- **[매수 후보]**: 재무 + 기술 필터를 모두 통과한 종목
- **[관심 종목]**: 재무 필터는 통과했지만 아직 기술적 타이밍(골든크로스/RSI/거래량)이
  맞지 않은 종목 — 계속 관찰 대상

## 테스트

지표(골든크로스/RSI/거래량 급증)와 재무 필터 로직은 순수 함수라 API 키 없이
바로 테스트할 수 있다.

```bash
pytest tests/ -v
```

## 참고 사항

- 재무비율(ROE, 부채비율) 및 업종 PER 조회에 사용하는 KIS API 응답 필드명은
  공식 문서를 기준으로 매핑했다 (`quant/kis/client.py`). 실제 응답 구조가
  다를 경우 해당 파일의 필드명만 수정하면 되도록 파싱 로직을 분리해두었으니,
  실계좌/모의계좌로 첫 호출을 해본 뒤 응답 필드를 확인해 보정하는 것을 권장한다.
- 주문(`KISClient.place_order`)은 지정가/시장가 현금 매수·매도를 지원하며,
  모의투자와 실전투자의 TR_ID를 자동으로 구분한다. 실전 주문 실행 전
  모의투자 환경에서 충분히 검증할 것.
