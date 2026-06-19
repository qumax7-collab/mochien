import sys
import os
import re
import json
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 파일 경로 =====
INPUT_AUDIO     = "long_voice.mp3"
INPUT_VIDEO     = "long_output_no_sub.mp4"
OUTPUT_VIDEO    = "long_output.mp4"
ASS_FILE        = "long_subtitle.ass"
SRT_FILE        = "long_subtitle.srt"
GLOSSARY_PATH    = "glossary.json"
GPT_RESULT_PATH  = "gpt_result.json"
LONG_SCRIPT_PATH = "long_script.json"

KNOWN_ASR_ERRORS = [
    # 한자 오인식
    ("機区",         "機構"),
    ("安全保証",     "安全保障"),
    ("確信され",     "確認され"),
    ("連系",         "連携"),
    ("隠密に",       "緊密に"),
    ("公私",         "高市"),
    ("営業",         "影響"),
    ("教材",         "経済"),
    # 고유명사 오인식
    ("公満事務省庁", "コーマン事務総長"),
    ("公満事",       "コーマン事"),
    ("務省庁",       "務総長"),
    ("イラン行政",   "イラン情勢"),
    ("乱行政",       "ラン情勢"),         # イラン情勢 세그먼트 분리 시 후반부
    ("モッチェン",   "モチエン"),
    ("岸外務省",     "外務省"),           # 元外務省 → 岸外務省 오인식
    # 히라가나 붕괴
    ("こ用",         "雇用"),
    ("つなごある",   "つながる"),
    # 자막 잔상·중복
    ("保障部に",     "保障分野"),
    # 동음이자 오인식
    ("市立",         "仕事"),           # 仕事の状況 → 市立 오인식
    ("歯き",         "動き"),           # 動き → 歯き 오인식
    ("長材",         "地域経済"),       # 地域経済 → 長材 오인식
]

# ===== 자막 스타일 (1920×1080 기준) =====
FONT_SIZE      = 90    # 쇼츠 132px → 가로형 비율 조정 / 40~60대 가독성 기준
OUTLINE_SIZE   = 4
WORDS_PER_LINE = 6     # 가로 화면이 넓으므로 쇼츠(4)보다 많게
GAP_THRESHOLD  = 0.4

YEAR_PAT = re.compile(r'20\d{2}年')


def extract_script_years(text: str) -> set:
    """스크립트 텍스트에서 20XX年 패턴 추출 → 정답 연도 집합."""
    return set(YEAR_PAT.findall(text))


def correct_year_tokens(segments: list, script_years: set) -> tuple:
    """자막 연도 토큰을 대본 정답 집합과 대조해 교정.
    정답 연도 1종: 불일치 연도 강제 교정.
    정답 연도 2종 이상: 불일치 연도 경고만 출력 (자동 교정 없음 — 다연도 대본 보존)."""
    if not script_years:
        return segments, 0
    mismatches = {
        year
        for seg in segments
        for year in YEAR_PAT.findall(seg["text"])
        if year not in script_years
    }
    if not mismatches:
        return segments, 0
    if len(script_years) >= 2:
        print(f"  [⚠ 연도 가드] Whisper 불일치 {len(mismatches)}건: {sorted(mismatches)}")
        print(f"  대본 연도 {len(script_years)}종: {sorted(script_years)} — 자동 교정 불가, 수동 확인 권장")
        return segments, 0
    correct = next(iter(script_years))
    fixed = 0
    for seg in segments:
        for wrong in YEAR_PAT.findall(seg["text"]):
            if wrong != correct:
                print(f"  [연도 교정] {wrong} → {correct}")
                seg["text"] = seg["text"].replace(wrong, correct)
                fixed += 1
    return segments, fixed


def apply_rule_corrections(segments):
    """long_script.json 원고를 참조해 알려진 ASR 오류를 규칙 기반 교정."""
    if not os.path.exists(LONG_SCRIPT_PATH):
        return segments
    try:
        with open(LONG_SCRIPT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        script = "".join(
            data.get(key, {}).get("script", "")
            for key in ["intro", "issue1", "issue2", "issue3", "outro"]
        )
    except Exception:
        return segments
    rule_fixed = 0
    for seg in segments:
        for wrong, correct in KNOWN_ASR_ERRORS:
            if wrong in seg["text"] and correct in script:
                seg["text"] = seg["text"].replace(wrong, correct)
                rule_fixed += 1
    if rule_fixed:
        print(f"  규칙 교정: {rule_fixed}건")
    return segments


def apply_glossary(segments):
    """glossary.json의 오인식 패턴을 세그먼트에 일괄 적용."""
    if not os.path.exists(GLOSSARY_PATH):
        return segments
    try:
        with open(GLOSSARY_PATH, encoding="utf-8") as f:
            glossary = json.load(f)
        for seg in segments:
            for wrong, correct in glossary.items():
                seg["text"] = seg["text"].replace(wrong, correct)
    except Exception:
        pass
    return segments


def get_font():
    if os.path.exists("fonts/NotoSansJP-Bold.ttf"):
        return "Noto Sans JP", "fonts"
    for path, name in [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "Noto Sans CJK JP"),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", "Noto Sans CJK JP"),
        ("C:/Windows/Fonts/YuGothB.ttc", "Yu Gothic"),
        ("C:/Windows/Fonts/YuGothR.ttc", "Yu Gothic"),
        ("C:/Windows/Fonts/meiryo.ttc",  "Meiryo"),
        ("C:/Windows/Fonts/msgothic.ttc", "MS Gothic"),
    ]:
        if os.path.exists(path):
            return name, None
    return "Sans", None


