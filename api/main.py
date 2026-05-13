"""
KBO 승부예측 FastAPI 서버
"""
import sys
import json
import logging
import re
import numpy as np
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    MODEL_DIR, RAW_DIR, PROCESSED_DIR,
    KBO_TEAMS, SCRAPE_END_DATE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="KBO 승부예측 AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (프론트엔드)
FRONTEND_BUILD = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_BUILD.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_BUILD / "assets")), name="assets")


# ===== 전역 모델/데이터 =====
ensemble = None
feature_cols = None
features_df = None
games_df = None
standings_cache = {"data": [], "updated_at": None}


def get_live_standings(force: bool = False) -> list[dict]:
    """KBO 공식 최신 순위를 가져오고 짧게 캐시한다."""
    now = datetime.now()
    cached_at = standings_cache.get("updated_at")
    if (
        not force and standings_cache.get("data") and cached_at and
        (now - cached_at).total_seconds() < 600
    ):
        return standings_cache["data"]

    try:
        from scraper.lineup_scraper import scrape_kbo_official_standings
        standings = scrape_kbo_official_standings()
        if standings:
            standings_cache["data"] = standings
            standings_cache["updated_at"] = now
            return standings
    except Exception as e:
        logger.warning(f"실시간 순위 수집 실패: {e}")

    # 캐시/파일/로컬 계산 순으로 폴백
    if standings_cache.get("data"):
        return standings_cache["data"]

    try:
        lineup_path = RAW_DIR / "lineup_data.json"
        if lineup_path.exists():
            with open(lineup_path, encoding="utf-8") as f:
                data = json.load(f)
            standings = data.get("standings", [])
            if standings:
                return standings
    except Exception:
        pass

    return calculate_standings_from_games()


def load_models_and_data():
    global ensemble, feature_cols, features_df, games_df

    # 앙상블 모델 로드
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "model"))
        from ensemble import KBOEnsemble, load_ensemble_config
        weights = load_ensemble_config()
        ensemble = KBOEnsemble(weights=weights).load()
        feature_cols = ensemble.feature_cols
        logger.info("앙상블 모델 로드 완료")
    except Exception as e:
        logger.warning(f"모델 로드 실패: {e}")

    # 피처 데이터 로드
    try:
        features_path = PROCESSED_DIR / "features.csv"
        if features_path.exists():
            import pandas as pd
            features_df = pd.read_csv(features_path, encoding="utf-8-sig")
            features_df["date"] = pd.to_datetime(features_df["date"])
            logger.info(f"피처 데이터 로드: {len(features_df):,}행")
    except Exception as e:
        logger.warning(f"피처 데이터 로드 실패: {e}")

    # 경기 원시 데이터 로드
    try:
        games_path = RAW_DIR / "games_raw.csv"
        if games_path.exists():
            import pandas as pd
            games_df = pd.read_csv(games_path, encoding="utf-8-sig")
            games_df["date"] = pd.to_datetime(games_df["date"])
            logger.info(f"경기 데이터 로드: {len(games_df):,}행")
    except Exception as e:
        logger.warning(f"경기 데이터 로드 실패: {e}")


@app.on_event("startup")
async def startup_event():
    load_models_and_data()


# ===== Pydantic 모델 =====
class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    game_date: Optional[str] = None
    home_pitcher: Optional[str] = None
    away_pitcher: Optional[str] = None
    home_pitcher_stats: Optional[dict] = None
    away_pitcher_stats: Optional[dict] = None


class TeamStatsRequest(BaseModel):
    team: str
    n_games: Optional[int] = 20


