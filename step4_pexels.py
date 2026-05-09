import sys
import json
import os
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

INPUT_FILE = "gpt_result.json"
OUTPUT_FILE = "pexels_result.json"
VIDEO_FILE = "background.mp4"

PEXELS_API_URL = "https://api.pexels.com/videos/search"


def search_video(query):
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key or api_key == "여기에_키_입력":
        raise Exception("PEXELS_API_KEY가 .env에 설정되지 않았습니다.")

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}

    res = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=10)
    res.raise_for_status()
    data = res.json()

    if not data.get("videos"):
        raise Exception(f"검색 결과 없음: '{query}'")

    return data["videos"][0]


def pick_video_file(video):
    files = video.get("video_files", [])
    if not files:
        raise Exception("video_files가 비어 있습니다.")

    # HD(1280px 이상) 중 가장 작은 파일 선택 → 다운로드 속도 고려
    hd_files = [f for f in files if f.get("width", 0) >= 1280]
    if hd_files:
        hd_files.sort(key=lambda f: f.get("width", 0))
        return hd_files[0]

    # HD 없으면 첫 번째 파일
    return files[0]


def download_video(url, dest):
    print(f"다운로드 중: {url}")
    res = requests.get(url, stream=True, timeout=60)
    res.raise_for_status()

    total = int(res.headers.get("content-length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in res.iter_content(chunk_size=1024 * 64):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\r  {pct:.1f}% ({downloaded // 1024}KB / {total // 1024}KB)", end="")

    print()


def main():
    print("=== gpt_result.json 로드 ===")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        gpt = json.load(f)

    query = gpt["image_prompt"]
    print(f"검색 키워드: {query}")

    print("\n=== Pexels API 검색 중... ===")
    video = search_video(query)
    print(f"영상 ID    : {video['id']}")
    print(f"영상 URL   : {video['url']}")

    vfile = pick_video_file(video)
    print(f"선택 파일  : {vfile.get('width')}x{vfile.get('height')} / {vfile.get('file_type')}")
    print(f"다운로드 URL: {vfile['link']}")

    print(f"\n=== {VIDEO_FILE} 다운로드 중... ===")
    download_video(vfile["link"], VIDEO_FILE)
    print(f"{VIDEO_FILE} 저장 완료")

    result = {
        "video_id": video["id"],
        "video_url": video["url"],
        "download_url": vfile["link"],
        "width": vfile.get("width"),
        "height": vfile.get("height"),
        "local_file": VIDEO_FILE,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"{OUTPUT_FILE} 저장 완료")
    return result


if __name__ == "__main__":
    main()
