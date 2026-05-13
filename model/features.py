"""
피처 엔지니어링
- 경기별 팀 이동평균 성적 계산
- 홈/원정 성적, 최근 폼, 상대 전적 등
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RAW_DIR, PROCESSED_DIR, ROLLING_WINDOWS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_games() -> pd.DataFrame:
    """원시 경기 데이터 로드"""
    path = RAW_DIR / "games_raw.csv"
    if not path.exists():
        raise FileNotFoundError(f"경기 데이터 없음: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[df["home_win"].isin([0, 1])].copy()
    return df


def compute_team_rolling_stats(df: pd.DataFrame, windows: list[int] = ROLLING_WINDOWS) -> pd.DataFrame:
    """
    각 경기 시점 기준 팀별 최근 N경기 이동 통계 계산
    데이터 누수 방지: shift(1) 사용 (현재 경기 제외)
    """
    teams = pd.concat([df["home_team"], df["away_team"]]).unique()

    team_game_logs: dict[str, list] = {t: [] for t in teams}

    for _, row in df.iterrows():
        game_date = row["date"]
        home = row["home_team"]
        away = row["away_team"]
        home_score = row["home_score"]
        away_score = row["away_score"]
        home_win = row["home_win"]

        team_game_logs[home].append({
            "date": game_date,
            "runs_scored": home_score,
            "runs_allowed": away_score,
            "win": home_win,
            "is_home": 1,
            "opponent": away,
        })
        team_game_logs[away].append({
            "date": game_date,
            "runs_scored": away_score,
            "runs_allowed": home_score,
            "win": 1 - home_win,
            "is_home": 0,
            "opponent": home,
        })

    # 팀별 데이터프레임
    team_dfs: dict[str, pd.DataFrame] = {}
    for team, logs in team_game_logs.items():
        if not logs:
            continue
        t_df = pd.DataFrame(logs).sort_values("date").reset_index(drop=True)

        for w in windows:
            t_df[f"win_rate_{w}"] = t_df["win"].shift(1).rolling(w, min_periods=1).mean()
            t_df[f"runs_scored_{w}"] = t_df["runs_scored"].shift(1).rolling(w, min_periods=1).mean()
            t_df[f"runs_allowed_{w}"] = t_df["runs_allowed"].shift(1).rolling(w, min_periods=1).mean()
            t_df[f"run_diff_{w}"] = t_df[f"runs_scored_{w}"] - t_df[f"runs_allowed_{w}"]

        # 시즌 전체 누적 승률 (누수 방지)
        t_df["season_win_rate"] = t_df["win"].expanding().mean().shift(1)

        # 홈/원정 최근 10경기 승률
        home_mask = t_df["is_home"] == 1
        away_mask = t_df["is_home"] == 0
        t_df["home_win_rate_10"] = np.nan
        t_df["away_win_rate_10"] = np.nan
        t_df.loc[home_mask, "home_win_rate_10"] = (
            t_df.loc[home_mask, "win"].shift(1).rolling(10, min_periods=1).mean()
        )
        t_df.loc[away_mask, "away_win_rate_10"] = (
            t_df.loc[away_mask, "win"].shift(1).rolling(10, min_periods=1).mean()
        )
        t_df["home_win_rate_10"] = t_df["home_win_rate_10"].ffill()
        t_df["away_win_rate_10"] = t_df["away_win_rate_10"].ffill()

        # 연속 승/패 (streak) - 현재 경기 이전까지의 연속 기록
        # 현재 경기 결과 포함 방지: shift(1) 후 계산
        wins_shifted = t_df["win"].shift(1).fillna(0)
        streaks = [0]
        s = 0
        for i in range(1, len(wins_shifted)):
            w = wins_shifted.iloc[i]
            if w == 1:
                s = s + 1 if s > 0 else 1
            else:
                s = s - 1 if s < 0 else -1
            streaks.append(s)
        t_df["streak"] = streaks

        # 마지막 경기로부터 휴식일
        t_df["days_rest"] = t_df["date"].diff().dt.days.fillna(1).clip(0, 10)

        # 불펜 피로도 프록시: 최근 3일 경기 수/실점.
        # 실제 투구수 데이터가 없을 때, 최근 짧은 간격의 경기와 실점을 피로도 대용값으로 사용한다.
        games_last_3d = []
        runs_allowed_last_3d = []
        high_stress_last_3d = []
        for i, game in t_df.iterrows():
            current_date = game["date"]
            prev = t_df[
                (t_df.index < i) &
                (t_df["date"] >= current_date - timedelta(days=3)) &
                (t_df["date"] < current_date)
            ]
            games_last_3d.append(len(prev))
            runs_allowed_last_3d.append(prev["runs_allowed"].sum() if not prev.empty else 0)
            high_stress_last_3d.append((prev["runs_allowed"] >= 6).sum() if not prev.empty else 0)

        t_df["games_last_3d"] = games_last_3d
        t_df["runs_allowed_last_3d"] = runs_allowed_last_3d
        t_df["high_stress_games_last_3d"] = high_stress_last_3d

        team_dfs[team] = t_df

    return team_dfs


def compute_stadium_run_factors(df: pd.DataFrame) -> dict[tuple[pd.Timestamp, str], float]:
    """각 경기 이전까지의 구장별 평균 총득점 런팩터."""
    if "stadium" not in df.columns:
        return {}

    league_avg_total_runs = (df["home_score"] + df["away_score"]).expanding().mean().shift(1)
    stadium_history: dict[str, list[float]] = {}
    factors: dict[tuple[pd.Timestamp, str], float] = {}

    for idx, row in df.sort_values("date").iterrows():
        stadium = row.get("stadium", "")
        game_date = row["date"]
        total_runs = float(row["home_score"] + row["away_score"])
        league_avg = float(league_avg_total_runs.loc[idx]) if not pd.isna(league_avg_total_runs.loc[idx]) else 9.0

        if stadium:
            prev = stadium_history.get(stadium, [])
            stadium_avg = float(np.mean(prev)) if prev else league_avg
            factors[(game_date, stadium)] = stadium_avg / league_avg if league_avg > 0 else 1.0
            stadium_history.setdefault(stadium, []).append(total_runs)

    return factors


def compute_h2h_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    팀간 상대 전적 계산 (시즌 내)
    각 경기 이전까지의 누적 상대 전적
    """
    df = df.copy()
    df["h2h_home_wins"] = 0
    df["h2h_games"] = 0

    # 시즌 추출
    df["season"] = df["date"].dt.year

    for idx, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        season = row["season"]
        game_date = row["date"]

        # 이전 경기 중 같은 시즌, 같은 팀페어
        prev = df[
            (df["date"] < game_date) &
            (df["season"] == season) &
            (
                ((df["home_team"] == home) & (df["away_team"] == away)) |
                ((df["home_team"] == away) & (df["away_team"] == home))
            )
        ]

        if prev.empty:
            continue

        h2h_games = len(prev)
        home_wins = (
            ((prev["home_team"] == home) & (prev["home_win"] == 1)).sum() +
            ((prev["away_team"] == home) & (prev["home_win"] == 0)).sum()
        )

        df.at[idx, "h2h_home_wins"] = home_wins
        df.at[idx, "h2h_games"] = h2h_games

    df["h2h_home_win_rate"] = np.where(
        df["h2h_games"] > 0,
        df["h2h_home_wins"] / df["h2h_games"],
        0.5
    )

    return df


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """최종 피처 매트릭스 생성"""
    logger.info("팀별 이동 통계 계산 중...")
    team_dfs = compute_team_rolling_stats(df)

    logger.info("상대 전적 계산 중...")
    df_h2h = compute_h2h_stats(df)

    logger.info("구장 런팩터 계산 중...")
    stadium_factors = compute_stadium_run_factors(df)

    feature_rows = []

    for idx, row in df_h2h.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        game_date = row["date"]

        home_df = team_dfs.get(home)
        away_df = team_dfs.get(away)

        if home_df is None or away_df is None:
            continue

        # 해당 경기 시점의 팀 통계 찾기
        home_stats = home_df[home_df["date"] == game_date]
        away_stats = away_df[away_df["date"] == game_date]

        if home_stats.empty or away_stats.empty:
            continue

        hs = home_stats.iloc[0]
        as_ = away_stats.iloc[0]

        feat = {
            "date": game_date,
            "home_team": home,
            "away_team": away,
            "home_win": row["home_win"],
            "season": row["date"].year,
        }

        # 홈팀 피처
        for w in ROLLING_WINDOWS:
            feat[f"home_win_rate_{w}"] = hs.get(f"win_rate_{w}", 0.5)
            feat[f"home_runs_scored_{w}"] = hs.get(f"runs_scored_{w}", 4.5)
            feat[f"home_runs_allowed_{w}"] = hs.get(f"runs_allowed_{w}", 4.5)
            feat[f"home_run_diff_{w}"] = hs.get(f"run_diff_{w}", 0.0)

        feat["home_season_win_rate"] = hs.get("season_win_rate", 0.5)
        feat["home_home_win_rate_10"] = hs.get("home_win_rate_10", 0.5)
        feat["home_streak"] = hs.get("streak", 0)
        feat["home_days_rest"] = hs.get("days_rest", 1)
        feat["home_games_last_3d"] = hs.get("games_last_3d", 0)
        feat["home_runs_allowed_last_3d"] = hs.get("runs_allowed_last_3d", 0)
        feat["home_high_stress_games_last_3d"] = hs.get("high_stress_games_last_3d", 0)

        # 원정팀 피처
        for w in ROLLING_WINDOWS:
            feat[f"away_win_rate_{w}"] = as_.get(f"win_rate_{w}", 0.5)
            feat[f"away_runs_scored_{w}"] = as_.get(f"runs_scored_{w}", 4.5)
            feat[f"away_runs_allowed_{w}"] = as_.get(f"runs_allowed_{w}", 4.5)
            feat[f"away_run_diff_{w}"] = as_.get(f"run_diff_{w}", 0.0)

        feat["away_season_win_rate"] = as_.get("season_win_rate", 0.5)
        feat["away_away_win_rate_10"] = as_.get("away_win_rate_10", 0.5)
        feat["away_streak"] = as_.get("streak", 0)
        feat["away_days_rest"] = as_.get("days_rest", 1)
        feat["away_games_last_3d"] = as_.get("games_last_3d", 0)
        feat["away_runs_allowed_last_3d"] = as_.get("runs_allowed_last_3d", 0)
        feat["away_high_stress_games_last_3d"] = as_.get("high_stress_games_last_3d", 0)

        # 차이 피처
        for w in ROLLING_WINDOWS:
            feat[f"diff_win_rate_{w}"] = feat[f"home_win_rate_{w}"] - feat[f"away_win_rate_{w}"]
            feat[f"diff_run_diff_{w}"] = feat[f"home_run_diff_{w}"] - feat[f"away_run_diff_{w}"]

        feat["diff_season_win_rate"] = feat["home_season_win_rate"] - feat["away_season_win_rate"]
        feat["diff_days_rest"] = feat["home_days_rest"] - feat["away_days_rest"]
        feat["diff_games_last_3d"] = feat["home_games_last_3d"] - feat["away_games_last_3d"]
        feat["diff_bullpen_stress_3d"] = (
            feat["home_high_stress_games_last_3d"] - feat["away_high_stress_games_last_3d"]
        )

        # 상대 전적
        feat["h2h_home_win_rate"] = row.get("h2h_home_win_rate", 0.5)
        feat["h2h_games"] = row.get("h2h_games", 0)

        # 시즌 내 위치 (0~1)
        feat["season_progress"] = (game_date.timetuple().tm_yday - 60) / 240

        stadium = row.get("stadium", "")
        feat["stadium_run_factor"] = stadium_factors.get((game_date, stadium), 1.0)

        feature_rows.append(feat)

    features_df = pd.DataFrame(feature_rows)
    features_df = features_df.fillna(features_df.median(numeric_only=True))

    out_path = PROCESSED_DIR / "features.csv"
    features_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"피처 저장: {out_path} ({len(features_df)}행 x {len(features_df.columns)}컬럼)")

    return features_df


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """모델 입력 피처 컬럼 목록"""
    exclude = {"date", "home_team", "away_team", "home_win", "season",
               "home_pitcher", "away_pitcher", "stadium", "game_id", "preview_url", "status"}
    return [c for c in df.columns if c not in exclude]


if __name__ == "__main__":
    df = load_games()
    print(f"경기 데이터: {len(df):,}행")
    features = build_feature_matrix(df)
    print(f"피처 매트릭스: {features.shape}")
    print(f"피처 컬럼: {get_feature_columns(features)[:10]}...")
