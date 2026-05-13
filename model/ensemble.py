"""
앙상블 예측기
XGBoost + LightGBM + Neural Network 가중 앙상블
"""
import logging
import numpy as np
import joblib
from pathlib import Path
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score, log_loss

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODEL_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class KBOEnsemble:
    """KBO 승부예측 앙상블 모델"""

    def __init__(self, weights: dict = None):
        self.weights = weights or {"xgb": 0.4, "lgb": 0.35, "neural": 0.25}
        self.xgb_model = None
        self.lgb_model = None
        self.neural_model = None
        self.neural_scaler = None
        self.feature_cols = None
        self.calibrator = None
        self.stacker = None
        self._loaded = False

    def load(self):
        """저장된 모델 로드"""
        try:
            from xgb_model import load_models
            self.xgb_model, self.lgb_model, self.feature_cols = load_models()
            logger.info("XGBoost/LightGBM 모델 로드 완료")
        except Exception as e:
            logger.warning(f"XGB/LGB 로드 실패: {e}")

        try:
            from neural_model import load_neural_model
            self.neural_model, self.neural_scaler = load_neural_model()
            logger.info("신경망 모델 로드 완료")
        except Exception as e:
            logger.warning(f"신경망 로드 실패: {e}")

        try:
            self.stacker = load_stacking_model()
            logger.info("스태킹 메타 모델 로드 완료")
        except Exception:
            self.stacker = None

        try:
            self.calibrator = load_probability_calibrator()
            logger.info("확률 캘리브레이터 로드 완료")
        except Exception:
            self.calibrator = None

        self._loaded = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """앙상블 예측 (홈팀 승리 확률)"""
        if not self._loaded:
            self.load()

        probs = []
        used_weights = []

        if self.xgb_model is not None:
            try:
                p = self.xgb_model.predict_proba(X)[:, 1]
                probs.append(p)
                used_weights.append(self.weights["xgb"])
            except Exception as e:
                logger.warning(f"XGBoost 예측 실패: {e}")

        if self.lgb_model is not None:
            try:
                p = self.lgb_model.predict_proba(X)[:, 1]
                probs.append(p)
                used_weights.append(self.weights["lgb"])
            except Exception as e:
                logger.warning(f"LightGBM 예측 실패: {e}")

        if self.neural_model is not None:
            try:
                from neural_model import predict_neural
                p = predict_neural(self.neural_model, self.neural_scaler, X)
                probs.append(p)
                used_weights.append(self.weights["neural"])
            except Exception as e:
                logger.warning(f"신경망 예측 실패: {e}")

        if not probs:
            logger.error("모든 모델 예측 실패 - 0.5 반환")
            return np.full(X.shape[0], 0.5)

        if self.stacker is not None and len(probs) == 3:
            try:
                ensemble_prob = self.stacker.predict_proba(np.stack(probs, axis=1))[:, 1]
            except Exception as e:
                logger.warning(f"스태킹 예측 실패, 가중 평균으로 폴백: {e}")
                ensemble_prob = None
        else:
            ensemble_prob = None

        if ensemble_prob is None:
            # 가중 평균
            total_weight = sum(used_weights)
            weights_norm = [w / total_weight for w in used_weights]

            ensemble_prob = np.zeros(X.shape[0])
            for p, w in zip(probs, weights_norm):
                ensemble_prob += p * w

        if self.calibrator is not None:
            try:
                ensemble_prob = self.calibrator.predict_proba(ensemble_prob.reshape(-1, 1))[:, 1]
            except Exception as e:
                logger.warning(f"확률 캘리브레이션 실패: {e}")

        return ensemble_prob

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        """모델 성능 평가"""
        probs = self.predict_proba(X)
        preds = (probs >= 0.5).astype(int)

        metrics = {
            "accuracy": accuracy_score(y, preds),
            "auc_roc": roc_auc_score(y, probs),
            "log_loss": log_loss(y, probs),
            "home_win_rate": y.mean(),
            "predicted_home_win_rate": preds.mean(),
        }

        logger.info(f"앙상블 성능:")
        for k, v in metrics.items():
            logger.info(f"  {k}: {v:.4f}")

        return metrics

    def get_feature_importance(self) -> dict:
        """피처 중요도"""
        importance = {}

        if self.xgb_model is not None and self.feature_cols:
            try:
                xgb_imp = self.xgb_model.feature_importances_
                for col, imp in zip(self.feature_cols, xgb_imp):
                    importance[col] = importance.get(col, 0) + imp * self.weights["xgb"]
            except Exception:
                pass

        if self.lgb_model is not None and self.feature_cols:
            try:
                lgb_imp = self.lgb_model.feature_importances_
                for col, imp in zip(self.feature_cols, lgb_imp):
                    importance[col] = importance.get(col, 0) + imp * self.weights["lgb"]
            except Exception:
                pass

        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))


