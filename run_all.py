import sys
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

TOTAL_SLOTS = 3


def main():
    for i in range(1, TOTAL_SLOTS + 1):
        print(f"\n{'='*50}")
        print(f"쇼츠 슬롯 {i}/{TOTAL_SLOTS} 시작")
        print(f"{'='*50}")

        result = subprocess.run([sys.executable, "run_pipeline.py"])

        if result.returncode != 0:
            print(f"\n[실패] 슬롯 {i} — 종료 코드 {result.returncode}")
            print("전체 파이프라인 중단.")
            sys.exit(result.returncode)

    print(f"\n{'='*50}")
    print("✅ 전체 파이프라인 완료 (쇼츠 3편 + 롱폼)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
