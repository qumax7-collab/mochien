import argparse
import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

# long6 이전 스크립트 목록 (--slot 인수 불필요)
PIPELINE_PRE_UPLOAD = [
    "long1_script.py",
    "long2_tts.py",
    "long3_pexels.py",
    "long_render_charts.py",   # 차트 데이터 fetch + Remotion 렌더
    "long4_ffmpeg.py",
    "long5_whisper.py",
]
LONG7 = "long7_wordpress.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default="sun", choices=["sun", "thu"],
                        help="발행 슬롯 (sun=일요일 / thu=목요일, 기본: sun)")
    parser.add_argument("--skip-long1", action="store_true",
                        help="KO/JA 이미 완료 시 long1_script.py 건너뜀")
    args = parser.parse_args()

    pre = PIPELINE_PRE_UPLOAD[1:] if args.skip_long1 else PIPELINE_PRE_UPLOAD
    pipeline = pre + [f"long6_youtube.py --slot {args.slot}", LONG7]
    total = len(pipeline)

    for i, entry in enumerate(pipeline, 1):
        parts = entry.split()
        script = parts[0]
        extra  = parts[1:]

        print(f"\n{'='*50}")
        print(f"[{i}/{total}] {entry} 실행 중...")
        print(f"{'='*50}")

        result = subprocess.run([sys.executable, script] + extra)

        if result.returncode != 0:
            print(f"\n[실패] {entry} — 종료 코드 {result.returncode}")
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
