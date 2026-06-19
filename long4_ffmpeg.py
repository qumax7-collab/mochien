import sys
import json
import os
import re
import subprocess

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 레이아웃 설정 (1920×1080) =====
OUTPUT_W = 1920
OUTPUT_H = 1080
OUTPUT_FPS = 30

TOP_BAR_H      = 108
RED_LINE_H     = 5
TOP_BAR_COLOR  = "0x1B2A4A"
RED_LINE_COLOR = "0xE50000"
TITLE_FONT_SIZE = 80

FACE_H        = 300
FACE_MARGIN_X = 30
FACE_MARGIN_Y = 60
MOUTH_OFFSET_X = 0
MOUTH_OFFSET_Y = -40

# ===== 컬러 그레이딩 + 비네팅 =====
VIGNETTE_ANGLE = 0.8
CG_RS = -0.10
CG_RM = -0.05
CG_RH = -0.03
CG_BS =  0.08
CG_BM =  0.05
CG_BH =  0.03

# ===== 나레이션 배경 폴백 (bg_section 없을 때) =====
BRIEF_FALLBACK_COLOR    = "0x1B2A4A"   # NavyDark 단색
SCREEN_TEXT_FONT_SIZE   = 56           # テロップ 폰트 크기
TELOP_Y                 = 520          # テロップ 수직 위치 (1920×1080 / 타이틀바·캐릭터 사이)

# ===== 파일 경로 =====
LONG_SCRIPT_FILE  = "long_script.json"
FONT_DIR          = "fonts"
FONT_PATH         = "fonts/NotoSansJP-Bold.ttf"
TITLE_TEXT_FILE   = "long_title.txt"
CONCAT_LIST_FILE  = "long_clips_concat.txt"
OUTPUT_FILE       = "long_output_no_sub.mp4"
ASSETS_BASE       = "https://raw.githubusercontent.com/qumax7-collab/mochien-assets/main"

SECTIONS = [
    {"key": "intro",  "audio": "long_voice_intro.mp3",  "bg": "long_bg_main.mp4",   "clip": "long_clip_intro.mp4"},
    {"key": "issue1", "audio": "long_voice_issue1.mp3", "bg": "long_bg_issue1.mp4", "clip": "long_clip_issue1.mp4"},
    {"key": "issue2", "audio": "long_voice_issue2.mp3", "bg": "long_bg_issue2.mp4", "clip": "long_clip_issue2.mp4"},
    {"key": "outro",  "audio": "long_voice_outro.mp3",  "bg": "long_bg_main.mp4",   "clip": "long_clip_outro.mp4"},
]

# ===== 차트 합성 설정 =====
LONG_CHART_TIMESTAMPS_FILE = "long_chart_timestamps.json"
CHART_ITEM_MAP_FILE        = "chart_item_map.json"
REMOTION_OUT_DIR           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "remotion", "out")
CHART_RENDER_SECONDS       = 5.0   # NavyDark = 150프레임 / 30fps

# ===== テロップ 표시 타이밍 =====
TELOP_MIN_SEC  = 2.5   # テロップ 최소 표시 시간 (초)
TELOP_MAX_SEC  = 6.0   # テロップ 최대 표시 시간 (초)
SRT_FILE       = "long_subtitle.srt"
CHAPTERS_FILE  = "long_chapters.json"

# ===== 차트 표시 타이밍 =====
# 차트 블록 내 "데이터 언급 SRT 구간"에만 차트 표시. 그 외 → 배경+텍스트.
CHART_DATA_RE   = re.compile(r"\d{2,}|マイナス|プラス|前年|横ば")
CHART_LEAD_IN   = 0.3   # 첫 데이터 세그먼트 이전 여유 (초)
CHART_LEAD_OUT  = 1.5   # 마지막 데이터 세그먼트 이후 여유 (초)
CHART_MIN_DUR   = 3.0   # 이보다 짧은 표시 구간 → 전체 블록 폴백 (초)


# ─────────────────────────────────────────
# brief 로드 / 섹션별 bg_section 취득
# ─────────────────────────────────────────

def load_brief() -> dict:
    """long_script.json의 _slug_keyword 기반으로 brief_{slug}.json 탐색."""
    if not os.path.exists(LONG_SCRIPT_FILE):
        return {}
    try:
        with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        slug = data.get("_slug_keyword", "").replace("-", "_")
        brief_path = f"brief_{slug}.json"
        if slug and os.path.exists(brief_path):
            with open(brief_path, encoding="utf-8") as f:
                brief = json.load(f)
            print(f"  brief 로드: {brief_path}")
            return brief
    except Exception:
        pass
    return {}


