# KBO 승부예측 AI

KBO 프로야구 경기 일정, 팀 성적, 1군 로스터를 수집해 경기 승률을 예측하는 웹 애플리케이션입니다.

## 주요 기능

- 날짜별 KBO 경기 조회 및 승부예측
- 완료 경기 스코어와 실제 승리팀 표시
- 직접 매치업 선택 예측
- 팀 순위, 최근 성적, 상대 전적 분석
- 실시간 1군 로스터 로드
- XGBoost, LightGBM, PyTorch 신경망 앙상블 모델
- RTX 5070 Ti / CUDA 12.8 환경 대응

## 기술 스택

- Python, FastAPI, Pandas, BeautifulSoup, Selenium
- XGBoost, LightGBM, PyTorch
- React, Vite, Recharts
- ChromeDriver / webdriver-manager

## 시작하기

### 1. 환경 설치

```bat
setup.bat
```

`setup.bat`은 Python 패키지, RTX 5070 Ti용 PyTorch nightly CUDA 12.8, 프론트엔드 의존성을 설치합니다.

### 2. 데이터 수집

```bash
python collect_data.py --all
```

기본 설정은 2016년부터 2026년 5월 12일까지 경기 결과를 수집합니다.

### 3. 모델 학습 (GPU 자동 감지)

```bash
python train_model.py
```

학습 결과와 모델 파일은 `model/saved/`에 생성됩니다. 이 디렉터리는 Git에 포함하지 않습니다.

### 4. 서버 실행

```bash
python run_server.py
```

브라우저에서 `http://localhost:8000`에 접속합니다.

### 5. 개발 모드

```bash
start_dev.bat
```

개발 모드는 FastAPI 서버와 Vite 개발 서버를 함께 실행합니다.

## 주요 API

- `GET /api/health`: 서버/모델 상태
- `GET /api/games/date?game_date=YYYY-MM-DD`: 날짜별 경기와 예측
- `GET /api/today`: 오늘 날짜 경기와 예측
- `POST /api/predict`: 직접 매치업 예측
- `GET /api/team/{team}/lineup`: 팀별 1군 로스터
- `POST /api/lineups/refresh`: 실시간 1군 로스터 갱신
- `GET /api/standings`: 팀 순위
- `GET /api/h2h/{home_team}/{away_team}`: 상대 전적

## 모델 구조

```
입력 피처 (~35개)
├── 팀 성적 (최근 5/10/20경기 이동평균)
│   ├── 승률, 득점, 실점, 득실차
│   └── 홈/원정 성적
├── 상황 지표
│   ├── 연속승패 (streak)
│   ├── 휴식일
│   └── 시즌 진행도
└── 상대 전적

XGBoost (CUDA)  ─┐
LightGBM (GPU)  ─┼→ 가중 앙상블 → 승리 확률
PyTorch MLP     ─┘
```

## 디렉터리 구조

```
kbo/
├── scraper/          # 데이터 수집
├── model/            # ML 모델
├── api/              # FastAPI 서버
├── frontend/         # React UI
├── data/
│   ├── raw/          # 원시 데이터 (Git 제외)
│   └── processed/    # 전처리 데이터 (Git 제외)
└── logs/             # 로그
```

## Git에 포함하지 않는 것

- `data/raw/`, `data/processed/`: 수집 데이터
- `model/saved/`: 학습된 모델 파일
- `logs/`: 실행 로그
- `frontend/node_modules/`, `frontend/dist/`: 의존성/빌드 산출물

## 주의사항

- 승부예측은 참고용입니다. 실제 경기 결과와 다를 수 있습니다.
- 데이터는 공개 웹사이트 기반으로 수집하며, 과도한 요청은 피해야 합니다.
- 1군 로스터는 실시간 갱신 시 외부 페이지 구조 변경에 영향을 받을 수 있습니다.
