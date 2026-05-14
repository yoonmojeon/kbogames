"""
KBO 경기 결과 스크래퍼
- KBO 공식 사이트 Selenium 기반 수집
- 백업: requests 기반 파싱
"""
import re
import time
import json
import logging
from datetime import datetime, date
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    RAW_DIR, HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT,
    SCRAPE_START_YEAR, SCRAPE_END_YEAR, SCRAPE_END_DATE, TEAM_NAME_MAP
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

KBO_SCHEDULE_URL = "https://www.koreabaseball.com/Schedule/Schedule.aspx"


def normalize_team(name: str) -> str:
    name = name.strip().replace(" ", "").replace("\xa0", "")
    return TEAM_NAME_MAP.get(name, name)


def get_selenium_driver():
    """헤드리스 Chrome 드라이버 초기화"""
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
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        options.add_argument("--lang=ko-KR")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logger.warning(f"Selenium 초기화 실패: {e}")
        return None


def scrape_kbo_schedule_selenium(year: int, month: int, driver=None) -> list[dict]:
    """Selenium으로 KBO 공식 스케줄 페이지 스크래핑"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC

    own_driver = driver is None
    if own_driver:
        driver = get_selenium_driver()
        if not driver:
            return []

    games = []
    try:
        driver.get(KBO_SCHEDULE_URL)
        wait = WebDriverWait(driver, 10)

        # 연도/월 선택
        try:
            year_sel = Select(wait.until(EC.presence_of_element_located((By.ID, "ddlYear"))))
            year_sel.select_by_value(str(year))
            time.sleep(0.8)

            month_sel = Select(driver.find_element(By.ID, "ddlMonth"))
            month_sel.select_by_value(f"{month:02d}")
            time.sleep(1.5)
        except Exception:
            # ID가 다른 경우 시도
            try:
                selects = driver.find_elements(By.TAG_NAME, "select")
                for sel in selects:
                    opts = [o.get_attribute("value") for o in sel.find_elements(By.TAG_NAME, "option")]
                    if str(year) in opts:
                        Select(sel).select_by_value(str(year))
                        time.sleep(0.8)
                        break
            except Exception:
                pass

        # 스케줄 테이블 파싱
        soup = BeautifulSoup(driver.page_source, "lxml")
        games = _parse_kbo_schedule_html(soup, year)

    except Exception as e:
        logger.warning(f"Selenium 스크래핑 실패 {year}-{month}: {e}")
    finally:
        if own_driver and driver:
            driver.quit()

    return games


# 팀별 홈 구장 매핑
TEAM_HOME_STADIUMS = {
    "수원": "KT",
    "인천": "SSG",
    "대구": "삼성",
    "창원": "NC",
    "부산": "롯데",
    "사직": "롯데",
    "잠실": None,        # LG & 두산 공동
    "고척": "키움",
    "광주": "KIA",
    "대전": "한화",
    "청주": "한화",
}


def _determine_home_away(team_a: str, score_a: int,
                          team_b: str, score_b: int,
                          stadium: str) -> dict | None:
    """
    팀A{scoreA}vs{scoreB}팀B 형식과 구장 정보로 홈/원정 결정
    KBO 공식 사이트 형식: 원정팀{원정점수}vs{홈점수}홈팀
    (예: 롯데10vs7SSG 인천 = 롯데(원정)10, SSG(홈)7)
    """
    home_team_by_stadium = TEAM_HOME_STADIUMS.get(stadium)

    if home_team_by_stadium == team_b:
        # team_b가 홈 = 원정(A)점수 vs 홈(B)점수 -> away first
        home_team, away_team = team_b, team_a
        home_score, away_score = score_b, score_a
    elif home_team_by_stadium == team_a:
        # team_a가 홈 = 홈(A)점수 vs 원정(B)점수 -> home first
        home_team, away_team = team_a, team_b
        home_score, away_score = score_a, score_b
    elif stadium == "잠실":
        # 잠실: LG 또는 두산이 홈
        if team_b in ("LG", "두산"):
            home_team, away_team = team_b, team_a
            home_score, away_score = score_b, score_a
        elif team_a in ("LG", "두산"):
            home_team, away_team = team_a, team_b
            home_score, away_score = score_a, score_b
        else:
            # 기본: right=home
            home_team, away_team = team_b, team_a
            home_score, away_score = score_b, score_a
    else:
        # 구장 미상 - 오른쪽 팀을 홈으로 가정
        home_team, away_team = team_b, team_a
        home_score, away_score = score_b, score_a

    if home_score == away_score:
        return None  # 무승부

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "home_win": int(home_score > away_score),
    }


def _parse_kbo_schedule_html(soup: BeautifulSoup, year: int, respect_cutoff: bool = True) -> list[dict]:
    """
    KBO 공식 사이트 스케줄 테이블 파싱
    형식: 팀A{scoreA}vs{scoreB}팀B (예: NC1vs5LG)
    """
    games = []
    current_date = None
    current_time = ""

    # 가장 많은 행의 테이블 선택
    tables = soup.find_all("table")
    schedule_table = max(tables, key=lambda t: len(t.find_all("tr")), default=None)
    if not schedule_table:
        return []

    rows = schedule_table.find_all("tr")

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]
        classes = [" ".join(c.get("class", [])) for c in cells]

        # 날짜 행 감지 (class="day" 또는 MM.DD 패턴)
        if "day" in classes[0] or (texts[0] and re.match(r"\d{1,2}\.\d{1,2}", texts[0])):
            m = re.match(r"(\d{1,2})\.(\d{1,2})", texts[0])
            if m:
                current_date = f"{year}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
            current_time = texts[1] if len(texts) > 1 and re.match(r"\d{1,2}:\d{2}", texts[1]) else ""
        elif texts[0] and re.match(r"\d{1,2}:\d{2}", texts[0]):
            current_time = texts[0]

        if not current_date:
            continue
        if respect_cutoff and current_date > SCRAPE_END_DATE:
            continue

        # 경기 결과/일정 셀 찾기
        # 완료: 삼성 3 vs 5 LG / NC5vs13LG
        completed_pattern = re.compile(
            r"^([가-힣A-Z]{2,5})\s*(\d{1,2})\s*vs\s*(\d{1,2})\s*([가-힣A-Z]{2,5})$"
        )
        scheduled_pattern = re.compile(
            r"^([가-힣A-Z]{2,5})\s*vs\s*([가-힣A-Z]{2,5})$"
        )

        for i, text in enumerate(texts):
            text = text.replace("\xa0", " ").strip()
            completed = completed_pattern.match(text)
            scheduled = scheduled_pattern.match(text)
            if not completed and not scheduled:
                continue

            if completed:
                team_a = normalize_team(completed.group(1))
                score_a = int(completed.group(2))
                score_b = int(completed.group(3))
                team_b = normalize_team(completed.group(4))
            else:
                team_a = normalize_team(scheduled.group(1))
                score_a = None
                score_b = None
                team_b = normalize_team(scheduled.group(2))

            if not team_a or not team_b or team_a == team_b:
                continue

            # 구장 정보 (뒤에서 2번째 컬럼)
            stadium = texts[-2] if len(texts) >= 2 else ""
            preview_url = ""
            game_id = ""
            for link in row.find_all("a"):
                href = link.get("href", "")
                if "section=START_PIT" in href or "gameId=" in href:
                    preview_url = href
                    match_game_id = re.search(r"gameId=([^&]+)", href)
                    game_id = match_game_id.group(1) if match_game_id else ""
                    break

            if completed:
                result = _determine_home_away(team_a, score_a, team_b, score_b, stadium)
                if not result:
                    continue
            else:
                # 일정만 있는 경우 KBO 공식 표기는 보통 원정 vs 홈 순서다.
                home_team_by_stadium = TEAM_HOME_STADIUMS.get(stadium)
                if home_team_by_stadium == team_a:
                    home_team, away_team = team_a, team_b
                elif home_team_by_stadium == team_b:
                    home_team, away_team = team_b, team_a
                elif stadium == "잠실":
                    home_team = team_b if team_b in ("LG", "두산") else team_a
                    away_team = team_a if home_team == team_b else team_b
                else:
                    home_team, away_team = team_b, team_a
                result = {
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": None,
                    "away_score": None,
                    "home_win": None,
                }

            games.append({
                "date": current_date,
                **result,
                "home_pitcher": "",
                "away_pitcher": "",
                "stadium": stadium,
                "game_time": current_time,
                "status": "completed" if completed else "scheduled",
                "game_id": game_id,
                "preview_url": preview_url,
            })
            break  # 한 행에 하나의 경기만

    return games


def scrape_kbo_gamecenter_api(year: int, month: int) -> list[dict]:
    """KBO 게임센터 내부 API 호출"""
    session = requests.Session()
    session.headers.update(HEADERS)

    games = []

    # 월의 모든 날짜 순회
    import calendar
    _, last_day = calendar.monthrange(year, month)

    for day in range(1, last_day + 1):
        game_date = f"{year}{month:02d}{day:02d}"
        if game_date > SCRAPE_END_DATE.replace("-", ""):
            break

        # 게임센터 일별 조회
        url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx"
        params = {"date": game_date}

        try:
            r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "lxml")

            # 경기 결과 파싱
            day_games = _parse_gamecenter_html(soup, f"{year}-{month:02d}-{day:02d}")
            if day_games:
                games.extend(day_games)

        except Exception as e:
            logger.debug(f"게임센터 오류 {game_date}: {e}")

        time.sleep(0.3)

    return games


def _parse_gamecenter_html(soup: BeautifulSoup, game_date: str) -> list[dict]:
    """게임센터 HTML에서 경기 결과 파싱"""
    games = []

    # 경기 박스 찾기
    game_boxes = soup.find_all(class_=re.compile(r"(game|match|schedule)", re.I))

    for box in game_boxes:
        text = box.get_text(separator=" ")

        # 점수 패턴 찾기
        score_match = re.search(r"(\w+)\s+(\d+)\s*[:\-]\s*(\d+)\s+(\w+)", text)
        if score_match:
            # 팀과 점수 추출 시도
            teams_in_box = []
            for team_key in TEAM_NAME_MAP:
                if team_key in text:
                    normalized = TEAM_NAME_MAP[team_key]
                    if normalized not in teams_in_box:
                        teams_in_box.append(normalized)

            # 점수 찾기
            scores = re.findall(r"\b(\d{1,2})\b", text)
            if len(teams_in_box) >= 2 and len(scores) >= 2:
                # 간단한 추측: 홈팀은 오른쪽
                pass  # 더 복잡한 로직 필요

    # 테이블 기반 파싱
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            score_idx = next(
                (i for i, t in enumerate(cells) if re.match(r"^\d+:\d+$", t)),
                None
            )
            if score_idx and score_idx > 0 and score_idx + 1 < len(cells):
                m = re.match(r"(\d+):(\d+)", cells[score_idx])
                if m:
                    away_score, home_score = int(m.group(1)), int(m.group(2))
                    if home_score != away_score:
                        away_team = normalize_team(cells[score_idx - 1])
                        home_team = normalize_team(cells[score_idx + 1])
                        if away_team and home_team and away_team != home_team:
                            games.append({
                                "date": game_date,
                                "home_team": home_team,
                                "away_team": away_team,
                                "home_score": home_score,
                                "away_score": away_score,
                                "home_win": int(home_score > away_score),
                                "home_pitcher": "",
                                "away_pitcher": "",
                            })

    return games


def scrape_with_selenium_batch(year: int, month: int, driver=None, respect_cutoff: bool = True) -> list[dict]:
    """Selenium 배치 스크래핑 (연도/월 선택)"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC

    own_driver = driver is None
    if own_driver:
        driver = get_selenium_driver()
        if not driver:
            return []

    games = []
    try:
        driver.get(KBO_SCHEDULE_URL)
        time.sleep(2)

        # 연도 선택
        try:
            year_sel = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "select[id*='Year'], select[name*='Year']"))
            )
            Select(year_sel).select_by_value(str(year))
            time.sleep(1)
        except Exception:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel in selects:
                try:
                    opts = [o.get_attribute("value") for o in sel.find_elements(By.TAG_NAME, "option")]
                    if str(year) in opts:
                        Select(sel).select_by_value(str(year))
                        time.sleep(1)
                        break
                except Exception:
                    pass

        # 월 선택
        try:
            month_sel = driver.find_element(By.CSS_SELECTOR, "select[id*='Month'], select[name*='Month']")
            month_val = f"{month:02d}"
            try:
                Select(month_sel).select_by_value(month_val)
            except Exception:
                Select(month_sel).select_by_value(str(month))
            time.sleep(2)
        except Exception:
            pass

        soup = BeautifulSoup(driver.page_source, "lxml")
        games = _parse_kbo_schedule_html(soup, year, respect_cutoff=respect_cutoff)
        logger.info(f"  Selenium 수집: {year}/{month} -> {len(games)}경기")

    except Exception as e:
        logger.warning(f"Selenium 배치 실패 {year}/{month}: {e}")
    finally:
        if own_driver and driver:
            driver.quit()

    return games


