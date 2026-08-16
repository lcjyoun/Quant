"""KIS OAuth 접근토큰 발급 및 캐싱.

접근토큰은 발급 후 24시간 유효하며, 동일 앱키로 짧은 시간 내 재발급을
요청하면 제한에 걸릴 수 있으므로 파일에 캐싱해 재사용한다.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from quant.config import KISSettings
from quant.kis.endpoints import TOKEN_PATH

# 만료 시각 이전에 미리 갱신해 경계에서 요청이 실패하는 것을 방지한다.
_EXPIRY_SAFETY_MARGIN_SECONDS = 300


class KISAuthError(RuntimeError):
    """토큰 발급/조회 실패."""


class TokenManager:
    def __init__(self, settings: KISSettings, session: requests.Session | None = None):
        self._settings = settings
        self._session = session or requests.Session()
        self._cache_path = Path(settings.token_cache_path)
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_access_token(self) -> str:
        if self._access_token and time.time() < self._expires_at:
            return self._access_token

        if self._load_from_cache():
            return self._access_token  # type: ignore[return-value]

        return self._issue_new_token()

    def _load_from_cache(self) -> bool:
        if not self._cache_path.exists():
            return False

        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False

        if cached.get("app_key") != self._settings.app_key:
            return False

        expires_at = cached.get("expires_at", 0)
        if time.time() >= expires_at - _EXPIRY_SAFETY_MARGIN_SECONDS:
            return False

        self._access_token = cached.get("access_token")
        self._expires_at = expires_at
        return bool(self._access_token)

    def _issue_new_token(self) -> str:
        url = self._settings.base_url + TOKEN_PATH
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._settings.app_key,
            "appsecret": self._settings.app_secret,
        }

        response = self._session.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            raise KISAuthError(
                f"토큰 발급 실패 ({response.status_code}): {response.text}"
            )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 86400)
        if not access_token:
            raise KISAuthError(f"토큰 발급 응답에 access_token이 없습니다: {data}")

        self._access_token = access_token
        self._expires_at = time.time() + int(expires_in)
        self._save_to_cache()
        return access_token

    def _save_to_cache(self) -> None:
        cache = {
            "app_key": self._settings.app_key,
            "access_token": self._access_token,
            "expires_at": self._expires_at,
        }
        try:
            self._cache_path.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass  # 캐시 저장 실패는 치명적이지 않으므로 무시한다.
