"""생활밀착 점수 + 토픽뱅크 매치 (SRP)."""
import json
import os

TOPIC_BANK_FILE    = "topic_bank.json"
LIFE_KEYWORDS_FILE = "life_keywords.json"


def _load_keywords() -> dict:
    """life_keywords.json → {keyword: weight} dict. 파일 없으면 빈 dict."""
    if not os.path.exists(LIFE_KEYWORDS_FILE):
        return {}
    try:
        with open(LIFE_KEYWORDS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.get("keywords", {}).items()}
    except Exception:
        return {}


def _load_topics() -> list:
    """topic_bank.json → topics 리스트. 파일 없으면 빈 list."""
    if not os.path.exists(TOPIC_BANK_FILE):
        return []
    try:
        with open(TOPIC_BANK_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("topics", [])
    except Exception:
        return []


def life_score(article: dict) -> int:
    """기사 제목+본문에서 생활밀착 키워드 가중치 합산."""
    kw_map = _load_keywords()
    if not kw_map:
        return 0
    text = (article.get("title", "") + " " + article.get("article_body", ""))
    total = 0
    for kw, weight in kw_map.items():
        if kw in text:
            total += weight
    return total


def match_topic(article: dict) -> dict | None:
    """topic_bank.json keywords_ja와 기사 텍스트 중복 수 최다 토픽 반환. 0개면 None."""
    topics = _load_topics()
    if not topics:
        return None
    text = (article.get("title", "") + " " + article.get("article_body", ""))
    best_topic = None
    best_count = 0
    for t in topics:
        count = sum(1 for kw in t.get("keywords_ja", []) if kw in text)
        if count > best_count:
            best_count = count
            best_topic = t
    return best_topic if best_count > 0 else None


def enrich_articles(articles: list, active_topic_id: str | None = None) -> list:
    """각 기사에 life_score / match_topic_id / match_topic_ja / is_active_match 필드 추가.
    정렬: is_active_match=True 먼저 → life_score 내림차순.
    원본 리스트 미변경 — 새 리스트 반환.
    """
    enriched = []
    for a in articles:
        score = life_score(a)
        topic = match_topic(a)
        topic_id = topic["id"] if topic else None
        topic_ja = topic["title_ja"] if topic else None
        is_match = bool(active_topic_id and topic_id == active_topic_id)
        enriched.append({
            **a,
            "life_score":      score,
            "match_topic_id":  topic_id,
            "match_topic_ja":  topic_ja,
            "is_active_match": is_match,
        })

    enriched.sort(key=lambda x: (
        -int(x["is_active_match"]),
        -x["life_score"],
    ))
    return enriched
