import sys
import json
import os
import re
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

INPUT_FILE = "gpt_result.json"
OUTPUT_FILE = "voice.mp3"

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
TTS_MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
PRONUNCIATION_PATH = "pronunciation.json"
PD_ID = os.getenv("ELEVENLABS_PD_ID", "")
PD_VERSION_ID = os.getenv("ELEVENLABS_PD_VERSION_ID", "")


def get_api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise Exception("ELEVENLABS_API_KEY가 .env에 설정되지 않았습니다.")
    return key


def list_voices():
    key = get_api_key()
    res = requests.get(
        f"{ELEVENLABS_API}/voices",
        headers={"xi-api-key": key},
        timeout=10,
    )
    res.raise_for_status()
    voices = res.json().get("voices", [])

    print(f"\n{'='*60}")
    print(f"{'ID':<30} {'이름':<25} {'언어'}")
    print(f"{'='*60}")
    for v in voices:
        labels = v.get("labels", {})
        lang = labels.get("language", labels.get("accent", "-"))
        print(f"{v['voice_id']:<30} {v['name']:<25} {lang}")
    print(f"{'='*60}")
    print(f"\n총 {len(voices)}개 보이스")
    print("\n.env에 ELEVENLABS_VOICE_ID=<위 ID 중 하나> 를 추가하고 다시 실행하세요.")


def generate_tts(text, voice_id):
    key = get_api_key()
    url = f"{ELEVENLABS_API}/text-to-speech/{voice_id}?output_format={OUTPUT_FORMAT}"
    payload = {
        "text": text,
        "model_id": TTS_MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }
    if PD_ID and PD_VERSION_ID:
        payload["pronunciation_dictionary_locators"] = [
            {"pronunciation_dictionary_id": PD_ID, "version_id": PD_VERSION_ID}
        ]
    res = requests.post(
        url,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    return res.content


def apply_pronunciation(text: str) -> str:
    """pronunciation.json의 고유명사 발음 치환을 적용한다.
    파일이 없거나 비어 있으면 원본을 그대로 반환한다."""
    import json, os
    if not os.path.exists(PRONUNCIATION_PATH):
        return text
    try:
        with open(PRONUNCIATION_PATH, "r", encoding="utf-8") as f:
            mapping = json.load(f)
    except Exception:
        return text
    for kanji, hira in mapping.items():
        text = text.replace(kanji, hira)
    return text


def main():
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

    if not voice_id:
        print("=== 사용 가능한 ElevenLabs 보이스 목록 ===")
        list_voices()
        return

    print("=== gpt_result.json 로드 ===")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        gpt = json.load(f)

    hook_text   = re.sub(r"[（(][^）)]*[）)]", "", gpt.get("hook", ""))
    script_text = re.sub(r"[（(][^）)]*[）)]", "", gpt["script"])
    hook_text   = apply_pronunciation(hook_text)
    script_text = apply_pronunciation(script_text)
    full_text   = (hook_text + "　" + script_text).strip() if hook_text else script_text
    print(f"hook ({len(hook_text)}자) + script ({len(script_text)}자) = 합계 {len(full_text)}자")
    print(f"hook: {hook_text[:60]}...\n")

    print(f"=== TTS 생성 중... (voice_id: {voice_id}) ===")
    audio = generate_tts(full_text, voice_id)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(audio)

    size_kb = len(audio) // 1024
    print(f"{OUTPUT_FILE} 저장 완료 ({size_kb}KB)")


if __name__ == "__main__":
    main()
