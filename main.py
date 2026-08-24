"""국내 주식(코스피/코스닥) 스크리닝 CLI.

사용 예:
    python main.py --universe config/universe.csv --output output/candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
import sys
from pathlib import Path

from src.config import Criteria, KISSettings, get_dart_api_key
from src.dart_client import DartClient
from src.kis_client import KISClient
from src.screener import Screener, load_universe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="국내 주식 재무+기술 지표 스크리너")
    parser.add_argument(
        "--universe",
        default="config/universe.csv",
        help="스크리닝 대상 종목 목록 CSV 경로 (기본: config/universe.csv)",
    )
    parser.add_argument(
        "--criteria",
        default="config/settings.yaml",
        help="기준값 YAML 경로 (기본: config/settings.yaml)",
    )
    parser.add_argument(
        "--output",
        default="output/candidates.csv",
        help="최종 매수 후보 저장 경로 (기본: output/candidates.csv)",
    )
    parser.add_argument(
        "--env",
        choices=["mock", "real"],
        default=None,
        help="KIS_ENV 환경변수를 덮어쓴다 (기본: .env의 KIS_ENV 사용)",
    )
    parser.add_argument(
        "--fiscal-year",
        default=str(datetime.date.today().year - 1),
        help="ROE/부채비율/영업이익 조회에 쓸 회계연도 (기본: 작년, 사업보고서가 "
        "확정 공시된 완결 연도를 쓸 것)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    settings = KISSettings.from_env()
    if args.env:
        settings = KISSettings(
            app_key=settings.app_key,
            app_secret=settings.app_secret,
            account_no=settings.account_no,
            env=args.env,
            token_cache_path=settings.token_cache_path,
        )

    if not settings.app_key or not settings.app_secret:
        logging.error(
            "KIS_APP_KEY / KIS_APP_SECRET이 설정되지 않았습니다. "
            ".env 파일을 .env.example 기준으로 생성하세요."
        )
        return 1

    dart_api_key = get_dart_api_key()
    if not dart_api_key:
        logging.error(
            "DART_API_KEY가 설정되지 않았습니다. "
            "https://opendart.fss.or.kr 에서 발급받아 .env에 추가하세요."
        )
        return 1

    criteria = Criteria.from_yaml(args.criteria)
    universe = load_universe(args.universe)
    logging.info(
        "유니버스 %d개 종목 로드 완료 (env=%s, 회계연도=%s)",
        len(universe),
        settings.env,
        args.fiscal_year,
    )

    client = KISClient(settings)
    dart_client = DartClient(dart_api_key)
    screener = Screener(client, dart_client, criteria, args.fiscal_year)
    results = screener.run(universe)

    final_candidates = screener.final_candidates(results)
    watchlist = screener.fundamental_only_candidates(results)

    logging.info(
        "스크리닝 완료: 전체 %d종목 중 최종 후보 %d종목, 관심종목(재무만 통과) %d종목",
        len(results),
        len(final_candidates),
        len(watchlist),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["code", "name", "rsi", "volume_surge_ratio"])
        for result in final_candidates:
            rsi_value = result.technical.details["rsi"]["value"] if result.technical else None
            volume_ratio = (
                result.technical.details["volume_surge"]["ratio"] if result.technical else None
            )
            writer.writerow([result.code, result.name, rsi_value, volume_ratio])

    logging.info("최종 후보를 %s 에 저장했습니다.", output_path)

    for result in final_candidates:
        print(f"[매수 후보] {result.code} {result.name}")
    for result in watchlist:
        print(f"[관심 종목] {result.code} {result.name} (기술적 타이밍 대기)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
