import sys
import json
import os
import time
import calendar
import datetime
import argparse
from concurrent import futures

import feedparser
import requests
from dotenv import load_dotenv
from openai import OpenAI
import article_score as _article_score
import longform_link
from step3_chatgpt import _strip_signoff, SIGNOFF_DEFAULT_JA, SIGNOFF_FUNNEL_JA

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== RSS =====
RSS_URLS = [
    "https://www3.nhk.or.jp/rss/news/cat5.xml",         # NHK 経済
    "https://www3.nhk.or.jp/rss/news/cat6.xml",         # NHK 国際 (에너지·지정학 연동)
    "https://www3.nhk.or.jp/rss/news/cat2.xml",         # NHK 生活·社会政策 ← 신규
    "https://news.yahoo.co.jp/rss/topics/business.xml", # Yahoo Japan 経済
    "https://news.yahoo.co.jp/rss/topics/domestic.xml", # Yahoo Japan 国内 ← 신규
]
MAX_ARTICLES   = 5
MAX_CANDIDATES = 5
RSS_FETCH_LIMIT = 20
FRESHNESS_HOURS = 6
RECENT_USED_URL_DAYS = 30
ECONOMIC_KEYWORDS = ["株", "円", "物価", "金利", "為替", "経済", "GDP", "インフレ", "日銀", "財務"]
BLOCKED_KEYWORDS = [
    # 종목·주가 예측·추천
    "個別銘柄", "株価予想", "株価予測", "推奨銘柄", "注目株", "おすすめ株", "買い推奨", "売り推奨",
    # 가상화폐
    "暗号資産", "仮想通貨", "ビットコイン", "イーサリアム", "NFT",
    # 자산 운용 상품
    "NISA", "iDeCo", "投資信託", "つみたて投資", "積立NISA",
    # 부동산 투자
    "不動産投資", "REIT", "リート", "マンション投資", "不動産ファンド",
]

# ===== 출력 파일 =====
ARTICLE_FILE    = "article.json"
GPT_RESULT_FILE = "gpt_result.json"
OUTPUT_DIR      = "output"

# ===== 시간대 =====
JST = datetime.timezone(datetime.timedelta(hours=9))

SLOT_NAMES       = ["09", "18"]
SELECTION_TARGET = 2

def get_next_slot(out_dir):
    for slot in SLOT_NAMES:
        if not os.path.exists(os.path.join(out_dir, f"{slot}_gpt_result.json")):
            return slot
    return SLOT_NAMES[-1]

# ===== ChatGPT =====
GPT_MODEL       = "gpt-4.1-mini"
GPT_TEMPERATURE = 0.7
REQUIRED_KEYS     = {"title", "hook", "script", "hashtags", "korean_summary", "image_prompt"}
VALID_EXPRESSIONS = {"smile", "happy", "surprised", "shocked", "worried",
                     "angry", "anxious", "sad", "base"}
VALID_DIRECTIONS  = {"up", "down", "none"}

