import sys
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(encoding="utf-8")

INPUT_FILE = "article.json"
OUTPUT_FILE = "gpt_result.json"

SYSTEM_PROMPT = """\
あなたはJSONのみを出力するAIです。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。
以下のキー以外は絶対に追加しないこと:
  title, hook, script, hashtags, korean_summary, emotion, image_prompt, short_title\
"""

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


def load_article():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def call_chatgpt(title, article_body):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)
    user_prompt = USER_PROMPT_TEMPLATE.format(title=title, article_body=article_body)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()
    return raw


def parse_json(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[경고] JSON 파싱 실패: {e}")
        print(f"원본 응답:\n{raw}")
        raise


REQUIRED_KEYS = {"title", "hook", "script", "hashtags", "korean_summary", "emotion", "image_prompt", "short_title"}
VALID_EMOTIONS = {"smile", "happy", "surprised", "shocked", "worried", "angry", "anxious", "sad", "neutral", "shy", "embarrassed", "sleepy"}


def validate(data):
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise Exception(f"필수 키 누락: {missing}")
    if data["emotion"] not in VALID_EMOTIONS:
        print(f"[경고] emotion 값 '{data['emotion']}'이 허용 목록에 없습니다. neutral로 대체합니다.")
        data["emotion"] = "neutral"
    return data


def main():
    print("=== article.json 로드 ===")
    article = load_article()
    print(f"제목: {article['title']}")

    print("\n=== ChatGPT API 호출 중... ===")
    raw = call_chatgpt(article["title"], article["article_body"])
    print(f"원본 응답:\n{raw}\n")

    print("=== JSON 파싱 및 검증 ===")
    data = parse_json(raw)
    data = validate(data)

    print(f"title         : {data['title']}")
    print(f"hook          : {data['hook']}")
    print(f"short_title   : {data['short_title']}")
    print(f"emotion       : {data['emotion']}")
    print(f"image_prompt  : {data['image_prompt']}")
    print(f"korean_summary: {data['korean_summary']}")
    print(f"hashtags      : {data['hashtags']}")
    print(f"script 미리보기: {data['script'][:80]}...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{OUTPUT_FILE} 저장 완료")
    return data


if __name__ == "__main__":
    main()
