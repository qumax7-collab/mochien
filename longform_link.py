"""롱폼 발행 슬롯 계산 + active_longform.json 읽기/쓰기 (SRP)."""
import json
import os
from datetime import datetime, timezone, timedelta

# ===== 상수 =====
ACTIVE_FILE   = "active_longform.json"
MAX_ACTIVE    = 6
PUBLISH_HOUR  = 18
SLOT_WEEKDAYS = {"sun": 6, "thu": 3}   # Python weekday(): Mon=0, Sun=6, Thu=3

JST = timezone(timedelta(hours=9))


def next_publish_jst(slot: str) -> str:
    """now 기준 다음 일(sun)/목(thu) 18:00 JST → RFC3339 문자열.

    - 오늘이 해당 요일이고 아직 18:00 안 지났으면 오늘 18:00 반환
    - 이미 지났거나 다른 요일이면 다음 해당 요일 18:00 반환
    """
    target_weekday = SLOT_WEEKDAYS.get(slot, SLOT_WEEKDAYS["sun"])
    now = datetime.now(JST)
    target = now.replace(hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)

    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0 and target <= now:
        days_ahead = 7
    target += timedelta(days=days_ahead)

    return target.isoformat()


def _load() -> list:
    if not os.path.exists(ACTIVE_FILE):
        return []
    try:
        with open(ACTIVE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(entries: list) -> None:
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def append_active(entry: dict) -> None:
    """active_longform.json 끝에 항목 추가 + MAX_ACTIVE 초과 시 앞에서 trim."""
    entries = _load()
    entries.append(entry)
    if len(entries) > MAX_ACTIVE:
        entries = entries[-MAX_ACTIVE:]
    _save(entries)


def get_active() -> dict | None:
    """publish_at_jst <= 현재 JST인 항목 중 가장 최신 1개 반환. 없으면 None."""
    now = datetime.now(JST)
    entries = _load()
    published = []
    for e in entries:
        try:
            pub = datetime.fromisoformat(e["publish_at_jst"])
            if pub <= now:
                published.append((pub, e))
        except Exception:
            pass
    if not published:
        return None
    published.sort(key=lambda x: x[0])
    return published[-1][1]


def get_active_for_topic(topic_id: str | None) -> dict | None:
    """같은 topic_id로 발행된 롱폼 중 가장 최신 1개 반환.
    없으면 get_active()(최신 발행 롱폼)로 폴백. 둘 다 없으면 None."""
    now = datetime.now(JST)
    entries = _load()
    published = []
    for e in entries:
        try:
            pub = datetime.fromisoformat(e["publish_at_jst"])
            if pub <= now:
                published.append((pub, e))
        except Exception:
            pass
    if not published:
        return None
    published.sort(key=lambda x: x[0])

    if topic_id:
        matched = [(pub, e) for pub, e in published if e.get("topic_id") == topic_id]
        if matched:
            return matched[-1][1]

    # 폴백: 최신 발행 롱폼
    return published[-1][1]


def get_upcoming() -> str | None:
    """publish_at_jst > 현재 JST인 항목 중 가장 가까운 것의 topic_id 반환. 없으면 None."""
    now = datetime.now(JST)
    entries = _load()
    future = []
    for e in entries:
        try:
            pub = datetime.fromisoformat(e["publish_at_jst"])
            if pub > now:
                future.append((pub, e))
        except Exception:
            pass
    if not future:
        return None
    future.sort(key=lambda x: x[0])
    return future[0][1].get("topic_id")
