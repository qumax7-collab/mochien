import sys
import os
import shutil
import subprocess
import datetime
import glob
import requests
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

SLOTS          = ["09", "18"]
OUTPUT_DIR     = "output"
JST            = datetime.timezone(datetime.timedelta(hours=9))
RETENTION_DAYS = 30

TEMP_JSON_FILES = [
    "article.json",
    "gpt_result.json",
    "pexels_result.json",
    "long_script.json",
    "long_chapters.json",
    "subtitle.srt",
    "subtitle.ass",
    "long_subtitle.srt",
    "short_thumb.jpg",
]

SLOT_STEPS = [
    "step4_pexels.py",
    "step5_tts.py",
    "step6_ffmpeg.py",
    "step7_whisper_subtitle.py",
    "step8_thumbnail.py",
    "step9_youtube.py",
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


def today_dir():
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    return os.path.join(OUTPUT_DIR, today)


def slot_file(slot):
    return os.path.join(today_dir(), f"{slot}_gpt_result.json")


def clear_today_slots():
    for slot in SLOTS:
        path = slot_file(slot)
        if os.path.exists(path):
            os.remove(path)
            print(f"[삭제] {path}")


def cleanup_temp_files():
    targets = glob.glob("*.mp4") + glob.glob("*.mp3") + [
        f for f in TEMP_JSON_FILES if os.path.exists(f)
    ]
    deleted = []
    for path in targets:
        try:
            os.remove(path)
            deleted.append(path)
        except Exception as e:
            print(f"[정리 실패] {path}: {e}")
    if deleted:
        print(f"🗑 임시파일 정리: {len(deleted)}개 삭제")
        for f in deleted:
            print(f"  - {f}")
    else:
        print("🗑 임시파일 없음 (정리 불필요)")


def cleanup_old_output_folders(retention_days):
    if not os.path.exists(OUTPUT_DIR):
        return
    cutoff = datetime.datetime.now(JST).date() - datetime.timedelta(days=retention_days)
    for name in os.listdir(OUTPUT_DIR):
        folder_path = os.path.join(OUTPUT_DIR, name)
        if not os.path.isdir(folder_path):
            continue
        try:
            folder_date = datetime.date.fromisoformat(name)
        except ValueError:
            continue
        if folder_date < cutoff:
            shutil.rmtree(folder_path)
            print(f"🗑 30일 이전 폴더 삭제: {name}")


def tg_notify(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        print(f"[TG 알림 실패] {e}")


def run_step(script, extra_args=None):
    cmd = [sys.executable, script] + (extra_args or [])
    result = subprocess.run(cmd)
    return result.returncode


def main():
    cleanup_old_output_folders(RETENTION_DAYS)
    print("오늘 슬롯 파일 초기화 중...")
    clear_today_slots()
    try:
        # ── 1. 기사 일괄 선택 ───────────────────────────────────────────
        print(f"\n{'='*50}")
        print("step2_select.py --batch 실행 중...")
        print(f"{'='*50}")
        rc = run_step("step2_select.py", ["--batch"])
        if rc != 0:
            print(f"\n[실패] step2_select.py --batch — 종료 코드 {rc}")
            print("전체 파이프라인 중단.")
            sys.exit(rc)

        # 슬롯 파일 생성 확인
        missing = [s for s in SLOTS if not os.path.exists(slot_file(s))]
        if missing:
            msg = f"⚠️ 슬롯 파일 미생성: {missing}\n파이프라인 중단."
            print(msg)
            tg_notify(msg)
            sys.exit(1)

        # ── 2. 슬롯별 영상 생성 ─────────────────────────────────────────
        failed_slots = []
        for slot in SLOTS:
            print(f"\n{'='*50}")
            print(f"슬롯 {slot} 영상 생성 시작")
            print(f"{'='*50}")

            # Approach B: 슬롯 파일 → gpt_result.json 복사
            shutil.copy(slot_file(slot), "gpt_result.json")
            print(f"[복사] {slot_file(slot)} → gpt_result.json")

            slot_failed = False
            failed_step = None
            for script in SLOT_STEPS:
                print(f"\n  [{script}] 실행 중...")
                rc = run_step(script)
                if rc != 0:
                    slot_failed = True
                    failed_step = script
                    break

            if slot_failed:
                remaining = [s for s in SLOTS if s != slot and s not in failed_slots and s > slot]
                msg = (
                    f"⚠️ 슬롯 {slot} 영상 생성 실패\n"
                    f"실패 단계: {failed_step}\n"
                    f"나머지 슬롯({', '.join(remaining) if remaining else '없음'})은 계속 진행합니다."
                )
                print(f"\n{msg}")
                tg_notify(msg)
                failed_slots.append(slot)
                continue

            # step10 검수 — 실패해도 계속
            print(f"\n  [step10_gemini_review.py --mode shorts] 실행 중...")
            rc10 = run_step("step10_gemini_review.py", ["--mode", "shorts"])
            if rc10 != 0:
                print(f"  [step10 실패] 종료 코드 {rc10} — 계속 진행")

            print(f"\n✅ 슬롯 {slot} 완료")

        succeeded = len(SLOTS) - len(failed_slots)

        if succeeded == 0:
            print("\n[실패] 전체 슬롯 실패 — 롱폼 파이프라인 건너뜀.")
            sys.exit(1)

        print(f"\n{'='*50}")
        print(f"✅ 쇼츠 파이프라인 완료 ({succeeded}/{len(SLOTS)}편 성공)")
        print("💡 롱폼은 run_longform.py 로 단독 실행하세요.")
        print(f"{'='*50}")
    finally:
        cleanup_temp_files()


if __name__ == "__main__":
    main()
