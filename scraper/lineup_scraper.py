"""
1군 엔트리 및 오늘의 라인업/순위 스크래퍼
Selenium 기반 (JavaScript 렌더링 필요 페이지)
"""
import re
import time
import json
import logging
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RAW_DIR, HEADERS, REQUEST_TIMEOUT, KBO_TEAMS, TEAM_NAME_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def normalize_team(name: str) -> str:
    name = name.strip().replace(" ", "").replace("\xa0", "")
    return TEAM_NAME_MAP.get(name, name)


YAGOONARA_TEAM_MAP = {
    "두산": "두산",
    "롯데": "롯데",
    "삼성": "삼성",
    "키움": "키움",
    "한화": "한화",
    "KIA": "KIA",
    "KT": "KT",
    "LG": "LG",
    "NC": "NC",
    "SSG": "SSG",
}


def _normalize_roster_position(position: str) -> str:
    position = (position or "").strip()
    return {
        "투수": "투수",
        "포수": "포수",
        "내야수": "내야수",
        "외야수": "외야수",
    }.get(position, position)


def scrape_yagoonara_current_roster() -> dict[str, list]:
    """
    야구나라 1군 로스터 페이지에서 현재 등록 선수 명단을 가져온다.
    페이지의 Next.js 초기 데이터(initialRoster)는 KBO 데이터를 출처로 제공한다.
    """
    url = "https://www.yagoonara.com/roster"
    headers = {
        **HEADERS,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.warning(f"야구나라 로스터 요청 실패: {e}")
        return {}

    for script in soup.find_all("script"):
        text = script.get_text()
        if "initialRoster" not in text:
            continue

        try:
            match = re.match(r"self\.__next_f\.push\((.*)\)$", text)
            if not match:
                continue

            # Next.js flight payload: [1, "6:[\"$\", ... {\"initialRoster\": ...}]"]
            payload_wrapper = json.loads(match.group(1))
            payload = payload_wrapper[1]
            flight_data = json.loads(payload.split(":", 1)[1])
            roster_items = flight_data[3]["initialRoster"]
        except Exception as e:
            logger.warning(f"야구나라 로스터 파싱 실패: {e}")
            continue

        lineups: dict[str, list] = {}
        for team_item in roster_items:
            team = YAGOONARA_TEAM_MAP.get(team_item.get("teamName"))
            if not team:
                continue

            players = []
            for player in team_item.get("players", []):
                name = (player.get("player_name") or "").strip()
                if not name:
                    continue

                players.append({
                    "number": str(player.get("back_number") or ""),
                    "position": _normalize_roster_position(player.get("position")),
                    "name": name,
                    "team": team,
                    "throws_bats": player.get("throws_bats") or "",
                    "kbo_id": player.get("kbo_id") or "",
                    "register_date": str(player.get("register_date") or "").replace("$D", ""),
                    "source": "yagoonara",
                })

            if players:
                # 화면에서 보기 좋게 포지션/등번호 순 정렬
                pos_order = {"투수": 0, "포수": 1, "내야수": 2, "외야수": 3}
                players.sort(key=lambda p: (
                    pos_order.get(p["position"], 9),
                    int(p["number"]) if p["number"].isdigit() else 999,
                    p["name"],
                ))
                lineups[team] = players

        if lineups:
            logger.info(f"야구나라 실시간 1군 로스터 수집: {len(lineups)}팀")
            return lineups

    return {}


def get_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(20)
        return driver
    except Exception as e:
        logger.warning(f"Selenium 초기화 실패: {e}")
        return None


def scrape_standings_selenium() -> list[dict]:
    """KBO 현재 순위 (Selenium)"""
    driver = get_driver()
    if not driver:
        return []

    standings = []
    try:
        driver.get("https://www.koreabaseball.com/Record/Standing/Current.aspx")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "lxml")

        table = None
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) > 5:
                table = t
                break

        if not table:
            return []

        for i, row in enumerate(table.find_all("tr")[1:], 1):
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 5:
                continue

            team_name = ""
            for c in cells[:4]:
                n = normalize_team(c)
                if n in KBO_TEAMS:
                    team_name = n
                    break
            if not team_name:
                continue

            def safe(val, typ=float):
                try:
                    return typ(val.replace(",", "").replace("-", "0"))
                except:
                    return 0

            standings.append({
                "rank": i,
                "team": team_name,
                "games": safe(cells[2]) if len(cells) > 2 else 0,
                "wins": safe(cells[3]) if len(cells) > 3 else 0,
                "losses": safe(cells[4]) if len(cells) > 4 else 0,
                "draws": safe(cells[5]) if len(cells) > 5 else 0,
                "win_rate": safe(cells[6]) if len(cells) > 6 else 0,
                "gb": cells[7] if len(cells) > 7 else "0",
            })

    except Exception as e:
        logger.warning(f"순위 수집 실패: {e}")
    finally:
        driver.quit()

    return standings


