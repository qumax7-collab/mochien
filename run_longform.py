import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

PIPELINE = [
    "long1_script.py",
    "long2_tts.py",
    "long3_pexels.py",
    "long4_ffmpeg.py",
    "long5_whisper.py",
    "long6_youtube.py",
]


def main():
    total = len(PIPELINE)
    for i, script in enumerate(PIPELINE, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{total}] {script} 실행 중...")
        print(f"{'='*50}")

        result = subprocess.run([sys.executable, script])

        if result.returncode != 0:
            print(f"\n[실패] {script} — 종료 코드 {result.returncode}")
            print("롱폼 파이프라인 중단.")
            sys.exit(result.returncode)

    # long6 완료 후 검수 — 실패해도 파이프라인 계속 진행
    print(f"\n{'='*50}")
    print("[step10] step10_gemini_review.py --mode longform 실행 중...")
    print(f"{'='*50}")
    r10 = subprocess.run([sys.executable, "step10_gemini_review.py", "--mode", "longform"])
    if r10.returncode != 0:
        print(f"[step10 실패] 종료 코드 {r10.returncode} — 계속 진행")

    print(f"\n{'='*50}")
    print("✅ 롱폼 파이프라인 완료")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
