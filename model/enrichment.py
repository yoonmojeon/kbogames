"""
추가 컨텍스트 피처

외부 상세 데이터가 있으면 우선 사용하고, 없으면 경기 이전 시점의 팀 성적만으로
누수 없는 프록시 값을 만든다. 이렇게 해두면 데이터 수집이 실패해도 학습 파이프라인이
깨지지 않고, 나중에 실제 과거 선발/라인업/날씨 CSV를 병합하기 쉽다.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RAW_DIR

logger = logging.getLogger(__name__)


STADIUM_COORDS = {
    "잠실": (37.5122, 127.0719),
    "고척": (37.4982, 126.8671),
    "문학": (37.4369, 126.6933),
    "수원": (37.2998, 127.0097),
    "대전": (36.3170, 127.4280),
    "대구": (35.8410, 128.6816),
    "광주": (35.1682, 126.8891),
    "사직": (35.1940, 129.0615),
    "창원": (35.2225, 128.5822),
    "울산": (35.5323, 129.2656),
    "포항": (36.0081, 129.3594),
    "청주": (36.6372, 127.4749),
}


def normalize_stadium(stadium: str) -> str:
    stadium = str(stadium or "").strip()
    for key in STADIUM_COORDS:
        if key in stadium:
            return key
    return stadium


def _safe_float(value, default: float) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def seasonal_weather_proxy(game_date: pd.Timestamp, stadium: str = "") -> dict:
    """날씨 API가 없을 때 사용하는 계절성 기반 구장 환경 프록시."""
    day = int(pd.Timestamp(game_date).dayofyear)
    temp = 18 + 10 * math.sin(2 * math.pi * (day - 105) / 365)
    humidity = 62 + 12 * math.sin(2 * math.pi * (day - 170) / 365)
    wind = 2.4 + 0.8 * math.sin(2 * math.pi * (day + 30) / 365)
    rain = max(0.0, 3.0 * math.sin(2 * math.pi * (day - 150) / 365))

    dome = 1 if normalize_stadium(stadium) == "고척" else 0
    if dome:
        temp, humidity, wind, rain = 22.0, 45.0, 0.2, 0.0

    return {
        "weather_temp_c": round(temp, 2),
        "weather_humidity": round(humidity, 2),
        "weather_wind_mps": round(wind, 2),
        "weather_rain_mm": round(rain, 2),
        "weather_is_dome": dome,
    }


def load_external_weather_context() -> pd.DataFrame:
    """선택 파일: data/raw/weather_context.csv(date, stadium, temp_c, humidity, wind_mps, rain_mm)."""
    path = RAW_DIR / "weather_context.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
        df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
        if "stadium" not in df.columns:
            df["stadium"] = ""
        df["stadium_key"] = df["stadium"].apply(normalize_stadium)
        return df
    except Exception as e:
        logger.warning(f"날씨 컨텍스트 로드 실패: {e}")
        return pd.DataFrame()


def build_game_context_features(games: pd.DataFrame) -> pd.DataFrame:
    """경기별 선발투수/라인업/날씨 컨텍스트 피처를 생성."""
    df = games.copy().sort_values("date").reset_index()
    teams = pd.concat([df["home_team"], df["away_team"]]).dropna().unique()
    team_logs: dict[str, list[dict]] = {team: [] for team in teams}
    pitcher_logs: dict[str, list[dict]] = {}
    weather_df = load_external_weather_context()

    rows = []
    for _, game in df.iterrows():
        game_date = pd.Timestamp(game["date"])
        home = game["home_team"]
        away = game["away_team"]
        stadium = game.get("stadium", "")
        stadium_key = normalize_stadium(stadium)

        home_prev = pd.DataFrame(team_logs.get(home, []))
        away_prev = pd.DataFrame(team_logs.get(away, []))

        def team_proxy(prev: pd.DataFrame, side: str) -> dict:
            if prev.empty:
                return {
                    f"{side}_lineup_ops_proxy": 0.700,
                    f"{side}_lineup_obp_proxy": 0.330,
                    f"{side}_lineup_power_proxy": 0.120,
                    f"{side}_bullpen_pitch_count_proxy_3d": 0.0,
                }
            recent = prev.tail(10)
            runs_scored = _safe_float(recent["runs_scored"].mean(), 4.5)
            runs_allowed_3d = prev[prev["date"] >= game_date - pd.Timedelta(days=3)]["runs_allowed"].sum()
            games_3d = len(prev[prev["date"] >= game_date - pd.Timedelta(days=3)])
            return {
                f"{side}_lineup_ops_proxy": round(np.clip(0.610 + runs_scored * 0.035, 0.560, 0.920), 4),
                f"{side}_lineup_obp_proxy": round(np.clip(0.285 + runs_scored * 0.010, 0.280, 0.390), 4),
                f"{side}_lineup_power_proxy": round(np.clip((runs_scored - 3.2) * 0.045, 0.020, 0.260), 4),
                f"{side}_bullpen_pitch_count_proxy_3d": round(games_3d * 28 + runs_allowed_3d * 4, 2),
            }

        def pitcher_proxy(team: str, pitcher: str, side: str, team_prev: pd.DataFrame) -> dict:
            pitcher = str(pitcher or "").strip()
            history = pd.DataFrame(pitcher_logs.get(f"{team}:{pitcher}", [])) if pitcher else pd.DataFrame()
            if not history.empty:
                recent = history.tail(8)
                innings = max(_safe_float(recent["innings_proxy"].mean(), 5.0), 1.0)
                era = _safe_float(recent["runs_allowed"].sum() / max(recent["innings_proxy"].sum(), 1.0) * 9, 4.5)
                whip = _safe_float(1.15 + era / 18, 1.4)
                quality = _safe_float((4.5 - era) * 0.18 + (innings - 5.0) * 0.10, 0.0)
            elif not team_prev.empty:
                recent = team_prev.tail(10)
                era = _safe_float(recent["runs_allowed"].mean() * 9 / 8.8, 4.5)
                innings = 4.8
                whip = _safe_float(1.10 + era / 20, 1.4)
                quality = _safe_float((4.5 - era) * 0.12, 0.0)
            else:
                era, innings, whip, quality = 4.5, 4.8, 1.4, 0.0
            return {
                f"{side}_starter_era_proxy": round(float(np.clip(era, 1.5, 9.5)), 3),
                f"{side}_starter_whip_proxy": round(float(np.clip(whip, 0.8, 2.2)), 3),
                f"{side}_starter_innings_proxy": round(float(np.clip(innings, 2.5, 7.5)), 3),
                f"{side}_starter_quality_proxy": round(float(np.clip(quality, -1.2, 1.2)), 3),
            }

        weather = seasonal_weather_proxy(game_date, stadium)
        if not weather_df.empty:
            match = weather_df[
                (weather_df["date"] == game_date.date().isoformat()) &
                (weather_df["stadium_key"] == stadium_key)
            ]
            if not match.empty:
                w = match.iloc[0]
                weather = {
                    "weather_temp_c": _safe_float(w.get("temp_c"), weather["weather_temp_c"]),
                    "weather_humidity": _safe_float(w.get("humidity"), weather["weather_humidity"]),
                    "weather_wind_mps": _safe_float(w.get("wind_mps"), weather["weather_wind_mps"]),
                    "weather_rain_mm": _safe_float(w.get("rain_mm"), weather["weather_rain_mm"]),
                    "weather_is_dome": weather["weather_is_dome"],
                }

        feat = {
            "index": int(game["index"]),
            **team_proxy(home_prev, "home"),
            **team_proxy(away_prev, "away"),
            **pitcher_proxy(home, game.get("home_pitcher", ""), "home", home_prev),
            **pitcher_proxy(away, game.get("away_pitcher", ""), "away", away_prev),
            **weather,
        }
        feat["diff_lineup_ops_proxy"] = feat["home_lineup_ops_proxy"] - feat["away_lineup_ops_proxy"]
        feat["diff_lineup_obp_proxy"] = feat["home_lineup_obp_proxy"] - feat["away_lineup_obp_proxy"]
        feat["diff_starter_quality_proxy"] = feat["home_starter_quality_proxy"] - feat["away_starter_quality_proxy"]
        feat["diff_bullpen_pitch_count_proxy_3d"] = (
            feat["home_bullpen_pitch_count_proxy_3d"] - feat["away_bullpen_pitch_count_proxy_3d"]
        )
        rows.append(feat)

        home_score = _safe_float(game.get("home_score"), 0.0)
        away_score = _safe_float(game.get("away_score"), 0.0)
        team_logs.setdefault(home, []).append({
            "date": game_date,
            "runs_scored": home_score,
            "runs_allowed": away_score,
        })
        team_logs.setdefault(away, []).append({
            "date": game_date,
            "runs_scored": away_score,
            "runs_allowed": home_score,
        })
        if str(game.get("home_pitcher", "")).strip():
            pitcher_logs.setdefault(f"{home}:{game.get('home_pitcher')}", []).append({
                "runs_allowed": away_score,
                "innings_proxy": 5.0 if away_score <= 5 else 4.2,
            })
        if str(game.get("away_pitcher", "")).strip():
            pitcher_logs.setdefault(f"{away}:{game.get('away_pitcher')}", []).append({
                "runs_allowed": home_score,
                "innings_proxy": 5.0 if home_score <= 5 else 4.2,
            })

    return pd.DataFrame(rows).set_index("index").sort_index()
