"""모찌엔 웹 UI — Pexels 후보 관리 + used_videos.json 운용"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

BASE               = Path(__file__).parent
USED_VIDEOS_FILE   = BASE / "used_videos.json"
PEXELS_API_URL     = "https://api.pexels.com/videos/search"
RETENTION_DAYS     = 30
JST                = timezone(timedelta(hours=9))
PEXELS_QUERY_SUFFIX = " no people b-roll"  # 인물 클로즈업 억제


# ── 사용 이력 관리 ────────────────────────────────────────
def _load_raw() -> list:
    if not USED_VIDEOS_FILE.exists():
        return []
    try:
        return json.loads(USED_VIDEOS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _entry_is_recent(e: dict, cutoff_date) -> bool:
    """used_at(date str) 또는 ts(unix) 두 형식 모두 지원."""
    if "used_at" in e:
        try:
            from datetime import date as _date
            return _date.fromisoformat(e["used_at"]) >= cutoff_date
        except Exception:
            return False
    if "ts" in e:
        try:
            return datetime.fromtimestamp(e["ts"], tz=timezone.utc).date() >= cutoff_date
        except Exception:
            return False
    return False


def load_used_video_urls() -> set:
    """최근 RETENTION_DAYS일 이내 사용된 영상 URL 세트 반환 (used_at / ts 형식 모두 처리)."""
    cutoff = (datetime.now(JST) - timedelta(days=RETENTION_DAYS)).date()
    return {
        e["url"]
        for e in _load_raw()
        if e.get("url") and _entry_is_recent(e, cutoff)
    }


def save_used_video(url: str, thumb: str = ""):
    """사용된 영상 URL을 used_videos.json에 누적 저장 (used_at 형식)."""
    today = datetime.now(JST).date().isoformat()
    entries = [e for e in _load_raw() if e.get("url") != url]
    entries.append({"url": url, "thumb": thumb, "used_at": today})
    cutoff  = (datetime.now(JST) - timedelta(days=RETENTION_DAYS)).date()
    entries = [e for e in entries if _entry_is_recent(e, cutoff)]
    USED_VIDEOS_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Pexels API 호출 ───────────────────────────────────────
def fetch_pexels_candidates(query: str, count: int = 6, page_start: int = 1) -> list:
    """
    Pexels에서 count개 후보 영상을 가져온다.
    최근 30일 사용 영상은 제외하고, 부족하면 쿼리를 fallback으로 보완한다.
    page_start: 시작 페이지 (새로고침 시 2, 3으로 올려 다른 영상 세트 반환)
    반환: list of {url, thumb, duration, width, height}
    """
    api_key = os.getenv("PEXELS_API_KEY", "")
    headers = {"Authorization": api_key}
    used    = load_used_video_urls()
    query   = query.strip() + PEXELS_QUERY_SUFFIX

    candidates: list = []
    per_page   = min(count + len(used) + 5, 30)   # 여유 있게 요청
    page       = max(1, page_start)

    while len(candidates) < count and page <= page_start + 2:
        params = {"query": query, "per_page": per_page, "page": page}
        try:
            resp = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Pexels] API 오류: {e}")
            break

        videos = resp.json().get("videos", [])
        if not videos:
            break

        for v in videos:
            # 가장 긴 (고화질) 파일 우선
            files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
            if not files:
                continue
            best  = files[0]
            url   = best.get("link", "")
            thumb = v.get("image", "")

            if not url or url in used:
                continue

            candidates.append({
                "url":      url,
                "thumb":    thumb,
                "duration": v.get("duration", 0),
                "width":    best.get("width", 0),
                "height":   best.get("height", 0),
            })

            if len(candidates) >= count:
                break

        page += 1

    # 후보가 부족하고 fallback query 시도 (page_start=1 고정으로 무한재귀 방지)
    if len(candidates) < count and query != "japanese economy":
        extras = fetch_pexels_candidates("japanese economy", count - len(candidates), 1)
        existing_urls = {c["url"] for c in candidates}
        for e in extras:
            if e["url"] not in existing_urls:
                candidates.append(e)

    return candidates[:count]