SYSTEM_PROMPT = """\
あなたはJSONのみを出力するAIです。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。
以下のキー以外は絶対に追加しないこと:
  title, hook, hook_korean, script, hashtags, korean_summary, expression, direction, image_prompt, short_title, thumb_headline
hashtagsは必ずJSON配列で出力すること。例: ["#Shorts", "#経済", "#日本"]
人名・企業名・役職名は正確に表記すること。略称・誤字・当て字は絶対禁止。

【モチエンの人格】
- 一人称: 「モチエン」(私やボクは使わない)
- 落ち着いた中性的な語り口、慌てない
- 視聴者を「あなた」で呼ぶ (皆さんは使わない)
- 数字を出すときは必ず一度立ち止まって解説する
- 経済の話を生活の手触りに翻訳する役割
- 政治的立場は取らない、事実と影響だけ語る

【モチエンが繰り返し使うフレーズ】
- 「これ、実はあなたの○○に関わってきます」
- 「数字だけ見ると○○ですが」
- 「結局のところ」
- 「ここがポイントです」

【モチエンが絶対に言わないこと】
- 投資の推奨や予想
- 政治家・特定企業への評価
- 視聴者の決定への干渉
- 「儲かる」「損する」という直接表現

【モチエンキャラクターシート】

■ 人格・話し方
- 落ち着いた口調で経済ニュースを整理して伝える、信頼感重視のニュースキャスター。
- 40〜60代の視聴者に向けて、難しい経済用語はやさしい言葉に言い換える。
- 視聴者を「あなた」と呼ぶ。
- 個人的な感情の起伏は出さず、事実を整理して落ち着いて伝える。

■ 背景設定
- 日本経済を20年見続けてきた、もちもち系経済ニュース解説キャラ。

■ 感情表現ルール
- 驚き・怒り・興奮などの強い感情表現は使わない。
- 「!」の多用禁止（1スクリプトに最大1回まで）。
- 「!」を2つ以上連続して使わないこと（「大変です！！」禁止）。
- 「〜と言われています」「〜という見方があります」など中立的な語尾を優先。
- 断定的な未来予測（「絶対に〜なります」「必ず〜になる」）は使わないこと。
- 「〜ですよね？」「〜じゃないですか」などの過剰な同意を求める語尾は多用しないこと（最大1回/スクリプト）。

■ 禁止語彙（絶対に使用しないこと）
- やばい / オワコン / 爆益 / 神回 / 草 / ガチで / マジで
- ぶっちゃけ / めっちゃ / やっぱ / リアルに / ヤバすぎ / すごすぎ
- その他、ネットスラング・若者言葉・投資扇動的な強調語彙はすべて禁止。
- 落ち着いたニュースキャスターの語彙のみ使用すること。

【絶対に扱わないテーマ】
このチャンネルは以下のテーマを絶対に扱わないこと。記事がこれらに該当する場合は、
title/script/hook/korean_summaryすべてに「__BLOCKED__」とだけ出力すること。他のフィールドは空文字でよい。
- 個別銘柄・株価予測・投資判断・買い推奨・売り推奨
- 暗号資産・仮想通貨・ビットコイン・NFT
- NISA・iDeCo・投資信託など個人資産運用商品の解説や推奨
- 不動産投資・REIT
- 金利・為替の動向を「資産運用・投資への影響」の文脈で語ること
  （政策・経済情勢・企業業績への影響としての解説は可）

扱える範囲: マクロ経済政策の社会的意味、企業動向、社会変化、国際情勢の経済的影響。"""

