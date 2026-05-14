import argparse
import json
import os
import sys
from datetime import date

import anthropic
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 모델 =====
GEMINI_MODEL = "gemini-2.5-flash"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# ===== 파일 경로 (shorts) =====
SHORTS_AUDIO       = "voice.mp3"
SHORTS_SCRIPT_PATH = "gpt_result.json"
SHORTS_SRT_PATH    = "subtitle.srt"

# ===== 파일 경로 (longform) =====
LONGFORM_AUDIO       = "long_voice.mp3"
LONGFORM_SCRIPT_PATH = "long_script.json"
LONGFORM_SRT_PATH    = "long_subtitle.srt"

# ===== 사전 파일 =====
PRONUNCIATION_PATH      = "pronunciation.json"
GLOSSARY_PATH           = "glossary.json"
SUGGESTED_PRONUNC_PATH  = "suggested_pronunciation.json"
SUGGESTED_GLOSSARY_PATH = "suggested_glossary.json"

# ===== 텔레그램 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# ===== Gemini 스키마 =====
GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "pronunciation_errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kanji":           {"type": "string"},
                    "wrong_reading":   {"type": "string"},
                    "correct_reading": {"type": "string"},
                },
                "required": ["kanji", "wrong_reading", "correct_reading"],
            },
        },
        "subtitle_errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "correct":  {"type": "string"},
                    "misheard": {"type": "string"},
                },
                "required": ["correct", "misheard"],
            },
        },
    },
    "required": ["pronunciation_errors", "subtitle_errors"],
}

GEMINI_SYSTEM = """\
あなたは日本語音声品質検査AIです。
以下の3点を照合し、エラーのみをJSONで出力してください。

入力:
- mp3: TTS音声
- script: 原稿テキスト
- srt: Whisper自動字幕

出力ルール:
(a) pronunciation_errors: TTSが漢字を誤読した発音ミス
    → 原稿にある漢字をTTSが別の読み方をした場合のみ
(b) subtitle_errors: Whisperが音声を聞き間違えた字幕誤認識
    → 原稿・音声の正しい語と字幕の誤字が明確に食い違う場合のみ

除外:
- 正常な発音・正常な字幕は絶対に含めないこと
- 確信が持てないものは含めないこと
- すでに補正辞書に登録済みの項目は含めないこと
"""

CLAUDE_SYSTEM = """\
あなたは日本語自動化パイプラインの辞書登録安全性レビュアーです。
Geminiが抽出した誤り候補を以下の基準で審査し、approve/reject を判定してください。

審査基準:
1. 他の文脈でも正常な日本語として使われる単語ではないか
2. 元の原稿に正解の語が実際に含まれているか
3. 一回性の誤認識の可能性が高く、安定したパターンではないか
4. 登録すると正常語を誤置換するリスクがないか

出力ルール:
- 安全な項目のみ approve: true にすること
- meaning_ko: 対象の日本語単語の韓国語の意味を簡潔に記載（例: 今年度 → "올해 회계연도"）
- reason: 必ず韓国語で記載すること
- 必ずJSONのみを出力すること
"""


# ===== 유틸리티 =====

