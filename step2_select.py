import sys
import json
import os
import time

import feedparser
import requests
from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== RSS =====
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat6.xml"
MAX_ARTICLES = 5

# ===== 출력 파일 =====
ARTICLE_FILE = "article.json"
GPT_RESULT_FILE = "gpt_result.json"

# ===== ChatGPT =====
GPT_MODEL = "gpt-4.1-mini"
GPT_TEMPERATURE = 0.7
REQUIRED_KEYS = {"title", "hook", "script", "hashtags", "korean_summary",
                 "emotion", "image_prompt", "short_title"}
VALID_EMOTIONS = {"smile", "happy", "surprised", "shocked", "worried",
                  "angry", "anxious", "sad", "neutral", "shy", "embarrassed", "sleepy"}

SYSTEM_PROMPT = """\
あなたはJSONのみを出力するAIです。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。
以下のキー以外は絶対に追加しないこと:
  title, hook, script, hashtags, korean_summary, emotion, image_prompt, short_title"""

USER_PROMPT_TEMPLATE = """\
【モチエンキャラクター設定】
- 落ち着いていて信頼感がある話し方（40〜60代向け）
- 難しい経済用語はやさしい言葉に言い換える
- 視聴者を「あなた」と呼ぶ
- スクリプト末尾は必ず「以上、モチエンがお伝えしました！」で締める

short_title : 6〜10字の核心キーワード（例:「日越首脳会談」「原油急騰の影響」）
image_prompt: Pexels検索用英語キーワード（例: "japanese economy stock market"）

emotion許容値:
smile / happy / surprised / shocked / worried / angry / anxious / sad / neutral / shy / embarrassed / sleepy

ニュースタイトル: {title}
ニュース本文: {article_body}
"""

# ===== 텔레그램 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LONG_POLL_SEC = 30
WAIT_TIMEOUT_SEC = 300  # 5분

CALLBACK_SELECT = "select"
CALLBACK_NEXT = "next"
CALLBACK_CANCEL = "cancel"

BUTTONS = {
    "inline_keyboard": [[
        {"text": "✅ 이 기사로 진행", "callback_data": CALLBACK_SELECT},
        {"text": "🔄 다음 기사",      "callback_data": CALLBACK_NEXT},
        {"text": "❌ 취소",           "callback_data": CALLBACK_CANCEL},
    ]]
}


# ─────────────────────────────────────────
# 텔레그램 헬퍼
# ─────────────────────────────────────────

def _tg(method):
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"


