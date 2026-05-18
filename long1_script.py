import sys
import json
import os
import datetime

from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 설정 =====
GPT_MODEL        = "gpt-4.1"
GPT_TEMPERATURE  = 0.7
OUTPUT_DIR       = "output"
LONG_SCRIPT_FILE = "long_script.json"
SLOTS            = ["09", "18"]

JST              = datetime.timezone(datetime.timedelta(hours=9))
MIN_ISSUE_CHARS  = 700   # 재시도 임계값 (자)

# ===== 공통 시스템 프롬프트 (5회 모두 적용) =====
SYSTEM_PROMPT = """\
あなたは日本経済の専門解説者です。JSONのみを出力してください。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。

【モチエンの人格】
- 一人称: 「モチエン」(私やボクは使わない)
- 落ち着いた中性的な語り口、慌てない
- 視聴者を「あなた」で呼ぶ (皆さんは使わない)
- 数字を出すときは必ず一度立ち止まって解説する
- 経済の話を生活の手触りに翻訳する役割
- 政治的立場は取らない、事実と影響だけ語る
- 末尾は必ず「以上、モチエンがお伝えしました！」

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

【文章スタイル】
- 項目番号や見出しを出力に含めないこと
- すべての項目を自然な日本語の文章として統合すること
- 「背景として〜」「現状を見ると〜」のような滑らかな繋ぎ言葉を使うこと
- 誤読しやすい漢字にはふりがなを括弧で併記すること（例：財務省（ざいむしょう））\
"""

# ===== 섹션별 유저 프롬프트 =====
PROMPT_INTRO = """\
【イントロセクション生成】
以下の2つのトピックを紹介するイントロを書いてください。

必須項目（すべて含めること / 各項目3〜4文）:
1. フック: 視聴者を引き込む冒頭の一文（数字・疑問・生活への影響）
2. 今日の2つのトピック紹介: 各トピックを1〜2文で予告
3. 共通テーマの提示: 2つを貫く経済トレンドを一言で

末尾は必ず「今日は2つのニュースを深掘りしていきます。」で締めること。

【本日のトピック】
■ トピック①: {title1}（{summary1}）
■ トピック②: {title2}（{summary2}）

出力フォーマット（このJSONのみ）:
{{
  "content": "イントロスクリプト本文",
  "summary": "次のセクションへ渡す要点3行（日本語）",
  "image_prompt": "Pexels検索用英語キーワード（場所・時間帯・素材を具体的に / 例: 'tokyo cityscape dawn' / 'japanese office workers meeting'）"
}}\
"""

PROMPT_ISSUE = """\
【トピック{idx}セクション生成】
このセクション全体で最低700字以上の日本語で書くこと。
titleは必ず日本語のみで書くこと（韓国語・英語禁止）。

必須項目（すべて含めること / 各項目2〜3文）:
1. 背景: なぜこの出来事が起きたのか
2. 現状の事実: 数値・固有名詞・引用を原文から正確に
3. データの読み解き: 数字が示す本当の意味
4. 影響分析: 誰が得をして誰が損をするか、産業・市場への波及
5. 視聴者へのメッセージ: 日常生活・家計への具体的アドバイス

【トピック{idx} 原文（日本語）】
{raw}

【これまでの流れ（前セクション要約）】
{prev_summaries}

出力フォーマット（このJSONのみ）:
{{
  "title": "このトピックのセクションタイトル（日本語のみ・14字以内）",
  "content": "トピック{idx}スクリプト本文",
  "summary": "次のセクションへ渡す要点3行（日本語）"
}}\
"""

PROMPT_OUTRO = """\
【アウトロセクション生成】
以下の2つのトピックをまとめるアウトロを書いてください。

必須項目（すべて含めること / 各項目3〜4文）:
1. 2つのトピックの要約: 各核心を1文で
2. 共通する教訓: 視聴者が持ち帰るべきインサイト
3. CTA: チャンネル登録・コメント誘導

末尾は必ず「以上、モチエンがお伝えしました！チャンネル登録・高評価よろしくお願いします！」で締めること。

【本日のトピック】
■ トピック①: {title1}
■ トピック②: {title2}

【全セクション要約】
{all_summaries}

出力フォーマット（このJSONのみ）:
{{
  "content": "アウトロスクリプト本文",
  "title": "動画タイトル（40字以内 / 数字・インパクトある表現を含む）",
  "short_title": "6〜10字の核心キーワード",
  "hashtags": ["#経済ニュース", "#モチエン", "...（#Shortsは含めないこと）"],
  "korean_summary": "한국어 1줄 요약",
  "image_prompt": "Pexels検索用英語キーワード（イントロと異なる場所・素材を指定 / 例: 'japanese people commuting evening' / 'bank building exterior morning'）"
}}\
"""


