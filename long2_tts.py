import sys
import json
import os
import re
import subprocess
import datetime

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 설정 =====
LONG_SCRIPT_FILE  = "long_script.json"
LONG_CHAPTERS_FILE = "long_chapters.json"
OUTPUT_DIR        = "output"
SLOTS             = ["09", "18"]
JST               = datetime.timezone(datetime.timedelta(hours=9))
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_MODEL_ID      = "eleven_multilingual_v2"
TTS_OUTPUT_FORMAT = "mp3_44100_128"
PD_ID             = os.getenv("ELEVENLABS_PD_ID", "")
PD_VERSION_ID     = os.getenv("ELEVENLABS_PD_VERSION_ID", "")
CONCAT_LIST_FILE  = "long_voice_concat.txt"
PRONUNCIATION_PATH = "pronunciation.json"
SECTION_LABEL_PAT  = re.compile(
    r'[\[【〔](?:issue[12]|intro|outro|이슈\s*[12]|イントロ|アウトロ)[\]】〕]'
    r'|^(?:issue[12]|intro|outro|이슈\s*[12]|イントロ|アウトロ)\s*[:：]\s*',
    re.IGNORECASE | re.MULTILINE,
)

# 섹션 순서 (파일명, long_script.json 내 위치)
SECTIONS = [
    ("long_voice_intro.mp3",  "intro"),
    ("long_voice_issue1.mp3", "issue1"),
    ("long_voice_issue2.mp3", "issue2"),
    ("long_voice_outro.mp3",  "outro"),
]
VOICE_LONG_FILE = "long_voice.mp3"


def ffprobe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return float(result.stdout.decode().strip())


def build_chapters():
    now_jst  = datetime.datetime.now(JST)
    date_dir = os.path.join(OUTPUT_DIR, now_jst.strftime("%Y-%m-%d"))

    short_titles = {}
    for slot in SLOTS:
        path = os.path.join(date_dir, f"{slot}_gpt_result.json")
        try:
            with open(path, encoding="utf-8") as f:
                short_titles[slot] = json.load(f).get("short_title", "")
        except Exception:
            short_titles[slot] = ""

    nums = ["①", "②"]
    labels = {
        "intro":  "オープニング",
        "issue1": f"{nums[0]} {short_titles.get(SLOTS[0], 'トピック①')}",
        "issue2": f"{nums[1]} {short_titles.get(SLOTS[1], 'トピック②')}",
        "outro":  "まとめ",
    }

    chapters = []
    cumulative = 0.0
    for filename, key in SECTIONS:
        chapters.append({"time": int(cumulative), "label": labels[key]})
        try:
            cumulative += ffprobe_duration(filename)
        except Exception as e:
            print(f"  [경고] {filename} 길이 측정 실패: {e}")

    with open(LONG_CHAPTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)

    print(f"\n=== 챕터 저장 → {LONG_CHAPTERS_FILE} ===")
    for ch in chapters:
        m, s = divmod(ch["time"], 60)
        print(f"  {m:02d}:{s:02d}  {ch['label']}")


def get_section_script(data, key):
    if key == "intro":
        text = data["intro"]["script"]
    elif key == "outro":
        text = data["outro"]["script"]
    else:
        idx = int(key[-1]) - 1  # issue1 → 0
        text = data["issues"][idx]["script"]
    # 운영자 검수용 출처 태그를 TTS 전에 제거 (한국어·일본어 양쪽 패턴 대응)
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    text = re.sub(r'===차트(?:\[[^\]]*\])?===|===차트끝===', '', text)
    text = SECTION_LABEL_PAT.sub('', text)
    return text.strip()


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


def tts_request(text, voice_id, api_key):
    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": TTS_MODEL_ID,
        "output_format": TTS_OUTPUT_FORMAT,
    }
    if PD_ID and PD_VERSION_ID:
        body["pronunciation_dictionary_locators"] = [
            {"pronunciation_dictionary_id": PD_ID, "version_id": PD_VERSION_ID}
        ]
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
        text = apply_pronunciation(text)
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

    build_chapters()


if __name__ == "__main__":
    main()
