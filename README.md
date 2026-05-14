# KBO 승부예측 AI

KBO 프로야구 경기 일정, 팀 성적, 1군 로스터를 수집해 경기 승률을 예측하는 웹 애플리케이션입니다.

## 주요 기능

- 날짜별 KBO 경기 조회 및 승부예측
- 완료 경기 스코어와 실제 승리팀 표시
- 직접 매치업 선택 예측
- 팀 순위, 최근 성적, 상대 전적 분석
- 실시간 1군 로스터 로드
- KBO 공식 최신 팀 순위 실시간 반영
- KBO 게임센터 기반 선발투수 전력분석 반영
- 예측 근거, 보정값, 데이터 품질 점수 표시
- 과거 경기 기준 선발투수/라인업 강도/날씨 환경 피처 병합
- 예측-실제 결과 비교 대시보드
- 로컬 Ollama LLM 기반 설명가능한 AI 해설
- XGBoost, LightGBM, PyTorch 신경망 앙상블 모델
- Elo 레이팅 피처와 예상 득점 모델
- LogLoss/Brier 기반 앙상블 가중치 최적화
- Docker, Compose, CI, 운영 스모크 테스트
- RTX 5070 Ti / CUDA 12.8 환경 대응

## 기술 스택

- Python, FastAPI, Pandas, BeautifulSoup, Selenium
- XGBoost, LightGBM, PyTorch
- React, Vite, Recharts
- ChromeDriver / webdriver-manager
- Docker, GitHub Actions, Ollama

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

### 6. 운영 모드

```bat
run_prod.bat
```

운영 모드는 React 프론트엔드를 빌드한 뒤 FastAPI를 reload 없이 실행합니다. 환경값은 `.env.example`을 참고해 설정할 수 있습니다.

### 7. Docker 배포

```bash
docker compose up --build -d
```

모델 파일과 수집 데이터는 `data/`, `model/saved/`, `logs/` 볼륨으로 유지합니다.

### 8. 운영 점검

```bash
python ops_smoke_test.py --base-url http://127.0.0.1:8000
```

매일 데이터 갱신과 재학습을 자동화하려면 Windows 작업 스케줄러나 cron에서 다음 명령을 등록합니다.

```bash
python daily_update.py
```

## 주요 API

- `GET /api/health`: 서버/모델 상태
- `GET /api/games/date?game_date=YYYY-MM-DD`: 날짜별 경기와 예측
- `GET /api/today`: 오늘 날짜 경기와 예측
- `POST /api/predict`: 직접 매치업 예측
- `GET /api/team/{team}/lineup`: 팀별 1군 로스터
- `POST /api/lineups/refresh`: 실시간 1군 로스터 갱신
- `GET /api/standings`: 팀 순위
- `POST /api/standings/refresh`: KBO 공식 최신 순위 강제 갱신
- `GET /api/h2h/{home_team}/{away_team}`: 상대 전적
- `GET /api/model/performance`: 예측-실제 결과 비교 지표와 최근 적중 기록
- `GET /api/llm/status`: 로컬 Ollama 연결 상태
- `POST /api/explain/prediction`: Ollama 기반 예측 설명 생성

## 배포 수준 판단

현재 상태는 개인 서버 또는 소규모 공개 배포 기준으로 실행 가능한 수준입니다. Docker, CI, 스모크 테스트, 일일 업데이트 스크립트가 포함되어 있습니다.

상용 서비스로 확장하려면 공식 데이터 라이선스, HTTPS/도메인, 장애 알림, 외부 모니터링, 클라우드 비밀값 관리가 추가로 필요합니다.

## 모델 구조

현재 모델은 2016년부터 2026년 5월 12일까지 수집한 KBO 경기 결과를 바탕으로, 각 경기 직전 시점에서 알 수 있는 정보만 사용해 홈팀 승리 여부를 학습합니다.

### 학습 대상

- 타깃: `home_win`
  - 홈팀 승리: `1`
  - 원정팀 승리: `0`
- 학습 데이터: KBO 정규시즌 경기 결과
- 분할 방식: 시간 순서 유지
  - 과거 경기로 학습
  - 이후 경기로 검증/테스트
  - 현재 경기 결과가 피처에 섞이지 않도록 이동평균에는 `shift(1)` 적용

### 입력 피처