# ─────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────

def load_today_results():
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    date_dir = os.path.join(OUTPUT_DIR, today)

    if not os.path.exists(date_dir):
        raise Exception(
            f"오늘 날짜 폴더가 없습니다: {date_dir}\n"
            "쇼츠 파이프라인(step2_select.py)이 먼저 실행되어야 합니다."
        )

    results = {}
    missing = []
    for slot in SLOTS:
        path = os.path.join(date_dir, f"{slot}_gpt_result.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                results[slot] = json.load(f)
            print(f"  ✅ {slot}_gpt_result.json 로드")
        else:
            missing.append(slot)
            print(f"  ⚠️  {slot}_gpt_result.json 없음")

    if len(results) < 2:
        raise Exception(
            f"쇼츠 결과 파일이 부족합니다. 필요: 2개, 현재: {len(results)}개 "
            f"(없는 슬롯: {missing})"
        )

    return results


# ─────────────────────────────────────────
# GPT 호출
# ─────────────────────────────────────────

def call_section(client, messages, name):
    """공통 GPT 호출 + JSON 파싱 + 1회 재시도."""
    last_err = None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=GPT_MODEL,
                messages=messages,
                temperature=GPT_TEMPERATURE,
            )
            result = json.loads(resp.choices[0].message.content.strip())
            return result, resp.usage
        except Exception as e:
            last_err = e
            if attempt == 0:
                print(f"  [재시도] {name} 실패 ({type(e).__name__}), 재시도 중...")
    print(f"  [오류] {name} 최종 실패: {last_err}")
    sys.exit(1)


def call_intro(client, r1, r2):
    print("[1/4] intro 생성 중...")
    prompt = PROMPT_INTRO.format(
        title1=r1["title"], summary1=r1["korean_summary"],
        title2=r2["title"], summary2=r2["korean_summary"],
    )
    result, usage = call_section(
        client,
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user",   "content": prompt}],
        "intro",
    )
    print(f"      완료 ({len(result.get('content', ''))}자 / 토큰 {usage.total_tokens:,})")
    return result, usage


def call_issue(client, idx, r, prev_summaries):
    print(f"[{idx + 1}/4] issue{idx} 생성 중...")
    prev_text = "\n".join(prev_summaries) if prev_summaries else "（なし）"
    prompt = PROMPT_ISSUE.format(
        idx=idx,
        raw=r.get("raw_summary_jp") or r["korean_summary"],
        prev_summaries=prev_text,
    )
    result, usage = call_section(
        client,
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user",   "content": prompt}],
        f"issue{idx}",
    )
    print(f"      완료 ({len(result.get('content', ''))}자 / 토큰 {usage.total_tokens:,})")
    return result, usage


def call_issue_retry(client, idx, r, prev_summaries, prev_content):
    """issue 글자수 부족 시 1회 재시도 — 짧았다는 지시를 prepend."""
    prev_text = "\n".join(prev_summaries) if prev_summaries else "（なし）"
    retry_prefix = (
        f"前回の出力は{len(prev_content)}字と短すぎました。"
        f"各項目を最低5文以上で詳しく書き直してください。\n\n"
    )
    prompt = retry_prefix + PROMPT_ISSUE.format(
        idx=idx,
        raw=r.get("raw_summary_jp") or r["korean_summary"],
        prev_summaries=prev_text,
    )
    result, usage = call_section(
        client,
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user",   "content": prompt}],
        f"issue{idx}_retry",
    )
    print(f"      완료 ({len(result.get('content', ''))}자 / 토큰 {usage.total_tokens:,})")
    return result, usage


