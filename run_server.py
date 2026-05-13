"""
FastAPI 서버 실행 스크립트
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    from config import API_HOST, API_PORT
    reload_enabled = os.getenv("KBO_RELOAD", "true").lower() in {"1", "true", "yes", "y"}
    host = os.getenv("KBO_API_HOST", API_HOST)
    port = int(os.getenv("KBO_API_PORT", API_PORT))

    print(f"\nKBO 승부예측 AI 서버 시작")
    print(f"주소: http://localhost:{port}")
    print(f"API 문서: http://localhost:{port}/docs")
    print(f"Reload: {'on' if reload_enabled else 'off'}")
    print("종료: Ctrl+C\n")

    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level="info",
    )


if __name__ == "__main__":
    main()
