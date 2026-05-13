import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = BASE_DIR / "model" / "saved"

for d in [RAW_DIR, PROCESSED_DIR, MODEL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# KBO 팀 정보
KBO_TEAMS = {
    "KIA":    {"name": "기아 타이거즈",   "code": "HT", "color": "#EA0029", "bg": "#1a0005"},
    "LG":     {"name": "LG 트윈스",      "code": "LG", "color": "#C30452", "bg": "#1a0009"},
    "SSG":    {"name": "SSG 랜더스",     "code": "SK", "color": "#CE0E2D", "bg": "#1a0005"},
    "KT":     {"name": "KT 위즈",        "code": "WO", "color": "#000000", "bg": "#0a0a0a"},
    "NC":     {"name": "NC 다이노스",     "code": "NC", "color": "#1D467E", "bg": "#050d1a"},
    "두산":   {"name": "두산 베어스",     "code": "OB", "color": "#131230", "bg": "#05050f"},
    "롯데":   {"name": "롯데 자이언츠",   "code": "LT", "color": "#002B5B", "bg": "#000a14"},
    "삼성":   {"name": "삼성 라이온즈",   "code": "SS", "color": "#1428A0", "bg": "#030514"},
    "한화":   {"name": "한화 이글스",     "code": "HH", "color": "#FF6600", "bg": "#1a0800"},
    "키움":   {"name": "키움 히어로즈",   "code": "NX", "color": "#820024", "bg": "#120005"},
}

TEAM_NAME_MAP = {
    "기아": "KIA", "KIA": "KIA", "KIA타이거즈": "KIA", "기아타이거즈": "KIA",
    "LG": "LG", "LG트윈스": "LG",
    "SSG": "SSG", "SSG랜더스": "SSG", "SK": "SSG",
    "KT": "KT", "KT위즈": "KT",
    "NC": "NC", "NC다이노스": "NC",
    "두산": "두산", "두산베어스": "두산",
    "롯데": "롯데", "롯데자이언츠": "롯데",
    "삼성": "삼성", "삼성라이온즈": "삼성",
    "한화": "한화", "한화이글스": "한화",
    "키움": "키움", "키움히어로즈": "키움", "넥센": "키움",
}

# 스크래핑 설정
SCRAPE_START_YEAR = 2016
SCRAPE_END_YEAR = 2026
SCRAPE_END_DATE = "2026-05-12"

REQUEST_DELAY = 1.5   # 요청 간격 (초)
REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 모델 설정
ROLLING_WINDOWS = [5, 10, 20]   # 최근 N경기 이동평균 윈도우
TEST_SIZE = 0.15
RANDOM_STATE = 42

# XGBoost GPU 설정
XGB_PARAMS = {
    "device": "cuda",
    "n_estimators": 1200,
    "learning_rate": 0.03,
    "max_depth": 6,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "random_state": RANDOM_STATE,
}

# LightGBM GPU 설정
LGB_PARAMS = {
    "device": "gpu",
    "n_estimators": 1200,
    "learning_rate": 0.03,
    "max_depth": 6,
    "num_leaves": 63,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 20,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "binary",
    "metric": "binary_logloss",
    "random_state": RANDOM_STATE,
    "verbose": -1,
}

# API 설정
API_HOST = "0.0.0.0"
API_PORT = 8000
