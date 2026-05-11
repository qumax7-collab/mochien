import sys
import os
import subprocess
import datetime

sys.stdout.reconfigure(encoding="utf-8")

PIPELINE = [
    "step2_select.py",
    "step4_pexels.py",
    "step5_tts.py",
    "step6_ffmpeg.py",
    "step7_whisper_subtitle.py",
    "step9_youtube.py",
]

OUTPUT_DIR = "output"
SLOT_FILES = ["09_gpt_result.json", "13_gpt_result.json", "18_gpt_result.json"]
JST = datetime.timezone(datetime.timedelta(hours=9))


def all_slots_done():
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    out_dir = os.path.join(OUTPUT_DIR, today)
    return all(os.path.exists(os.path.join(out_dir, f)) for f in SLOT_FILES)


def main():
    total = len(PIPELINE)
    for i, script in enumerate(PIPELINE, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{total}] {script} 실행 중...")
        print(f"{'='*50}")

        result = subprocess.run([sys.executable, script])

        if result.returncode != 0:
            print(f"\n[실패] {script} — 종료 코드 {result.returncode}")
            print("파이프라인 중단.")
            sys.exit(result.returncode)

    print(f"\n{'='*50}")
    print("✅ 쇼츠 파이프라인 완료")
    print(f"{'='*50}")

    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    out_dir = os.path.join(OUTPUT_DIR, today)
    completed = sum(1 for f in SLOT_FILES if os.path.exists(os.path.join(out_dir, f)))
    print(f"오늘 쇼츠: {completed}/3 완료")

    if all_slots_done():
        print("\n3개 완료 → 롱폼 파이프라인 자동 실행")
        print(f"{'='*50}")
        result = subprocess.run([sys.executable, "run_longform.py"])
        if result.returncode != 0:
            print(f"\n[실패] run_longform.py — 종료 코드 {result.returncode}")
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