def transcribe(api_key):
    client = OpenAI(api_key=api_key)
    initial_prompt = "モチエン"  # 채널명은 항상 포함
    if os.path.exists(GPT_RESULT_PATH):
        try:
            with open(GPT_RESULT_PATH, encoding="utf-8") as f:
                gpt = json.load(f)
            title_hook = f"{gpt.get('title', '')} {gpt.get('hook', '')}".strip()
            if title_hook:
                initial_prompt = f"モチエン {title_hook}"
        except Exception:
            pass
    print(f"Whisper API 전송 중: {INPUT_AUDIO}")
    with open(INPUT_AUDIO, "rb") as f:
        params = dict(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
            language="ja",
        )
        if initial_prompt:
            params["prompt"] = initial_prompt
        result = client.audio.transcriptions.create(**params)
    words = [{"word": w.word, "start": w.start, "end": w.end} for w in result.words]
    print(f"단어 수: {len(words)}")
    return words


def group_words(words):
    segments = []
    current = []

    for i, w in enumerate(words):
        current.append(w)
        is_last = (i == len(words) - 1)
        has_gap = (not is_last and words[i + 1]["start"] - w["end"] > GAP_THRESHOLD)
        has_punct = w["word"].rstrip().endswith(("。", "、", "！", "？", ".", "!", ","))
        at_limit = (len(current) >= WORDS_PER_LINE)

        if at_limit or has_gap or has_punct or is_last:
            segments.append({
                "text": "".join(c["word"] for c in current).strip(),
                "start": current[0]["start"],
                "end": current[-1]["end"],
            })
            current = []

    return segments


def to_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, path):
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def to_ass_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(segments, font_name):
    header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,{OUTLINE_SIZE},0,2,40,40,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""

    events = []
    for seg in segments:
        # \\an2 = 하단 중앙
        text = "{\\an2}" + seg["text"]
        events.append(
            f"Dialogue: 0,{to_ass_time(seg['start'])},{to_ass_time(seg['end'])},Default,,0,0,0,,{text}"
        )

    return header + "\n" + "\n".join(events)


def burn_subtitles(font_dir):
    vf = f"ass={ASS_FILE}"
    if font_dir:
        font_dir_abs = os.path.abspath(font_dir).replace("\\", "/").replace(":", "\\:")
        vf = f"ass={ASS_FILE}:fontsdir={font_dir_abs}"

    cmd = [
        "ffmpeg", "-y",
        "-i", INPUT_VIDEO,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        OUTPUT_VIDEO,
    ]
    print("FFmpeg 자막 합성 중...")
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if result.returncode != 0:
        print("[에러] FFmpeg 실패:")
        print(result.stderr.decode("utf-8", errors="replace")[-2000:])
        return False
    return True


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY가 .env에 없습니다.")

    print("=== 1단계: Whisper 트랜스크립션 ===")
    words = transcribe(api_key)

    print("\n=== 2단계: 자막 세그먼트 생성 ===")
    segments = group_words(words)
    print(f"세그먼트 수: {len(segments)}")
    segments = apply_glossary(segments)
    segments = apply_rule_corrections(segments)

    print("\n=== 2-1단계: 연도 토큰 대본 대조 교정 ===")
    script_years: set = set()
    if os.path.exists(LONG_SCRIPT_PATH):
        try:
            with open(LONG_SCRIPT_PATH, encoding="utf-8") as f:
                d = json.load(f)
            parts = [d.get("intro", {}).get("script", "")]
            for iss in d.get("issues", []):
                parts.append(iss.get("script", ""))
            parts.append(d.get("outro", {}).get("script", ""))
            combined = " ".join(parts)
            script_years = extract_script_years(combined)
        except Exception:
            pass
    print(f"대본 연도: {sorted(script_years) if script_years else '없음'}")
    segments, n_yr = correct_year_tokens(segments, script_years)
    if n_yr:
        print(f"  연도 교정 {n_yr}건")

    for s in segments[:5]:
        print(f"  [{s['start']:.2f}s - {s['end']:.2f}s] {s['text']}")

    print("\n=== 3단계: ASS 자막 파일 생성 ===")
    font_name, font_dir = get_font()
    print(f"폰트: {font_name}  fontsdir: {font_dir}")
    ass_content = build_ass(segments, font_name)
    with open(ASS_FILE, "w", encoding="utf-8") as f:
        f.write(ass_content)
    print(f"{ASS_FILE} 저장 완료")

    write_srt(segments, SRT_FILE)
    print(f"{SRT_FILE} 저장 완료")

    print("\n=== 4단계: FFmpeg 자막 합성 ===")
    if not burn_subtitles(font_dir):
        sys.exit(1)

    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print(f"\n{OUTPUT_VIDEO} 생성 완료 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
