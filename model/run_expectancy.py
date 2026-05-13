"""
예상 득점 모델.

승패 분류 모델과 별개로 홈/원정 득점을 각각 예측하고, 두 기대득점 차이를
승률 보조 신호로 변환한다.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODEL_DIR, RANDOM_STATE

logger = logging.getLogger(__name__)


class RunExpectancyModel:
    def __init__(self):
        self.home_model = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.04,
            max_leaf_nodes=31,
            l2_regularization=0.05,
            random_state=RANDOM_STATE,
        )
        self.away_model = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.04,
            max_leaf_nodes=31,
            l2_regularization=0.05,
            random_state=RANDOM_STATE + 1,
        )

    def fit(self, X: np.ndarray, home_runs: np.ndarray, away_runs: np.ndarray):
        self.home_model.fit(X, home_runs)
        self.away_model.fit(X, away_runs)
        return self

    def predict_scores(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        home = np.clip(self.home_model.predict(X), 0.5, 12.0)
        away = np.clip(self.away_model.predict(X), 0.5, 12.0)
        return home, away

    def predict_home_win_prob(self, X: np.ndarray) -> np.ndarray:
        home, away = self.predict_scores(X)
        diff = home - away
        # KBO 경기 득점차의 대략적인 표준편차를 이용한 정규근사.
        sigma = 4.4
        return np.array([0.5 * (1 + math.erf(d / (sigma * math.sqrt(2)))) for d in diff])

    def evaluate(self, X: np.ndarray, home_runs: np.ndarray, away_runs: np.ndarray) -> dict:
        pred_home, pred_away = self.predict_scores(X)
        return {
            "home_mae": float(mean_absolute_error(home_runs, pred_home)),
            "away_mae": float(mean_absolute_error(away_runs, pred_away)),
            "home_rmse": float(mean_squared_error(home_runs, pred_home) ** 0.5),
            "away_rmse": float(mean_squared_error(away_runs, pred_away) ** 0.5),
        }


def train_run_expectancy_model(
    X_train: np.ndarray,
    y_home_train: np.ndarray,
    y_away_train: np.ndarray,
    X_val: np.ndarray,
    y_home_val: np.ndarray,
    y_away_val: np.ndarray,
) -> tuple[RunExpectancyModel, dict]:
    model = RunExpectancyModel().fit(X_train, y_home_train, y_away_train)
    metrics = model.evaluate(X_val, y_home_val, y_away_val)
    logger.info(
        "예상 득점 모델 검증 - "
        f"Home MAE: {metrics['home_mae']:.3f}, Away MAE: {metrics['away_mae']:.3f}"
    )
    return model, metrics


def save_run_expectancy_model(model: RunExpectancyModel):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "run_expectancy_model.pkl")


def load_run_expectancy_model() -> RunExpectancyModel:
    return joblib.load(MODEL_DIR / "run_expectancy_model.pkl")
