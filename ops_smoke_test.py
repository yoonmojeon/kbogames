"""
운영 배포 전 스모크 테스트.

서버가 떠 있는 상태에서 핵심 API와 정적 페이지 응답을 확인한다.
"""
from __future__ import annotations

import argparse
import sys
import requests


def check(name: str, url: str, timeout: int = 15) -> dict:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    try:
        payload = resp.json()
    except Exception:
        payload = {"status_code": resp.status_code}
    print(f"[OK] {name}: {resp.status_code}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="KBO predictor smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    try:
        health = check("health", f"{base}/api/health")
        if not health.get("model_loaded"):
            raise RuntimeError("model_loaded=false")
        if not health.get("data_loaded"):
            raise RuntimeError("data_loaded=false")

        check("teams", f"{base}/api/teams")
        perf = check("performance", f"{base}/api/model/performance?limit=50", timeout=30)
        if not perf.get("available"):
            raise RuntimeError(f"performance unavailable: {perf}")

        llm = check("llm", f"{base}/api/llm/status")
        print(f"[INFO] ollama_available={llm.get('available')} selected_model={llm.get('selected_model')}")

        page = requests.get(f"{base}/", timeout=15)
        page.raise_for_status()
        print(f"[OK] page: {page.status_code}")
        return 0
    except Exception as e:
        print(f"[FAIL] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
