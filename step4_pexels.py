import sys
import json
import os
import datetime
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

INPUT_FILE  = "gpt_result.json"
OUTPUT_FILE = "pexels_result.json"
VIDEO_FILE  = "background.mp4"

PEXELS_API_URL            = "https://api.pexels.com/videos/search"
PEXELS_PER_PAGE           = 10
MIN_VIDEO_DURATION        = 15   # seconds — 이 미만이면 루프 영상이 어색해짐
USED_VIDEOS_FILE          = "used_videos.json"
USED_VIDEO_RETENTION_DAYS = 30


def _entry_is_recent(e, cutoff: datetime.date) -> bool:
    """used_at(date) 또는 ts(unix) 두 형식 모두 지원."""
    if "used_at" in e:
        try:
            return datetime.date.fromisoformat(e["used_at"]) >= cutoff
        except Exception:
            return False
    if "ts" in e:
        try:
            return datetime.date.fromtimestamp(float(e["ts"])) >= cutoff
        except Exception:
            return False
    return False


def load_used_video_ids():
    """최근 30일 사용한 영상 ID set 반환. webui 형식(url/ts) 항목은 건너뜀."""
    if not os.path.exists(USED_VIDEOS_FILE):
        return set()
    try:
        with open(USED_VIDEOS_FILE, encoding="utf-8") as f:
            entries = json.load(f)
        cutoff = datetime.date.today() - datetime.timedelta(days=USED_VIDEO_RETENTION_DAYS)
        return {e["video_id"] for e in entries
                if "video_id" in e and e["video_id"] is not None
                and _entry_is_recent(e, cutoff)}
    except Exception:
        return set()


def save_used_video(video_id):
    """사용한 영상 ID를 used_videos.json에 누적 저장. 30일 초과 항목 자동 제거."""
    entries = []
    if os.path.exists(USED_VIDEOS_FILE):
        try:
            with open(USED_VIDEOS_FILE, encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            entries = []
    cutoff = datetime.date.today() - datetime.timedelta(days=USED_VIDEO_RETENTION_DAYS)
    entries = [e for e in entries if _entry_is_recent(e, cutoff)]
    entries.append({"video_id": video_id, "used_at": str(datetime.date.today())})
    with open(USED_VIDEOS_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def select_best_video(videos, used_ids):
    """미사용 영상 중 duration ≥ MIN_VIDEO_DURATION 최장 선택.
    없으면 미사용 전체 최장 → 전부 사용 이력 있으면 전체 pool fallback."""
    fresh = [v for v in videos if v["id"] not in used_ids]
    pool = fresh if fresh else videos
    long_enough = [v for v in pool if v.get("duration", 0) >= MIN_VIDEO_DURATION]
    if long_enough:
        return max(long_enough, key=lambda v: v.get("duration", 0))
    return max(pool, key=lambda v: v.get("duration", 0))


def search_video(query):
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key or api_key == "여기에_키_입력":
        raise Exception("PEXELS_API_KEY가 .env에 설정되지 않았습니다.")

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": PEXELS_PER_PAGE, "orientation": "landscape"}

    res = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=10)
    res.raise_for_status()
    data = res.json()

    if not data.get("videos"):
        raise Exception(f"검색 결과 없음: '{query}'")

    return data["videos"]


def pick_video_file(video):
    files = video.get("video_files", [])
    if not files:
        raise Exception("video_files가 비어 있습니다.")

    # HD(1280px 이상) 중 가장 작은 파일 선택 → 다운로드 속도 고려
    hd_files = [f for f in files if f.get("width", 0) >= 1280]
    if hd_files:
        hd_files.sort(key=lambda f: f.get("width", 0))
        return hd_files[0]

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
    videos = search_video(query)
    print(f"검색 결과  : {len(videos)}개")

    used_ids = load_used_video_ids()
    print(f"최근 {USED_VIDEO_RETENTION_DAYS}일 사용 영상: {len(used_ids)}개 제외 대상")

    video = select_best_video(videos, used_ids)
    print(f"영상 ID    : {video['id']} (duration: {video.get('duration', 0)}초)")
    print(f"영상 URL   : {video['url']}")

    vfile = pick_video_file(video)
    print(f"선택 파일  : {vfile.get('width')}x{vfile.get('height')} / {vfile.get('file_type')}")
    print(f"다운로드 URL: {vfile['link']}")

    print(f"\n=== {VIDEO_FILE} 다운로드 중... ===")
    download_video(vfile["link"], VIDEO_FILE)
    print(f"{VIDEO_FILE} 저장 완료")

    save_used_video(video["id"])
    print("used_videos.json 업데이트 완료")

    result = {
        "video_id":     video["id"],
        "video_url":    video["url"],
        "download_url": vfile["link"],
        "width":        vfile.get("width"),
        "height":       vfile.get("height"),
        "local_file":   VIDEO_FILE,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"{OUTPUT_FILE} 저장 완료")
    return result


if __name__ == "__main__":
    main()