```
입력 피처 (~80개+)
├── 팀 최근 성적 (최근 5/10/20경기 이동평균)
│   ├── 승률, 득점, 실점, 득실차
│   └── 홈/원정 성적
├── 상황 지표
│   ├── 연속승패 (streak)
│   ├── 휴식일
│   ├── 시즌 진행도
│   └── Elo 레이팅/기대승률
├── 상대 전적
│   ├── 같은 시즌 맞대결 경기 수
│   └── 홈팀 기준 상대 승률
├── 불펜 피로도 프록시
│   ├── 최근 3일 경기 수
│   ├── 최근 3일 실점
│   └── 최근 3일 고실점 경기 수
├── 선발투수/라인업 확장 피처
│   ├── 과거 선발투수 ERA/WHIP/이닝 프록시
│   ├── 라인업 OPS/OBP/장타력 프록시
│   └── 불펜 투구수 프록시
└── 구장 컨텍스트
    ├── 경기 이전까지의 구장별 평균 총득점 런팩터
    └── 기온/습도/풍속/강수/돔구장 여부

XGBoost (CUDA)  ─┐
LightGBM (GPU)  ─┼→ LogLoss/Brier 최적 가중 앙상블 → 기본 승률
PyTorch MLP     ─┘

예상 득점 모델 → 홈/원정 기대득점 → 보조 승률 신호
```

### 선발투수 반영 방식

예정 경기나 특정 날짜를 실시간 조회할 때는 KBO 게임센터 `START_PIT` 프리뷰에서 선발투수 전력분석을 가져옵니다.

수집하는 선발투수 정보:

- 선발투수 이름
- 투타 유형
- 시즌 승수
- ERA
- WAR
- 경기 수
- 선발 평균 이닝
- QS
- WHIP

이 값으로 홈/원정 선발투수 전력 점수를 만들고, 기본 앙상블 확률에 보정값을 더합니다. 따라서 같은 팀 매치업이어도 선발투수가 다르면 확률이 달라집니다.

예측 흐름:

```
날짜별 경기 조회
→ 팀 단위 최근 성적 피처 생성
→ 앙상블 모델로 기본 홈 승률 예측
→ 예상 득점 모델로 홈/원정 기대득점 계산
→ KBO 게임센터에서 선발투수 스탯 수집
→ 선발투수 전력 차이로 확률 보정
→ KBO 공식 최신 순위/최근10경기/홈·원정 성적 보정
→ 데이터 품질 점수 산출
→ 화면에 최종 승률, 선발투수 스탯, 보정값, 예측 근거 표시
→ 필요 시 로컬 Ollama LLM으로 자연어 해설 생성
```

### Ollama 설명형 AI

로컬에 Ollama가 실행 중이면 예측 카드의 `Ollama AI 설명 보기` 버튼으로 설명을 생성합니다.

```bash
ollama serve
ollama list
```

기본 주소는 `http://localhost:11434`이며, 다른 주소를 쓰려면 `.env` 또는 실행 환경에 `OLLAMA_BASE_URL`을 설정합니다. 사용 가능한 모델이 없거나 호출에 실패하면 시스템이 기본 설명문으로 폴백합니다.

### 추가 데이터 파일

실제 과거 날씨 데이터를 쓰려면 `data/raw/weather_context.csv`를 둘 수 있습니다.

```csv
date,stadium,temp_c,humidity,wind_mps,rain_mm
2026-05-12,잠실,21.4,61,2.1,0.0
```

파일이 없으면 계절성과 돔구장 여부를 기준으로 한 환경 프록시를 사용합니다.

### 현재 한계와 다음 개선 방향

- 과거 선발투수/라인업/날씨 피처는 실제 상세 데이터가 있으면 병합하고, 없으면 경기 이전 데이터 기반 프록시를 사용합니다.
- 상용 수준 정확도를 더 올리려면 공식/유료 데이터로 과거 타순, 개인 타자 OPS, 실제 투구수, 경기장별 실측 날씨를 장기 축적해야 합니다.
- 예측-실제 대시보드는 운영 모니터링용이며, 완전한 워크포워드 백테스트는 별도 리포트로 확장할 수 있습니다.

## 디렉터리 구조

```
kbo/
├── scraper/          # 데이터 수집
├── model/            # ML 모델
├── api/              # FastAPI 서버
├── frontend/         # React UI
├── .github/workflows # CI
├── Dockerfile        # 컨테이너 배포
├── docker-compose.yml
├── daily_update.py   # 일일 수집/재학습
├── ops_smoke_test.py # 운영 스모크 테스트
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

## 실시간 일정 스크래핑 (KBO 월간 스케줄)

`/api/games/date` 등은 Selenium으로 KBO `Schedule.aspx` 월간 표를 파싱합니다. KBO는 경기 전에 `삼성0vs0LG`처럼 **점수가 붙은 압축 문자열**로 표기하는 날이 있고, 예정만 있을 때는 `롯데 vs 두산` 형식입니다.

- 압축 점수형(`팀NvsM팀`)을 공백형 완료 패턴보다 **먼저** 판별합니다.
- `0vs0`은 실제 0–0 종료가 아니라 **경기 전 표기**로 간주해 예정 경기로 넣습니다.

`run_server.py`를 `KBO_RELOAD=false`(기본 reload 없음)로 띄운 뒤 `scraper/kbo_scraper.py`를 수정했다면, 변경이 반영되도록 **API 프로세스를 한 번 재시작**해야 합니다.
