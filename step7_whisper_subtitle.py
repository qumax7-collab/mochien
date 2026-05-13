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
GLOSSARY_PATH   = "glossary.json"

# 자막 스타일
FONT_SIZE = 132
OUTLINE_SIZE = 4
WORDS_PER_LINE = 4       # 한 자막에 최대 단어 수
GAP_THRESHOLD = 0.4      # 이 시간(초) 이상 공백이면 세그먼트 분리
MAX_LINE_CHARS = 8       # 자막 한 줄 최대 글자 수 (132px × 8 = 1056px, 영상 1080px 이내)

# 고유명사 교정
GPT_CORRECTION_MODEL = "gpt-4.1-mini"


def wrap_text(text, sep):
    """MAX_LINE_CHARS 초과 시 줄바꿈. 구두점 위치 우선, 없으면 문자 단위 분리."""
    if len(text) <= MAX_LINE_CHARS:
        return text
    lines = []
    while len(text) > MAX_LINE_CHARS:
        cut = MAX_LINE_CHARS
        for j in range(MAX_LINE_CHARS - 1, -1, -1):
            if text[j] in "。、！？!?,":
                cut = j + 1
                break
        lines.append(text[:cut])
        text = text[cut:]
    if text:
        lines.append(text)
    return sep.join(lines)


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
    initial_prompt = "モチエン"  # 채널명은 gpt_result.json 없어도 항상 포함
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


# 규칙 기반 선처리: (잘못된 표기, 올바른 표기)
# 참조 스크립트에 올바른 표기가 있을 때만 적용
KNOWN_ASR_ERRORS = [
    # 한자 오인식 (1~2자 차이)
    ("機区",         "機構"),        # 経済協力開発機構
    ("安全保証",     "安全保障"),    # 経済安全保障
    ("確信され",     "確認され"),
    ("連系",         "連携"),
    ("隠密に",       "緊密に"),      # 緊密に連携
    ("公私",         "高市"),        # 高市大臣
    ("営業",         "影響"),        # 影響 → 営業 오인식
    ("教材",         "経済"),        # 経済 → 教材 오인식
    # 고유명사 오인식
    ("公満事務省庁", "コーマン事務総長"),
    ("公満事",       "コーマン事"),       # 세그먼트 분리 시 전반부
    ("務省庁",       "務総長"),           # 세그먼트 분리 시 후반부
    ("イラン行政",   "イラン情勢"),       # イラン情勢 오인식
    ("モッチェン",   "モチエン"),         # 채널명 오인식
    # 히라가나 붕괴
    ("こ用",         "雇用"),
    ("つなごある",   "つながる"),
    # 자막 잔상·중복
    ("保障部に",     "保障分野"),
]


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


def apply_rule_corrections(text, script):
    """알려진 오류 패턴을 스크립트와 대조해 즉시 교정."""
    for wrong, correct in KNOWN_ASR_ERRORS:
        if wrong in text and correct in script:
            text = text.replace(wrong, correct)
    return text


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

    # 1단계: 규칙 기반 선처리 (GPT 호출 전)
    rule_fixed = 0
    for seg in segments:
        fixed = apply_rule_corrections(seg["text"], script)
        if fixed != seg["text"]:
            seg["text"] = fixed
            rule_fixed += 1
    if rule_fixed:
        print(f"  규칙 교정: {rule_fixed}건")
    reference = f"タイトル: {title}\nフック: {hook}\nスクリプト全文:\n{script}"

    system_msg = (
        "あなたは日本語音声認識の後処理AIです。\n"
        "参照テキスト（元の原稿）をもとに、与えられた音声認識テキスト1件を修正してください。\n\n"
        "【参照テキストの使い方 — 最重要】\n"
        "音声認識テキストの各語句を参照テキストと照合し、"
        "1〜2文字の違いで似ている語句があれば参照テキストの表記に統一すること。\n"
        "例: 参照テキストに「開発機構」がある → 音声認識「開発機区」は「開発機構」に修正。\n"
        "例: 参照テキストに「経済安全保障」がある → 音声認識「経済安全保証」は「経済安全保障」に修正。\n\n"
        "【経済ニュースでよくある誤認識パターン】\n"
        "  ✗ 開発機区   → ✓ 開発機構   （構↔区）\n"
        "  ✗ 安全保証   → ✓ 安全保障   （障↔証）\n"
        "  ✗ 確信され   → ✓ 確認され   （認↔信）\n"
        "  ✗ 連系       → ✓ 連携       （携↔系）\n"
        "  ✗ こ用の     → ✓ 雇用の     （ひらがな崩れ）\n"
        "  ✗ 保障部に   → ✓ 保障分野   （分野↔部）\n"
        "  ✗ つなごある → ✓ つながる   （ひらがな崩れ）\n\n"
        "【実際に発生した音声認識エラーパターン — 必ず修正】\n"
        "以下のような誤認識にも注意して修正すること:\n"
        "①発音が似た漢字への誤変換\n"
        "  ✗ 高市 → 公私　　✗ 緊密に → 隠密に　　✗ 影響 → 営業\n"
        "②固有名詞の誤認識\n"
        "  ✗ コーマン事務総長 → 公満事務省庁\n"
        "③字幕の重複・残像（同じ語が連続・断片化している場合は一方を削除）\n"
        "  ✗ 効果果 → 効果　　✗ 保障保障 → 保障\n\n"
        "【その他の修正対象】\n"
        "- 原稿にない幻覚ワード（冒頭・末尾に紛れ込む無関係な語）は削除\n\n"
        "【制約】\n"
        "- テキストのみ出力。説明・記号一切不要。\n"
        "- 原稿にない語句は追加しないこと。\n"
        "- 修正箇所がなければ入力をそのまま返すこと。"
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
            # 교정 결과가 원본의 3배 이상이면 GPT가 참조 텍스트를 그대로 반환한 것으로 판단 → 원본 유지
            if result and len(result) <= len(seg["text"]) * 3:
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
        lines.append(wrap_text(seg["text"], "\n"))
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
        # \\an5 = 화면 정중앙 (numpad 5) / \\N = ASS 줄바꿈
        text = "{\\an5}" + wrap_text(seg["text"], "\\N")
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
    segments = apply_glossary(segments)

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