def get_brief_section_bg(brief: dict, section_key: str):
    """brief에서 섹션별 bg_section 경로 반환. 없거나 비어있으면 None."""
    if not brief:
        return None
    sec = brief.get(section_key)
    if isinstance(sec, dict):
        bg = sec.get("bg_section")
        if bg and os.path.exists(bg):
            return bg
    return None


def get_section_screen_text(brief: dict, section_key: str) -> list:
    """brief에서 섹션별 screen_text 배열 반환. 없으면 []."""
    if not brief:
        return []
    sec = brief.get(section_key)
    if isinstance(sec, dict):
        return sec.get("screen_text", []) or []
    return []


def distribute_telop(screen_text: list, narration_durations: list) -> list:
    """
    screen_text 항목을 나레이션 청크들에 균등 분배.
    반환: [[(text, local_start, local_end), ...], ...] 청크당 1개 리스트
    """
    n = len(screen_text)
    if not n or not narration_durations:
        return [[] for _ in narration_durations]
    total = sum(narration_durations)
    if total <= 0:
        return [[] for _ in narration_durations]

    item_dur = total / n
    result   = [[] for _ in narration_durations]

    chunk_starts = []
    acc = 0.0
    for d in narration_durations:
        chunk_starts.append(acc)
        acc += d

    for idx, text in enumerate(screen_text):
        g_start = idx * item_dur
        g_end   = (idx + 1) * item_dur
        mid     = (g_start + g_end) / 2

        ci = len(narration_durations) - 1
        for k in range(len(narration_durations)):
            if mid < chunk_starts[k] + narration_durations[k]:
                ci = k
                break

        local_start = max(0.0, g_start - chunk_starts[ci])
        local_end   = min(narration_durations[ci], g_end - chunk_starts[ci])
        if local_start < local_end:
            result[ci].append((text, local_start, local_end))

    return result


# ─────────────────────────────────────────
# SRT 기반 테롭 타이밍 산출
# ─────────────────────────────────────────

