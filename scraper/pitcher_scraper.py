"""
KBO 게임센터 선발투수 전력분석 스크래퍼

KBO 공식 게임센터의 START_PIT 프리뷰 섹션에서 선발투수 이름과
시즌 ERA/WAR/WHIP 등 경기 단위 예측에 필요한 투수 피처를 가져온다.
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import KBO_TEAMS
from scraper.kbo_scraper import scrape_games_by_date, get_selenium_driver

logger = logging.getLogger(__name__)

KBO_BASE_URL = "https://www.koreabaseball.com"


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").replace("-", "").strip())
    except Exception:
        return default


def _parse_pitcher_name(raw: str) -> tuple[str, str, int]:
    """
    예: '양창섭 우투우타 시즌 1승' -> ('양창섭', '우투우타', 1)
    """
    raw = re.sub(r"\s+", " ", raw or "").strip()
    tokens = raw.split()
    name = tokens[0] if tokens else ""
    throws_bats = next((t for t in tokens[1:] if "투" in t and "타" in t), "")
    wins_match = re.search(r"시즌\s*(\d+)승", raw)
    wins = int(wins_match.group(1)) if wins_match else 0
    return name, throws_bats, wins


def _parse_starting_pitcher_table(soup: BeautifulSoup) -> list[dict]:
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        if not header or "선발투수" not in header[0]:
            continue

        pitchers = []
        for row in rows[1:3]:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            if len(cells) < 7:
                continue

            name, throws_bats, season_wins = _parse_pitcher_name(cells[0])
            pitchers.append({
                "name": name,
                "throws_bats": throws_bats,
                "season_wins": season_wins,
                "era": _safe_float(cells[1], 4.50),
                "war": _safe_float(cells[2], 0.0),
                "games": int(_safe_float(cells[3], 0.0)),
                "starter_avg_innings": _safe_float(cells[4], 4.5),
                "qs": int(_safe_float(cells[5], 0.0)),
                "whip": _safe_float(cells[6], 1.45),
            })

        if len(pitchers) == 2:
            return pitchers

    return []


def scrape_starting_pitcher_analysis(preview_url: str, driver=None) -> dict:
    """KBO START_PIT 페이지 1개에서 원정/홈 선발투수 분석을 가져온다."""
    if not preview_url:
        return {}

    own_driver = driver is None
    if own_driver:
        driver = get_selenium_driver()
        if not driver:
            return {}

    try:
        url = urljoin(KBO_BASE_URL, preview_url)
        driver.get(url)
        time.sleep(2.5)
        soup = BeautifulSoup(driver.page_source, "lxml")
        pitchers = _parse_starting_pitcher_table(soup)
        if len(pitchers) != 2:
            return {}

        return {
            "away_pitcher": pitchers[0]["name"],
            "home_pitcher": pitchers[1]["name"],
            "away_pitcher_stats": pitchers[0],
            "home_pitcher_stats": pitchers[1],
        }
    except Exception as e:
        logger.warning(f"선발투수 분석 수집 실패({preview_url}): {e}")
        return {}
    finally:
        if own_driver and driver:
            driver.quit()


def scrape_pitcher_matchups_by_date(game_date: str) -> list[dict]:
    """특정 날짜 경기 일정에 선발투수 분석을 붙여 반환한다."""
    games = scrape_games_by_date(game_date)
    driver = get_selenium_driver()
    if not driver:
        return games

    try:
        enriched = []
        for game in games:
            analysis = scrape_starting_pitcher_analysis(game.get("preview_url", ""), driver=driver)
            enriched.append({**game, **analysis})
        return enriched
    finally:
        driver.quit()


if __name__ == "__main__":
    import json

    rows = scrape_pitcher_matchups_by_date(sys.argv[1] if len(sys.argv) > 1 else "2026-05-14")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
