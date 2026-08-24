# Quant — 국내 주식 퀀트 트레이딩 시스템

한국투자증권(KIS) Developers API를 이용해 코스피/코스닥 종목을
**재무지표 1차 필터 → 기술적 지표 타이밍 → 백테스트 → 모의투자 검증 →
(승인 시) 실전 자동매매** 순서로 진행하는 프로젝트.

개발은 아래 Phase 순서대로, 각 Phase가 실제로 동작하는 것을 확인한 뒤
다음 단계로 넘어가는 방식으로 진행한다. **지금은 Phase 1(환경 세팅 +
KIS API 연결 확인) 단계다.**

## 전략 파라미터 (확정)

### 1차 필터 — 재무지표

| 지표 | 기준 |
| --- | --- |
| PER | 업종 평균 대비 20% 이상 저평가 |
| PBR | 1.5배 이하 |
| ROE | 10% 이상 |
| 부채비율 | 100% 이하 |
| 시가총액 | 2,000억원 이상 |
| 영업이익 | 최근 4개 분기 연속 흑자 |

### 2차 필터 — 기술적 지표 (타이밍)

| 지표 | 기준 |
| --- | --- |
| 골든크로스 | 20일선이 60일선을 최근 5거래일 이내 상향 돌파 |
| RSI(14) | 40 ~ 60 구간 |
| 거래량 | 20일 평균 대비 150% 이상 |

기준값은 `config/settings.yaml`에서 조정한다. 값을 바꿀 때는 근거(백테스트
성과 지표) 없이 임의로 바꾸지 않는다.

## 프로젝트 구조

```
.
├── .env                   # KIS API 키 (git 제외, 직접 작성)
├── .env.example
├── config/
│   ├── settings.yaml        # 스크리닝 기준값
│   └── universe.csv         # 스크리닝 대상 종목 (code,name,market,industry)
├── src/
│   ├── config.py             # .env / settings.yaml 로딩
│   ├── models.py             # 공용 데이터 구조
│   ├── kis_client.py         # KIS API 인증 + 시세(PER/PBR/시가총액)/잔고/주문 래퍼
│   ├── dart_client.py        # DART API — ROE/부채비율/영업이익 연속흑자
│   ├── screener.py           # 1차 필터(재무) + 전체 파이프라인
│   ├── technical.py          # 2차 필터(기술적 타이밍)
│   ├── backtest.py           # 백테스트 엔진 (Phase 4, 미구현)
│   ├── paper_trading.py      # 모의투자 자동 실행 (Phase 5, 미구현)
│   └── live_trading.py       # 실전매매 (Phase 6 승인 전까지 비활성)
├── logs/                     # 매매 판단 근거 로그 (Phase 5부터 사용)
├── tests/                    # 지표/필터 단위 테스트
├── test_kis_connection.py    # [Phase 1] KIS 인증 + 잔고조회 테스트 스크립트
├── test_dart_connection.py   # [Phase 1] DART 연동 테스트 스크립트
└── main.py                   # [Phase 2~3] 전체 스크리닝 CLI
```

**데이터 소스가 왜 KIS + DART 두 개인지**: KIS는 시세/PER/PBR/시가총액과
계좌 잔고·주문까지 다 되지만 증권계좌+가입이 필요하다. ROE/부채비율/
영업이익은 DART(전자공시) OpenAPI로 받는데, 증권계좌 없이 이메일만으로
즉시 키가 나오고, 실제 삼성전자 데이터로 검증까지 마쳤다. 한때 회원가입이
전혀 필요 없는 `pykrx` 라이브러리로 시세까지 전부 대체하는 것도
시도했지만, **한국거래소(KRX)가 pykrx 같은 비공식 스크래핑 라이브러리
사용자의 IP를 의도적으로 차단하고 있고 해제도 안 해준다고 공식
답변한 사례**가 있어 포기했다 (특히 Colab/Codespaces처럼 IP를 여러
사용자와 공유하는 환경에서는 내가 안 써도 차단될 수 있음). 그래서 시세
쪽은 결국 공식 경로인 KIS로 되돌아왔다.

## Phase 진행 상황

- [ ] **Phase 1**: 환경 세팅 + KIS API 연결 확인 — `test_kis_connection.py`
      (DART 연동은 삼성전자 실데이터로 검증 완료. KIS는 아직 실계좌로
      확인 전 — 사용자가 KIS Developers 가입 + 모의투자 계좌 신청을
      완료해야 다음 단계로 넘어간다.)
