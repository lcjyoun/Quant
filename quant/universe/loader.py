"""스크리닝 대상 종목 유니버스 로딩.

KIS API는 "코스피/코스닥 전체 종목 목록"을 REST로 직접 제공하지
않으므로, 종목코드/업종 정보는 `config/universe.csv` 파일로 관리한다.
(KRX 상장종목 목록이나 한국투자증권에서 배포하는 종목마스터 파일을
내려받아 이 형식으로 변환해 사용하면 된다.)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UniverseEntry:
    code: str
    name: str
    market: str
    industry: str


def load_universe(path: str | Path) -> list[UniverseEntry]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"유니버스 파일을 찾을 수 없습니다: {path}")

    entries: list[UniverseEntry] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(
                UniverseEntry(
                    code=row["code"].strip(),
                    name=row.get("name", "").strip(),
                    market=row.get("market", "").strip(),
                    industry=row.get("industry", "").strip(),
                )
            )
    return entries
