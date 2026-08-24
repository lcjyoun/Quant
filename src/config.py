"""환경 설정 및 전략 파라미터 로딩.

- KIS API 인증 정보(앱키/시크릿/계좌번호)는 절대 코드에 적지 않고 `.env`
  (환경변수)에서만 읽는다.
- 스크리닝 기준값 등 전략 파라미터는 `config/settings.yaml`에서 읽는다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"

KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"


@dataclass(frozen=True)
class KISSettings:
    """KIS Developers API 접속 설정."""

    app_key: str
    app_secret: str
    account_no: str
    env: str  # "mock" | "real"
    token_cache_path: str = ".kis_token_cache.json"

    @property
    def is_mock(self) -> bool:
        return self.env.lower() == "mock"

    @property
    def base_url(self) -> str:
        return KIS_MOCK_BASE_URL if self.is_mock else KIS_REAL_BASE_URL

    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> "KISSettings":
        load_dotenv(dotenv_path=dotenv_path)

        app_key = os.environ.get("KIS_APP_KEY", "")
        app_secret = os.environ.get("KIS_APP_SECRET", "")
        account_no = os.environ.get("KIS_ACCOUNT_NO", "")
        env = os.environ.get("KIS_ENV", "mock")
        token_cache_path = os.environ.get(
            "KIS_TOKEN_CACHE_PATH", ".kis_token_cache.json"
        )

        if env.lower() not in ("mock", "real"):
            raise ValueError(f"KIS_ENV는 'mock' 또는 'real'이어야 합니다: {env!r}")

        return cls(
            app_key=app_key,
            app_secret=app_secret,
            account_no=account_no,
            env=env.lower(),
            token_cache_path=token_cache_path,
        )


@dataclass(frozen=True)
class FundamentalCriteria:
    """1차 필터: 재무지표 기준값."""

    per_industry_discount: float = 0.20
    pbr_max: float = 1.5
    roe_min: float = 10.0
    debt_ratio_max: float = 100.0
    market_cap_min: float = 200_000_000_000


@dataclass(frozen=True)
class TechnicalCriteria:
    """2차 필터: 기술적 지표(타이밍) 기준값."""

    short_ma_window: int = 5
    long_ma_window: int = 20
    golden_cross_lookback_days: int = 3
    rsi_period: int = 14
    rsi_min: float = 40.0
    rsi_max: float = 60.0
    volume_avg_window: int = 20
    volume_surge_ratio: float = 1.5


@dataclass(frozen=True)
class Criteria:
    fundamental: FundamentalCriteria
    technical: TechnicalCriteria

    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_SETTINGS_PATH) -> "Criteria":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        fundamental = FundamentalCriteria(**raw.get("fundamental", {}))
        technical = TechnicalCriteria(**raw.get("technical", {}))
        return cls(fundamental=fundamental, technical=technical)