def call_outro(client, r1, r2, all_summaries):
    print("[4/4] outro 생성 중...")
    prompt = PROMPT_OUTRO.format(
        title1=r1["title"], title2=r2["title"],
        all_summaries="\n".join(all_summaries),
    )
    result, usage = call_section(
        client,
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user",   "content": prompt}],
        "outro",
    )
    print(f"      완료 ({len(result.get('content', ''))}자 / 토큰 {usage.total_tokens:,})")
    return result, usage


# ─────────────────────────────────────────
# 조립
# ─────────────────────────────────────────

def assemble_result(intro_result, issue_results, outro_result, r_list):
    fallback_img = r_list[0].get("image_prompt", "japanese economy news")
    return {
        "title":          outro_result["title"],
        "short_title":    outro_result.get("short_title", r_list[0].get("short_title", "")),
        "hashtags":       outro_result["hashtags"],
        "korean_summary": outro_result["korean_summary"],
        "intro": {
            "script":       intro_result["content"],
            "image_prompt": intro_result.get("image_prompt", fallback_img),
        },
        "issues": [
            {
                "title":        issue_results[i].get("title", f"トピック{i + 1}"),
                "script":       issue_results[i]["content"],
                "image_prompt": r_list[i].get("image_prompt", fallback_img),
            }
            for i in range(2)
        ],
        "outro": {
            "script":       outro_result["content"],
            "image_prompt": outro_result.get("image_prompt", fallback_img),
        },
    }


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def main():
    print("=== 당일 쇼츠 gpt_result 로드 ===")
    results = load_today_results()
    r_list = [results["09"], results["18"]]

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    total_tokens = 0
    summaries = []

    print("\n=== ChatGPT gpt-4.1 롱폼 스크립트 4회 순차 생성 ===")

    # 1/4 intro
    intro_result, u = call_intro(client, r_list[0], r_list[1])
    summaries.append(f"イントロ要約:\n{intro_result['summary']}")
    total_tokens += u.total_tokens

    # 2~3/4 issues
    issue_results = []
    for i in range(2):
        # 직전 섹션 summary 1개만 전달 (전체 누적 시 GPT가 요약 모드로 전환되는 문제 방지)
        prev = [summaries[-1]] if summaries else []
        result, u = call_issue(client, i + 1, r_list[i], prev)
        total_tokens += u.total_tokens

        content_len = len(result.get("content", ""))
        if content_len < MIN_ISSUE_CHARS:
            print(f"  [경고] issue{i+1} 글자수 부족 ({content_len}자 / 목표 {MIN_ISSUE_CHARS}자), 재시도 중...")
            retry_result, retry_u = call_issue_retry(
                client, i + 1, r_list[i], prev, result.get("content", "")
            )
            total_tokens += retry_u.total_tokens
            retry_len = len(retry_result.get("content", ""))
            if retry_len >= MIN_ISSUE_CHARS:
                result = retry_result
            else:
                print(f"  [경고] issue{i+1} 재시도도 짧음 ({retry_len}자), 그대로 사용")

        summaries.append(f"トピック{i + 1}要約:\n{result['summary']}")
        issue_results.append(result)

    # 4/4 outro
    outro_result, u = call_outro(client, r_list[0], r_list[1], list(summaries))
    total_tokens += u.total_tokens

    data = assemble_result(intro_result, issue_results, outro_result, r_list)

    with open(LONG_SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    section_chars = {
        "intro":  len(data["intro"]["script"]),
        "issue1": len(data["issues"][0]["script"]),
        "issue2": len(data["issues"][1]["script"]),
        "outro":  len(data["outro"]["script"]),
    }
    total_chars = sum(section_chars.values())

    print(f"\n=== 완료 ===")
    print(f"제목       : {data['title']}")
    print(f"한국어 요약: {data['korean_summary']}")
    print(f"섹션별 글자수:")
    for sec, chars in section_chars.items():
        print(f"  {sec:<8}: {chars}자")
    print(f"합계       : {total_chars}자 (목표: 3,200자)")
    print(f"총 토큰    : {total_tokens:,}")
    print(f"\n{LONG_SCRIPT_FILE} 저장 완료")


if __name__ == "__main__":
    main()
