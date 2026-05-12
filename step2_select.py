import sys
import json
import os
import time
import datetime

import feedparser
import requests
from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== RSS =====
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat6.xml"
MAX_ARTICLES = 5
RSS_FETCH_LIMIT = 20
ECONOMIC_KEYWORDS = ["株", "円", "物価", "金利", "為替", "経済", "GDP", "インフレ", "日銀", "財務"]

# ===== 출력 파일 =====
ARTICLE_FILE = "article.json"
GPT_RESULT_FILE = "gpt_result.json"
OUTPUT_DIR = "output"

# ===== 시간대 =====
JST = datetime.timezone(datetime.timedelta(hours=9))

# 오늘 폴더에 파일이 몇 개 있는지 보고 순서대로 슬롯 배정 (09→13→18)
SLOT_ORDER = ["09", "13", "18"]

def get_next_slot(out_dir):
    for slot in SLOT_ORDER:
        if not os.path.exists(os.path.join(out_dir, f"{slot}_gpt_result.json")):
            return slot
    return SLOT_ORDER[-1]  # 3개 초과 시 18 덮어씀

# ===== ChatGPT =====
GPT_MODEL = "gpt-4.1-mini"
GPT_TEMPERATURE = 0.7
REQUIRED_KEYS = {"title", "hook", "script", "hashtags", "korean_summary",
                 "emotion", "image_prompt"}
VALID_EMOTIONS = {"smile", "happy", "surprised", "shocked", "worried",
                  "angry", "anxious", "sad", "neutral", "shy", "embarrassed", "sleepy"}

SYSTEM_PROMPT = """\
あなたはJSONのみを出力するAIです。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。
以下のキー以外は絶対に追加しないこと:
  title, hook, hook_korean, script, hashtags, korean_summary, emotion, image_prompt, short_title
人名・企業名・役職名は正確に表記すること。略称・誤字・当て字は絶対禁止。"""

USER_PROMPT = """
【モチエンキャラクター設定】
- 冒頭の挨拶は禁止。最初の一文は必ずhookの内容から始めること。
- 落ち着いていて信頼感がある話し方（40〜60代向け）
- 難しい経済用語はやさしい言葉に言い換える
- 視聴者を「あなた」と呼ぶ
- スクリプト末尾は必ず下記で締めること:
  「皆さんはどう思いますか？コメントで教えてください！
   以上、モチエンがお伝えしました！
   チャンネル登録お願いします！」

【title ルール】
- 30字以内
- 事実の羅列ではなく視聴者の損得・驚き・生活への影響に直結すること
- 数字・疑問形・「あなたの〇〇」形式を優先
- 例：✗「アゼルバイジャン産原油到着」→ ✅「ガソリン代安くなる？アゼルバイジャン産原油の力」

【hook ルール】
- 必ず日本語で生成すること
- 視聴者の生活・損得・驚きと直結させること
- 数字・疑問形・「あなたの○○が変わる」形式を優先すること

【hashtags ルール】
- 日本語または英語のみ（韓国語タグは絶対に含めないこと）
- 日本語検索ボリュームが高いタグを優先
- #Shorts必須

【その他】
- 誤読しやすい漢字にはふりがなを括弧で併記すること
- 人名・企業名・役職名は正確に表記すること
- short_title：6〜10字の核心キーワード
- image_prompt：Pexels検索用英語キーワード（例："japanese economy stock market"）

ニュースタイトル：{title}
ニュース本文：{article_body}
"""

# ===== API 잔액 경고 =====
OPENAI_BALANCE_WARN = 3.0       # USD
ELEVENLABS_CHARS_WARN = 10000   # 잔여 캐릭터 수

# ===== 텔레그램 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LONG_POLL_SEC = 30
WAIT_TIMEOUT_SEC = 600  # 10분

CALLBACK_SELECT = "select"
CALLBACK_NEXT = "next"
CALLBACK_CANCEL = "cancel"
CALLBACK_TIMEOUT = "timeout"  # 무응답 자동 진행용

_poll_offset = None  # 세션 내 getUpdates offset 공유

BUTTONS = {
    "inline_keyboard": [[
        {"text": "✅ 이 기사로 진행", "callback_data": CALLBACK_SELECT},
        {"text": "🔄 다음 기사",      "callback_data": CALLBACK_NEXT},
        {"text": "❌ 취소",           "callback_data": CALLBACK_CANCEL},
    ]]
}


# ─────────────────────────────────────────
# API 잔액 체크
# ─────────────────────────────────────────

