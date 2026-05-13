@echo off
setlocal

set KBO_API_HOST=0.0.0.0
set KBO_API_PORT=8000
set KBO_RELOAD=false

echo [1/2] Frontend production build
cd frontend
call npm run build
if errorlevel 1 (
    echo Frontend build failed.
    exit /b 1
)
cd ..

echo [2/2] FastAPI production server
python run_server.py

endlocal