def scrape_gamecenter_day_boxes(game_date: str) -> list[dict]:
    """
    게임센터 일별 페이지에서 경기 목록 추출 (requests).
    월간 스케줄 파싱이 비어 있을 때 폴백으로 사용한다.
    """
    ymd = game_date.replace("-", "")
    url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?date={ymd}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"게임센터 일별 요청 실패({game_date}): {e}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    games: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for box in soup.find_all(class_=re.compile(r"(game|schedule|match)", re.I)):
        text = box.get_text(separator=" ", strip=True)
        teams_found: list[str] = []
        for team_key, team_val in TEAM_NAME_MAP.items():
            if team_key in text:
                if team_val not in teams_found:
                    teams_found.append(team_val)
        if len(teams_found) < 2:
            continue

        preview_url = ""
        game_id = ""
        for link in box.find_all("a", href=True):
            href = link.get("href", "")
            if "gameId=" in href or "START_PIT" in href:
                preview_url = href
                m_gid = re.search(r"gameId=([^&]+)", href)
                game_id = m_gid.group(1) if m_gid else ""
                break

        away_team, home_team = teams_found[0], teams_found[1]
        key = (home_team, away_team)
        if key in seen:
            continue
        seen.add(key)

        games.append({
            "date": game_date,
            "away_team": away_team,
            "home_team": home_team,
            "home_score": None,
            "away_score": None,
            "home_win": None,
            "home_pitcher": "",
            "away_pitcher": "",
            "stadium": "",
            "game_time": "",
            "status": "scheduled",
            "game_id": game_id,
            "preview_url": preview_url,
        })

    if games:
        logger.info(f"게임센터 일별 폴백: {game_date} -> {len(games)}경기")
    return games