# ===== 유틸 함수 =====
def get_team_recent_stats(team: str, before_date: str = None, n: int = 20) -> dict:
    """팀 최근 N경기 성적"""
    if games_df is None:
        return {}

    if before_date:
        mask = (
            ((games_df["home_team"] == team) | (games_df["away_team"] == team)) &
            (games_df["date"] < before_date)
        )
    else:
        mask = (games_df["home_team"] == team) | (games_df["away_team"] == team)

    team_games = games_df[mask].sort_values("date").tail(n)

    if team_games.empty:
        return {}

    wins = 0
    total = 0
    runs_scored = []
    runs_allowed = []

    for _, row in team_games.iterrows():
        is_home = row["home_team"] == team
        if is_home:
            rs, ra = row["home_score"], row["away_score"]
            win = row["home_win"] == 1
        else:
            rs, ra = row["away_score"], row["home_score"]
            win = row["home_win"] == 0

        wins += int(win)
        total += 1
        runs_scored.append(rs)
        runs_allowed.append(ra)

    return {
        "wins": wins,
        "losses": total - wins,
        "total": total,
        "win_rate": round(wins / total, 3) if total > 0 else 0.5,
        "avg_runs_scored": round(float(np.mean(runs_scored)), 2) if runs_scored else 4.5,
        "avg_runs_allowed": round(float(np.mean(runs_allowed)), 2) if runs_allowed else 4.5,
        "recent_form": [
            1 if (row["home_team"] == team and row["home_win"] == 1) or
                 (row["away_team"] == team and row["home_win"] == 0)
            else 0
            for _, row in team_games.tail(10).iterrows()
        ],
    }


def calculate_standings_from_games() -> list[dict]:
    """로컬 경기 데이터로 2026 시즌 순위를 계산."""
    if games_df is None:
        return []

    season_games = games_df[games_df["date"].dt.year == 2026]

    standings = []
    for team in KBO_TEAMS:
        home_games = season_games[season_games["home_team"] == team]
        away_games = season_games[season_games["away_team"] == team]

        wins = (home_games["home_win"] == 1).sum() + (away_games["home_win"] == 0).sum()
        losses = (home_games["home_win"] == 0).sum() + (away_games["home_win"] == 1).sum()
        total = wins + losses

        standings.append({
            "team": team,
            "wins": int(wins),
            "losses": int(losses),
            "draws": 0,
            "games": int(total),
            "win_rate": round(wins / total, 3) if total > 0 else 0.0,
            "source": "local_games",
        })

    standings.sort(key=lambda x: x["win_rate"], reverse=True)
    for i, s in enumerate(standings):
        s["rank"] = i + 1
        s["gb"] = "0" if i == 0 else "-"

    return standings


def build_prediction_features(home_team: str, away_team: str,
                                game_date: str = None) -> np.ndarray | None:
    """예측용 피처 생성"""
    if features_df is None or feature_cols is None:
        return None

    if game_date:
        query_date = game_date
        past = features_df[
            (features_df["date"] < query_date) &
            (
                ((features_df["home_team"] == home_team) & (features_df["away_team"] == away_team)) |
                ((features_df["home_team"] == away_team) & (features_df["away_team"] == home_team))
            )
        ]
        if not past.empty:
            last = past.sort_values("date").iloc[[-1]]
            if last.iloc[0]["home_team"] == home_team:
                return last[feature_cols].values.astype(np.float32)

    # 각 팀의 최근 피처
    home_recent = features_df[
        (features_df["home_team"] == home_team) | (features_df["away_team"] == home_team)
    ].sort_values("date").tail(1)

    away_recent = features_df[
        (features_df["home_team"] == away_team) | (features_df["away_team"] == away_team)
    ].sort_values("date").tail(1)

    if home_recent.empty or away_recent.empty:
        return None

    # 홈팀이 홈인 경우의 최근 피처 사용
    home_row = features_df[
        features_df["home_team"] == home_team
    ].sort_values("date").tail(1)

    if home_row.empty:
        home_row = home_recent

    return home_row[feature_cols].values.astype(np.float32)


def _pitcher_quality_score(stats: dict | None) -> float:
    if not stats:
        return 0.0

    era = float(stats.get("era") or 4.5)
    whip = float(stats.get("whip") or 1.45)
    war = float(stats.get("war") or 0.0)
    innings = float(stats.get("starter_avg_innings") or 4.5)
    qs = float(stats.get("qs") or 0.0)
    games = max(float(stats.get("games") or 1.0), 1.0)

    # 점수가 높을수록 좋은 선발투수. 대략 -3~+3 범위가 나오도록 압축한다.
    return (
        (4.50 - era) * 0.35 +
        (1.45 - whip) * 1.00 +
        war * 0.55 +
        (innings - 4.8) * 0.18 +
        (qs / games) * 0.45
    )


