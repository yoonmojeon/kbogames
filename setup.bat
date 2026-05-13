@echo off
chcp 65001 >nul
echo ============================================
echo  KBO 승부예측 AI - 환경 설정
echo ============================================
echo.

:: Python 패키지 설치
echo [1/3] Python 패키지 설치 중...
pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] Python 패키지 설치 실패
    pause
    exit /b 1
)

:: PyTorch CUDA 설치 (RTX 5070 Ti - Blackwell sm_120, CUDA 12.8)
echo.
echo [2/3] PyTorch CUDA 설치 중... (RTX 5070 Ti Blackwell 최적화 - CUDA 12.8)
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
if errorlevel 1 (
    echo [경고] PyTorch GPU 설치 실패 - CPU 버전으로 대체
    pip install torch torchvision torchaudio
)

:: scipy 설치 (앙상블 가중치 최적화)
pip install scipy

:: 프론트엔드 빌드
echo.
echo [3/3] 프론트엔드 빌드 중...
cd frontend
npm install
npm run build
cd ..

echo.
echo ============================================
echo  설치 완료!
echo.
echo  다음 단계:
echo  1. python collect_data.py  (데이터 수집 ~1-2시간)
echo  2. python train_model.py   (모델 학습 ~10-30분)
echo  3. python run_server.py    (서버 시작)
echo  4. http://localhost:8000 접속
echo ============================================
pause