def _tc_to_sec(tc: str) -> float:
    """SRT 타임코드 HH:MM:SS,mmm → 초."""
    h, mn, rest = tc.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(mn) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: str) -> list:
    """SRT 파일 → [{"start": float, "end": float, "text": str}, ...]."""
    import re
    segs = []
    if not os.path.exists(path):
        return segs
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    pattern = re.compile(
        r"\d+\r?\n"
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\r?\n"
        r"(.*?)(?=\r?\n\r?\n\d+\r?\n|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(raw):
        text = re.sub(r"\{[^}]+\}", "", m.group(3)).strip()
        segs.append({
            "start": _tc_to_sec(m.group(1)),
            "end":   _tc_to_sec(m.group(2)),
            "text":  text,
        })
    return segs


def _telop_tokens(text: str) -> list:
    """テロップ 문구 → 1차 검색 토큰.
    순수 漢字 연속 2자+, 4자리 숫자, カタカナ 2자+.
    히라가나는 포함하지 않으므로 SRT 단어 단위와 정확히 매칭됨."""
    import re
    kanji_runs = re.findall(r"[一-龯々]{2,}", text)
    nums       = re.findall(r"[0-9]{4}", text)
    kata       = re.findall(r"[ァ-ヶ]{2,}", text)
    primary = list(dict.fromkeys(kanji_runs + nums + kata))
    if primary:
        return primary
    EXCLUDE = set("のはをがにでともかなもらてへ")
    return [c for c in re.findall(r"[一-龯]", text) if c not in EXCLUDE]


def _telop_bigrams(text: str) -> list:
    """テロップ 문구 → 漢字 2자 bigram (1차 매칭 실패 시 폴백)."""
    import re
    kanjis = re.findall(r"[一-龯々]", text)
    seen, result = set(), []
    for i in range(len(kanjis) - 1):
        b = kanjis[i] + kanjis[i + 1]
        if b not in seen:
            seen.add(b)
            result.append(b)
    return result


def _single_kanji_fallback(text: str) -> list:
    """テロップ 문구 → 단일 漢字 (최후 폴백 / 상용 조사 제외)."""
    import re
    EXCLUDE = set("のはをがにでともかなもらてへ")
    return [c for c in re.findall(r"[一-龯]", text) if c not in EXCLUDE]


def chart_srt_window(block_abs_start: float, block_abs_end: float, srt_segs: list):
    """
    차트 블록 내 '데이터 언급 SRT 구간' → (chart_start_rel, chart_end_rel).
    반환값은 block_abs_start 기준 상대값(초). 못 찾으면 None (전체 블록 폴백).
    """
    data_segs = [
        seg for seg in srt_segs
        if block_abs_start - 0.01 <= seg["start"] < block_abs_end
        and CHART_DATA_RE.search(seg["text"])
    ]
    if not data_segs:
        return None
    start_abs = max(block_abs_start, data_segs[0]["start"] - CHART_LEAD_IN)
    end_abs   = min(block_abs_end,   data_segs[-1]["end"] + CHART_LEAD_OUT)
    if end_abs - start_abs < CHART_MIN_DUR:
        return None
    return (start_abs - block_abs_start, end_abs - block_abs_start)


def telop_from_srt(
    screen_text: list,
    section_start_abs: float,
    srt_segs: list,
    ts_list: list,
) -> tuple:
    """
    SRT 타임코드 기반 テロップ 타이밍 산출.
    반환: (chunk_dict, failures)
      chunk_dict : {ts_list_idx: [(text, local_start, local_end), ...]}
      failures   : 자동 매칭 실패 문구 목록
    """
    narr_blocks = [(i, ts) for i, ts in enumerate(ts_list) if ts["type"] == "narration"]
    chunk_dict  = {i: [] for i, _ in narr_blocks}
    failures    = []
    search_from = section_start_abs

    def _find_seg(toks):
        for seg in srt_segs:
            if seg["start"] < search_from - 0.01:
                continue
            for tok in toks:
                if tok in seg["text"]:
                    return seg
        return None

    for telop_text in screen_text:
        import re as _re
        _kr   = _re.findall(r"[一-龯々]{2,}", telop_text)
        _nums = _re.findall(r"[0-9]{4}", telop_text)
        _kata = _re.findall(r"[ァ-ヶ]{2,}", telop_text)
        _long = [t for t in _kr if len(t) >= 3]   # 3자+ 漢字 run
        _sht  = [t for t in _kr if len(t) == 2]   # 2자 漢字 run
        # 특이성 순 4패스: (숫자·장문漢字·카타카나) → 2자漢字 → bigram → 단일 한자
        matched_seg = (
            _find_seg(_nums + _long + _kata) or
            _find_seg(_sht) or
            _find_seg(_telop_bigrams(telop_text)) or
            _find_seg(_single_kanji_fallback(telop_text))
        )

        if matched_seg is None:
            failures.append(telop_text)
            continue

        abs_start   = matched_seg["start"]
        search_from = abs_start + 0.05
        sec_rel_s   = abs_start - section_start_abs

        # 어느 narration 청크에 속하는지 결정
        matched_chunk = None
        for ci, ts in narr_blocks:
            if ts["start"] <= sec_rel_s < ts["end"]:
                matched_chunk = (ci, ts)
                break
        if matched_chunk is None:
            # 차트 구간 → 가장 가까운 다음 narration 청크
            for ci, ts in narr_blocks:
                if ts["end"] > sec_rel_s:
                    matched_chunk = (ci, ts)
                    break
            if matched_chunk is None:
                matched_chunk = narr_blocks[-1]

        ci, ts = matched_chunk
        chunk_dur   = ts["end"] - ts["start"]
        local_start = max(0.0, sec_rel_s - ts["start"])
        local_end   = min(chunk_dur, local_start + TELOP_MAX_SEC)
        if local_end - local_start < TELOP_MIN_SEC:
            local_end = min(chunk_dur, local_start + TELOP_MIN_SEC)
        chunk_dict[ci].append((telop_text, local_start, local_end))

    # 2차 패스: "다음 テロップ까지 표시" 규칙
    for ci in list(chunk_dict.keys()):
        items = chunk_dict[ci]
        if len(items) < 2:
            continue
        adjusted = []
        for k, (text, s, e) in enumerate(items):
            if k + 1 < len(items):
                # 다음 テロップ 시작까지 표시, TELOP_MAX_SEC 초과 금지
                e = min(items[k + 1][1], s + TELOP_MAX_SEC)
            adjusted.append((text, s, e))
        chunk_dict[ci] = adjusted

    return chunk_dict, failures


# ─────────────────────────────────────────
# 에셋 준비
# ─────────────────────────────────────────

def download_file(url, dest):
    print(f"  다운로드: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as f:
        f.write(r.content)


def get_font():
    if os.path.exists(FONT_PATH):
        return FONT_PATH
    system_fonts = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/NotoSansJP-Bold.ttf",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for p in system_fonts:
        if os.path.exists(p):
            print(f"  시스템 폰트 사용: {p}")
            return p
    import zipfile, io
    print("  폰트 없음 → Google Fonts에서 다운로드...")
    os.makedirs(FONT_DIR, exist_ok=True)
    r = requests.get("https://fonts.google.com/download?family=Noto+Sans+JP", timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    for name in z.namelist():
        if "Bold" in name and name.endswith(".ttf"):
            with open(FONT_PATH, "wb") as f:
                f.write(z.read(name))
            return FONT_PATH
    raise Exception("NotoSansJP-Bold.ttf를 찾지 못했습니다.")


def get_mouth_gif():
    filename = "mochien_talk.gif"
    if os.path.exists(filename):
        return filename
    try:
        download_file(f"{ASSETS_BASE}/{filename}", filename)
        return filename
    except Exception:
        print("  mochien_talk.gif 없음 → 입 애니메이션 생략")
        return None


def ffmpeg_font_path(path):
    return path.replace("\\", "/").replace(":", "\\\\:")


# ─────────────────────────────────────────
# FFmpeg 필터 / 명령어 생성
# ─────────────────────────────────────────

def build_filter(font_path, mouth_gif, use_color_source=False, telop_items=None):
    """
    use_color_source=True: [0:v]가 lavfi 단색 소스 (scale/colorgrade/vignette 생략)
    use_color_source=False: [0:v]가 배경 영상 (기존 처리 유지)
    telop_items: [(text, start_sec, end_sec), ...] 나레이션 구간 テロップ
    Returns: (filter_str, audio_idx, telop_temp_files)
    """
    mouth_x = OUTPUT_W - FACE_H - FACE_MARGIN_X + MOUTH_OFFSET_X
    mouth_y = OUTPUT_H - FACE_H - FACE_MARGIN_Y + MOUTH_OFFSET_Y
    fp = ffmpeg_font_path(font_path)
    title_y = f"({TOP_BAR_H}-text_h)/2"

    f = []
    if use_color_source:
        f.append("[0:v]copy[bg]")
    else:
        f.append(
            f"[0:v]scale={OUTPUT_W}:{OUTPUT_H}:force_original_aspect_ratio=increase"
            f",crop={OUTPUT_W}:{OUTPUT_H},setsar=1[bg_raw]"
        )
        f.append(
            f"[bg_raw]colorbalance=rs={CG_RS}:rm={CG_RM}:rh={CG_RH}"
            f":bs={CG_BS}:bm={CG_BM}:bh={CG_BH}[bg_graded]"
        )
        f.append(f"[bg_graded]vignette=angle={VIGNETTE_ANGLE}[bg]")

    f.append(
        f"[bg]drawbox=x=0:y=0:w={OUTPUT_W}:h={TOP_BAR_H}"
        f":color={TOP_BAR_COLOR}:t=fill[bg1]"
    )
    f.append(
        f"[bg1]drawbox=x=0:y={TOP_BAR_H}:w={OUTPUT_W}:h={RED_LINE_H}"
        f":color={RED_LINE_COLOR}:t=fill[bg2]"
    )
    f.append(
        f"[bg2]drawtext=fontfile={fp}:textfile={TITLE_TEXT_FILE}"
        f":fontcolor=white:fontsize={TITLE_FONT_SIZE}"
        f":x=(w-text_w)/2:y={title_y}[bg3]"
    )

    # テロップ chain: bg3 → telop0 → telop1 → ... → telopN
    telop_temp_files = []
    cur_label = "bg3"
    if telop_items:
        for i, (text, t_start, t_end) in enumerate(telop_items):
            tf = f"long_telop_text_{i}.txt"
            with open(tf, "w", encoding="utf-8") as ft:
                ft.write(text)
            telop_temp_files.append(tf)
            nxt    = f"telop{i}"
            tf_esc = ffmpeg_font_path(tf)
            f.append(
                f"[{cur_label}]drawtext=fontfile={fp}:textfile={tf_esc}"
                f":fontcolor=white:fontsize={SCREEN_TEXT_FONT_SIZE}"
                f":x=(w-text_w)/2:y={TELOP_Y}"
                f":box=1:boxcolor=black@0.55:boxborderw=12"
                f":enable='between(t,{t_start:.3f},{t_end:.3f})'[{nxt}]"
            )
            cur_label = nxt

    if mouth_gif:
        gif_idx = 1
        audio_idx = 2
        f.append(f"[{gif_idx}:v]scale=-2:{FACE_H}[mouth]")
        f.append(
            f"[{cur_label}][mouth]overlay=x={mouth_x}:y={mouth_y}[out]"
        )
    else:
        audio_idx = 1
        f.append(f"[{cur_label}]copy[out]")

    return ";".join(f), audio_idx, telop_temp_files


def _bg_input_args(bg_path):
    """배경 소스 ffmpeg 입력 인수 반환.
    bg_path=None → lavfi 단색 / bg_path 존재 → 동영상 루프."""
    if bg_path and os.path.exists(bg_path):
        return ["-stream_loop", "-1", "-i", bg_path], False
    return (
        ["-f", "lavfi", "-i",
         f"color=c={BRIEF_FALLBACK_COLOR}:s={OUTPUT_W}x{OUTPUT_H}:r={OUTPUT_FPS}"],
        True,   # use_color_source
    )


def get_audio_duration(audio_file):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_file],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def build_clip_cmd(section, font_path, mouth_gif, bg_path=None, telop_items=None):
    """인트로/아웃트로 전용 — 오디오 포함 단일 클립 생성.
    Returns: (cmd, telop_temp_files)
    """
    bg_args, use_color = _bg_input_args(bg_path)
    filter_str, audio_idx, tf_list = build_filter(
        font_path, mouth_gif, use_color_source=use_color, telop_items=telop_items
    )
    duration = get_audio_duration(section["audio"])

    cmd = ["ffmpeg", "-y"]
    cmd += bg_args
    if mouth_gif:
        cmd += ["-ignore_loop", "0", "-i", mouth_gif]
    cmd += ["-i", section["audio"]]
    cmd += ["-filter_complex", filter_str]
    cmd += ["-map", "[out]", "-map", f"{audio_idx}:a"]
    cmd += ["-t", str(duration)]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-r", str(OUTPUT_FPS)]
    cmd += [section["clip"]]
    return cmd, tf_list


# ─────────────────────────────────────────
# 섹션 라벨 생성
# ─────────────────────────────────────────

def get_section_label(data, key):
    if key in ("intro", "outro"):
        return data["short_title"]
    idx = int(key[-1]) - 1
    nums = ["①", "②"]
    title = data["issues"][idx]["title"]
    return f"{nums[idx]} {title[:14]}"  # 상단 바에 맞게 14자 제한


# ─────────────────────────────────────────
# concat
# ─────────────────────────────────────────

def concat_clips(clips, output):
    with open(CONCAT_LIST_FILE, "w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", CONCAT_LIST_FILE,
        "-c", "copy",
        output,
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise Exception(f"FFmpeg concat 실패:\n{err[-2000:]}")
    os.remove(CONCAT_LIST_FILE)


# ─────────────────────────────────────────
# 차트 합성 — 섹션 단위 클립 생성
# ─────────────────────────────────────────

def concat_video_clips(clips, output):
    """비디오 전용 클립 목록을 concat (오디오 없음)."""
    list_file = output + "_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output,
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    os.remove(list_file)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise Exception(f"FFmpeg 비디오 concat 실패:\n{err[-2000:]}")


def build_narration_video_cmd(section, duration, font_path, mouth_gif, tmp_file, bg_path=None, telop_items=None):
    """나레이션 구간 비디오 전용 클립 (오디오 없음).
    Returns: (cmd, telop_temp_files)
    """
    bg_args, use_color = _bg_input_args(bg_path)
    filter_str, _, tf_list = build_filter(
        font_path, mouth_gif, use_color_source=use_color, telop_items=telop_items
    )
    cmd = ["ffmpeg", "-y"]
    cmd += bg_args
    if mouth_gif:
        cmd += ["-ignore_loop", "0", "-i", mouth_gif]
    cmd += ["-filter_complex", filter_str]
    cmd += ["-map", "[out]"]
    cmd += ["-t", str(round(duration, 3))]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]
    cmd += ["-r", str(OUTPUT_FPS), "-an"]
    cmd += [tmp_file]
    return cmd, tf_list


def build_chart_video_cmd(item_key, duration, tmp_file):
    """Remotion 차트 클립 → 완전 루프 × N 회 + 마지막 프레임 freeze (중간 끊김 없음)."""
    mp4_path   = os.path.join(REMOTION_OUT_DIR, f"{item_key}.mp4")
    chart_dur  = CHART_RENDER_SECONDS
    full_loops = max(1, int(duration // chart_dur))   # 완전 재생 횟수
    freeze_t   = max(0.0, duration - full_loops * chart_dur)  # 마지막 freeze 길이
    loop_n     = full_loops - 1                       # stream_loop 추가 횟수 (0=1회 재생)

    cmd  = ["ffmpeg", "-y", "-stream_loop", str(loop_n), "-i", mp4_path]
    vf   = []
    if freeze_t > 0.01:
        vf.append(f"tpad=stop_mode=clone:stop_duration={freeze_t:.3f}")
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-t", str(round(duration, 3))]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]
    cmd += ["-r", str(OUTPUT_FPS), "-an"]
    cmd += [tmp_file]
    return cmd


def build_issue_clip_with_charts(section, ts_list, font_path, mouth_gif, bg_path=None, brief=None, telop_chunk_dict=None, srt_segs=None, section_abs_start=0.0):
    """
    issue 섹션을 타임스탬프 블록 단위로 분리해 클립 생성 후 concat.
    narration 블록 → telop_chunk_dict (SRT 기반) 또는 균등 분배 폴백.
    chart/list 블록 → Remotion 차트 mp4 루프 (기존 유지).
    """
    with open(CHART_ITEM_MAP_FILE, encoding="utf-8") as f:
        item_map = json.load(f)

    # screen_text → 나레이션 청크별 テロップ 배정
    screen_text = get_section_screen_text(brief, section["key"])
    if telop_chunk_dict is None:
        narr_durs  = [ts["end"] - ts["start"] for ts in ts_list if ts["type"] == "narration"]
        telop_dist = distribute_telop(screen_text, narr_durs)
    narr_idx = 0

    video_clips = []

    for ci, ts in enumerate(ts_list):
        duration = ts["end"] - ts["start"]
        if duration <= 0.0:
            continue

        tmp = f"long_clip_{section['key']}_chunk_{ci}.mp4"

        if ts["type"] == "narration":
            if telop_chunk_dict is not None:
                telop_for_chunk = telop_chunk_dict.get(ci, [])
            else:
                telop_for_chunk = telop_dist[narr_idx] if narr_idx < len(telop_dist) else []
                narr_idx += 1
            cmd, tf_list = build_narration_video_cmd(
                section, duration, font_path, mouth_gif, tmp,
                bg_path=bg_path, telop_items=telop_for_chunk,
            )
            chunk_label = f"내레이션 {ci+1}"

        elif ts["type"] == "list":
            key      = ts.get("key", "")
            mp4_path = os.path.join(REMOTION_OUT_DIR, f"{key}.mp4") if key else None
            if mp4_path and os.path.exists(mp4_path):
                cmd      = build_chart_video_cmd(key, duration, tmp)
                tf_list  = []
            else:
                missing = f"{mp4_path} 없음" if key else "key 없음"
                print(f"    [경고] list '{ts.get('title', '')}' → {missing}, 배경으로 대체")
                cmd, tf_list = build_narration_video_cmd(
                    section, duration, font_path, mouth_gif, tmp, bg_path=bg_path
                )
            chunk_label = f"리스트 {ci+1} ({ts.get('title', '')})"

        else:  # chart
            item_name = ts["item"]
            item_def  = item_map.get(item_name)
            mp4_path  = os.path.join(REMOTION_OUT_DIR, f"{item_def['key']}.mp4") if item_def else None
            chunk_label = f"차트 {ci+1} ({item_name})"

            if item_def is None or not os.path.exists(mp4_path):
                missing = "item_map 없음" if item_def is None else f"{mp4_path} 없음"
                print(f"    [경고] '{item_name}' → {missing}, 배경으로 대체")
                cmd, tf_list = build_narration_video_cmd(
                    section, duration, font_path, mouth_gif, tmp, bg_path=bg_path
                )
                print(f"    {chunk_label}  {duration:.1f}s → {tmp}")
                result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                for tf in tf_list:
                    try:
                        os.remove(tf)
                    except OSError:
                        pass
                if result.returncode != 0:
                    raise Exception(f"청크 클립 생성 실패 ({tmp}):\n{result.stderr.decode('utf-8', errors='replace')[-1000:]}")
                video_clips.append(tmp)
                continue

            # SRT 기반 데이터 언급 구간 분할
            block_abs_s = section_abs_start + ts["start"]
            block_abs_e = section_abs_start + ts["end"]
            window = chart_srt_window(block_abs_s, block_abs_e, srt_segs) if srt_segs else None

            if window is None:
                # 폴백: 전체 블록을 차트로 (기존 동작)
                cmd = build_chart_video_cmd(item_def["key"], duration, tmp)
                print(f"    {chunk_label}  {duration:.1f}s → {tmp}  [전체 블록]")
                result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                if result.returncode != 0:
                    raise Exception(f"청크 클립 생성 실패 ({tmp}):\n{result.stderr.decode('utf-8', errors='replace')[-1000:]}")
                video_clips.append(tmp)
            else:
                pre_rel, post_rel = window
                pre_dur   = round(pre_rel, 3)
                chart_dur = round(post_rel - pre_rel, 3)
                post_dur  = round(duration - post_rel, 3)
                print(f"    {chunk_label}  {duration:.1f}s → 배경{pre_dur:.1f}s + 차트{chart_dur:.1f}s + 배경{post_dur:.1f}s")

                sub_tmps = []
                def _run(sub_cmd, sub_tf, sub_file):
                    r = subprocess.run(sub_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    for tf in sub_tf:
                        try:
                            os.remove(tf)
                        except OSError:
                            pass
                    if r.returncode != 0:
                        raise Exception(f"서브 클립 생성 실패 ({sub_file}):\n{r.stderr.decode('utf-8', errors='replace')[-800:]}")
                    sub_tmps.append(sub_file)

                if pre_dur > 0.05:
                    f_pre = f"long_clip_{section['key']}_chunk_{ci}_pre.mp4"
                    c_pre, tf_pre = build_narration_video_cmd(section, pre_dur, font_path, mouth_gif, f_pre, bg_path=bg_path)
                    _run(c_pre, tf_pre, f_pre)

                f_chart = f"long_clip_{section['key']}_chunk_{ci}_chart.mp4"
                c_chart = build_chart_video_cmd(item_def["key"], chart_dur, f_chart)
                _run(c_chart, [], f_chart)

                if post_dur > 0.05:
                    f_post = f"long_clip_{section['key']}_chunk_{ci}_post.mp4"
                    c_post, tf_post = build_narration_video_cmd(section, post_dur, font_path, mouth_gif, f_post, bg_path=bg_path)
                    _run(c_post, tf_post, f_post)

                if len(sub_tmps) == 1:
                    os.rename(sub_tmps[0], tmp)
                else:
                    concat_video_clips(sub_tmps, tmp)
                    for f in sub_tmps:
                        try:
                            os.remove(f)
                        except OSError:
                            pass
                video_clips.append(tmp)
            continue  # 이 블록은 이미 video_clips에 추가됨

        # narration / list 블록: 공통 실행 경로
        print(f"    {chunk_label}  {duration:.1f}s → {tmp}")
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        for tf in tf_list:
            try:
                os.remove(tf)
            except OSError:
                pass
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise Exception(f"청크 클립 생성 실패 ({tmp}):\n{err[-1000:]}")

        video_clips.append(tmp)

    # 비디오 클립 concat
    video_combined = f"long_clip_{section['key']}_video_combined.mp4"
    concat_video_clips(video_clips, video_combined)

    # 비디오 + 섹션 mp3 = 섹션 클립
    cmd = [
        "ffmpeg", "-y",
        "-i", video_combined,
        "-i", section["audio"],
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        section["clip"],
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        raise Exception(f"오디오 합성 실패 ({section['key']}):\n{err[-1000:]}")

    for f_path in video_clips + [video_combined]:
        try:
            os.remove(f_path)
        except OSError:
            pass


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def main():
    print("=== long_script.json 로드 ===")
    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    chart_timestamps: dict = {}
    if os.path.exists(LONG_CHART_TIMESTAMPS_FILE):
        with open(LONG_CHART_TIMESTAMPS_FILE, encoding="utf-8") as f:
            chart_timestamps = json.load(f)
        print(f"  차트 타임스탬프 로드: {LONG_CHART_TIMESTAMPS_FILE}")
    else:
        print(f"  [{LONG_CHART_TIMESTAMPS_FILE} 없음] 기존 방식으로 영상 생성")

    print("\n=== brief 로드 ===")
    brief = load_brief()

    print("\n=== SRT 기반 テロップ 타이밍 산출 ===")
    srt_segs: list = parse_srt(SRT_FILE)
    all_telop_data: dict = {}   # key → chunk_dict or None
    if not srt_segs:
        print(f"  [경고] {SRT_FILE} 없음 — 균등 분배로 폴백")
    else:
        section_abs_starts: dict = {}
        if os.path.exists(CHAPTERS_FILE):
            with open(CHAPTERS_FILE, encoding="utf-8") as f:
                chapters = json.load(f)
            for key_name, ch in zip(["intro", "issue1", "issue2", "outro"], chapters):
                section_abs_starts[key_name] = float(ch["time"])

        all_failures: dict = {}
        for sec in SECTIONS:
            _key      = sec["key"]
            _ts_list  = chart_timestamps.get(_key, [])
            _has_ch   = any(t["type"] == "chart" for t in _ts_list)
            _sec_abs  = section_abs_starts.get(_key, 0.0)
            _scr_text = get_section_screen_text(brief, _key)
            if not _scr_text:
                all_telop_data[_key] = None
                all_failures[_key]   = []
                continue
            if _key in ("issue1", "issue2") and _has_ch:
                cd, fails = telop_from_srt(_scr_text, _sec_abs, srt_segs, _ts_list)
            else:
                _dur     = get_audio_duration(sec["audio"])
                fake_ts  = [{"type": "narration", "start": 0.0, "end": _dur}]
                cd, fails = telop_from_srt(_scr_text, _sec_abs, srt_segs, fake_ts)
            all_telop_data[_key] = cd
            all_failures[_key]   = fails

        total_fails = sum(len(v) for v in all_failures.values())
        if total_fails:
            print(f"  ★ 자동 매칭 실패 항목 {total_fails}개 (균등 분배 폴백):")
            for k, fails in all_failures.items():
                for t in fails:
                    print(f"    [{k}] {t}")
        else:
            print("  모든 テロップ 자동 매칭 성공 ✓")

    print("\n=== 에셋 준비 ===")
    font_path = get_font()
    mouth_gif = get_mouth_gif()

    print("\n=== 섹션별 클립 생성 ===")
    total = len(SECTIONS)
    for i, section in enumerate(SECTIONS, 1):
        key   = section["key"]
        label = get_section_label(data, key)
        print(f"  [{i}/{total}] {key} — '{label}'")

        with open(TITLE_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(label)

        ts_list    = chart_timestamps.get(key, [])
        has_charts = any(t["type"] == "chart" for t in ts_list)

        bg_path = get_brief_section_bg(brief, key)
        if bg_path:
            print(f"    배경: {bg_path}")
        else:
            print(f"    배경: 폴백 단색 ({BRIEF_FALLBACK_COLOR})")

        if key in ("issue1", "issue2") and has_charts:
            chart_count = sum(1 for t in ts_list if t["type"] == "chart")
            print(f"         차트 {chart_count}개 포함 ({len(ts_list)}블록)")
            try:
                build_issue_clip_with_charts(
                    section, ts_list, font_path, mouth_gif,
                    bg_path=bg_path, brief=brief,
                    telop_chunk_dict=all_telop_data.get(key) if all_telop_data else None,
                    srt_segs=srt_segs,
                    section_abs_start=section_abs_starts.get(key, 0.0),
                )
            except Exception as e:
                print(f"[에러] {key} 차트 합성 실패: {e}")
                sys.exit(1)
        else:
            # 인트로/아웃트로: SRT 기반 타이밍 또는 균등 분배 폴백
            duration  = get_audio_duration(section["audio"])
            scr_text  = get_section_screen_text(brief, key)
            cd = all_telop_data.get(key) if all_telop_data else None
            if cd is not None and 0 in cd and cd[0]:
                telop_items = cd[0]
            else:
                telop_dist  = distribute_telop(scr_text, [duration])
                telop_items = telop_dist[0] if telop_dist else []

            cmd, tf_list = build_clip_cmd(
                section, font_path, mouth_gif, bg_path=bg_path, telop_items=telop_items
            )
            result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            for tf in tf_list:
                try:
                    os.remove(tf)
                except OSError:
                    pass
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")
                print(f"[에러] {key} 클립 생성 실패:")
                print(err[-2000:])
                sys.exit(1)

        size_mb = os.path.getsize(section["clip"]) / (1024 * 1024)
        print(f"         → {section['clip']} ({size_mb:.1f}MB)")

    print(f"\n=== 클립 연결 → {OUTPUT_FILE} ===")
    clips = [s["clip"] for s in SECTIONS]
    concat_clips(clips, OUTPUT_FILE)

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"  완료: {OUTPUT_FILE} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