def apply_pitcher_adjustment(prob: float, home_stats: dict | None, away_stats: dict | None) -> tuple[float, float]:
    """선발투수 전력 차이를 승률에 보정한다."""
    if not home_stats or not away_stats:
        return prob, 0.0

    home_score = _pitcher_quality_score(home_stats)
    away_score = _pitcher_quality_score(away_stats)
    diff = home_score - away_score
    adjustment = float(np.tanh(diff / 2.0) * 0.10)
    adjusted = max(0.08, min(0.92, prob + adjustment))
    return adjusted, adjustment


def _parse_recent_10_score(recent: str) -> float:
    if not recent:
        return 0.0
    wins = losses = draws = 0
    for count, label in re.findall(r"(\d+)(승|패|무)", recent):
        if label == "승":
            wins = int(count)
        elif label == "패":
            losses = int(count)
        elif label == "무":
            draws = int(count)
    total = wins + losses + draws
    if total == 0:
        return 0.0
    return (wins + draws * 0.5) / total - 0.5


def _parse_split_record(record: str) -> float | None:
    """KBO 표기 '승-무-패'를 승률로 변환."""
    if not record or "-" not in record:
        return None
    try:
        wins, draws, losses = [int(x) for x in record.split("-")[:3]]
        total = wins + draws + losses
        if total == 0:
            return None
        return (wins + draws * 0.5) / total
    except Exception:
        return None


def apply_standings_adjustment(prob: float, home_team: str, away_team: str) -> tuple[float, float, dict]:
    """최신 순위/최근 10경기/홈원정 기록 기반 보정."""
    standings = get_live_standings()
    by_team = {row.get("team"): row for row in standings}
    home = by_team.get(home_team)
    away = by_team.get(away_team)
    if not home or not away:
        return prob, 0.0, {}

    home_wr = float(home.get("win_rate") or 0.5)
    away_wr = float(away.get("win_rate") or 0.5)
    rank_diff = float((away.get("rank") or 5.5) - (home.get("rank") or 5.5))
    recent_diff = _parse_recent_10_score(home.get("recent_10", "")) - _parse_recent_10_score(away.get("recent_10", ""))

    home_split = _parse_split_record(home.get("home_record", ""))
    away_split = _parse_split_record(away.get("away_record", ""))
    split_diff = (home_split - away_split) if home_split is not None and away_split is not None else 0.0

    strength = (
        (home_wr - away_wr) * 2.5 +
        rank_diff * 0.025 +
        recent_diff * 0.35 +
        split_diff * 0.45
    )
    adjustment = float(np.tanh(strength) * 0.055)
    adjusted = max(0.08, min(0.92, prob + adjustment))

    context = {
        "home_rank": home.get("rank"),
        "away_rank": away.get("rank"),
        "home_win_rate": home_wr,
        "away_win_rate": away_wr,
        "home_recent_10": home.get("recent_10", ""),
        "away_recent_10": away.get("recent_10", ""),
        "home_home_record": home.get("home_record", ""),
        "away_away_record": away.get("away_record", ""),
        "source": home.get("source") or away.get("source") or "",
    }
    return adjusted, adjustment, context


# ===== API 엔드포인트 =====

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": ensemble is not None and ensemble._loaded,
        "data_loaded": games_df is not None,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/predict")
