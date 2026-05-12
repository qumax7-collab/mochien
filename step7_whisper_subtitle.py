import sys
import os
import json
import subprocess
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

INPUT_AUDIO = "voice.mp3"
INPUT_VIDEO = "output_no_sub.mp4"
OUTPUT_VIDEO = "output_video_subtitled.mp4"
ASS_FILE = "subtitle.ass"
SRT_FILE = "subtitle.srt"
GPT_RESULT_PATH = "gpt_result.json"

# 자막 스타일
FONT_SIZE = 132
OUTLINE_SIZE = 4
WORDS_PER_LINE = 4       # 한 자막에 최대 단어 수
GAP_THRESHOLD = 0.4      # 이 시간(초) 이상 공백이면 세그먼트 분리

# 고유명사 교정
GPT_CORRECTION_MODEL = "gpt-4.1-mini"


def get_font():
    if os.path.exists("fonts/NotoSansJP-Bold.ttf"):
        return "Noto Sans JP", "fonts"
    for path, name in [
        # Linux (apt: fonts-noto-cjk)
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "Noto Sans CJK JP"),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", "Noto Sans CJK JP"),
        # Windows
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
    print(f"Whisper API 전송 중: {INPUT_AUDIO}")
    with open(INPUT_AUDIO, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
            language="ja",
        )
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


def correct_proper_nouns(segments, api_key):
    """gpt_result.json 원고를 참조해 세그먼트를 1개씩 개별 GPT 교정."""
    if not os.path.exists(GPT_RESULT_PATH):
        print("  [자막 교정 건너뜀] gpt_result.json 없음")
        return segments

    with open(GPT_RESULT_PATH, encoding="utf-8") as f:
        gpt_result = json.load(f)

    title  = gpt_result.get("title", "")
    hook   = gpt_result.get("hook", "")
    script = gpt_result.get("script", "")
    reference = f"タイトル: {title}\nフック: {hook}\nスクリプト全文:\n{script}"

    system_msg = (
        "あなたは日本語音声認識の後処理AIです。"
        "参照テキスト（元の原稿）をもとに、与えられた音声認識テキスト1件を修正してください。\n"
        "修正対象:\n"
        "1. 固有名詞（人名・企業名・地名）の誤字\n"
        "2. 同音異字（原稿の表現を優先）\n"
        "3. 音声認識で崩れた語句を原稿の表現に合わせる\n"
        "制約: テキストのみ出力。説明・記号不要。原稿にない内容は追加しないこと。"
    )

    client = OpenAI(api_key=api_key)
    corrected_count = 0

    for i, seg in enumerate(segments):
        try:
            resp = client.chat.completions.create(
                model=GPT_CORRECTION_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": f"【参照テキスト】\n{reference}\n\n【修正対象】\n{seg['text']}"},
                ],
                temperature=0,
            )
            result = resp.choices[0].message.content.strip()
            if result:
                seg["text"] = result
            corrected_count += 1
        except Exception as e:
            print(f"  [교정 경고] seg{i} → {e} (원본 유지)")

    print(f"  자막 교정 완료 ({corrected_count}/{len(segments)}개)")
    return segments


def to_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def to_ass_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(segments, font_name):
    header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,{OUTLINE_SIZE},0,5,10,10,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""

    events = []
    for seg in segments:
        # \\an5 = 화면 정중앙 (numpad 5)
        text = "{\\an5}" + seg["text"]
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
    print("FFmpeg 실행 중...")
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

    print("\n=== 2-1단계: 고유명사 교정 ===")
    segments = correct_proper_nouns(segments, api_key)

    for s in segments[:5]:
        print(f"  [{s['start']:.2f}s - {s['end']:.2f}s] {s['text']}")

    print("\n=== 3단계: ASS 자막 파일 생성 ===")
    font_name, font_dir = get_font()
    print(f"폰트: {font_name}  fontsdir: {font_dir}")
    ass_content = build_ass(segments, font_name)
    with open(ASS_FILE, "w", encoding="utf-8") as f:
        f.write(ass_content)
    print(f"{ASS_FILE} 저장 완료")

    srt_content = build_srt(segments)
    with open(SRT_FILE, "w", encoding="utf-8") as f:
        f.write(srt_content)
    print(f"{SRT_FILE} 저장 완료")

    print("\n=== 4단계: FFmpeg 자막 합성 ===")
    if not burn_subtitles(font_dir):
        return

    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print(f"\n{OUTPUT_VIDEO} 생성 완료 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
