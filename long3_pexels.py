import sys
import json
import os
import datetime

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 설정 =====
LONG_SCRIPT_FILE          = "long_script.json"
PEXELS_API_URL            = "https://api.pexels.com/videos/search"
PEXELS_PER_PAGE           = 10
MIN_VIDEO_DURATION        = 15   # seconds
USED_VIDEOS_FILE          = "used_videos.json"
USED_VIDEO_RETENTION_DAYS = 30

# (출력 파일명, long_script.json 내 image_prompt 위치)
BACKGROUNDS = [
    ("long_bg_main.mp4",   "intro"),    # 인트로 + 아웃트로 공용
    ("long_bg_issue1.mp4", "issue1"),
    ("long_bg_issue2.mp4", "issue2"),
]


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


def get_image_prompt(data, key):
    if key == "intro":
        return data["intro"]["image_prompt"]
    idx = int(key[-1]) - 1  # issue1 → 0
    return data["issues"][idx]["image_prompt"]


def search_videos(query, api_key):
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
    return videos


def pick_video_file(video):
    """HD(1280px 이상) 중 가장 작은 파일 선택. HD 없으면 첫 번째 파일."""
    files = video.get("video_files", [])
    if not files:
        raise Exception("video_files가 비어 있습니다.")
    hd_files = [f for f in files if f.get("width", 0) >= 1280]
    if hd_files:
        hd_files.sort(key=lambda f: f.get("width", 0))
        return hd_files[0]
    return files[0]


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

    used_ids = load_used_video_ids()
    print(f"최근 {USED_VIDEO_RETENTION_DAYS}일 사용 영상: {len(used_ids)}개 제외 대상")

    print("\n=== Pexels 배경 영상 다운로드 ===")
    total = len(BACKGROUNDS)
    for i, (filename, key) in enumerate(BACKGROUNDS, 1):
        query = get_image_prompt(data, key)
        print(f"  [{i}/{total}] {key} → '{query}'")
        videos = search_videos(query, api_key)
        video = select_best_video(videos, used_ids)
        print(f"    선택: ID={video['id']} / duration={video.get('duration', 0)}초")
        vfile = pick_video_file(video)
        download_video(vfile["link"], filename)
        save_used_video(video["id"])
        used_ids.add(video["id"])  # 동일 세션 내 3개 중복 방지

    print("\n배경 영상 3개 다운로드 완료")


if __name__ == "__main__":
    main()
