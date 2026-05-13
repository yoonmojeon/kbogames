"""
Statiz.co.kr 팀/선수 통계 스크래퍼
- 팀 타격/투구 시즌 성적
- 개인 투수 성적
- 개인 타자 성적
"""
import re
import time
import logging
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    RAW_DIR, HEADERS, REQUEST_DELAY, REQUEST_TIMEOUT,
    SCRAPE_START_YEAR, SCRAPE_END_YEAR, TEAM_NAME_MAP
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://statiz.co.kr"


def normalize_team(name: str) -> str:
    name = name.strip().replace(" ", "")
    return TEAM_NAME_MAP.get(name, name)


def _get_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.warning(f"요청 실패 {url}: {e}")
        return None


def _parse_stat_table(soup: BeautifulSoup) -> pd.DataFrame | None:
    """통계 테이블 파싱"""
    table = soup.find("table", id=re.compile(r"(tblStat|stat|table)"))
    if not table:
        tables = soup.find_all("table")
        table = tables[0] if tables else None
    if not table:
        return None

    headers = []
    header_row = table.find("thead")
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

    rows = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if cells and any(c for c in cells):
            rows.append(cells)

    if not rows:
        return None

    if headers and len(headers) == len(rows[0]):
        df = pd.DataFrame(rows, columns=headers)
    elif headers:
        df = pd.DataFrame(rows)
        df.columns = headers[:len(df.columns)] if len(headers) >= len(df.columns) else list(range(len(df.columns)))
    else:
        df = pd.DataFrame(rows)

    return df


def scrape_team_batting(year: int) -> pd.DataFrame:
    """팀 타격 통계"""
    url = f"{BASE_URL}/stat.php?opt=0&sopt=0&year={year}"
    soup = _get_soup(url)
    if not soup:
        return pd.DataFrame()

    df = _parse_stat_table(soup)
    if df is None or df.empty:
        return pd.DataFrame()

    df["year"] = year
    # 팀명 정규화
    for col in df.columns[:3]:
        if df[col].astype(str).str.contains("기아|LG|SSG|KT|NC|두산|롯데|삼성|한화|키움").any():
            df = df.rename(columns={col: "team"})
            df["team"] = df["team"].apply(normalize_team)
            break

    return df


def scrape_team_pitching(year: int) -> pd.DataFrame:
    """팀 투구 통계"""
    url = f"{BASE_URL}/stat.php?opt=1&sopt=0&year={year}"
    soup = _get_soup(url)
    if not soup:
        return pd.DataFrame()

    df = _parse_stat_table(soup)
    if df is None or df.empty:
        return pd.DataFrame()

    df["year"] = year
    for col in df.columns[:3]:
        if df[col].astype(str).str.contains("기아|LG|SSG|KT|NC|두산|롯데|삼성|한화|키움").any():
            df = df.rename(columns={col: "team"})
            df["team"] = df["team"].apply(normalize_team)
            break

    return df


def scrape_pitcher_stats(year: int) -> pd.DataFrame:
    """개인 투수 성적"""
    all_rows = []
    page = 1

    while True:
        url = f"{BASE_URL}/stat.php?opt=1&sopt=1&year={year}&pos=pitcher&page={page}"
        soup = _get_soup(url)
        if not soup:
            break

        df = _parse_stat_table(soup)
        if df is None or df.empty:
            break

        # 이름 컬럼 찾기
        name_col = None
        for col in df.columns[:5]:
            sample = df[col].dropna().head(5).astype(str)
            if sample.str.match(r"^[가-힣]{2,4}$").any():
                name_col = col
                break

        if name_col is None:
            break

        df = df.rename(columns={name_col: "pitcher_name"})
        df["year"] = year
        all_rows.append(df)

        # 다음 페이지 확인
        next_btn = soup.find("a", string=re.compile(r"다음|next", re.I))
        if not next_btn:
            break
        page += 1
        if page > 20:
            break
        time.sleep(0.5)

    if not all_rows:
        return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True)


def scrape_batter_stats(year: int) -> pd.DataFrame:
    """개인 타자 성적"""
    all_rows = []
    page = 1

    while True:
        url = f"{BASE_URL}/stat.php?opt=0&sopt=1&year={year}&pos=batter&page={page}"
        soup = _get_soup(url)
        if not soup:
            break

        df = _parse_stat_table(soup)
        if df is None or df.empty:
            break

        name_col = None
        for col in df.columns[:5]:
            sample = df[col].dropna().head(5).astype(str)
            if sample.str.match(r"^[가-힣]{2,4}$").any():
                name_col = col
                break

        if name_col is None:
            break

        df = df.rename(columns={name_col: "batter_name"})
        df["year"] = year
        all_rows.append(df)

        next_btn = soup.find("a", string=re.compile(r"다음|next", re.I))
        if not next_btn:
            break
        page += 1
        if page > 20:
            break
        time.sleep(0.5)

    if not all_rows:
        return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True)


def collect_all_stats(start_year: int = SCRAPE_START_YEAR,
                      end_year: int = SCRAPE_END_YEAR) -> dict[str, pd.DataFrame]:
    """전체 기간 통계 수집"""
    team_batting_list = []
    team_pitching_list = []
    pitcher_list = []
    batter_list = []

    for year in range(start_year, end_year + 1):
        logger.info(f"통계 수집: {year}년")

        tb = scrape_team_batting(year)
        if not tb.empty:
            team_batting_list.append(tb)
        time.sleep(REQUEST_DELAY)

        tp = scrape_team_pitching(year)
        if not tp.empty:
            team_pitching_list.append(tp)
        time.sleep(REQUEST_DELAY)

        p = scrape_pitcher_stats(year)
        if not p.empty:
            pitcher_list.append(p)
        time.sleep(REQUEST_DELAY)

        b = scrape_batter_stats(year)
        if not b.empty:
            batter_list.append(b)
        time.sleep(REQUEST_DELAY)

    results = {}

    if team_batting_list:
        results["team_batting"] = pd.concat(team_batting_list, ignore_index=True)
        results["team_batting"].to_csv(RAW_DIR / "team_batting.csv", index=False, encoding="utf-8-sig")
        logger.info(f"팀 타격: {len(results['team_batting'])}행")

    if team_pitching_list:
        results["team_pitching"] = pd.concat(team_pitching_list, ignore_index=True)
        results["team_pitching"].to_csv(RAW_DIR / "team_pitching.csv", index=False, encoding="utf-8-sig")
        logger.info(f"팀 투구: {len(results['team_pitching'])}행")

    if pitcher_list:
        results["pitchers"] = pd.concat(pitcher_list, ignore_index=True)
        results["pitchers"].to_csv(RAW_DIR / "pitchers.csv", index=False, encoding="utf-8-sig")
        logger.info(f"투수: {len(results['pitchers'])}행")

    if batter_list:
        results["batters"] = pd.concat(batter_list, ignore_index=True)
        results["batters"].to_csv(RAW_DIR / "batters.csv", index=False, encoding="utf-8-sig")
        logger.info(f"타자: {len(results['batters'])}행")

    return results


if __name__ == "__main__":
    results = collect_all_stats()
    for k, v in results.items():
        print(f"{k}: {len(v)}행, 컬럼: {list(v.columns[:5])}")
