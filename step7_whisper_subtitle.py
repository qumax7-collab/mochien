import sys
import os
import re
import json
import subprocess
import requests
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

# 자막 커버리지 검증
SUBTITLE_COVERAGE_THRESHOLD = 2.0   # 첫 자막 시작이 이 값(초)을 초과하면 업로드 금지

# 자막 스타일
FONT_SIZE = 132
OUTLINE_SIZE = 4
WORDS_PER_LINE = 4       # 한 자막에 최대 단어 수
GAP_THRESHOLD = 0.4      # 이 시간(초) 이상 공백이면 세그먼트 분리
MAX_LINE_CHARS = 8       # 자막 한 줄 최대 글자 수 (132px × 8 = 1056px, 영상 1080px 이내)

# 스크립트 정렬
MAX_SKIP           = 15    # greedy 탐색 창 크기 (wt 문자 수)
MAX_UNMAPPED_RATIO = 0.30  # 미매핑 허용 상한

# 수치 토큰 보호 (분절 억제 대상 문자 집합)
_NUM_DIGITS = set("0123456789")
_NUM_EXT    = set(".%年円")  # 숫자 뒤에 붙어 하나의 수치 단위를 이루는 문자
PARTICLES   = frozenset("はがをにへとのもでねよわ")  # 의미 경계 조사 12종 (や·か 제외 — 형용사 어간 오매칭 방지)
MIN_PARTICLE_FLUSH_LEN = 3  # 조사 분절 최소 세그먼트 길이 (미만이면 억제)

# 고유명사 교정
GPT_CORRECTION_MODEL = "gpt-4.1-mini"

YEAR_PAT = re.compile(r'20\d{2}年')


def extract_script_years(text: str) -> set:
    """스크립트 텍스트에서 20XX年 패턴 추출 → 정답 연도 집합."""
    return set(YEAR_PAT.findall(text))


def correct_year_tokens(segments: list, script_years: set) -> tuple:
    """자막 연도 토큰을 대본 정답 집합과 대조해 교정.
    정답 연도 1종일 때만 강제 교정. 2종 이상이면 경고 후 sys.exit(1)."""
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
        print(f"  [⚠ 연도 가드] Whisper 불일치: {sorted(mismatches)}")
        print(f"  대본 연도 {len(script_years)}종: {sorted(script_years)} — 자동 교정 불가")
        print("  자막을 수동 확인하세요.")
        sys.exit(1)
    correct = next(iter(script_years))
    fixed = 0
    for seg in segments:
        for wrong in YEAR_PAT.findall(seg["text"]):
            if wrong != correct:
                print(f"  [연도 교정] {wrong} → {correct}")
                seg["text"] = seg["text"].replace(wrong, correct)
                fixed += 1
    return segments, fixed


def wrap_text(text, sep):
    """MAX_LINE_CHARS 초과 시 줄바꿈. 구두점 위치 우선, 없으면 문자 단위 분리.
    수치 토큰(digit·.·%·年·円) 중간 분리 금지: cut 점을 수치 토큰 앞으로 이동."""
    if len(text) <= MAX_LINE_CHARS:
        return text
    lines = []
    while len(text) > MAX_LINE_CHARS:
        cut = MAX_LINE_CHARS
        # 1. 우선순위: 구두점 → 조사 → 수치 토큰 직후 (우측에서 좌측 탐색)
        for j in range(MAX_LINE_CHARS - 1, -1, -1):
            if text[j] in "。、！？!?,":
                cut = j + 1
                break
            if text[j] in PARTICLES:
                # がり/がる 패턴 보호: が 직후가 り·る면 동사 어간이므로 컷 억제
                if text[j] == 'が' and j + 1 < len(text) and text[j + 1] in 'りる':
                    continue
                cut = j + 1
                break
            if j > 0 and text[j - 1] in (_NUM_DIGITS | _NUM_EXT) and text[j] not in (_NUM_DIGITS | _NUM_EXT):
                cut = j
                break
        # 2. 수치 토큰 중간 분리 방지: cut이 숫자 토큰 안을 자를 경우 앞으로 이동
        while 0 < cut < len(text):
            last = text[cut - 1]
            nxt  = text[cut]
            if (last in _NUM_DIGITS or last == ".") and nxt in (_NUM_DIGITS | _NUM_EXT):
                cut -= 1
            else:
                break
        if cut == 0:
            # 전체가 수치 토큰이거나 안전한 분리점 없음 → 통째로 한 줄
            lines.append(text)
            text = ""
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
            title = gpt.get('title', '').strip()
            if title:
                initial_prompt = f"モチエン {title}"
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


