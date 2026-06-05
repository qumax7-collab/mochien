"""생활밀착 점수 + 토픽뱅크 매치 (SRP).

match_topic / enrich_articles 는 GPT(gpt-4.1-mini) 인과·방향 판정을 사용.
키워드 사전필터 없음 — 토픽뱅크 전체를 GPT에 넘겨 정확도 우선.
확신 없으면 None (오매칭보다 폴백이 안전).
"""
import json
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

TOPIC_BANK_FILE    = "topic_bank.json"
LIFE_KEYWORDS_FILE = "life_keywords.json"
GPT_MODEL_MATCH    = "gpt-4.1-mini"

_SYSTEM_MATCH = (
    "당신은 경제 기사와 토픽 원리의 인과 방향 일치를 판정하는 AI입니다. "
    "JSON만 출력하세요. 다른 텍스트 절대 금지."
)


# ─────────────────────────────────────────────────────
# 내부 로드 헬퍼
# ─────────────────────────────────────────────────────

def _load_keywords() -> dict:
    if not os.path.exists(LIFE_KEYWORDS_FILE):
        return {}
    try:
        with open(LIFE_KEYWORDS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.get("keywords", {}).items()}
    except Exception:
        return {}


def _load_topics() -> list:
    if not os.path.exists(TOPIC_BANK_FILE):
        return []
    try:
        with open(TOPIC_BANK_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("topics", [])
    except Exception:
        return []


def _topics_block(topics: list) -> str:
    return "\n".join(
        f"- id: {t['id']}\n  원리: {t['principle']}"
        for t in topics
    )


# ─────────────────────────────────────────────────────
# GPT 판정 — 단건 / 배치
# ─────────────────────────────────────────────────────

def _gpt_judge_topic(article: dict, topics: list) -> tuple[str, str]:
    """기사 1건 × 토픽 전체 → GPT 인과·방향 판정 → (topic_id, reason).
    OPENAI_API_KEY 없거나 오류 시 ("none", "") 반환."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "none", ""
    title = article.get("title", "")
    body  = article.get("article_body", "")[:300]
    user = (
        f"【토픽 후보】\n{_topics_block(topics)}\n\n"
        f"【기사】\n제목: {title}\n본문: {body}\n\n"
        "이 기사의 인과·경제 방향이 위 토픽 중 하나의 원리에 명확히 부합하면 그 id를 반환.\n"
        "방향 반대(예: 가격 하락 기사 ↔ 가격 상승 메커니즘 토픽), 불확실, 맞는 토픽 없으면 \"none\".\n"
        "출력: {\"topic_id\": \"...\", \"reason\": \"한국어 근거 30자 이내\"}"
    )
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=GPT_MODEL_MATCH,
            messages=[
                {"role": "system", "content": _SYSTEM_MATCH},
                {"role": "user",   "content": user},
            ],
            temperature=0,
            max_tokens=120,
        )
        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        return str(data.get("topic_id", "none")), str(data.get("reason", ""))
    except Exception as e:
        print(f"[match_topic GPT 오류] {e}")
        return "none", ""


def _gpt_judge_topic_batch(articles: list, topics: list) -> list:
    """기사 N건 × 토픽 전체 → GPT 1회 배치 판정 → [(topic_id, reason), ...].
    오류 시 전체 ("none", "") 리스트 반환."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [("none", "")] * len(articles)
    articles_block = "\n".join(
        f"[{i}] 제목: {a.get('title', '')}\n     본문: {a.get('article_body', '')[:150]}"
        for i, a in enumerate(articles)
    )
    user = (
        f"【토픽 후보】\n{_topics_block(topics)}\n\n"
        f"【기사 목록 — {len(articles)}건】\n{articles_block}\n\n"
        "각 기사에 대해: 인과·방향이 토픽 원리에 명확히 부합하면 그 id를, 아니면 \"none\"을.\n"
        "방향 반대, 불확실, 어느 토픽도 안 맞으면 반드시 \"none\".\n"
        f"출력: 기사 순서대로 {len(articles)}개 객체의 JSON 배열.\n"
        "예: [{\"topic_id\": \"real-wage\", \"reason\": \"실질임금 구조와 인과 일치\"}, "
        "{\"topic_id\": \"none\", \"reason\": \"\"}]"
    )
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=GPT_MODEL_MATCH,
            messages=[
                {"role": "system", "content": _SYSTEM_MATCH},
                {"role": "user",   "content": user},
            ],
            temperature=0,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            raise ValueError("Expected JSON array")
        out = []
        for item in results[:len(articles)]:
            if isinstance(item, dict):
                out.append((str(item.get("topic_id", "none")), str(item.get("reason", ""))))
            else:
                out.append(("none", ""))
        while len(out) < len(articles):
            out.append(("none", ""))
        return out
    except Exception as e:
        print(f"[match_topic batch GPT 오류] {e}")
        return [("none", "")] * len(articles)


# ─────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────

def life_score(article: dict) -> int:
    """기사 제목+본문에서 생활밀착 키워드 가중치 합산."""
    kw_map = _load_keywords()
    if not kw_map:
        return 0
    text = (article.get("title", "") + " " + article.get("article_body", ""))
    return sum(w for kw, w in kw_map.items() if kw in text)


def match_topic(article: dict) -> dict | None:
    """GPT 인과·방향 판정으로 기사에 맞는 토픽 반환. 없으면 None.
    반환 dict에 match_reason(한국어 근거) 필드 포함.
    외부 시그니처 변경 없음 — step3_chatgpt 등 기존 호출부 무수정."""
    topics = _load_topics()
    if not topics:
        return None
    topic_id, reason = _gpt_judge_topic(article, topics)
    if not topic_id or topic_id == "none":
        return None
    for t in topics:
        if t["id"] == topic_id:
            result = dict(t)
            result["match_reason"] = reason
            return result
    return None


def enrich_articles(articles: list, active_topic_id: str | None = None) -> list:
    """각 기사에 life_score / match_topic_id / match_topic_ja / match_topic_ko /
    match_reason / is_active_match 필드 추가.
    GPT 1회 배치 호출로 전체 기사 판정 (호출 횟수 최소화).
    정렬: is_active_match=True 먼저 → life_score 내림차순.
    원본 리스트 미변경 — 새 리스트 반환.
    """
    if not articles:
        return []
    topics = _load_topics()
    judgments = _gpt_judge_topic_batch(articles, topics) if topics else [("none", "")] * len(articles)
    topic_map = {t["id"]: t for t in topics}

    enriched = []
    for a, (tid, reason) in zip(articles, judgments):
        score   = life_score(a)
        matched = topic_map.get(tid) if (tid and tid != "none") else None
        enriched.append({
            **a,
            "life_score":      score,
            "match_topic_id":  matched["id"]              if matched else None,
            "match_topic_ja":  matched.get("title_ja", "") if matched else None,
            "match_topic_ko":  matched.get("title_ko", "") if matched else None,
            "match_reason":    reason                      if matched else "",
            "is_active_match": bool(active_topic_id and matched and matched["id"] == active_topic_id),
        })
    enriched.sort(key=lambda x: (
        -int(x["is_active_match"]),
        -x["life_score"],
    ))
    return enriched
