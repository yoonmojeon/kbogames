@echo off
chcp 65001 >nul
echo KBO 승부예측 AI - 개발 서버 시작

:: FastAPI 백엔드 (백그라운드)
start cmd /k "python run_server.py"

:: React 개발서버
cd frontend
npm run dev
