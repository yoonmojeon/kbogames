"""
XGBoost + LightGBM 예측 모델
RTX 5070 Ti GPU 최적화 (CUDA)
"""
import logging
import numpy as np
import joblib
from pathlib import Path

import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, roc_auc_score, log_loss,
    classification_report, confusion_matrix
)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODEL_DIR, XGB_PARAMS, LGB_PARAMS, RANDOM_STATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def train_xgboost(X_train, y_train, X_val, y_val):
    """XGBoost GPU 학습"""
    import xgboost as xgb

    logger.info("XGBoost 학습 시작 (GPU)...")

    params = XGB_PARAMS.copy()

    params["early_stopping_rounds"] = 50
    model = xgb.XGBClassifier(**params)

    try:
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=100,
        )
        logger.info("XGBoost GPU 학습 완료")
    except Exception as e:
        logger.warning(f"GPU 학습 실패: {e} -> CPU로 재시도")
        params["device"] = "cpu"
        params["tree_method"] = "hist"
        model = xgb.XGBClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=100,
        )

    val_prob = model.predict_proba(X_val)[:, 1]
    val_pred = (val_prob >= 0.5).astype(int)

    acc = accuracy_score(y_val, val_pred)
    auc = roc_auc_score(y_val, val_prob)
    ll = log_loss(y_val, val_prob)
    logger.info(f"XGBoost 검증 - Acc: {acc:.4f}, AUC: {auc:.4f}, LogLoss: {ll:.4f}")

    return model


def train_lightgbm(X_train, y_train, X_val, y_val):
    """LightGBM GPU 학습"""
    import lightgbm as lgb

    logger.info("LightGBM 학습 시작 (GPU)...")

    params = LGB_PARAMS.copy()

    model = lgb.LGBMClassifier(**params)

    try:
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
        )
        logger.info("LightGBM GPU 학습 완료")
    except Exception as e:
        logger.warning(f"GPU 학습 실패: {e} -> CPU로 재시도")
        params["device"] = "cpu"
        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
        )

    val_prob = model.predict_proba(X_val)[:, 1]
    val_pred = (val_prob >= 0.5).astype(int)

    acc = accuracy_score(y_val, val_pred)
    auc = roc_auc_score(y_val, val_prob)
    ll = log_loss(y_val, val_prob)
    logger.info(f"LightGBM 검증 - Acc: {acc:.4f}, AUC: {auc:.4f}, LogLoss: {ll:.4f}")

    return model


def cross_validate_models(X: np.ndarray, y: np.ndarray, n_splits: int = 5):
    """시계열 교차 검증"""
    import xgboost as xgb
    import lightgbm as lgb

    tscv = TimeSeriesSplit(n_splits=n_splits)
    xgb_aucs, lgb_aucs = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_tr, X_va = X[train_idx], X[val_idx]
        y_tr, y_va = y[train_idx], y[val_idx]

        # XGBoost
        xgb_model = xgb.XGBClassifier(**{**XGB_PARAMS, "n_estimators": 500, "verbose": 0, "early_stopping_rounds": 30})
        try:
            xgb_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        except Exception:
            xgb_model = xgb.XGBClassifier(**{**XGB_PARAMS, "device": "cpu", "n_estimators": 500, "verbose": 0, "early_stopping_rounds": 30})
            xgb_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)

        xgb_prob = xgb_model.predict_proba(X_va)[:, 1]
        xgb_auc = roc_auc_score(y_va, xgb_prob)
        xgb_aucs.append(xgb_auc)

        # LightGBM
        lgb_model = lgb.LGBMClassifier(**{**LGB_PARAMS, "n_estimators": 500, "verbose": -1})
        try:
            lgb_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
                          callbacks=[lgb.early_stopping(30), lgb.log_evaluation(9999)])
        except Exception:
            lgb_model = lgb.LGBMClassifier(**{**LGB_PARAMS, "device": "cpu", "n_estimators": 500, "verbose": -1})
            lgb_model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)],
                          callbacks=[lgb.early_stopping(30), lgb.log_evaluation(9999)])

        lgb_prob = lgb_model.predict_proba(X_va)[:, 1]
        lgb_auc = roc_auc_score(y_va, lgb_prob)
        lgb_aucs.append(lgb_auc)

        logger.info(f"Fold {fold+1}: XGB AUC={xgb_auc:.4f}, LGB AUC={lgb_auc:.4f}")

    logger.info(f"\n교차 검증 결과:")
    logger.info(f"  XGBoost: {np.mean(xgb_aucs):.4f} ± {np.std(xgb_aucs):.4f}")
    logger.info(f"  LightGBM: {np.mean(lgb_aucs):.4f} ± {np.std(lgb_aucs):.4f}")

    return {
        "xgb_auc": np.mean(xgb_aucs),
        "lgb_auc": np.mean(lgb_aucs),
    }


def save_models(xgb_model, lgb_model, feature_cols: list[str]):
    """모델 저장"""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(xgb_model, MODEL_DIR / "xgb_model.pkl")
    joblib.dump(lgb_model, MODEL_DIR / "lgb_model.pkl")
    joblib.dump(feature_cols, MODEL_DIR / "feature_cols.pkl")
    logger.info(f"모델 저장 완료: {MODEL_DIR}")


def load_models():
    """모델 로드"""
    xgb_model = joblib.load(MODEL_DIR / "xgb_model.pkl")
    lgb_model = joblib.load(MODEL_DIR / "lgb_model.pkl")
    feature_cols = joblib.load(MODEL_DIR / "feature_cols.pkl")
    return xgb_model, lgb_model, feature_cols


if __name__ == "__main__":
    from features import load_games, build_feature_matrix, get_feature_columns
    from sklearn.model_selection import train_test_split

    df = load_games()
    features_df = build_feature_matrix(df)
    feature_cols = get_feature_columns(features_df)

    X = features_df[feature_cols].values
    y = features_df["home_win"].values

    split = int(len(X) * 0.85)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    xgb_model = train_xgboost(X_train, y_train, X_val, y_val)
    lgb_model = train_lightgbm(X_train, y_train, X_val, y_val)
    save_models(xgb_model, lgb_model, feature_cols)