def scrape_standings_from_games() -> list[dict]:
    """수집된 경기 데이터로 순위 계산"""
    games_path = RAW_DIR / "games_raw.csv"
    if not games_path.exists():
        return []

    try:
        import pandas as pd
        games_df = pd.read_csv(games_path, encoding="utf-8-sig")
        games_df["date"] = pd.to_datetime(games_df["date"])
        season_games = games_df[games_df["date"].dt.year == 2026]

        standings = []
        for team in KBO_TEAMS:
            home_g = season_games[season_games["home_team"] == team]
            away_g = season_games[season_games["away_team"] == team]

            wins = (home_g["home_win"] == 1).sum() + (away_g["home_win"] == 0).sum()
            total = len(home_g) + len(away_g)
            losses = total - wins

            standings.append({
                "team": team,
                "wins": int(wins),
                "losses": int(losses),
                "games": int(total),
                "win_rate": round(wins / total, 3) if total > 0 else 0.0,
            })

        standings.sort(key=lambda x: x["win_rate"], reverse=True)
        for i, s in enumerate(standings):
            s["rank"] = i + 1

        return standings
    except Exception as e:
        logger.warning(f"데이터 기반 순위 계산 실패: {e}")
        return []


def scrape_today_schedule_selenium() -> list[dict]:
    """오늘의 경기 일정 (Selenium)"""
    today = date.today()
    driver = get_driver()
    if not driver:
        return []

    games = []
    try:
        url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx"
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "lxml")

        # 게임 박스 파싱
        game_pattern = re.compile(r"([가-힣A-Z]{2,5})(\d{1,2})vs(\d{1,2})([가-힣A-Z]{2,5})")
        all_text = soup.get_text()

        for match in game_pattern.finditer(all_text):
            team_a = normalize_team(match.group(1))
            team_b = normalize_team(match.group(4))
            if team_a in KBO_TEAMS and team_b in KBO_TEAMS and team_a != team_b:
                games.append({
                    "date": today.strftime("%Y%m%d"),
                    "away_team": team_a,
                    "home_team": team_b,
                    "home_pitcher": "미정",
                    "away_pitcher": "미정",
                    "game_time": "17:00",
                })

    except Exception as e:
        logger.warning(f"오늘 경기 수집 실패: {e}")
    finally:
        driver.quit()

    return games


def scrape_kbo_entry_selenium() -> dict[str, list]:
    """KBO 1군 엔트리 (Selenium)"""
    current_roster = scrape_yagoonara_current_roster()
    if current_roster:
        return current_roster

    driver = get_driver()
    if not driver:
        return {}

    lineups = {}
    try:
        driver.get("https://www.koreabaseball.com/Player/Entry1.aspx")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "lxml")

        # 팀별 섹션 파싱
        current_team = None
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                # 팀명 헤더 행
                th = row.find("th", colspan=True)
                if th:
                    t = normalize_team(th.get_text(strip=True))
                    if t in KBO_TEAMS:
                        current_team = t
                        lineups[current_team] = []
                    continue

                if not current_team:
                    continue

                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 3 and cells[0].isdigit() and cells[2]:
                    lineups[current_team].append({
                        "number": cells[0],
                        "position": cells[1],
                        "name": cells[2],
                        "team": current_team,
                    })

        # 대안: div 기반 파싱
        if not lineups:
            for team_key in KBO_TEAMS:
                team_divs = soup.find_all(string=re.compile(f"{'|'.join([KBO_TEAMS[team_key]['name']])}"))
                for txt in team_divs:
                    parent = txt.find_parent()
                    if parent:
                        team_table = parent.find_next("table")
                        if team_table:
                            players = []
                            for row in team_table.find_all("tr")[1:]:
                                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                                if len(cells) >= 3:
                                    players.append({
                                        "number": cells[0],
                                        "position": cells[1],
                                        "name": cells[2],
                                        "team": team_key,
                                    })
                            if players:
                                lineups[team_key] = players

    except Exception as e:
        logger.warning(f"1군 엔트리 수집 실패: {e}")
    finally:
        driver.quit()

    return lineups


def _get_default_entry_for_team(team: str) -> list[dict]:
    """기본 엔트리 (데이터 없을 때)"""
    positions = ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "CL",
                 "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH",
                 "RP", "RP", "RP", "SP", "C", "1B", "2B", "SS", "LF"]
    return [
        {
            "number": str(i + 1),
            "position": positions[i % len(positions)],
            "name": f"{team} 선수{i+1}",
            "team": team,
        }
        for i in range(28)
    ]


def get_full_lineup_data() -> dict:
    """전체 라인업/순위/일정 수집"""

    # 1군 엔트리
    logger.info("1군 엔트리 수집 중...")
    entry = scrape_kbo_entry_selenium()

    # 순위 (수집된 경기 데이터 우선, 없으면 Selenium)
    logger.info("순위 수집 중...")
    standings = scrape_standings_from_games()
    if not standings:
        standings = scrape_standings_selenium()

    # 오늘 경기
    logger.info("오늘 경기 일정 수집 중...")
    today_games = scrape_today_schedule_selenium()

    result = {
        "entry": entry,
        "today_games": today_games,
        "standings": standings,
        "updated_at": datetime.now().isoformat(),
    }

    out_path = RAW_DIR / "lineup_data.json"

    def json_serializer(obj):
        import numpy as np
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return str(obj)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=json_serializer)
    logger.info(f"라인업 데이터 저장: {out_path}")

    return result


if __name__ == "__main__":
    data = get_full_lineup_data()
    print(f"팀 수: {len(data['entry'])}")
    print(f"오늘 경기: {len(data['today_games'])}")
    print(f"순위: {len(data['standings'])}팀")