def _send_telegram(message):
    """자막 검증 실패 텔레그램 알림 (실패해도 파이프라인 계속 중단 처리는 호출측에서)."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=5,
        )
    except Exception:
        pass


def validate_subtitle_coverage(srt_path, threshold_sec=SUBTITLE_COVERAGE_THRESHOLD):
    """
    SRT 첫 이벤트 시작이 threshold_sec 초과이면 sys.exit(1).
    더미 자막·자동 보정 금지. 실패 사유를 콘솔·텔레그램으로 출력.
    """
    with open(srt_path, encoding="utf-8") as f:
        content = f.read()

    m = re.search(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->", content)
    if not m:
        msg = f"[자막 검증 실패] {srt_path}: 타임코드를 파싱할 수 없습니다. 업로드 금지."
        print(msg)
        _send_telegram(msg)
        sys.exit(1)

    h, mn, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    first_start = h * 3600 + mn * 60 + s + ms / 1000

    if first_start > threshold_sec:
        msg = (
            f"[자막 커버리지 불합격] 첫 자막 시작: {first_start:.3f}초 "
            f"(임계값: {threshold_sec}초) — 도입부 {first_start:.1f}초 무자막. 업로드 금지."
        )
        print(msg)
        _send_telegram(msg)
        sys.exit(1)

    print(f"[자막 커버리지 OK] 첫 자막 시작: {first_start:.3f}초 (임계값: {threshold_sec}초 이내)")


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
    ("乱行政",       "ラン情勢"),         # イラン情勢 세그먼트 분리 시 후반부 (イ는 앞 세그먼트에 흡수)
    ("モッチェン",   "モチエン"),         # 채널명 오인식
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
        "- 原稿にない語句は絶対に追加しないこと。文章を長くしたり補完したりしないこと。\n"
        "- 入力テキストの長さを大きく変えないこと（増減は1〜3文字程度まで）。\n"
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
            # 교정 결과가 원본의 2배 이상이면 GPT가 문장을 확장한 것으로 판단 → 원본 유지
            if result and len(result) <= len(seg["text"]) * 2:
                seg["text"] = result
            corrected_count += 1
        except Exception as e:
            print(f"  [교정 경고] seg{i} → {e} (원본 유지)")

    print(f"  자막 교정 완료 ({corrected_count}/{len(segments)}개)")
    return segments


def load_script_text():
    """gpt_result.json → 후리가나 제거한 자막용 스크립트 원문.
    step5_tts.py와 동일한 괄호 제거 regex 사용."""
    if not os.path.exists(GPT_RESULT_PATH):
        msg = "[step7] gpt_result.json 없음 — 스크립트 원문 취득 불가. sys.exit(1)"
        print(msg)
        _send_telegram(msg)
        sys.exit(1)
    with open(GPT_RESULT_PATH, encoding="utf-8") as f:
        gpt = json.load(f)
    _strip = lambda t: re.sub(r'[（(][^）)]*[）)]', '', t)
    hook   = _strip(gpt.get('hook', ''))
    script = _strip(gpt.get('script', ''))
    # step5_tts.py와 동일 결합 방식. 전각 스페이스는 자막에 불필요하므로 제거.
    combined = (hook + '　' + script).strip() if hook else script.strip()
    return combined.replace('　', '')


def build_wt_timing(corrected_segments):
    """교정된 세그먼트 → (wt, time_at[], seg_idx_at[]) 생성.
    seg_idx_at: 각 wt 문자가 속한 세그먼트 인덱스.
    세그먼트 내부는 start~end 선형 보간. 경계 갭은 자연 보존."""
    wt = ""
    time_at = []
    seg_idx_at = []
    for si, seg in enumerate(corrected_segments):
        text  = seg["text"]
        start = seg["start"]
        end   = seg["end"]
        n = len(text)
        for k in range(n):
            wt += text[k]
            t = start + (k / (n - 1)) * (end - start) if n > 1 else start
            time_at.append(t)
            seg_idx_at.append(si)
    return wt, time_at, seg_idx_at


def build_anchor_map(script_clean, wt_corrected, time_at, seg_idx_at):
    """스크립트 원문 각 문자를 wt에서 단조 greedy 탐색 → 타임코드 + Whisper 세그먼트 인덱스 배정.
    미매핑 구간은 전후 앵커 선형 보간. 실패 시 sys.exit(1)."""
    n_s = len(script_clean)
    anchor_map = [None] * n_s
    anchor_seg = [None] * n_s  # 매핑된 wt 세그먼트 인덱스 (보간 위치는 None 유지)
    p_w = 0

    for i, c in enumerate(script_clean):
        window = wt_corrected[p_w : p_w + MAX_SKIP]
        pos = window.find(c)
        if pos >= 0:
            matched = p_w + pos
            anchor_map[i] = time_at[matched]
            anchor_seg[i] = seg_idx_at[matched]
            p_w = matched + 1

    unmapped = sum(1 for a in anchor_map if a is None)
    ratio = unmapped / n_s if n_s else 0
    print(f"  정렬 결과: 매핑 {n_s - unmapped}/{n_s}  미매핑 {ratio:.1%}")

    if ratio > MAX_UNMAPPED_RATIO:
        msg = (f"[자막 정렬 실패] 미매핑 비율 {ratio:.1%} > {MAX_UNMAPPED_RATIO:.0%} "
               f"— Whisper 전사와 스크립트 불일치 과다. 업로드 금지.")
        print(msg)
        _send_telegram(msg)
        sys.exit(1)

    # 앞쪽 None: 최초 유효 앵커 값으로 채우기
    first_valid = next((i for i, a in enumerate(anchor_map) if a is not None), None)
    if first_valid is None:
        msg = "[자막 정렬 실패] 유효 앵커 없음 — sys.exit(1)"
        print(msg)
        _send_telegram(msg)
        sys.exit(1)
    for i in range(first_valid):
        anchor_map[i] = anchor_map[first_valid]

    # 중간/뒤쪽 None: 전후 선형 보간 (anchor_seg는 None 유지)
    i = 0
    while i < n_s:
        if anchor_map[i] is None:
            j = i + 1
            while j < n_s and anchor_map[j] is None:
                j += 1
            left_t  = anchor_map[i - 1]
            right_t = anchor_map[j] if j < n_s else anchor_map[i - 1]
            span = j - i + 1
            for k in range(i, j):
                anchor_map[k] = left_t + (k - i + 1) / span * (right_t - left_t)
            i = j
        else:
            i += 1

    # 단조증가 위반 검사 (10ms 여유)
    for i in range(1, n_s):
        if anchor_map[i] < anchor_map[i - 1] - 0.01:
            msg = (f"[자막 정렬 실패] 타임코드 역전 at script[{i}]='{script_clean[i]}' "
                   f"({anchor_map[i-1]:.3f}s → {anchor_map[i]:.3f}s) — sys.exit(1)")
            print(msg)
            _send_telegram(msg)
            sys.exit(1)

    return anchor_map, anchor_seg


def group_script_by_timing(script_clean, anchor_map, anchor_seg):
    """스크립트 원문 + anchor_map → 세그먼트 리스트.
    갭: Whisper 세그먼트 경계를 넘을 때만 감지 (보간 구간 내 가짜 갭 방지).
    구두점: 일본어 전용(。、！？!) — . , 는 소수점 오분절 방지를 위해 제외."""
    segments  = []
    cur_text  = ""
    cur_start = None
    cur_end   = None
    cur_seg   = None

    for i, c in enumerate(script_clean):
        t = anchor_map[i]
        s = anchor_seg[i]

        # 갭: 다른 Whisper 세그먼트로 넘어갈 때만 (보간 위치 s=None은 갭 감지 안 함)
        gap_detected = (
            cur_end is not None and
            cur_seg is not None and s is not None and
            s != cur_seg and
            t - cur_end > GAP_THRESHOLD
        )
        has_punct    = cur_text.rstrip().endswith(("。", "、", "！", "？", "!"))
        has_particle = bool(cur_text) and cur_text[-1] in PARTICLES

        # 조사 분절 억제 조건 (gap·punct는 항상 분절)
        if has_particle and not gap_detected and not has_punct:
            # ①がる/がり 패턴: 上がる·値上がり 등 동사 어간 속 が 보호
            if cur_text[-1] == 'が' and c in 'りる':
                has_particle = False
            # ②のか 패턴: 与えるのか 등 문말 のか 분리 억제
            elif cur_text[-1] == 'の' and c == 'か':
                has_particle = False
            # ③최소 길이 미만: 2자 이하 단독 세그먼트 억제
            elif len(cur_text) < MIN_PARTICLE_FLUSH_LEN:
                has_particle = False

        if (gap_detected or has_punct or has_particle) and cur_text:
            segments.append({"text": cur_text.strip(), "start": cur_start, "end": cur_end})
            cur_text  = ""
            cur_start = None
            cur_end   = None
            cur_seg   = None

        cur_text += c
        if cur_start is None:
            cur_start = t
        cur_end = t
        if s is not None:
            cur_seg = s

    if cur_text.strip():
        segments.append({"text": cur_text.strip(), "start": cur_start, "end": cur_end})

    return segments


def _absorb_lone_punct(segments):
    """구두점 단독 세그먼트(。、！？)를 직전 세그먼트 텍스트에 흡수. 타임코드 변경 없음."""
    LONE = frozenset("。、！？")
    result = []
    for seg in segments:
        if seg["text"] and all(c in LONE for c in seg["text"]) and result:
            result[-1]["text"] += seg["text"]
        else:
            result.append(seg)
    return result


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

    print("\n=== 2-2단계: 연도 토큰 대본 대조 교정 ===")
    script_years: set = set()
    if os.path.exists(GPT_RESULT_PATH):
        try:
            with open(GPT_RESULT_PATH, encoding="utf-8") as f:
                gpt = json.load(f)
            combined = f"{gpt.get('hook', '')} {gpt.get('script', '')}"
            script_years = extract_script_years(combined)
        except Exception:
            pass
    print(f"대본 연도: {sorted(script_years) if script_years else '없음'}")
    segments, n_yr = correct_year_tokens(segments, script_years)
    if n_yr:
        print(f"  연도 교정 {n_yr}건")

    for s in segments[:5]:
        print(f"  [{s['start']:.2f}s - {s['end']:.2f}s] {s['text']}")

    print("\n=== 2-3단계: 스크립트 원문 정렬 (텍스트=스크립트, 타이밍=Whisper) ===")
    script_clean = load_script_text()
    print(f"  스크립트 원문: {len(script_clean)}자")
    wt_corrected, time_at, seg_idx_at = build_wt_timing(segments)
    print(f"  Whisper 교정 전사: {len(wt_corrected)}자")
    ratio_wt = len(wt_corrected) / len(script_clean) if script_clean else 0
    print(f"  wt/script 비율: {ratio_wt:.2f}")
    if ratio_wt < 0.5:
        msg = (f"[자막 정렬 실패] Whisper 전사 과소 (비율 {ratio_wt:.2f} < 0.5) — sys.exit(1)")
        print(msg)
        _send_telegram(msg)
        sys.exit(1)
    if ratio_wt > 1.8:
        msg = (f"[자막 정렬 실패] Whisper 전사 과잉 (비율 {ratio_wt:.2f} > 1.8) — sys.exit(1)")
        print(msg)
        _send_telegram(msg)
        sys.exit(1)
    anchor_map, anchor_seg = build_anchor_map(script_clean, wt_corrected, time_at, seg_idx_at)
    segments = group_script_by_timing(script_clean, anchor_map, anchor_seg)
    segments = _absorb_lone_punct(segments)
    print(f"  최종 세그먼트: {len(segments)}개")
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

    print("\n=== 3-1단계: 자막 커버리지 검증 ===")
    validate_subtitle_coverage(SRT_FILE)

    print("\n=== 4단계: FFmpeg 자막 합성 ===")
    if not burn_subtitles(font_dir):
        return

    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print(f"\n{OUTPUT_VIDEO} 생성 완료 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
