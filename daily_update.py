"""
일일 운영 업데이트 스크립트.

경기 데이터/라인업을 갱신하고, 피처 재생성 및 모델 재학습까지 한 번에 수행한다.
Windows 작업 스케줄러나 cron에서 실행할 수 있다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).parent
LOG_DIR = ROOT / "logs"


def run_step(name: str, command: list[str]) -> None:
    print(f"\n[{datetime.now().isoformat(timespec='seconds')}] {name}")
    print(" ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="KBO daily update")
    parser.add_argument("--skip-collect", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--start-year", default="2016")
    parser.add_argument("--end-year", default=str(datetime.now().year))
    args = parser.parse_args()

    LOG_DIR.mkdir(exist_ok=True)

    try:
        if not args.skip_collect:
            run_step("collect games", [
                sys.executable, "collect_data.py",
                "--games",
                "--lineup",
                "--start-year", args.start_year,
                "--end-year", args.end_year,
            ])

        if not args.skip_train:
            run_step("retrain model", [
                sys.executable, "train_model.py",
                "--rebuild-features",
            ])

        print("\n일일 업데이트 완료")
        return 0
    except Exception as e:
        print(f"\n일일 업데이트 실패: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