async def predict_game(req: PredictRequest):
    """경기 승부 예측"""
    if req.home_team not in KBO_TEAMS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 팀: {req.home_team}")
    if req.away_team not in KBO_TEAMS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 팀: {req.away_team}")
    if req.home_team == req.away_team:
        raise HTTPException(status_code=400, detail="같은 팀은 대결할 수 없습니다")

    game_date = req.game_date or date.today().isoformat()

    # 최근 성적
    home_stats = get_team_recent_stats(req.home_team, game_date)
    away_stats = get_team_recent_stats(req.away_team, game_date)

    # 예측
    home_win_prob = 0.5
    confidence = "낮음"
    prediction_method = "통계 기반"

    if ensemble and ensemble._loaded:
        X = build_prediction_features(req.home_team, req.away_team, game_date)
        if X is not None:
            try:
                prob = ensemble.predict_proba(X)[0]
                home_win_prob = float(prob)
                prediction_method = "AI 앙상블"
            except Exception as e:
                logger.warning(f"앙상블 예측 실패: {e}")

    # 통계 기반 보정 (모델 없을 시)
    if prediction_method == "통계 기반" and home_stats and away_stats:
        home_wr = home_stats.get("win_rate", 0.5)
        away_wr = away_stats.get("win_rate", 0.5)
        home_advantage = 0.04  # 홈 어드밴티지
        home_win_prob = (home_wr / (home_wr + away_wr) + home_advantage)
        home_win_prob = max(0.1, min(0.9, home_win_prob))

    pitcher_adjustment = 0.0
    home_win_prob, pitcher_adjustment = apply_pitcher_adjustment(
        home_win_prob,
        req.home_pitcher_stats,
        req.away_pitcher_stats,
    )

    standings_adjustment = 0.0
    standings_context = {}
    home_win_prob, standings_adjustment, standings_context = apply_standings_adjustment(
        home_win_prob,
        req.home_team,
        req.away_team,
    )

    away_win_prob = 1.0 - home_win_prob

    diff = abs(home_win_prob - 0.5)
    if diff >= 0.15:
        confidence = "높음"
    elif diff >= 0.08:
        confidence = "중간"
    else:
        confidence = "낮음"

    winner = req.home_team if home_win_prob >= 0.5 else req.away_team
    winner_prob = max(home_win_prob, away_win_prob)

    return {
        "home_team": req.home_team,
        "away_team": req.away_team,
        "home_win_prob": round(home_win_prob, 4),
        "away_win_prob": round(away_win_prob, 4),
        "predicted_winner": winner,
        "winner_prob": round(winner_prob, 4),
        "confidence": confidence,
        "prediction_method": prediction_method,
        "game_date": game_date,
        "home_recent_stats": home_stats,
        "away_recent_stats": away_stats,
        "home_pitcher": req.home_pitcher or "미정",
        "away_pitcher": req.away_pitcher or "미정",
        "home_pitcher_stats": req.home_pitcher_stats,
        "away_pitcher_stats": req.away_pitcher_stats,
        "pitcher_adjustment": round(pitcher_adjustment, 4),
        "standings_adjustment": round(standings_adjustment, 4),
        "standings_context": standings_context,
    }


@app.get("/api/standings")
async def get_standings(refresh: bool = True):
    """현재 순위"""
    return get_live_standings(force=refresh)


@app.post("/api/standings/refresh")
async def refresh_standings():
    """KBO 공식 최신 순위를 강제 갱신"""
    standings = get_live_standings(force=True)
    return {
        "standings": standings,
        "updated_at": standings_cache.get("updated_at").isoformat() if standings_cache.get("updated_at") else None,
        "total": len(standings),
    }


@app.get("/api/teams")
async def get_teams():
    """팀 목록 및 정보"""
    return [
        {
            "key": k,
            "name": v["name"],
            "color": v["color"],
            "bg": v["bg"],
        }
        for k, v in KBO_TEAMS.items()
    ]


@app.post("/api/lineups/refresh")
async def refresh_lineups():
    """실시간 1군 로스터를 다시 수집하고 캐시를 갱신"""
    try:
        from scraper.lineup_scraper import get_full_lineup_data
        data = get_full_lineup_data()
        return {
            "entry": data.get("entry", {}),
            "updated_at": data.get("updated_at"),
            "source": "live",
        }
    except Exception as e:
        logger.exception("실시간 라인업 갱신 실패")
        raise HTTPException(status_code=500, detail=f"실시간 라인업 갱신 실패: {e}")