def scrape_games_by_date(game_date: str) -> list[dict]:
    """특정 날짜(YYYY-MM-DD)의 KBO 경기 일정/결과를 실시간 조회"""
    dt = datetime.strptime(game_date, "%Y-%m-%d")
    driver = get_selenium_driver()
    if not driver:
        return scrape_gamecenter_day_boxes(game_date)
    try:
        games = scrape_with_selenium_batch(dt.year, dt.month, driver, respect_cutoff=False)
        filtered = [g for g in games if g.get("date") == game_date]
        if filtered:
            return filtered
        logger.info(f"월간 스케줄에서 {game_date} 경기 없음, 게임센터 일별 폴백 시도")
        return scrape_gamecenter_day_boxes(game_date)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def collect_all_games(start_year: int = SCRAPE_START_YEAR,
                      end_year: int = SCRAPE_END_YEAR) -> pd.DataFrame:
    """전체 기간 경기 결과 수집"""
    all_games = []
    end_date = datetime.strptime(SCRAPE_END_DATE, "%Y-%m-%d").date()

    # Selenium 드라이버 초기화 (재사용)
    logger.info("Selenium 드라이버 초기화 중...")
    driver = get_selenium_driver()
    use_selenium = driver is not None

    if not use_selenium:
        logger.warning("Selenium 없음 - requests 기반으로 시도합니다")

    try:
        for year in range(start_year, end_year + 1):
            for month in range(3, 12):  # KBO: 3~11월
                # 수집 범위 체크
                check_date = date(year, month, 1)
                if check_date > end_date:
                    break

                logger.info(f"수집 중: {year}년 {month}월")
                games = []

                if use_selenium:
                    games = scrape_with_selenium_batch(year, month, driver)

                if not games:
                    # 게임센터 API 시도
                    games = scrape_kbo_gamecenter_api(year, month)

                if games:
                    all_games.extend(games)
                    logger.info(f"  -> {len(games)}경기 수집")
                else:
                    logger.warning(f"  -> {year}/{month}: 데이터 없음")

                time.sleep(REQUEST_DELAY)

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    if not all_games:
        logger.error("수집된 데이터 없음")
        return pd.DataFrame()

    df = pd.DataFrame(all_games)
    df = df.drop_duplicates(subset=["date", "home_team", "away_team"])
    df = df[df["home_win"].isin([0, 1])]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # KBO 팀만 필터
    from config import KBO_TEAMS
    valid_teams = set(KBO_TEAMS.keys())
    df = df[df["home_team"].isin(valid_teams) & df["away_team"].isin(valid_teams)]

    out_path = RAW_DIR / "games_raw.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"저장 완료: {out_path} ({len(df):,}경기)")
    return df


def get_today_schedule() -> list[dict]:
    """오늘의 경기 일정 수집"""
    games = []

    # Selenium으로 오늘 경기 수집
    driver = get_selenium_driver()
    if driver:
        try:
            driver.get(KBO_SCHEDULE_URL)
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, "lxml")
            today_str = date.today().strftime("%Y-%m-%d")
            year = date.today().year

            all_games = _parse_kbo_schedule_html(soup, year)
            games = [g for g in all_games if g.get("date") == today_str]
        finally:
            driver.quit()

    # 오늘 날짜가 없으면 예정 경기 반환
    if not games:
        games = _get_scheduled_games()

    return games


def _get_scheduled_games() -> list[dict]:
    """KBO 게임센터에서 오늘 예정 경기"""
    today_iso = date.today().isoformat()
    games = scrape_gamecenter_day_boxes(today_iso)
    if not games:
        return []
    for g in games:
        g.setdefault("home_pitcher", "미정")
        g.setdefault("away_pitcher", "미정")
    return games


if __name__ == "__main__":
    df = collect_all_games(2022, 2026)
    print(df.tail(10))
    print(f"\n총 {len(df):,}경기 수집")
