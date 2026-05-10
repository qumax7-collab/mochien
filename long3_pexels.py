import sys
import json
import os

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 설정 =====
LONG_SCRIPT_FILE = "long_script.json"
PEXELS_API_URL   = "https://api.pexels.com/videos/search"
PEXELS_PER_PAGE  = 1

# (출력 파일명, long_script.json 내 image_prompt 위치)
BACKGROUNDS = [
    ("long_bg_main.mp4",   "intro"),    # 인트로 + 아웃트로 공용
    ("long_bg_issue1.mp4", "issue1"),
    ("long_bg_issue2.mp4", "issue2"),
    ("long_bg_issue3.mp4", "issue3"),
]


def get_image_prompt(data, key):
    if key == "intro":
        return data["intro"]["image_prompt"]
    idx = int(key[-1]) - 1  # issue1 → 0
    return data["issues"][idx]["image_prompt"]


def search_video(query, api_key):
    resp = requests.get(
        PEXELS_API_URL,
        headers={"Authorization": api_key},
        params={"query": query, "per_page": PEXELS_PER_PAGE},
        timeout=15,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        raise Exception(f"Pexels 검색 결과 없음: '{query}'")
    return videos[0]["video_files"][0]["link"]


def download_video(url, dest):
    print(f"    다운로드 중: {url[:60]}...")
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"    저장: {dest} ({size_mb:.1f}MB)")


def main():
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("[오류] .env에 PEXELS_API_KEY를 입력하세요.")
        sys.exit(1)

    print("=== long_script.json 로드 ===")
    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print("\n=== Pexels 배경 영상 다운로드 ===")
    total = len(BACKGROUNDS)
    for i, (filename, key) in enumerate(BACKGROUNDS, 1):
        query = get_image_prompt(data, key)
        print(f"  [{i}/{total}] {key} → '{query}'")
        url = search_video(query, api_key)
        download_video(url, filename)

    print("\n배경 영상 4개 다운로드 완료")


if __name__ == "__main__":
    main()
