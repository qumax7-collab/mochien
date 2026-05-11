import sys
import json
import os
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
    {"key": "issue3", "audio": "long_voice_issue3.mp3", "bg": "long_bg_issue3.mp4", "clip": "long_clip_issue3.mp4"},
    {"key": "outro",  "audio": "long_voice_outro.mp3",  "bg": "long_bg_main.mp4",   "clip": "long_clip_outro.mp4"},
]


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

def build_filter(font_path, mouth_gif):
    mouth_x = OUTPUT_W - FACE_H - FACE_MARGIN_X + MOUTH_OFFSET_X
    mouth_y = OUTPUT_H - FACE_H - FACE_MARGIN_Y + MOUTH_OFFSET_Y
    fp = ffmpeg_font_path(font_path)
    title_y = f"({TOP_BAR_H}-text_h)/2"

    f = []
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

    if mouth_gif:
        gif_idx = 1
        audio_idx = 2
        f.append(f"[{gif_idx}:v]scale=-2:{FACE_H}[mouth]")
        f.append(
            f"[bg3][mouth]overlay=x={mouth_x}:y={mouth_y}:shortest=1[out]"
        )
    else:
        audio_idx = 1
        f.append("[bg3]copy[out]")

    return ";".join(f), audio_idx


def build_clip_cmd(section, font_path, mouth_gif):
    filter_str, audio_idx = build_filter(font_path, mouth_gif)

    cmd = ["ffmpeg", "-y"]
    cmd += ["-stream_loop", "-1", "-i", section["bg"]]
    if mouth_gif:
        cmd += ["-ignore_loop", "0", "-i", mouth_gif]
    cmd += ["-i", section["audio"]]
    cmd += ["-filter_complex", filter_str]
    cmd += ["-map", "[out]", "-map", f"{audio_idx}:a"]
    cmd += ["-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-r", str(OUTPUT_FPS)]
    cmd += [section["clip"]]
    return cmd


# ─────────────────────────────────────────
# 섹션 라벨 생성
# ─────────────────────────────────────────

def get_section_label(data, key):
    if key in ("intro", "outro"):
        return data["short_title"]
    idx = int(key[-1]) - 1
    nums = ["①", "②", "③"]
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
# 메인
# ─────────────────────────────────────────

def main():
    print("=== long_script.json 로드 ===")
    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print("\n=== 에셋 준비 ===")
    font_path = get_font()
    mouth_gif = get_mouth_gif()

    print("\n=== 섹션별 클립 생성 ===")
    total = len(SECTIONS)
    for i, section in enumerate(SECTIONS, 1):
        label = get_section_label(data, section["key"])
        print(f"  [{i}/{total}] {section['key']} — '{label}'")

        with open(TITLE_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(label)

        cmd = build_clip_cmd(section, font_path, mouth_gif)
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            print(f"[에러] {section['key']} 클립 생성 실패:")
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