- [x] **Phase 2**: 스크리닝 모듈 (`src/screener.py`) — 코드는 작성됨,
      KIS 데이터로 실검증 전
- [x] **Phase 3**: 기술적 지표 모듈 (`src/technical.py`) — 코드는 작성됨,
      실검증 전
- [ ] **Phase 4**: 백테스팅 엔진
- [ ] **Phase 5**: 모의투자(paper trading) 검증
- [ ] **Phase 6**: 실전 자동매매 — **사용자의 명시적 승인 전까지 보류**

## Phase 1: KIS Developers 가입 + 모의투자 계좌 신청 (사용자가 직접 해야 하는 일)

1. https://apiportal.koreainvestment.com 에서 회원가입 (한국투자증권
   실계좌가 이미 있어야 한다 — 계좌가 없으면 먼저 증권 계좌부터 개설).
2. 포털 로그인 후 "모의투자" 메뉴에서 모의투자 계좌를 신청한다. 실전
   계좌와 별도로 가상 잔고(보통 5천만원 또는 1억원)가 주어지는 테스트
   계좌다.
3. 포털의 "OpenAPI 신청" 메뉴에서 앱키(App Key)/앱시크릿(App Secret)을
   발급받는다. **모의투자용과 실전투자용 키는 서로 다르다.** 지금 단계는
   모의투자용 키만 있으면 된다.
4. 발급받은 값과 모의투자 계좌번호를 `.env`에 채운다.

```bash
cp .env.example .env
```

```
KIS_APP_KEY=발급받은_앱키
KIS_APP_SECRET=발급받은_앱시크릿
KIS_ACCOUNT_NO=12345678-01   # 모의투자 계좌번호
KIS_ENV=mock
DART_API_KEY=발급받은_DART_키   # https://opendart.fss.or.kr 에서 이메일로 즉시 발급
```

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Phase 1 완료 확인

```bash
python test_kis_connection.py
```

다음과 같이 출력되면 Phase 1 완료:

```
[정보] KIS_ENV = mock (base_url = https://openapivts.koreainvestment.com:29443)
[성공] 인증 토큰 발급 성공
[성공] 계좌 잔고 조회 성공
  - 예수금: 50,000,000원
  - 총평가금액: 50,000,000원
  - 보유 종목 수: 0개
```

DART 연동도 함께 확인한다 (증권계좌 불필요, `DART_API_KEY`만 있으면 됨):

```bash
python test_dart_connection.py
```

실패하면 에러 메시지를 그대로 공유해달라 — 추측하지 않고 그 메시지를
근거로 원인을 진단한다.

## (Phase 2~3) 전체 스크리닝 실행

Phase 1이 통과된 뒤 사용할 명령. `config/universe.csv`에 스크리닝하고
싶은 종목을 채운 뒤 실행한다. `--fiscal-year`는 ROE/부채비율/영업이익을
가져올 회계연도로, 기본값은 작년(사업보고서가 이미 확정 공시됐을 연도)이다.

```bash
python main.py --universe config/universe.csv --output output/candidates.csv --fiscal-year 2025
```

- **[매수 후보]**: 재무 + 기술 필터를 모두 통과한 종목
- **[관심 종목]**: 재무 필터는 통과했지만 아직 기술적 타이밍이 맞지 않은 종목

## 테스트

지표(골든크로스/RSI/거래량 급증)와 재무 필터 로직은 순수 함수라 API 키
없이 바로 테스트할 수 있다.

```bash
pytest tests/ -v
```

## 리스크/보안 가드레일

- API 키는 `.env`로만 관리하며 절대 코드에 하드코딩하지 않는다. `.env`는
  `.gitignore`에 포함되어 있다.
- `src/live_trading.py`는 `LIVE_TRADING_APPROVED = False`로 고정되어
  있어, 사용자가 Phase 5 결과를 확인하고 명시적으로 승인하기 전까지는
  호출 시 항상 예외를 발생시킨다.
- ROE/부채비율/영업이익(DART)은 삼성전자 실데이터로 검증 완료. 시세/PER/PBR/
  시가총액/업종 PER(KIS) 응답 필드명은 공식 문서 기준으로 매핑했지만
  아직 실계좌로 검증 전이다 — Phase 1을 실제로 통과시킬 때 응답을 확인해
  `src/kis_client.py`의 필드명을 보정할 것 (DART 필드명도 처음엔
  `thstrm_amt`로 잘못 짐작했다가 실제 응답을 보고 `thstrm_amount`로
  고친 적이 있다 — 같은 방식으로 검증하면 된다).
