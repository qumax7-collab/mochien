import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

PIPELINE = [
    "step2_select.py",
    "step4_pexels.py",
    "step5_tts.py",
    "step6_ffmpeg.py",
    "step7_whisper_subtitle.py",
    "step9_youtube.py",
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
            print("파이프라인 중단.")
            sys.exit(result.returncode)

    print(f"\n{'='*50}")
    print("✅ 파이프라인 완료")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
