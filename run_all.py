import sys
import os
import subprocess
import datetime

sys.stdout.reconfigure(encoding="utf-8")

TOTAL_SLOTS = 3
SLOT_FILES = ["09_gpt_result.json", "13_gpt_result.json", "18_gpt_result.json"]
OUTPUT_DIR = "output"
JST = datetime.timezone(datetime.timedelta(hours=9))


def today_dir():
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, today)


def clear_today_slots():
    out_dir = today_dir()
    for fname in SLOT_FILES:
        path = os.path.join(out_dir, fname)
        if os.path.exists(path):
            os.remove(path)
            print(f"[삭제] {path}")


def all_slots_done():
    out_dir = today_dir()
    return all(os.path.exists(os.path.join(out_dir, f)) for f in SLOT_FILES)


def main():
    print("오늘 슬롯 파일 초기화 중...")
    clear_today_slots()

    for i in range(1, TOTAL_SLOTS + 1):
        print(f"\n{'='*50}")
        print(f"쇼츠 슬롯 {i}/{TOTAL_SLOTS} 시작")
        print(f"{'='*50}")

        result = subprocess.run([sys.executable, "run_pipeline.py"])

        if result.returncode != 0:
            print(f"\n[실패] 슬롯 {i} — 종료 코드 {result.returncode}")
            print("전체 파이프라인 중단.")
            sys.exit(result.returncode)

        if all_slots_done():
            break

    print(f"\n{'='*50}")
    print("✅ 전체 파이프라인 완료 (쇼츠 3편 + 롱폼)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