@app.get("/api/team/{team}/lineup")
async def get_team_lineup(team: str, refresh: bool = False):
    """팀 1군 라인업"""
    if team not in KBO_TEAMS:
        raise HTTPException(status_code=404, detail=f"팀 없음: {team}")

    def has_placeholder_players(players: list[dict]) -> bool:
        return any(str(player.get("name", "")).startswith(f"{team} 선수") for player in players)

    def load_lineup_file() -> dict:
        lineup_path = RAW_DIR / "lineup_data.json"
        if not lineup_path.exists():
            return {}
        with open(lineup_path, encoding="utf-8") as f:
            return json.load(f)

    if refresh:
        try:
            from scraper.lineup_scraper import get_full_lineup_data
            data = get_full_lineup_data()
            entry = data.get("entry", {})
            players = entry.get(team, [])
            return {
                "team": team,
                "team_name": KBO_TEAMS[team]["name"],
                "players": players,
                "updated_at": data.get("updated_at"),
                "source": "live",
            }
        except Exception as e:
            logger.warning(f"실시간 라인업 수집 실패: {e}")

    try:
        data = load_lineup_file()
        entry = data.get("entry", {})
        if team in entry:
            players = entry[team]

            # 이전 버전에서 저장된 가짜 선수명이 있으면 즉시 실시간 재수집한다.
            if has_placeholder_players(players):
                from scraper.lineup_scraper import get_full_lineup_data
                data = get_full_lineup_data()
                players = data.get("entry", {}).get(team, [])

            if players:
                return {
                    "team": team,
                    "team_name": KBO_TEAMS[team]["name"],
                    "players": players,
                    "updated_at": data.get("updated_at"),
                    "source": "cache",
                }
    except Exception as e:
        logger.warning(f"라인업 로드 실패: {e}")

    return {
        "team": team,
        "team_name": KBO_TEAMS[team]["name"],
        "players": [],
        "updated_at": None,
        "message": "라인업 데이터 없음. 데이터 수집 후 다시 시도하세요."
    }


@app.get("/api/team/{team}/stats")
async def get_team_stats(team: str, n_games: int = 20):
    """팀 최근 성적"""
    if team not in KBO_TEAMS:
        raise HTTPException(status_code=404, detail=f"팀 없음: {team}")

    stats = get_team_recent_stats(team, n=n_games)

    # 시즌 성적
    season_stats = {}
    if games_df is not None:
        season_games = games_df[games_df["date"].dt.year == 2026]
        home_g = season_games[season_games["home_team"] == team]
        away_g = season_games[season_games["away_team"] == team]

        s_wins = (home_g["home_win"] == 1).sum() + (away_g["home_win"] == 0).sum()
        s_total = len(home_g) + len(away_g)
        season_stats = {
            "wins": int(s_wins),
            "losses": int(s_total - s_wins),
            "total": int(s_total),
            "win_rate": round(s_wins / s_total, 3) if s_total > 0 else 0.0,
        }

    return {
        "team": team,
        "team_name": KBO_TEAMS[team]["name"],
        "recent_stats": stats,
        "season_stats": season_stats,
        "color": KBO_TEAMS[team]["color"],
    }


@app.get("/api/today")
async def get_today_games():
    """오늘의 경기 일정 및 예측"""
    return await get_games_by_date(date.today().isoformat(), refresh=False)


@app.get("/api/games/date")
async def get_games_by_date(game_date: str, refresh: bool = False):
    """특정 날짜의 KBO 경기 일정/결과 및 예측"""
    try:
        query_date = datetime.strptime(game_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜 형식은 YYYY-MM-DD 이어야 합니다")

    selected_games = []

    # 먼저 저장된 경기 결과에서 조회한다.
    if games_df is not None and not refresh:
        day_games = games_df[games_df["date"].dt.date == query_date]
        for _, row in day_games.iterrows():
            selected_games.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": int(row["home_score"]),
                "away_score": int(row["away_score"]),
                "home_win": int(row["home_win"]),
                "home_pitcher": row.get("home_pitcher", "") if hasattr(row, "get") else "",
                "away_pitcher": row.get("away_pitcher", "") if hasattr(row, "get") else "",
                "game_time": "",
                "status": "completed",
                "source": "local",
            })

    # 저장 데이터에 없거나 강제 갱신이면 KBO 공식 일정에서 실시간 조회한다.
    if not selected_games:
        try:
            from scraper.pitcher_scraper import scrape_pitcher_matchups_by_date
            selected_games = scrape_pitcher_matchups_by_date(game_date)
            for game in selected_games:
                game["source"] = "kbo_live"
        except Exception as e:
            logger.warning(f"날짜별 경기 실시간 조회 실패({game_date}): {e}")

    # 각 경기 예측 추가
    predictions = []
    for game in selected_games:
        try:
            home = game["home_team"]
            away = game["away_team"]

            if home not in KBO_TEAMS or away not in KBO_TEAMS:
                continue

            pred_req = PredictRequest(
                home_team=home,
                away_team=away,
                game_date=game_date,
                home_pitcher=game.get("home_pitcher"),
                away_pitcher=game.get("away_pitcher"),
                home_pitcher_stats=game.get("home_pitcher_stats"),
                away_pitcher_stats=game.get("away_pitcher_stats"),
            )
            pred = await predict_game(pred_req)
            pred["game_time"] = game.get("game_time", "")
            pred["date"] = game.get("date", game_date)
            pred["status"] = game.get("status", "scheduled")
            pred["source"] = game.get("source", "")
            pred["stadium"] = game.get("stadium", "")
            pred["home_score"] = game.get("home_score")
            pred["away_score"] = game.get("away_score")
            pred["actual_winner"] = (
                home if game.get("home_win") == 1
                else away if game.get("home_win") == 0
                else None
            )
            predictions.append(pred)
        except Exception as e:
            logger.warning(f"날짜별 경기 예측 실패: {e}")

    return {
        "date": game_date,
        "games": predictions,
        "total": len(predictions),
        "refreshed": refresh,
    }


