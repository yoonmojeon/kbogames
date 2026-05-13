"""
KBO 데이터 수집 실행 스크립트
경기 결과 + 통계 + 라인업 데이터를 수집합니다.
"""
import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/collect_data.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

Path("logs").mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="KBO 데이터 수집")
    parser.add_argument("--games", action="store_true", help="경기 결과 수집")
    parser.add_argument("--stats", action="store_true", help="팀/선수 통계 수집")
    parser.add_argument("--lineup", action="store_true", help="1군 라인업 수집")
    parser.add_argument("--all", action="store_true", help="전체 수집")
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()

    if not any([args.games, args.stats, args.lineup, args.all]):
        args.all = True

    if args.all or args.games:
        logger.info("=" * 50)
        logger.info("1단계: 경기 결과 수집")
        logger.info("=" * 50)
        try:
            from scraper.kbo_scraper import collect_all_games
            df = collect_all_games(args.start_year, args.end_year)
            logger.info(f"경기 수집 완료: {len(df):,}경기")
        except Exception as e:
            logger.error(f"경기 수집 실패: {e}")

    if args.all or args.stats:
        logger.info("=" * 50)
        logger.info("2단계: 팀/선수 통계 수집")
        logger.info("=" * 50)
        try:
            from scraper.statiz_scraper import collect_all_stats
            results = collect_all_stats(args.start_year, args.end_year)
            logger.info(f"통계 수집 완료: {list(results.keys())}")
        except Exception as e:
            logger.error(f"통계 수집 실패: {e}")

    if args.all or args.lineup:
        logger.info("=" * 50)
        logger.info("3단계: 1군 라인업 + 순위 수집")
        logger.info("=" * 50)
        try:
            from scraper.lineup_scraper import get_full_lineup_data
            data = get_full_lineup_data()
            logger.info(f"라인업 수집 완료: {len(data['entry'])}팀 / 순위: {len(data['standings'])}팀")
        except Exception as e:
            logger.error(f"라인업 수집 실패: {e}")

    logger.info("\n데이터 수집 완료!")
    logger.info("다음 단계: python train_model.py")


if __name__ == "__main__":
    main()