USER_PROMPT = """
【モチエンキャラクター設定】
- 冒頭の挨拶は禁止。最初の一文は必ずhookの内容から始めること。
- 落ち着いていて信頼感がある話し方（40〜60代向け）
- 難しい経済用語はやさしい言葉に言い換える
- 視聴者を「あなた」と呼ぶ
- scriptのサインオフはコードが自動追加するため、scriptに含めないこと

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
- 人名・企業名・役職名・専門経済用語は必ずふりがなを括弧で併記すること
- ふりがなはひらがなのみで記載（カタカナ・漢字は禁止）
- 日常漢字（政府・経済・会社・日本・市場など）はふりがな不要
- 誤読リスクのある固有名詞・複合語のみ対象
- 例：高市（たかいち）首相、黒字転換（くろじてんかん）、萩生田（はぎうだ）氏
- 人名・企業名・役職名は正確に表記すること
- short_title：6〜10字の核心キーワード
- image_prompt：Pexels検索用英語キーワード（例："japanese economy stock market"）
  場所・時間帯・アングル・素材（工場/オフィス/街並み/人物など）が毎回異なるよう
  具体的なシーンを英語で記述すること（例："factory workers morning shift" / "tokyo street evening crowd" / "office desk financial charts"）
- korean_summary：記事の要点を必ず韓国語（한국어）で1文にまとめること。例：「일본 GDP가 예상을 웃도는 성장률을 기록했습니다.」
- expression: サムネイル用キャラクター表情を1つ選ぶこと。

【選び方の手順(必ずこの順で考えること)】
ステップ1: 記事の支配的な感情トーンを一行で言語化する。
  例: 「明確な好材料・家計改善」「悪材料・負担増」「衝撃・速報的下落」
ステップ2: そのトーンに最も合うexpressionを下記から1つ選ぶ。
ステップ3: 選んだexpressionがhook/thumb_headlineのフレーム
  (前向き/否定的/驚き/不安)と一致するか確認。一致しなければ再選択。

【許可された9種とマッピング例】
happy   — 明確な好材料・家計改善
  例: 「春闘で大企業賃上げ率3年連続5%超」→ happy
smile   — 軽い好材料・安定・改善
  例: 「ガソリン価格、補助金で170円水準で安定」→ smile
worried — 悪材料・家計負担増・じわじわ悪化
  例: 「米価が4週ぶりに上昇」→ worried
sad     — 深刻な悪材料・大幅損失
  例: 「日銀の含み損45兆円規模に拡大」→ sad
shocked — 衝撃的な急騰急落・速報的事件
  例: 「日経平均が1日で5%急落」→ shocked
surprised — 意外な結果・反転・予想外
  例: 「予想に反し、消費者物価が下落」→ surprised
angry   — 怒り誘発・不公正・転嫁
  例: 「大手企業が補助金を価格に反映せず」→ angry
anxious — 不確実な見通し・先行き不透明
  例: 「日銀総裁、利上げ判断は経済情勢次第」→ anxious
base    — 純粋に中立的な情報説明(極力避ける、表情のある選択を優先)

【両面記事の処理ルール(重要)】
記事に「安定」「補助金」「支援策」「改善」など前向き語が含まれ、
かつ全体トーンも安定・改善方向であれば、worried/sadを選ばずsmile/happyを選ぶこと。
逆にこれらの語が含まれても全体トーンが「依然高水準」「効果限定的」
「先行き不透明」など否定的であれば、hook/thumb_headlineのフレームに従うこと。

【絶対禁止】
shy / embarrassed / sleepy は絶対に選ばない(自動選択では使用不可)。
- direction：記事の主要な経済的方向性を"up"（上昇・好材料）/ "down"（下落・悪材料）/ "none"（方向性が判別不可・高止まり・複合）から1つ選ぶこと
  ※数字があっても方向が曖昧な場合はnoneが正しい（例：170円の壁＝価格高止まり→none）
  ※上昇・下落が明確な場合はup/downを積極的に選ぶこと（例：家賃+12%急上昇→up）
- thumb_headline：サムネイル専用ヘッドライン。14字以内、名詞句または短い断定形。句読点・疑問符禁止。本文引用禁止。
  【数字優先ルール】記事に%(パーセント)・金額・倍数・順位などの核心数値がある場合、必ずその数値をthumb_headlineに含めること。
  数値が複数あれば最もインパクトの大きい1つを選ぶ。本当に数値がない記事のみワード型を使用してよい。
  良い例：「家賃+12%」「原油-6%」「170円の壁」
  悪い例：「最高」（数値なし）／「費用の負担」（数値なし）／「まる可能性があります」（本文引用）
- scriptの冒頭はhookの内容を繰り返さないこと。hookの次の情報・詳細から始めること。

ニュースタイトル：{title}
ニュース本文：{article_body}
"""

class BlockedArticleError(Exception):
    pass


# ===== API 잔액 경고 =====
OPENAI_BALANCE_WARN   = 3.0
ELEVENLABS_CHARS_WARN = 10000

# ===== 텔레그램 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
LONG_POLL_SEC      = 30
WAIT_TIMEOUT_SEC   = 600   # 단편 모드 10분
BATCH_TIMEOUT_SEC  = 1800  # 일괄 모드 30분

CALLBACK_SELECT  = "select"
CALLBACK_NEXT    = "next"
CALLBACK_CANCEL  = "cancel"
CALLBACK_TIMEOUT = "timeout"

_poll_offset = None

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
    """단편 모드: 버튼 응답 대기. 콜백 데이터 문자열 반환, 타임아웃 시 CALLBACK_TIMEOUT 반환."""
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