def tg_notify(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def tg_error(msg):
    tg_notify(f"⚠️ step10 오류\n{msg}")


def load_json_safe(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===== 핵심 함수 =====

def load_inputs(mode):
    """mode에 따라 (audio_bytes, script_text, srt_text) 반환."""
    if mode == "shorts":
        audio_path  = SHORTS_AUDIO
        script_path = SHORTS_SCRIPT_PATH
        srt_path    = SHORTS_SRT_PATH
    else:
        audio_path  = LONGFORM_AUDIO
        script_path = LONGFORM_SCRIPT_PATH
        srt_path    = LONGFORM_SRT_PATH

    for path in [audio_path, script_path, srt_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"필수 파일 없음: {path}")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    with open(script_path, encoding="utf-8") as f:
        data = json.load(f)

    if mode == "shorts":
        script_text = data.get("script", "")
    else:
        parts = [data.get("intro", {}).get("script", "")]
        for issue in data.get("issues", []):
            parts.append(issue.get("script", ""))
        parts.append(data.get("outro", {}).get("script", ""))
        script_text = "\n\n".join(p for p in parts if p)

    with open(srt_path, encoding="utf-8") as f:
        srt_text = f.read()

    return audio_bytes, script_text, srt_text


def load_known_entries():
    """이미 등록된 발음·자막 교정 키 집합 반환.
    pronunciation.json / glossary.json 키 외에
    step7·long5의 KNOWN_ASR_ERRORS wrong 패턴도 known_glossary에 합산."""
    known_pronunc  = set(load_json_safe(PRONUNCIATION_PATH).keys())
    known_glossary = set(load_json_safe(GLOSSARY_PATH).keys())

    for module_name in ("step7_whisper_subtitle", "long5_whisper"):
        try:
            import importlib
            mod = importlib.import_module(module_name)
            for wrong, _ in mod.KNOWN_ASR_ERRORS:
                known_glossary.add(wrong)
        except Exception:
            pass  # 파일 없거나 import 실패 시 해당 소스만 건너뜀

    return known_pronunc, known_glossary


def call_gemini(audio_bytes, script_text, srt_text, known_pronunc, known_glossary):
    """Gemini 1차 검수. 후보 dict 반환."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY가 .env에 없습니다.")

    client = genai.Client(api_key=api_key)

    known_info = ""
    if known_pronunc:
        known_info += f"\n\n登録済み発音補正キー: {', '.join(sorted(known_pronunc))}"
    if known_glossary:
        known_info += f"\n登録済み字幕補正キー: {', '.join(sorted(known_glossary))}"

    user_content = [
        types.Part.from_bytes(data=audio_bytes, mime_type="audio/mpeg"),
        types.Part.from_text(text=f"【原稿】\n{script_text}\n\n【SRT字幕】\n{srt_text}{known_info}"),
    ]

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=GEMINI_SYSTEM,
            response_mime_type="application/json",
            response_schema=GEMINI_RESPONSE_SCHEMA,
        ),
    )

    result = json.loads(response.text)

    # Python 측에서도 기등록 항목 필터링 (이중 안전장치)
    result["pronunciation_errors"] = [
        e for e in result.get("pronunciation_errors", [])
        if e["kanji"] not in known_pronunc
    ]
    result["subtitle_errors"] = [
        e for e in result.get("subtitle_errors", [])
        if e["misheard"] not in known_glossary
    ]

    return result


def call_claude(gemini_result, script_text, pronunciation_data, glossary_data):
    """Claude 2차 검증. 검토 결과 dict 반환."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY가 .env에 없습니다.")

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = f"""\
【Gemini抽出候補】
{json.dumps(gemini_result, ensure_ascii=False, indent=2)}

【原稿全文】
{script_text}

【現在のpronunciation.json】
{json.dumps(pronunciation_data, ensure_ascii=False, indent=2)}

【現在のglossary.json】
{json.dumps(glossary_data, ensure_ascii=False, indent=2)}

上記の候補を審査し、以下のスキーマでJSONのみを返してください:
{{
  "pronunciation_reviewed": [
    {{"kanji": "...", "correct_reading": "...", "meaning_ko": "한국어 뜻", "approve": true/false, "reason": "한국어로 이유"}}
  ],
  "subtitle_reviewed": [
    {{"correct": "...", "misheard": "...", "meaning_ko": "한국어 뜻", "approve": true/false, "reason": "한국어로 이유"}}
  ]
}}
"""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=CLAUDE_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def apply_approved(claude_result):
    """approve=true 항목을 pronunciation.json / glossary.json에 반영.
    이미 있는 키는 건너뜀. (applied_pronunc, applied_glossary) 반환."""
    pronunc  = load_json_safe(PRONUNCIATION_PATH)
    glossary = load_json_safe(GLOSSARY_PATH)
    applied_pronunc  = []
    applied_glossary = []

    for item in claude_result.get("pronunciation_reviewed", []):
        if item.get("approve") and item["kanji"] not in pronunc:
            pronunc[item["kanji"]] = item["correct_reading"]
            applied_pronunc.append(item)

    for item in claude_result.get("subtitle_reviewed", []):
        if item.get("approve") and item["misheard"] not in glossary:
            glossary[item["misheard"]] = item["correct"]
            applied_glossary.append(item)

    if applied_pronunc:
        save_json(PRONUNCIATION_PATH, pronunc)
    if applied_glossary:
        save_json(GLOSSARY_PATH, glossary)

    return applied_pronunc, applied_glossary


def update_suggested(claude_result):
    """모든 후보(approve 무관)를 suggested 파일에 누적."""
    today = date.today().isoformat()

    sug_pronunc  = load_json_safe(SUGGESTED_PRONUNC_PATH)
    sug_glossary = load_json_safe(SUGGESTED_GLOSSARY_PATH)

    for item in claude_result.get("pronunciation_reviewed", []):
        key = item["kanji"]
        if key in sug_pronunc:
            sug_pronunc[key]["count"]    += 1
            sug_pronunc[key]["last_seen"] = today
            sug_pronunc[key]["approved"]  = item.get("approve", False)
            sug_pronunc[key]["reason"]    = item.get("reason", "")
        else:
            sug_pronunc[key] = {
                "suggested":  item["correct_reading"],
                "count":      1,
                "first_seen": today,
                "last_seen":  today,
                "approved":   item.get("approve", False),
                "reason":     item.get("reason", ""),
                "examples":   [],
            }

    for item in claude_result.get("subtitle_reviewed", []):
        key = item["misheard"]
        if key in sug_glossary:
            sug_glossary[key]["count"]    += 1
            sug_glossary[key]["last_seen"] = today
            sug_glossary[key]["approved"]  = item.get("approve", False)
            sug_glossary[key]["reason"]    = item.get("reason", "")
        else:
            sug_glossary[key] = {
                "suggested":  item["correct"],
                "count":      1,
                "first_seen": today,
                "last_seen":  today,
                "approved":   item.get("approve", False),
                "reason":     item.get("reason", ""),
                "examples":   [],
            }

    save_json(SUGGESTED_PRONUNC_PATH, sug_pronunc)
    save_json(SUGGESTED_GLOSSARY_PATH, sug_glossary)


def notify_telegram(applied_pronunc, applied_glossary, rejected_pronunc, rejected_glossary):
    """자동 반영·보류 항목을 텔레그램으로 통지. 합산 0건이면 생략."""
    n_applied  = len(applied_pronunc)  + len(applied_glossary)
    n_rejected = len(rejected_pronunc) + len(rejected_glossary)
    if n_applied + n_rejected == 0:
        return

    lines = ["🔍 Gemini+Claude 자막·발음 검수 결과"]

    lines.append(f"\n✅ 자동 반영: {n_applied}건")
    for item in applied_pronunc:
        meaning = f"({item.get('meaning_ko', '')})" if item.get('meaning_ko') else ""
        lines.append(f"  · 발음 수정: {item['kanji']}{meaning} → {item['correct_reading']}")
    for item in applied_glossary:
        meaning = f"({item.get('meaning_ko', '')})" if item.get('meaning_ko') else ""
        lines.append(f"  · 자막 수정: {item['misheard']} → {item['correct']}{meaning}")

    lines.append(f"\n⏸ 보류: {n_rejected}건")
    for item in rejected_pronunc:
        meaning = f"({item.get('meaning_ko', '')})" if item.get('meaning_ko') else ""
        lines.append(f"  · 발음: {item['kanji']}{meaning} → {item['correct_reading']}")
        lines.append(f"    이유: {item.get('reason', '')}")
    for item in rejected_glossary:
        meaning = f"({item.get('meaning_ko', '')})" if item.get('meaning_ko') else ""
        lines.append(f"  · 자막: {item['misheard']} → {item['correct']}{meaning}")
        lines.append(f"    이유: {item.get('reason', '')}")

    tg_notify("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Gemini+Claude 자막·발음 검수")
    parser.add_argument("--mode", choices=["shorts", "longform"], required=True,
                        help="shorts 또는 longform")
    args = parser.parse_args()

    print(f"=== step10 검수 시작 (mode={args.mode}) ===")

    try:
        print("\n--- 1단계: 입력 파일 로드 ---")
        audio_bytes, script_text, srt_text = load_inputs(args.mode)
        print(f"  오디오: {len(audio_bytes)//1024}KB / 스크립트: {len(script_text)}자 / SRT: {len(srt_text)}자")

        known_pronunc, known_glossary = load_known_entries()
        print(f"  기등록 발음: {len(known_pronunc)}건 / 자막: {len(known_glossary)}건")

        print("\n--- 2단계: Gemini 1차 검수 ---")
        gemini_result = call_gemini(audio_bytes, script_text, srt_text, known_pronunc, known_glossary)
        n_p = len(gemini_result.get("pronunciation_errors", []))
        n_s = len(gemini_result.get("subtitle_errors", []))
        print(f"  발음 오류 후보: {n_p}건 / 자막 오인식 후보: {n_s}건")

        if n_p + n_s == 0:
            print("  후보 없음. 텔레그램 알림 생략 후 종료.")
            return

        pronunciation_data = load_json_safe(PRONUNCIATION_PATH)
        glossary_data      = load_json_safe(GLOSSARY_PATH)

        print("\n--- 3단계: Claude 2차 검증 ---")
        claude_result = call_claude(gemini_result, script_text, pronunciation_data, glossary_data)
        print(f"  검토 완료: pronunciation {len(claude_result.get('pronunciation_reviewed', []))}건 / "
              f"subtitle {len(claude_result.get('subtitle_reviewed', []))}건")

        print("\n--- 4단계: 자동 반영 ---")
        applied_pronunc, applied_glossary = apply_approved(claude_result)
        print(f"  반영: pronunciation {len(applied_pronunc)}건 / glossary {len(applied_glossary)}건")

        print("\n--- 5단계: suggested 파일 누적 ---")
        update_suggested(claude_result)
        print(f"  {SUGGESTED_PRONUNC_PATH} / {SUGGESTED_GLOSSARY_PATH} 갱신 완료")

        rejected_pronunc  = [i for i in claude_result.get("pronunciation_reviewed", []) if not i.get("approve")]
        rejected_glossary = [i for i in claude_result.get("subtitle_reviewed", [])      if not i.get("approve")]

        print("\n--- 6단계: 텔레그램 통지 ---")
        notify_telegram(applied_pronunc, applied_glossary, rejected_pronunc, rejected_glossary)

    except Exception as e:
        msg = f"[mode={args.mode}] {type(e).__name__}: {e}"
        print(f"[오류] {msg}")
        tg_error(msg)
        sys.exit(0)  # 파이프라인 중단 금지

    print("\n=== step10 완료 ===")


if __name__ == "__main__":
    main()