@app.get("/api/games/recent")
async def get_recent_games(team: Optional[str] = None, limit: int = 20):
    """최근 경기 결과"""
    if games_df is None:
        return []

    df = games_df.copy()
    if team:
        if team not in KBO_TEAMS:
            raise HTTPException(status_code=404, detail=f"팀 없음: {team}")
        df = df[(df["home_team"] == team) | (df["away_team"] == team)]

    recent = df.sort_values("date").tail(limit)

    result = []
    for _, row in recent.iterrows():
        result.append({
            "date": row["date"].strftime("%Y-%m-%d"),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": int(row["home_score"]),
            "away_score": int(row["away_score"]),
            "home_win": int(row["home_win"]),
        })

    return list(reversed(result))


@app.get("/api/h2h/{home_team}/{away_team}")
async def get_h2h(home_team: str, away_team: str, season: Optional[int] = None):
    """팀간 상대 전적"""
    if games_df is None:
        return {}

    mask = (
        ((games_df["home_team"] == home_team) & (games_df["away_team"] == away_team)) |
        ((games_df["home_team"] == away_team) & (games_df["away_team"] == home_team))
    )

    if season:
        mask = mask & (games_df["date"].dt.year == season)

    h2h_games = games_df[mask].sort_values("date")

    if h2h_games.empty:
        return {"total": 0, "home_wins": 0, "away_wins": 0, "games": []}

    home_wins = (
        ((h2h_games["home_team"] == home_team) & (h2h_games["home_win"] == 1)).sum() +
        ((h2h_games["away_team"] == home_team) & (h2h_games["home_win"] == 0)).sum()
    )
    total = len(h2h_games)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "total": int(total),
        "home_wins": int(home_wins),
        "away_wins": int(total - home_wins),
        "home_win_rate": round(home_wins / total, 3) if total > 0 else 0.5,
        "season": season,
        "games": [
            {
                "date": row["date"].strftime("%Y-%m-%d"),
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_score": int(row["home_score"]),
                "away_score": int(row["away_score"]),
            }
            for _, row in h2h_games.tail(10).iterrows()
        ],
    }


@app.get("/api/model/info")
async def get_model_info():
    """모델 정보"""
    result_path = MODEL_DIR / "training_result.json"
    if result_path.exists():
        with open(result_path, encoding="utf-8") as f:
            return json.load(f)
    return {"message": "모델 학습 필요"}


@app.get("/api/predict/matchup")
async def predict_matchup(home_team: str, away_team: str):
    """간단 예측 (GET)"""
    req = PredictRequest(home_team=home_team, away_team=away_team)
    return await predict_game(req)


# SPA fallback
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    index = FRONTEND_BUILD / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "프론트엔드 빌드가 필요합니다. frontend/ 디렉토리에서 npm run build를 실행하세요."}


if __name__ == "__main__":
    import uvicorn
    from config import API_HOST, API_PORT
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
