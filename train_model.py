"""
KBO 모델 학습 실행 스크립트
GPU (RTX 5070 Ti) 최적화 적용
"""
import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/train_model.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

Path("logs").mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent / "model"))


def check_gpu():
    """GPU 상태 확인"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"GPU: {gpu_name} ({vram:.1f}GB VRAM)")
            logger.info(f"CUDA 버전: {torch.version.cuda}")
            return True
        else:
            logger.warning("CUDA GPU 없음 - CPU로 학습합니다")
            return False
    except ImportError:
        logger.error("PyTorch 미설치. setup.bat 실행 후 재시도하세요.")
        return False


def main():
    parser = argparse.ArgumentParser(description="KBO 승부예측 모델 학습")
    parser.add_argument("--rebuild-features", action="store_true",
                        help="피처 재빌드 (기존 피처 삭제)")
    parser.add_argument("--no-xgb", action="store_true", help="XGBoost 제외")
    parser.add_argument("--no-lgb", action="store_true", help="LightGBM 제외")
    parser.add_argument("--no-nn", action="store_true", help="신경망 제외")
    parser.add_argument("--no-optimize", action="store_true",
                        help="가중치 최적화 제외")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("KBO 승부예측 AI 모델 학습 시작")
    logger.info("=" * 60)

    # GPU 확인
    has_gpu = check_gpu()

    # 피처 빌드
    logger.info("\n피처 엔지니어링 중...")
    try:
        from features import load_games, build_feature_matrix, get_feature_columns
        import pandas as pd
        from config import PROCESSED_DIR

        features_path = PROCESSED_DIR / "features.csv"
        if args.rebuild_features and features_path.exists():
            features_path.unlink()
            logger.info("기존 피처 삭제됨")

        if not features_path.exists():
            games = load_games()
            logger.info(f"경기 데이터: {len(games):,}경기")
            features_df = build_feature_matrix(games)
        else:
            features_df = pd.read_csv(features_path, encoding="utf-8-sig")
            features_df["date"] = pd.to_datetime(features_df["date"])
            logger.info(f"기존 피처 사용: {len(features_df):,}행")

        feature_cols = get_feature_columns(features_df)
        logger.info(f"피처 수: {len(feature_cols)}개")

    except FileNotFoundError as e:
        logger.error(f"데이터 없음: {e}")
        logger.error("먼저 python collect_data.py를 실행하세요.")
        sys.exit(1)

    # 모델 학습
    from trainer import run_training
    ensemble = run_training(
        rebuild_features=False,
        train_xgb=not args.no_xgb,
        train_lgb=not args.no_lgb,
        train_nn=not args.no_nn and has_gpu,
        optimize_ensemble=not args.no_optimize,
    )

    logger.info("\n학습 완료!")
    logger.info("서버 실행: python run_server.py")


if __name__ == "__main__":
    main()
