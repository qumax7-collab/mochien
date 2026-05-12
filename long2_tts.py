import sys
import json
import os
import re
import subprocess

import pykakasi
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 설정 =====
LONG_SCRIPT_FILE = "long_script.json"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_MODEL         = "eleven_flash_v2_5"
TTS_OUTPUT_FORMAT = "mp3_44100_128"
CONCAT_LIST_FILE  = "long_voice_concat.txt"

# 섹션 순서 (파일명, long_script.json 내 위치)
SECTIONS = [
    ("long_voice_intro.mp3",  "intro"),
    ("long_voice_issue1.mp3", "issue1"),
    ("long_voice_issue2.mp3", "issue2"),
    ("long_voice_issue3.mp3", "issue3"),
    ("long_voice_outro.mp3",  "outro"),
]
VOICE_LONG_FILE = "long_voice.mp3"


def kanji_to_hiragana(text):
    kks = pykakasi.kakasi()
    return "".join(item["hira"] for item in kks.convert(text))


def get_section_script(data, key):
    """long_script.json에서 섹션 스크립트 추출."""
    if key == "intro":
        return data["intro"]["script"]
    if key == "outro":
        return data["outro"]["script"]
    idx = int(key[-1]) - 1  # issue1 → 0
    return data["issues"][idx]["script"]


def tts_request(text, voice_id, api_key):
    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": TTS_MODEL,
        "output_format": TTS_OUTPUT_FORMAT,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    return resp.content


def concat_audio(output_path):
    """FFmpeg concat으로 섹션 mp3 파일 연결."""
    with open(CONCAT_LIST_FILE, "w", encoding="utf-8") as f:
        for filename, _ in SECTIONS:
            f.write(f"file '{filename}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", CONCAT_LIST_FILE,
        "-c", "copy",
        output_path,
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise Exception(f"FFmpeg concat 실패:\n{err[-2000:]}")

    os.remove(CONCAT_LIST_FILE)


def main():
    api_key  = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        print("[오류] .env에 ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID를 입력하세요.")
        sys.exit(1)

    print("=== long_script.json 로드 ===")
    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print("\n=== ElevenLabs TTS 생성 ===")
    total = len(SECTIONS)
    for i, (filename, key) in enumerate(SECTIONS, 1):
        text = get_section_script(data, key)
        text = re.sub(r"[（(][^）)]*[）)]", "", text)
        text = kanji_to_hiragana(text)
        print(f"  [{i}/{total}] {key} ({len(text)}자) → {filename}")
        audio = tts_request(text, voice_id, api_key)
        with open(filename, "wb") as f:
            f.write(audio)
        size_kb = len(audio) // 1024
        print(f"         저장 완료 ({size_kb}KB)")

    print(f"\n=== 섹션 연결 → {VOICE_LONG_FILE} ===")
    concat_audio(VOICE_LONG_FILE)
    size_mb = os.path.getsize(VOICE_LONG_FILE) / (1024 * 1024)
    print(f"  연결 완료 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