def optimize_weights(
    xgb_model, lgb_model, neural_model, neural_scaler,
    X_val: np.ndarray, y_val: np.ndarray
) -> dict:
    """검증 세트로 앙상블 가중치 최적화"""
    from scipy.optimize import minimize

    probs_xgb = xgb_model.predict_proba(X_val)[:, 1]
    probs_lgb = lgb_model.predict_proba(X_val)[:, 1]

    from neural_model import predict_neural
    probs_nn = predict_neural(neural_model, neural_scaler, X_val)

    stacked = np.stack([probs_xgb, probs_lgb, probs_nn], axis=1)

    def objective(weights):
        w = np.array(weights)
        w = w / w.sum()
        ensemble = (stacked * w).sum(axis=1)
        clipped = np.clip(ensemble, 1e-5, 1 - 1e-5)
        # 실제 운영 확률은 AUC보다 logloss/Brier가 중요하다.
        return log_loss(y_val, clipped) + 0.35 * brier_score_loss(y_val, clipped)

    x0 = [0.4, 0.35, 0.25]
    constraints = [{"type": "eq", "fun": lambda w: sum(w) - 1}]
    bounds = [(0.05, 0.9)] * 3

    result = minimize(objective, x0, method="SLSQP",
                      bounds=bounds, constraints=constraints)

    opt_weights = result.x / result.x.sum()
    logger.info(f"최적 가중치: XGB={opt_weights[0]:.3f}, LGB={opt_weights[1]:.3f}, NN={opt_weights[2]:.3f}")

    return {"xgb": opt_weights[0], "lgb": opt_weights[1], "neural": opt_weights[2]}


def save_ensemble_config(weights: dict):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(weights, MODEL_DIR / "ensemble_weights.pkl")


def load_ensemble_config() -> dict:
    path = MODEL_DIR / "ensemble_weights.pkl"
    if path.exists():
        return joblib.load(path)
    return {"xgb": 0.4, "lgb": 0.35, "neural": 0.25}


def fit_stacking_model(probs_xgb: np.ndarray, probs_lgb: np.ndarray, probs_nn: np.ndarray, y_val: np.ndarray):
    """개별 모델 예측값을 입력으로 받는 메타 로지스틱 모델."""
    from sklearn.linear_model import LogisticRegression

    X_meta = np.stack([probs_xgb, probs_lgb, probs_nn], axis=1)
    stacker = LogisticRegression(C=0.5, solver="lbfgs")
    stacker.fit(X_meta, y_val)
    return stacker


def save_stacking_model(stacker):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(stacker, MODEL_DIR / "stacking_model.pkl")


def load_stacking_model():
    return joblib.load(MODEL_DIR / "stacking_model.pkl")


def fit_probability_calibrator(raw_probs: np.ndarray, y_val: np.ndarray):
    """검증 세트로 앙상블 확률을 Platt scaling 보정."""
    from sklearn.linear_model import LogisticRegression

    calibrator = LogisticRegression(C=0.35, solver="lbfgs")
    calibrator.fit(raw_probs.reshape(-1, 1), y_val)
    return calibrator


def save_probability_calibrator(calibrator):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrator, MODEL_DIR / "probability_calibrator.pkl")


def load_probability_calibrator():
    return joblib.load(MODEL_DIR / "probability_calibrator.pkl")
