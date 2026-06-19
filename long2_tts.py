import sys
import json
import os
import re
import shutil
import subprocess
import datetime

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 설정 =====
LONG_SCRIPT_FILE          = "long_script.json"
LONG_CHAPTERS_FILE        = "long_chapters.json"
LONG_CHART_TIMESTAMPS_FILE = "long_chart_timestamps.json"
OUTPUT_DIR                = "output"
SLOTS                     = ["09", "18"]
JST                       = datetime.timezone(datetime.timedelta(hours=9))
ELEVENLABS_API_URL        = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_MODEL_ID              = "eleven_multilingual_v2"
TTS_OUTPUT_FORMAT         = "mp3_44100_128"
PD_ID                     = os.getenv("ELEVENLABS_PD_ID", "")
PD_VERSION_ID             = os.getenv("ELEVENLABS_PD_VERSION_ID", "")
CONCAT_LIST_FILE          = "long_voice_concat.txt"
PRONUNCIATION_PATH        = "pronunciation.json"

SECTION_LABEL_PAT = re.compile(
    r'[\[【〔](?:issue[12]|intro|outro|이슈\s*[12]|イントロ|アウトロ)[\]】〕]'
    r'|^(?:issue[12]|intro|outro|이슈\s*[12]|イントロ|アウトロ)\s*[:：]\s*',
    re.IGNORECASE | re.MULTILINE,
)
# 차트 블록 파싱: ===차트[항목, 시점]=== ... ===차트끝===
CHART_BLOCK_PAT = re.compile(
    r'===차트\[([^\]]+)\]===\n?(.*?)\n?===차트끝===',
    re.DOTALL,
)
# 태그 마지막 칸이 이 집합에 속하면 해당 타입으로 해석 (없으면 기존 chart)
CHART_TAG_TYPES = {"list"}

# 섹션 순서 (파일명, long_script.json 내 위치)
SECTIONS = [
    ("long_voice_intro.mp3",  "intro"),
    ("long_voice_issue1.mp3", "issue1"),
    ("long_voice_issue2.mp3", "issue2"),
    ("long_voice_outro.mp3",  "outro"),
]
VOICE_LONG_FILE = "long_voice.mp3"


# ─────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────

def ffprobe_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return float(result.stdout.decode().strip())


def apply_pronunciation(text: str) -> str:
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


def _clean_tts_text(text: str) -> str:
    """출처 태그, 후리가나 제거 후 발음 사전 적용."""
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    return apply_pronunciation(text).strip()


# ─────────────────────────────────────────
# 스크립트 취득
# ─────────────────────────────────────────

def get_section_script(data, key):
    """intro / outro 용: 차트 태그 제거 후 단일 TTS 텍스트 반환."""
    if key == "intro":
        text = data["intro"]["script"]
    elif key == "outro":
        text = data["outro"]["script"]
    else:
        idx = int(key[-1]) - 1
        text = data["issues"][idx]["script"]
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    text = re.sub(r'===차트(?:\[[^\]]*\])?===|===차트끝===', '', text)
    text = SECTION_LABEL_PAT.sub('', text)
    return text.strip()


def get_issue_raw_script(data: dict, key: str) -> str:
    """이슈 섹션 raw 텍스트 (차트 태그 보존 / 출처 태그만 제거)."""
    idx = int(key[-1]) - 1
    text = data["issues"][idx]["script"]
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    text = SECTION_LABEL_PAT.sub('', text)
    return text.strip()


# ─────────────────────────────────────────
# 차트 경계 문단 분리
# ─────────────────────────────────────────

def split_issue_script(raw: str) -> list:
    """
    이슈 스크립트를 차트 태그 경계로 문단 분리.
    반환: [{"type": "narration"|"chart"|"list", "text": "...",
            "item": "...", "time_hint": "..."}, ...]
    chart 청크에만 item / time_hint 키 포함.
    list  청크에만 title / points 키 포함.
    """
    chunks = []
    last_end = 0

    for m in CHART_BLOCK_PAT.finditer(raw):
        pre = raw[last_end:m.start()].strip()
        if pre:
            chunks.append({"type": "narration", "text": pre})

        tag_content = m.group(1)           # "항목, 시점" 또는 "항목 vs 항목, 시점"
        inner_text  = m.group(2).strip()

        parts    = [p.strip() for p in tag_content.split(",")]
        tag_type = parts[-1] if parts[-1] in CHART_TAG_TYPES else ""

        if tag_type == "list":
            middle = ",".join(parts[1:-1])
            points = [p.strip() for p in middle.split("/") if p.strip()]
            chunks.append({
                "type":   "list",
                "title":  parts[0],
                "points": points,
                "text":   inner_text,
            })
        else:
            item      = parts[0]
            time_hint = parts[1] if len(parts) > 1 else ""
            chunks.append({
                "type":      "chart",
                "item":      item,
                "time_hint": time_hint,
                "text":      inner_text,
            })
        last_end = m.end()

    remainder = raw[last_end:].strip()
    if remainder:
        chunks.append({"type": "narration", "text": remainder})

    return chunks


# ─────────────────────────────────────────
# TTS 요청
# ─────────────────────────────────────────