def batch_poll(article_msg_ids, deadline):
    """일괄 선택 모드 전용 폴러. 복수 메시지 콜백 + "취소" 텍스트 대기.
    (action, idx) 반환 — action: "sel"|"pas"|"cancel"|"timeout"."""
    global _poll_offset
    while time.time() < deadline:
        poll_sec = min(LONG_POLL_SEC, int(deadline - time.time()))
        if poll_sec <= 0:
            break
        params = {
            "timeout": poll_sec,
            "allowed_updates": ["callback_query", "message"],
        }
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
            msg = update.get("message")
            if msg and "취소" in msg.get("text", ""):
                return ("cancel", -1)
            cb = update.get("callback_query")
            if not cb:
                continue
            if cb["message"]["message_id"] not in article_msg_ids:
                continue
            tg_answer(cb["id"])
            action, idx_str = cb["data"].split("_", 1)
            return (action, int(idx_str))
    return ("timeout", -1)


# ─────────────────────────────────────────
# RSS
# ─────────────────────────────────────────

def sort_by_freshness(articles):
    """fresh tier(최근 FRESHNESS_HOURS 이내) → stale tier 순, tier 내부는 pubDate 최신순.
    calendar.timegm: UTC struct_time → epoch / time.time(): 현재 UTC epoch — 둘 다 UTC 기준."""
    now = time.time()
    threshold = FRESHNESS_HOURS * 3600

    def _key(a):
        pub = a.get("_published", 0)
        is_stale = 0 if (now - pub) <= threshold else 1
        return (is_stale, -pub)

    return sorted(articles, key=_key)


def contains_keyword(title, body):
    text = title + body
    return any(kw in text for kw in ECONOMIC_KEYWORDS)


def contains_blocked_keyword(title, body):
    """차단 키워드 포함 시 해당 키워드 반환, 없으면 None."""
    text = title + body
    for kw in BLOCKED_KEYWORDS:
        if kw in text:
            return kw
    return None


def get_used_urls():
    """당일 이미 사용한 기사 URL 집합 반환. 첫 실행이면 빈 set."""
    now_jst = datetime.datetime.now(JST)
    out_dir = os.path.join(OUTPUT_DIR, now_jst.strftime("%Y-%m-%d"))
    used = set()
    for slot in SLOT_NAMES:
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