def tg_send(text, reply_markup=None):
    body = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        body["reply_markup"] = reply_markup
    resp = requests.post(_tg("sendMessage"), json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["message_id"]


def tg_edit(message_id, text, reply_markup=None):
    body = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        body["reply_markup"] = reply_markup
    requests.post(_tg("editMessageText"), json=body, timeout=10)


def tg_answer(callback_query_id):
    requests.post(
        _tg("answerCallbackQuery"),
        json={"callback_query_id": callback_query_id, "text": ""},
        timeout=10,
    )


def flush_updates():
    """이전 세션의 오래된 콜백 업데이트를 큐에서 비워 재처리 방지."""
    try:
        resp = requests.get(_tg("getUpdates"), params={"timeout": 0}, timeout=5)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        if updates:
            last_id = updates[-1]["update_id"]
            requests.get(_tg("getUpdates"), params={"timeout": 0, "offset": last_id + 1}, timeout=5)
            print(f"  [오래된 업데이트 {len(updates)}개 제거]")
    except Exception:
        pass


def wait_for_callback(message_id):
    """버튼 응답 대기. 콜백 데이터 문자열 반환, 타임아웃 시 cancel 반환."""
    offset = None
    deadline = time.time() + WAIT_TIMEOUT_SEC

    while time.time() < deadline:
        poll_sec = min(LONG_POLL_SEC, int(deadline - time.time()))
        if poll_sec <= 0:
            break

        params = {"timeout": poll_sec, "allowed_updates": ["callback_query"]}
        if offset is not None:
            params["offset"] = offset

        try:
            resp = requests.get(_tg("getUpdates"), params=params, timeout=poll_sec + 5)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [getUpdates 재시도] {e}")
            continue

        for update in resp.json().get("result", []):
            offset = update["update_id"] + 1
            cb = update.get("callback_query")
            if not cb:
                continue
            if cb["message"]["message_id"] != message_id:
                continue
            tg_answer(cb["id"])
            return cb["data"]

    return CALLBACK_CANCEL


# ─────────────────────────────────────────
# RSS
# ─────────────────────────────────────────

def fetch_articles():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        raise Exception("RSS 피드에서 기사를 가져오지 못했습니다.")
    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        body = entry.get("summary", "") or entry.get("description", "")
        articles.append({"title": entry.title, "url": entry.link, "article_body": body})
    return articles


# ─────────────────────────────────────────
# ChatGPT
# ─────────────────────────────────────────

def call_chatgpt(title, article_body):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_prompt = USER_PROMPT_TEMPLATE.format(title=title, article_body=article_body)
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=GPT_TEMPERATURE,
    )
    raw = response.choices[0].message.content.strip()
    data = json.loads(raw)
    if data.get("emotion") not in VALID_EMOTIONS:
        data["emotion"] = "neutral"
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise Exception(f"필수 키 누락: {missing}")
    return data


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def build_preview(article, gpt, index, total):
    hashtags = " ".join(gpt["hashtags"])
    return (
        f"<b>📰 기사 {index + 1}/{total}</b>\n\n"
        f"<b>{article['title']}</b>\n\n"
        f"🇰🇷 {gpt['korean_summary']}\n\n"
        f"{hashtags}"
    )


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[오류] .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 입력하세요.")
        sys.exit(1)

    flush_updates()
    print("=== NHK cat6 RSS 수집 ===")
    articles = fetch_articles()
    print(f"기사 {len(articles)}개 수집 완료\n")

    message_id = None

    for i, article in enumerate(articles):
        print(f"[{i + 1}/{len(articles)}] ChatGPT 분석 중: {article['title']}")

        # ChatGPT 실행 전 로딩 메시지 먼저 표시
        loading_text = f"⏳ 기사 {i + 1}/{len(articles)} 분석 중..."
        if message_id is None:
            message_id = tg_send(loading_text)
        else:
            tg_edit(message_id, loading_text)

        try:
            gpt = call_chatgpt(article["title"], article["article_body"])
        except Exception as e:
            print(f"  [ChatGPT 오류] {e} → 다음 기사로 넘어갑니다.")
            continue

        print(f"  한국어 요약: {gpt['korean_summary']}")

        text = build_preview(article, gpt, i, len(articles))
        tg_edit(message_id, text, BUTTONS)

        result = wait_for_callback(message_id)

        if result == CALLBACK_SELECT:
            tg_edit(message_id, text + "\n\n⏳ <b>영상 생성 시작...</b>")
            with open(ARTICLE_FILE, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            with open(GPT_RESULT_FILE, "w", encoding="utf-8") as f:
                json.dump(gpt, f, ensure_ascii=False, indent=2)
            print(f"\n선택 완료: {article['title']}")
            print(f"{ARTICLE_FILE}, {GPT_RESULT_FILE} 저장 완료")
            return

        if result == CALLBACK_CANCEL:
            tg_edit(message_id, text + "\n\n⛔ <b>취소됨</b>")
            print("취소됨.")
            sys.exit(0)

        # CALLBACK_NEXT → 다음 루프로 진행

    tg_edit(message_id, "⚠️ 더 이상 기사가 없습니다.")
    print("기사를 모두 확인했습니다.")
    sys.exit(0)


if __name__ == "__main__":
    main()