def check_api_balance():
    warnings = []

    # OpenAI 잔액 확인
    try:
        openai_key = os.getenv("OPENAI_API_KEY", "")
        resp = requests.get(
            "https://api.openai.com/dashboard/billing/credit_grants",
            headers={"Authorization": f"Bearer {openai_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            balance = resp.json().get("total_available", None)
            if balance is not None and balance < OPENAI_BALANCE_WARN:
                warnings.append(f"⚠️ OpenAI 잔액 부족: ${balance:.2f} (기준 ${OPENAI_BALANCE_WARN})")
    except Exception:
        pass

    # ElevenLabs 잔여 캐릭터 확인
    try:
        el_key = os.getenv("ELEVENLABS_API_KEY", "")
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": el_key},
            timeout=10,
        )
        if resp.status_code == 200:
            sub = resp.json().get("subscription", {})
            remaining = sub.get("character_limit", 0) - sub.get("character_count", 0)
            if remaining < ELEVENLABS_CHARS_WARN:
                warnings.append(f"⚠️ ElevenLabs 잔여 캐릭터 부족: {remaining:,}자 (기준 {ELEVENLABS_CHARS_WARN:,}자)")
    except Exception:
        pass

    if warnings:
        msg = "🔴 <b>API 잔액 경고</b>\n\n" + "\n".join(warnings)
        try:
            tg_send(msg)
        except Exception:
            print("\n".join(warnings))


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
    global _poll_offset
    try:
        resp = requests.get(_tg("getUpdates"), params={"timeout": 0}, timeout=5)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
        if updates:
            _poll_offset = updates[-1]["update_id"] + 1
            requests.get(_tg("getUpdates"), params={"timeout": 0, "offset": _poll_offset}, timeout=5)
            print(f"  [오래된 업데이트 {len(updates)}개 제거]")
    except Exception:
        pass


def wait_for_callback(message_id):
    """버튼 응답 대기. 콜백 데이터 문자열 반환, 타임아웃 시 cancel 반환."""
    global _poll_offset
    deadline = time.time() + WAIT_TIMEOUT_SEC

    while time.time() < deadline:
        poll_sec = min(LONG_POLL_SEC, int(deadline - time.time()))
        if poll_sec <= 0:
            break

        params = {"timeout": poll_sec, "allowed_updates": ["callback_query"]}
        if _poll_offset is not None:
            params["offset"] = _poll_offset

        try:
            resp = requests.get(_tg("getUpdates"), params=params, timeout=poll_sec + 5)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [getUpdates 재시도] {e}")
            continue

        for update in resp.json().get("result", []):
            _poll_offset = update["update_id"] + 1
            cb = update.get("callback_query")
            if not cb:
                continue
            if cb["message"]["message_id"] != message_id:
                continue
            tg_answer(cb["id"])
            return cb["data"]

    return CALLBACK_TIMEOUT


# ─────────────────────────────────────────
# RSS
# ─────────────────────────────────────────

def contains_keyword(title, body):
    text = title + body
    return any(kw in text for kw in ECONOMIC_KEYWORDS)


def get_used_urls():
    """당일 이미 사용한 기사 URL 집합 반환. 첫 실행이면 빈 set."""
    now_jst = datetime.datetime.now(JST)
    out_dir = os.path.join(OUTPUT_DIR, now_jst.strftime("%Y-%m-%d"))
    used = set()
    for slot in SLOT_ORDER:
        path = os.path.join(out_dir, f"{slot}_gpt_result.json")
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                url = data.get("article_url")
                if url:
                    used.add(url)
            except Exception:
                pass
    return used


def fetch_articles():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        raise Exception("RSS 피드에서 기사를 가져오지 못했습니다.")

    used_urls = get_used_urls()
    if used_urls:
        print(f"  당일 사용된 기사 {len(used_urls)}개 제외")

    all_articles = []
    for entry in feed.entries[:RSS_FETCH_LIMIT]:
        if entry.link in used_urls:
            continue
        body = entry.get("summary", "") or entry.get("description", "")
        all_articles.append({"title": entry.title, "url": entry.link, "article_body": body})

    filtered = [a for a in all_articles if contains_keyword(a["title"], a["article_body"])]

    if filtered:
        print(f"경제 키워드 기사 {len(filtered)}개 / 전체 {len(all_articles)}개")
        return filtered[:MAX_ARTICLES]

    print("경제 키워드 기사 없음 → 전체 기사에서 선택")
    tg_send("⚠️ 경제 키워드 기사 없어 전체에서 선택")
    return all_articles[:MAX_ARTICLES]


# ─────────────────────────────────────────
# ChatGPT
# ─────────────────────────────────────────

def call_chatgpt(title, article_body):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_prompt = USER_PROMPT.format(title=title, article_body=article_body)
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
    if not data.get("short_title"):
        data["short_title"] = data.get("title", "")[:8]
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

    check_api_balance()
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

        if result in (CALLBACK_SELECT, CALLBACK_TIMEOUT):
            label = "⏳ <b>영상 생성 시작...</b>" if result == CALLBACK_SELECT else "⏳ <b>무응답 — 자동 진행...</b>"
            tg_edit(message_id, text + f"\n\n{label}")
            now_jst = datetime.datetime.now(JST)
            out_dir = os.path.join(OUTPUT_DIR, now_jst.strftime("%Y-%m-%d"))
            os.makedirs(out_dir, exist_ok=True)
            slot = get_next_slot(out_dir)
            gpt["slot"] = slot
            gpt["article_url"] = article["url"]
            out_path = os.path.join(out_dir, f"{slot}_gpt_result.json")
            with open(ARTICLE_FILE, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            with open(GPT_RESULT_FILE, "w", encoding="utf-8") as f:
                json.dump(gpt, f, ensure_ascii=False, indent=2)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(gpt, f, ensure_ascii=False, indent=2)
            print(f"\n선택 완료: {article['title']}")
            print(f"{ARTICLE_FILE}, {GPT_RESULT_FILE}, {out_path} 저장 완료")
            return

        if result == CALLBACK_CANCEL:
            tg_edit(message_id, text + "\n\n⛔ <b>취소됨</b>")
            print("취소됨.")
            sys.exit(1)

        # CALLBACK_NEXT → 다음 루프로 진행

    tg_edit(message_id, "⚠️ 더 이상 기사가 없습니다.")
    print("기사를 모두 확인했습니다.")
    sys.exit(1)


if __name__ == "__main__":
    main()
