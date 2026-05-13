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
MODEL_ID = "eleven_flash_v2_5"
OUTPUT_FORMAT = "mp3_44100_128"


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
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }
    res = requests.post(
        url,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    return res.content


def main():
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

    if not voice_id:
        print("=== 사용 가능한 ElevenLabs 보이스 목록 ===")
        list_voices()
        return

    print("=== gpt_result.json 로드 ===")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        gpt = json.load(f)

    script = gpt["script"]
    script = re.sub(r"[（(][^）)]*[）)]", "", script)
    print(f"스크립트 ({len(script)}자):\n{script[:100]}...\n")

    print(f"=== TTS 생성 중... (voice_id: {voice_id}) ===")
    audio = generate_tts(script, voice_id)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(audio)

    size_kb = len(audio) // 1024
    print(f"{OUTPUT_FILE} 저장 완료 ({size_kb}KB)")


if __name__ == "__main__":
    main()
