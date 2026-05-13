"""
전체 학습 파이프라인
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PROCESSED_DIR, MODEL_DIR, TEST_SIZE, RANDOM_STATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_or_build_features() -> pd.DataFrame:
    """피처 데이터 로드 또는 빌드"""
    features_path = PROCESSED_DIR / "features.csv"

    if features_path.exists():
        logger.info(f"기존 피처 로드: {features_path}")
        df = pd.read_csv(features_path, encoding="utf-8-sig")
        df["date"] = pd.to_datetime(df["date"])
        return df
    else:
        logger.info("피처 빌드 중...")
        from features import load_games, build_feature_matrix
        games = load_games()
        return build_feature_matrix(games)


def run_training(
    rebuild_features: bool = False,
    train_xgb: bool = True,
    train_lgb: bool = True,
    train_nn: bool = True,
    optimize_ensemble: bool = True,
):
    """전체 학습 실행"""

    logger.info("=" * 60)
    logger.info("KBO 승부예측 모델 학습 시작")
    logger.info("=" * 60)

    # 피처 로드
    if rebuild_features:
        features_path = PROCESSED_DIR / "features.csv"
        if features_path.exists():
            features_path.unlink()

    features_df = load_or_build_features()

    from features import get_feature_columns
    feature_cols = get_feature_columns(features_df)

    logger.info(f"데이터: {len(features_df):,}경기, {len(feature_cols)}개 피처")

    # 시간 순서 유지 (데이터 누수 방지)
    features_df = features_df.sort_values("date").reset_index(drop=True)

    X = features_df[feature_cols].values.astype(np.float32)
    y = features_df["home_win"].values.astype(np.float32)

    # Train/Val/Test 분할 (시간 순)
    n = len(X)
    test_start = int(n * (1 - TEST_SIZE))
    val_start = int(n * (1 - TEST_SIZE * 2))

    X_train = X[:val_start]
    y_train = y[:val_start]
    X_val = X[val_start:test_start]
    y_val = y[val_start:test_start]
    X_test = X[test_start:]
    y_test = y[test_start:]

    logger.info(f"Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")
    logger.info(f"홈팀 승률 (train): {y_train.mean():.3f}")

    xgb_model = lgb_model = neural_model = neural_scaler = None

    # XGBoost 학습
    if train_xgb:
        logger.info("\n--- XGBoost 학습 ---")
        from xgb_model import train_xgboost
        xgb_model = train_xgboost(X_train, y_train, X_val, y_val)

    # LightGBM 학습
    if train_lgb:
        logger.info("\n--- LightGBM 학습 ---")
        from xgb_model import train_lightgbm
        lgb_model = train_lightgbm(X_train, y_train, X_val, y_val)

    # Neural Network 학습
    if train_nn:
        logger.info("\n--- PyTorch 신경망 학습 ---")
        from neural_model import train_neural_model
        neural_model, neural_scaler = train_neural_model(
            X_train, y_train, X_val, y_val,
            epochs=300, batch_size=512
        )

    # 모델 저장
    from xgb_model import save_models
    from neural_model import save_neural_model

    if xgb_model and lgb_model:
        save_models(xgb_model, lgb_model, feature_cols)

    if neural_model:
        save_neural_model(neural_model, neural_scaler)

    # 앙상블 가중치 최적화
    weights = {"xgb": 0.4, "lgb": 0.35, "neural": 0.25}

    if optimize_ensemble and xgb_model and lgb_model and neural_model:
        try:
            from ensemble import optimize_weights, save_ensemble_config
            weights = optimize_weights(xgb_model, lgb_model, neural_model, neural_scaler, X_val, y_val)
            save_ensemble_config(weights)
        except ImportError:
            logger.warning("scipy 없음 - 기본 가중치 사용")

    # 테스트 성능 평가
    logger.info("\n--- 최종 테스트 성능 ---")
    from ensemble import KBOEnsemble
    ensemble = KBOEnsemble(weights=weights)
    ensemble.xgb_model = xgb_model
    ensemble.lgb_model = lgb_model
    ensemble.neural_model = neural_model
    ensemble.neural_scaler = neural_scaler
    ensemble.feature_cols = feature_cols
    ensemble._loaded = True

    # 검증 세트로 확률 보정. AUC는 유지하면서 0.5 주변 확률 해석을 안정화한다.
    try:
        from ensemble import fit_probability_calibrator, save_probability_calibrator
        raw_val_probs = ensemble.predict_proba(X_val)
        calibrator = fit_probability_calibrator(raw_val_probs, y_val)
        save_probability_calibrator(calibrator)
        ensemble.calibrator = calibrator
        logger.info("확률 캘리브레이션 완료")
    except Exception as e:
        logger.warning(f"확률 캘리브레이션 실패: {e}")

    metrics = ensemble.evaluate(X_test, y_test)

    # 피처 중요도 출력
    importance = ensemble.get_feature_importance()
    logger.info("\n--- Top 10 피처 중요도 ---")
    for i, (feat, imp) in enumerate(list(importance.items())[:10]):
        logger.info(f"  {i+1:2d}. {feat}: {imp:.4f}")

    # 학습 결과 저장
    import json
    result = {
        "metrics": {k: float(v) for k, v in metrics.items()},
        "weights": {k: float(v) for k, v in weights.items()},
        "feature_importance": {k: float(v) for k, v in list(importance.items())[:20]},
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
    }
    with open(MODEL_DIR / "training_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("\n학습 완료!")
    return ensemble


if __name__ == "__main__":
    ensemble = run_training()
