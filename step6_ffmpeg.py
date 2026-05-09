import sys
import json
import os
import subprocess
import requests
from PIL import Image
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 레이아웃 설정 =====
OUTPUT_W = 1080
OUTPUT_H = 1920
OUTPUT_FPS = 30

TOP_BAR_H = 192
RED_LINE_H = 5
TOP_BAR_COLOR = "0x1B2A4A"
RED_LINE_COLOR = "0xE50000"
TITLE_FONT_SIZE = 105

FACE_H = 500
FACE_MARGIN_X = 30
FACE_MARGIN_Y = 100          # 하단 여백 증가 → 캐릭터 잘림 방지
FACE_EMOTION_OVERRIDE = "base"  # None으로 바꾸면 gpt_result.json의 emotion 자동 사용

# 입 GIF 오버레이 (face와 동일 크기, face 기준 오프셋)
MOUTH_OFFSET_X = 0
MOUTH_OFFSET_Y = -60         # face보다 60px 위 (올려서 맞춤)

# 파일 경로
FONT_DIR = "fonts"
FONT_PATH = "fonts/NotoSansJP-Bold.ttf"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/static/NotoSansJP-Bold.ttf"
ASSETS_BASE = "https://raw.githubusercontent.com/qumax7-collab/mochien-assets/main"
OUTPUT_FILE = "output_no_sub.mp4"


def download_file(url, dest):
    print(f"  다운로드: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"  저장: {dest} ({len(r.content) // 1024}KB)")


def get_font():
    if os.path.exists(FONT_PATH):
        return FONT_PATH
    # Windows 내장 일본어 폰트 우선 사용
    system_fonts = [
        # Linux (apt: fonts-noto-cjk)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        # Windows
        "C:/Windows/Fonts/NotoSansJP-Bold.ttf",
        "C:/Windows/Fonts/NotoSansJP-Bold.otf",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for p in system_fonts:
        if os.path.exists(p):
            print(f"  시스템 폰트 사용: {p}")
            return p
    # 없으면 Google Fonts zip에서 추출
    print("  일본어 폰트 없음 → Google Fonts에서 다운로드 중...")
    os.makedirs(FONT_DIR, exist_ok=True)
    import zipfile, io
    r = requests.get("https://fonts.google.com/download?family=Noto+Sans+JP", timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    for name in z.namelist():
        if "Bold" in name and name.endswith(".ttf"):
            data = z.read(name)
            with open(FONT_PATH, "wb") as f:
                f.write(data)
            print(f"  폰트 추출: {name} → {FONT_PATH}")
            return FONT_PATH
    raise Exception("Google Fonts zip에서 NotoSansJP-Bold.ttf를 찾지 못했습니다.")


def get_face_asset(emotion):
    filename = f"mochien_{emotion}.png"
    if not os.path.exists(filename):
        download_file(f"{ASSETS_BASE}/{filename}", filename)
    return filename


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
    # FFmpeg filter 내 폰트 경로: 콜론 이스케이프, 슬래시 통일
    return path.replace("\\", "/").replace(":", "\\\\:")


def build_filter(font_path, mouth_gif):
    mouth_x = OUTPUT_W - FACE_H - FACE_MARGIN_X + MOUTH_OFFSET_X
    mouth_y = OUTPUT_H - FACE_H - FACE_MARGIN_Y + MOUTH_OFFSET_Y

    fp = ffmpeg_font_path(font_path)
    title_y = f"({TOP_BAR_H}-text_h)/2"

    f = []
    f.append(
        f"[0:v]scale=-2:{OUTPUT_H},crop={OUTPUT_W}:{OUTPUT_H},setsar=1[bg]"
    )
    f.append(
        f"[bg]drawbox=x=0:y=0:w={OUTPUT_W}:h={TOP_BAR_H}:color={TOP_BAR_COLOR}:t=fill[bg1]"
    )
    f.append(
        f"[bg1]drawbox=x=0:y={TOP_BAR_H}:w={OUTPUT_W}:h={RED_LINE_H}:color={RED_LINE_COLOR}:t=fill[bg2]"
    )
    f.append(
        f"[bg2]drawtext=fontfile={fp}:textfile=short_title.txt"
        f":fontcolor=white:fontsize={TITLE_FONT_SIZE}"
        f":x=(w-text_w)/2:y={title_y}[bg3]"
    )
    if mouth_gif:
        gif_idx = 1
        audio_idx = 2
        f.append(f"[{gif_idx}:v]scale=-2:{FACE_H}[mouth]")
        f.append(f"[bg3][mouth]overlay=x={mouth_x}:y={mouth_y}:shortest=1[out]")
    else:
        audio_idx = 1
        f.append("[bg3]copy[out]")

    return ";".join(f), audio_idx


def build_cmd(mouth_gif, font_path):
    filter_str, audio_idx = build_filter(font_path, mouth_gif)

    cmd = ["ffmpeg", "-y"]
    cmd += ["-stream_loop", "-1", "-i", "background.mp4"]
    if mouth_gif:
        cmd += ["-ignore_loop", "0", "-i", mouth_gif]
    cmd += ["-i", "voice.mp3"]
    cmd += ["-filter_complex", filter_str]
    cmd += ["-map", "[out]", "-map", f"{audio_idx}:a"]
    cmd += ["-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-r", str(OUTPUT_FPS)]
    cmd += [OUTPUT_FILE]
    return cmd


def main():
    print("=== gpt_result.json 로드 ===")
    with open("gpt_result.json", "r", encoding="utf-8") as f:
        gpt = json.load(f)

    emotion = FACE_EMOTION_OVERRIDE or gpt["emotion"]
    short_title = gpt["short_title"]
    print(f"emotion: {emotion}  short_title: {short_title}")

    with open("short_title.txt", "w", encoding="utf-8") as f:
        f.write(short_title)

    print("\n=== 에셋 준비 ===")
    font_path = get_font()
    mouth_gif = get_mouth_gif()

    print("\n=== FFmpeg 영상 합성 ===")
    cmd = build_cmd(mouth_gif, font_path)
    print("명령어:", " ".join(cmd[:10]), "...")

    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    stderr = result.stderr.decode("utf-8", errors="replace")

    if result.returncode != 0:
        print("[에러] FFmpeg 실패:")
        print(stderr[-3000:])
        return

    if os.path.exists(OUTPUT_FILE):
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        print(f"\n{OUTPUT_FILE} 생성 완료 ({size_mb:.1f}MB)")
    else:
        print("[에러] 출력 파일이 생성되지 않았습니다.")
        print(stderr[-2000:])


if __name__ == "__main__":
    main()