def tts_request(text, voice_id, api_key):
    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
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


# ─────────────────────────────────────────
# 이슈 섹션 분리 TTS + 타임코드 기록
# ─────────────────────────────────────────

def record_issue_tts(key: str, data: dict, voice_id: str, api_key: str) -> list:
    """
    이슈 섹션을 차트 경계 단위로 분할해 청크별 TTS.
    섹션 mp3(long_voice_{key}.mp3)를 생성하고 타임코드 목록을 반환.
    """
    raw    = get_issue_raw_script(data, key)
    chunks = split_issue_script(raw)

    timestamps   = []
    chunk_files  = []
    cumulative   = 0.0

    for ci, chunk in enumerate(chunks):
        text = _clean_tts_text(chunk["text"])
        if not text:
            continue

        tmp_file = f"long_voice_{key}_chunk_{ci}.mp3"
        chunk_label = f"{'리스트' if chunk['type'] == 'list' else '차트' if chunk['type'] == 'chart' else '내레이션'} {ci+1}/{len(chunks)}"
        print(f"      {chunk_label} ({len(text)}자)")

        audio = tts_request(text, voice_id, api_key)
        with open(tmp_file, "wb") as f:
            f.write(audio)

        duration = ffprobe_duration(tmp_file)

        ts: dict = {
            "type":  chunk["type"],
            "start": round(cumulative, 3),
            "end":   round(cumulative + duration, 3),
        }
        if chunk["type"] == "chart":
            ts["item"]      = chunk["item"]
            ts["time_hint"] = chunk["time_hint"]
        elif chunk["type"] == "list":
            ts["title"]  = chunk["title"]
            ts["points"] = chunk["points"]

        timestamps.append(ts)
        chunk_files.append(tmp_file)
        cumulative += duration

    # 청크 concat → 섹션 mp3
    section_file = f"long_voice_{key}.mp3"
    if len(chunk_files) == 1:
        shutil.copy(chunk_files[0], section_file)
    elif len(chunk_files) > 1:
        concat_tmp = f"long_voice_{key}_concat.txt"
        with open(concat_tmp, "w", encoding="utf-8") as f:
            for cf in chunk_files:
                f.write(f"file '{cf}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", concat_tmp, "-c", "copy", section_file],
            capture_output=True, check=True,
        )
        os.remove(concat_tmp)

    for cf in chunk_files:
        try:
            os.remove(cf)
        except OSError:
            pass

    total_dur = round(cumulative, 1)
    print(f"         → {section_file} ({total_dur}s, {len(timestamps)}블록)")
    return timestamps


# ─────────────────────────────────────────
# 챕터 생성
# ─────────────────────────────────────────

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

    # --topic 직접 실행 시 슬롯 파일 없음 → long_script.json 이슈 제목으로 fallback
    issue_titles = ["", ""]
    if not (short_titles.get(SLOTS[0]) and short_titles.get(SLOTS[1])):
        try:
            with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
                ls = json.load(f)
            for i, iss in enumerate(ls.get("issues", [])[:2]):
                issue_titles[i] = iss.get("title", "")
        except Exception:
            pass

    def issue_label(idx: int) -> str:
        return short_titles.get(SLOTS[idx]) or issue_titles[idx] or f"トピック{'①②'[idx]}"

    nums = ["①", "②"]
    labels = {
        "intro":  "オープニング",
        "issue1": f"{nums[0]} {issue_label(0)}",
        "issue2": f"{nums[1]} {issue_label(1)}",
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


# ─────────────────────────────────────────
# 섹션 mp3 concat (long_voice.mp3)
# ─────────────────────────────────────────

def concat_audio(output_path):
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


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────

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
    chart_timestamps: dict = {}

    for i, (filename, key) in enumerate(SECTIONS, 1):
        if key in ("issue1", "issue2"):
            print(f"  [{i}/{total}] {key} → 차트 경계 분리 TTS")
            ts = record_issue_tts(key, data, voice_id, api_key)
            chart_timestamps[key] = ts
        else:
            text = get_section_script(data, key)
            text = re.sub(r"[（(][^）)]*[）)]", "", text)
            text = apply_pronunciation(text)
            print(f"  [{i}/{total}] {key} ({len(text)}자) → {filename}")
            audio = tts_request(text, voice_id, api_key)
            with open(filename, "wb") as f:
                f.write(audio)
            size_kb = len(audio) // 1024
            print(f"         저장 완료 ({size_kb}KB)")

    # 차트 타임코드 저장
    with open(LONG_CHART_TIMESTAMPS_FILE, "w", encoding="utf-8") as f:
        json.dump(chart_timestamps, f, ensure_ascii=False, indent=2)
    print(f"\n  차트 타임코드 → {LONG_CHART_TIMESTAMPS_FILE}")

    print(f"\n=== 섹션 연결 → {VOICE_LONG_FILE} ===")
    concat_audio(VOICE_LONG_FILE)
    size_mb = os.path.getsize(VOICE_LONG_FILE) / (1024 * 1024)
    print(f"  연결 완료 ({size_mb:.1f}MB)")

    build_chapters()


if __name__ == "__main__":
    main()
