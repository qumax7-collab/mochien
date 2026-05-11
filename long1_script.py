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
SLOTS            = ["09", "13", "18"]

JST = datetime.timezone(datetime.timedelta(hours=9))

REQUIRED_KEYS = {"title", "short_title", "hashtags", "korean_summary",
                 "emotion", "intro", "issues", "outro"}
VALID_EMOTIONS = {"smile", "happy", "surprised", "shocked", "worried",
                  "angry", "anxious", "sad", "neutral", "shy", "embarrassed", "sleepy"}

SYSTEM_PROMPT = """\
あなたはJSONのみを出力するAIです。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。
以下のキー以外は絶対に追加しないこと:
  title, short_title, hashtags, korean_summary, emotion, intro, issues, outro"""

USER_PROMPT_TEMPLATE = """\
【モチエンキャラクター設定】
- 落ち着いていて信頼感がある話し方（40〜60代向け）
- 難しい経済用語はやさしい言葉に言い換える
- 視聴者を「あなた」と呼ぶ
- 冒頭の挨拶は禁止。最初の一文は必ず本日のニュース概要から始めること
- introのscript末尾は必ず「今日は3つのニュースを深掘りしていきます。」で締めること
- outroのscript末尾は必ず「以上、モチエンがお伝えしました！チャンネル登録・高評価よろしくお願いします！」で締めること
- hashtagsには必ず#経済ニュースと#モチエンを含めること
- スクリプトの誤読しやすい漢字には、必ずひらがなで読み仮名を括弧内に併記すること。
  例：世界経済(せかいけいざい)、波及(はきゅう)、財務省(ざいむしょう)、拡大(かくだい)
  （TTS読み上げ用のため）

【深掘り分析の方針】
- 3つのトピックを単純にまとめるのではなく、共通する経済トレンドや因果関係で連結すること
- 各イシューは「背景・現状→具体的な影響→視聴者へのメッセージ」の3層構造で分析すること
- 専門用語は平易な言葉で言い換え、具体的な数字・事例・比較を盛り込むこと
- ショーツとは独立した深掘り内容とし、単なる要約の焼き直しは禁止

【文字数目安（TTS基準 / 約400字=1分）】
- intro.script : 約400字（1分）
- issues各.script: 約800字（2分）
- outro.script : 約400字（1分）
合計目標: 約3,200字 / 8分

【出力フォーマット — このJSONのみ出力すること】
{{
  "title": "40字以内の動画タイトル（数字・インパクトある表現を含む）",
  "short_title": "6〜10字の核心キーワード",
  "hashtags": ["#経済ニュース", "#モチエン", "..."],
  "korean_summary": "한국어 1줄 요약",
  "emotion": "smile|happy|surprised|shocked|worried|angry|anxious|sad|neutral|shy|embarrassed|sleepy のいずれか1つ",
  "intro": {{
    "script": "イントロスクリプト（約400字。本日3つのトピックの共通テーマと概要を紹介）",
    "image_prompt": "Pexels検索用英語キーワード（例: japanese economy news）"
  }},
  "issues": [
    {{
      "title": "イシュー①のタイトル",
      "script": "背景・現状→影響分析→視聴者へのメッセージの3層構成（約800字）",
      "image_prompt": "Pexels検索用英語キーワード"
    }},
    {{
      "title": "イシュー②のタイトル",
      "script": "背景・現状→影響分析→視聴者へのメッセージの3層構成（約800字）",
      "image_prompt": "Pexels検索用英語キーワード"
    }},
    {{
      "title": "イシュー③のタイトル",
      "script": "背景・現状→影響分析→視聴者へのメッセージの3層構成（約800字）",
      "image_prompt": "Pexels検索用英語キーワード"
    }}
  ],
  "outro": {{
    "script": "アウトロスクリプト（約400字。3つのイシューの共通点まとめ＋今後の展望＋行動喚起）",
    "image_prompt": "Pexels検索用英語キーワード（例: japanese economy future）"
  }}
}}

【本日のトピック3本（参考情報）】

■ トピック①
タイトル: {title1}
韓国語要約: {summary1}

■ トピック②
タイトル: {title2}
韓国語要約: {summary2}

■ トピック③
タイトル: {title3}
韓国語要約: {summary3}
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

    if len(results) < 3:
        raise Exception(
            f"쇼츠 결과 파일이 부족합니다. 필요: 3개, 현재: {len(results)}개 "
            f"(없는 슬롯: {missing})"
        )

    return results


# ─────────────────────────────────────────
# ChatGPT
# ─────────────────────────────────────────

def call_chatgpt(results):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    r1, r2, r3 = results["09"], results["13"], results["18"]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title1=r1["title"],   summary1=r1["korean_summary"], script1=r1["script"],
        title2=r2["title"],   summary2=r2["korean_summary"], script2=r2["script"],
        title3=r3["title"],   summary3=r3["korean_summary"], script3=r3["script"],
    )

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

    missing_keys = REQUIRED_KEYS - data.keys()
    if missing_keys:
        raise Exception(f"필수 키 누락: {missing_keys}")
    if data.get("emotion") not in VALID_EMOTIONS:
        data["emotion"] = "neutral"
    if len(data.get("issues", [])) != 3:
        raise Exception(f"issues는 3개여야 합니다. 현재: {len(data.get('issues', []))}")

    return data


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def main():
    print("=== 당일 쇼츠 gpt_result 로드 ===")
    results = load_today_results()

    print("\n=== ChatGPT gpt-4.1 롱폼 스크립트 생성 중 ===")
    print("(30~60초 소요될 수 있습니다...)")
    data = call_chatgpt(results)

    with open(LONG_SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n제목       : {data['title']}")
    print(f"감정       : {data['emotion']}")
    print(f"한국어 요약: {data['korean_summary']}")
    print(f"\n{LONG_SCRIPT_FILE} 저장 완료")


if __name__ == "__main__":
    main()
