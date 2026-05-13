"""
FastAPI 서버 실행 스크립트
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    from config import API_HOST, API_PORT
    print(f"\nKBO 승부예측 AI 서버 시작")
    print(f"주소: http://localhost:{API_PORT}")
    print(f"API 문서: http://localhost:{API_PORT}/docs")
    print("종료: Ctrl+C\n")

    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