def load_recent_used_urls(days: int) -> set:
    """최근 days일 이내 사용한 기사 URL 집합 반환. output 폴더 없거나 비어있으면 빈 set."""
    used = set()
    if not os.path.isdir(OUTPUT_DIR):
        return used
    now_jst = datetime.datetime.now(JST)
    cutoff_date = (now_jst - datetime.timedelta(days=days)).date()
    for folder in os.listdir(OUTPUT_DIR):
        try:
            folder_date = datetime.datetime.strptime(folder, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date < cutoff_date:
            continue
        folder_path = os.path.join(OUTPUT_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        for fname in os.listdir(folder_path):
            if not fname.endswith("_gpt_result.json"):
                continue
            try:
                with open(os.path.join(folder_path, fname), encoding="utf-8") as f:
                    data = json.load(f)
                url = data.get("article_url")
                if url:
                    used.add(url)
            except Exception:
                pass
    return used


def fetch_articles(limit: int = MAX_ARTICLES):
    used_urls = load_recent_used_urls(RECENT_USED_URL_DAYS)
    if used_urls:
        print(f"  최근 {RECENT_USED_URL_DAYS}일 사용된 기사 {len(used_urls)}개 제외")

    seen_urls = set(used_urls)
    all_articles = []

    for rss_url in RSS_URLS:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:RSS_FETCH_LIMIT]:
                if entry.link in seen_urls:
                    continue
                seen_urls.add(entry.link)
                body = entry.get("summary", "") or entry.get("description", "")
                pub_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                all_articles.append({
                    "title": entry.title,
                    "url": entry.link,
                    "article_body": body,
                    "_published": calendar.timegm(pub_struct) if pub_struct else 0,
                })
        except Exception as e:
            print(f"  [RSS 수집 실패] {rss_url}: {e}")

    if not all_articles:
        raise Exception("모든 RSS 피드에서 기사를 가져오지 못했습니다.")

    # 차단 키워드 필터 (filtered·fallback 양쪽에 적용)
    clean_articles = []
    for a in all_articles:
        blocked_kw = contains_blocked_keyword(a["title"], a["article_body"])
        if blocked_kw:
            print(f"[BLOCKED] 차단어 매칭: {blocked_kw} - {a['title']}")
        else:
            clean_articles.append(a)
    if len(clean_articles) < len(all_articles):
        print(f"  차단된 기사 {len(all_articles) - len(clean_articles)}개 제거")
    all_articles = clean_articles

    filtered = [a for a in all_articles if contains_keyword(a["title"], a["article_body"])]

    if filtered:
        print(f"경제 키워드 기사 {len(filtered)}개 / 전체 {len(all_articles)}개")
        return sort_by_freshness(filtered)[:limit]

    print("경제 키워드 기사 없음 → 전체 기사에서 선택")
    tg_send("⚠️ 경제 키워드 기사 없어 전체에서 선택")
    return sort_by_freshness(all_articles)[:limit]


# ─────────────────────────────────────────
# ChatGPT
# ─────────────────────────────────────────

def call_chatgpt(title, article_body, article=None):
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
    if any("__BLOCKED__" in str(data.get(k, "")) for k in ("title", "script", "hook")):
        raise BlockedArticleError("GPT가 투자 관련 주제로 차단했습니다.")
    if data.get("expression") not in VALID_EXPRESSIONS:
        data["expression"] = "base"
    if data.get("direction") not in VALID_DIRECTIONS:
        data["direction"] = "none"
    if not data.get("short_title"):
        data["short_title"] = data.get("title", "")[:8]
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise Exception(f"필수 키 누락: {missing}")
    _check_furigana(data.get("script", ""))

    # 사인오프: GPT 생성 분 제거 → 캐논 부착 (펀넬 분기)
    script_body = _strip_signoff(data.get("script", ""))
    matched_topic_id = None
    if article:
        try:
            topic = _article_score.match_topic(article)
            matched_topic_id = topic["id"] if topic else None
        except Exception:
            pass
    data["matched_topic_id"] = matched_topic_id
    active = longform_link.get_active_for_topic(matched_topic_id)
    if active:
        data["script"] = script_body + " " + SIGNOFF_FUNNEL_JA
        data["active_longform_url"]   = active.get("url", "")
        data["active_longform_title"] = active.get("title_ja", "")
        print(f"  [깔때기] {data['active_longform_title']} — {data['active_longform_url']}")
    else:
        data["script"] = script_body + " " + SIGNOFF_DEFAULT_JA
        data["active_longform_url"]   = ""
        data["active_longform_title"] = ""

    return data


def _check_furigana(script: str):
    """3자 이상 연속 한자가 있는데 후리가나 괄호가 0개면 경고 로그 출력 (파이프라인 중단 없음)."""
    import re as _re
    has_kanji_run = bool(_re.search(r"[一-鿿]{3,}", script))
    has_furigana  = bool(_re.search(r"[（(][ぁ-ん]{1,}[）)]", script))
    if has_kanji_run and not has_furigana:
        print("[경고] 스크립트에 3자 이상 연속 한자가 있지만 후리가나 괄호가 없습니다. GPT 출력 확인 권장.")


# ─────────────────────────────────────────
# 단편 모드 (run_pipeline.py 용 — 기사 1개 선택)
# ─────────────────────────────────────────

def build_preview(article, gpt, index, total):
    hashtags = " ".join(gpt["hashtags"])
    score = _article_score.life_score(article)
    topic = _article_score.match_topic(article)
    score_line = f"📊 생활밀착 {score}" if score > 0 else ""
    if topic:
        topic_label = topic.get("title_ko") or topic.get("title_ja", "")
        reason_text = topic.get("match_reason", "")
        topic_line = f" · 📌{topic_label[:16]}"
        topic_line += f" ({reason_text})" if reason_text else ""
    else:
        topic_line = ""
    meta_line = (score_line + topic_line).strip()
    meta_str = f"{meta_line}\n\n" if meta_line else ""
    return (
        f"<b>📰 기사 {index + 1}/{total}</b>\n\n"
        f"<b>{article['title']}</b>\n\n"
        f"🇰🇷 {gpt['korean_summary']}\n\n"
        f"{meta_str}"
        f"{hashtags}"
    )


def single_main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[오류] .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 입력하세요.")
        sys.exit(1)

    check_api_balance()
    flush_updates()
    print("=== RSS 수집 ===")
    try:
        articles = fetch_articles()
    except Exception as e:
        msg = f"⚠️ RSS 수집 실패 — 모든 소스 응답 없음\n{e}"
        print(f"[오류] {msg}")
        tg_send(msg)
        sys.exit(1)
    print(f"기사 {len(articles)}개 수집 완료\n")

    message_id = None

    for i, article in enumerate(articles):
        print(f"[{i + 1}/{len(articles)}] ChatGPT 분석 중: {article['title']}")

        loading_text = f"⏳ 기사 {i + 1}/{len(articles)} 분석 중..."
        if message_id is None:
            message_id = tg_send(loading_text)
        else:
            tg_edit(message_id, loading_text)

        try:
            gpt = call_chatgpt(article["title"], article["article_body"], article=article)
        except BlockedArticleError:
            print(f"  [차단] 투자 관련 주제 → 다음 기사로")
            tg_edit(message_id, "⚠️ 이 기사는 투자 관련 주제로 차단되었습니다. 다음 후보로 넘어갑니다.")
            continue
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
            gpt["raw_summary_jp"] = article["article_body"]
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

    tg_edit(message_id, "⚠️ 더 이상 기사가 없습니다.")
    print("기사를 모두 확인했습니다.")
    sys.exit(1)


# ─────────────────────────────────────────
# 일괄 선택 모드 (run_all.py 용 — 기사 3개 동시 선택)
# ─────────────────────────────────────────

def batch_main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[오류] .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 입력하세요.")
        sys.exit(1)

    check_api_balance()
    flush_updates()

    print("=== RSS 수집 ===")
    try:
        articles = fetch_articles()
    except Exception as e:
        msg = f"⚠️ RSS 수집 실패 — 모든 소스 응답 없음\n{e}"
        print(f"[오류] {msg}")
        tg_send(msg)
        sys.exit(1)
    print(f"후보 기사 {len(articles)}개 수집\n")

    # GPT 병렬 호출
    print("=== GPT 병렬 호출 중... ===")
    loading_msg_id = tg_send("⏳ 기사 분석 중... (최대 5개 병렬 처리)")

    def call_safe(article):
        try:
            return call_chatgpt(article["title"], article["article_body"], article=article)
        except BlockedArticleError as e:
            print(f"  [차단] {article['title'][:20]}: {e}")
            return None
        except Exception as e:
            print(f"  [GPT 오류] {article['title'][:20]}: {e}")
            return None

    with futures.ThreadPoolExecutor(max_workers=MAX_CANDIDATES) as ex:
        gpt_results = list(ex.map(call_safe, articles))

    candidates = [
        (articles[i], gpt_results[i])
        for i in range(len(articles))
        if gpt_results[i] is not None
    ]
    print(f"GPT 처리 성공: {len(candidates)}개")

    if len(candidates) < SELECTION_TARGET:
        msg = f"⚠️ GPT 처리 성공 기사가 {len(candidates)}개뿐입니다. 최소 {SELECTION_TARGET}개 필요합니다."
        print(f"[오류] {msg}")
        tg_edit(loading_msg_id, msg)
        sys.exit(1)

    # 후보 메시지 전송
    tg_edit(loading_msg_id, f"✅ 분석 완료 — {len(candidates)}개 기사\n{SELECTION_TARGET}개를 선택하세요.")

    article_msg_ids = set()
    for idx, (article, gpt) in enumerate(candidates):
        hashtags = " ".join(gpt["hashtags"]) if isinstance(gpt["hashtags"], list) else gpt["hashtags"]
        score = _article_score.life_score(article)
        topic = _article_score.match_topic(article)
        score_line = f"📊 생활밀착 {score}" if score > 0 else ""
        if topic:
            topic_label = topic.get("title_ko") or topic.get("title_ja", "")
            reason_text = topic.get("match_reason", "")
            topic_line = f" · 📌{topic_label[:16]}"
            topic_line += f" ({reason_text})" if reason_text else ""
        else:
            topic_line = ""
        meta_line = (score_line + topic_line).strip()
        meta_str = f"{meta_line}\n\n" if meta_line else ""
        text = (
            f"<b>📰 후보 {idx + 1}/{len(candidates)}</b>\n\n"
            f"<b>{article['title']}</b>\n\n"
            f"🇰🇷 {gpt['korean_summary']}\n\n"
            f"{meta_str}"
            f"{hashtags}"
        )
        buttons = {"inline_keyboard": [[
            {"text": "✅ 선택", "callback_data": f"sel_{idx}"},
            {"text": "❌ 패스", "callback_data": f"pas_{idx}"},
        ]]}
        mid = tg_send(text, reply_markup=buttons)
        article_msg_ids.add(mid)

    status_msg_id = tg_send(
        f'선택된 기사: 0/{SELECTION_TARGET}\n기사를 {SELECTION_TARGET}개 선택하면 영상 생성이 시작됩니다.\n"취소" 를 보내면 중단됩니다. (30분 타임아웃)'
    )

    # 선택 루프
    selected = []  # candidate index 순서대로
    deadline = time.time() + BATCH_TIMEOUT_SEC

    while len(selected) < SELECTION_TARGET and time.time() < deadline:
        action, idx = batch_poll(article_msg_ids, deadline)

        if action == "cancel":
            tg_edit(status_msg_id, "⛔ 취소됨")
            print("취소됨.")
            sys.exit(1)

        if action == "timeout":
            tg_edit(status_msg_id, "⏰ 30분 타임아웃 — 기사 선택이 완료되지 않았습니다.")
            print("타임아웃.")
            sys.exit(1)

        if action == "sel":
            if idx in selected:
                selected.remove(idx)       # 재탭 → 선택 해제
            elif len(selected) < SELECTION_TARGET:
                selected.append(idx)
            sel_labels = [f"{i + 1}번" for i in selected]
            status_text = f"선택된 기사: {len(selected)}/{SELECTION_TARGET}"
            if selected:
                status_text += "\n✅ " + ", ".join(sel_labels)
            if len(selected) < SELECTION_TARGET:
                status_text += f'\n기사를 {SELECTION_TARGET}개 선택하면 영상 생성이 시작됩니다.\n"취소" 를 보내면 중단됩니다.'
            tg_edit(status_msg_id, status_text)
        # "pas" → 무시

    # 3개 선택 완료 → 슬롯 파일 저장
    now_jst = datetime.datetime.now(JST)
    out_dir = os.path.join(OUTPUT_DIR, now_jst.strftime("%Y-%m-%d"))
    os.makedirs(out_dir, exist_ok=True)

    slot_times    = {"09": "07:00 JST", "18": "18:00 JST"}
    summary_lines = ["✅ 선택 완료! 영상 생성을 시작합니다.\n"]

    for order, cand_idx in enumerate(selected):
        slot = SLOT_NAMES[order]
        article, gpt = candidates[cand_idx]
        gpt["slot"]          = slot
        gpt["article_url"]   = article["url"]
        gpt["raw_summary_jp"] = article["article_body"]
        out_path = os.path.join(out_dir, f"{slot}_gpt_result.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(gpt, f, ensure_ascii=False, indent=2)
        print(f"저장: {out_path}")
        summary_lines.append(
            f"📌 {cand_idx + 1}번 → 슬롯{slot} ({slot_times[slot]})\n{gpt['title']}"
        )

    tg_edit(status_msg_id, "\n".join(summary_lines))
    print("=== 3개 기사 선택 완료 ===")


# ─────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true", help="3개 일괄 선택 모드 (run_all.py 전용)")
    args = parser.parse_args()

    if args.batch:
        batch_main()
    else:
        single_main()
