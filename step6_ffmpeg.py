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

# ===== 비네팅 + 컬러 그레이딩 =====
VIGNETTE_ANGLE = 0.8  # 비네팅 강도 (0~PI/2)
CG_RS = -0.10         # 그림자 레드 감소
CG_RM = -0.05         # 중간 레드 감소
CG_RH = -0.03         # 하이라이트 레드 감소
CG_BS =  0.08         # 그림자 블루 증가
CG_BM =  0.05         # 중간 블루 증가
CG_BH =  0.03         # 하이라이트 블루 증가

FACE_H = 500
FACE_MARGIN_X = 30
FACE_MARGIN_Y = 100          # 하단 여백 증가 → 캐릭터 잘림 방지
FACE_EMOTION_OVERRIDE = "base"  # None으로 바꾸면 gpt_result.json의 emotion 자동 사용

# 입 GIF 오버레이 (face와 동일 크기, face 기준 오프셋)
MOUTH_OFFSET_X = 0
MOUTH_OFFSET_Y = -60         # face보다 60px 위 (올려서 맞춤)

BOW_GIF = "mochien_bow.gif"
BOW_DURATION = 1.5  # 인사 GIF 재생 시간 (초)

# 파일 경로
FONT_DIR = "fonts"
FONT_PATH = "fonts/NotoSansJP-Bold.ttf"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/static/NotoSansJP-Bold.ttf"
ASSETS_BASE = "https://raw.githubusercontent.com/qumax7-collab/mochien-assets/main"
OUTPUT_FILE = "output_no_sub.mp4"
TEMP_MAIN_FILE = "output_no_sub_temp.mp4"
TEMP_BOW_FILE  = "output_no_sub_bow.mp4"


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


def get_bow_gif():
    if os.path.exists(BOW_GIF):
        return BOW_GIF
    print(f"  {BOW_GIF} 없음 → 인사 애니메이션 생략")
    return None


def get_audio_duration(audio_file):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_file],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def ffmpeg_font_path(path):
    # FFmpeg filter 내 폰트 경로: 콜론 이스케이프, 슬래시 통일
    return path.replace("\\", "/").replace(":", "\\\\:")


def detect_speech_end(audio_file, silence_db=-30, min_silence=0.2):
    """trailing silence 직전 발화 종료 시점(초)을 반환. 없으면 None."""
    import re
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio_file],
        capture_output=True, text=True,
    )
    file_dur = float(dur.stdout.strip())

    detect = subprocess.run(
        ["ffmpeg", "-i", audio_file,
         "-af", f"silencedetect=n={silence_db}dB:d={min_silence}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    starts = list(map(float, re.findall(r"silence_start: ([0-9.]+)", detect.stderr)))
    ends   = list(map(float, re.findall(r"silence_end: ([0-9.]+)",   detect.stderr)))

    if starts and ends and abs(ends[-1] - file_dur) < 0.5:
        cut_t = starts[-1]
        print(f"  trailing silence 감지: {file_dur:.2f}s → {cut_t:.2f}s ({file_dur - cut_t:.2f}s 제거)")
        return cut_t
    # trailing silence 없음 — file_dur 반환으로 -t 항상 적용 (-shortest 단독 사용 시 무한루프 방지)
    print(f"  trailing silence 없음 → 전체 길이 {file_dur:.2f}s 사용")
    return file_dur


def build_filter(font_path, mouth_gif):
    mouth_x = OUTPUT_W - FACE_H - FACE_MARGIN_X + MOUTH_OFFSET_X
    mouth_y = OUTPUT_H - FACE_H - FACE_MARGIN_Y + MOUTH_OFFSET_Y

    fp = ffmpeg_font_path(font_path)
    title_y = f"({TOP_BAR_H}-text_h)/2"

    f = []
    f.append(
        f"[0:v]scale=-2:{OUTPUT_H},crop={OUTPUT_W}:{OUTPUT_H},setsar=1[bg_raw]"
    )
    f.append(
        f"[bg_raw]colorbalance=rs={CG_RS}:rm={CG_RM}:rh={CG_RH}:bs={CG_BS}:bm={CG_BM}:bh={CG_BH}[bg_graded]"
    )
    f.append(
        f"[bg_graded]vignette=angle={VIGNETTE_ANGLE}[bg]"
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
        audio_idx = 2
        f.append(f"[1:v]scale=-2:{FACE_H}[mouth]")
        f.append(f"[bg3][mouth]overlay=x={mouth_x}:y={mouth_y}[out]")
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


def build_cmd_bow_clip(bow_gif, font_path):
    """BOW_DURATION 짜리 bow.gif 전용 클립 생성 (t=0부터 재생, -t로 깔끔하게 자름)."""
    # build_filter에 bow_gif를 mouth_gif처럼 전달 — 배경 처리 로직 재사용
    filter_str, audio_idx = build_filter(font_path, bow_gif)

    cmd = ["ffmpeg", "-y"]
    cmd += ["-stream_loop", "-1", "-i", "background.mp4"]  # [0] 배경
    cmd += ["-ignore_loop", "0", "-i", bow_gif]              # [1] bow gif (GIF 자체 루프 설정 존중)
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]  # [2] 무음
    cmd += ["-filter_complex", filter_str]
    cmd += ["-map", "[out]", "-map", f"{audio_idx}:a"]
    cmd += ["-t", str(BOW_DURATION)]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-r", str(OUTPUT_FPS)]
    cmd += [TEMP_BOW_FILE]
    return cmd


def build_cmd_concat(main_file, bow_file):
    """두 H.264 클립을 단순 concat."""
    cmd = ["ffmpeg", "-y"]
    cmd += ["-i", main_file]
    cmd += ["-i", bow_file]
    cmd += ["-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]"]
    cmd += ["-map", "[v]", "-map", "[a]"]
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
    bow_gif = get_bow_gif()

    def run_ffmpeg(cmd, label):
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        stderr = result.stderr.decode("utf-8", errors="replace")
        if result.returncode != 0:
            print(f"[에러] {label} FFmpeg 실패:")
            print(stderr[-3000:])
            return False
        return True

    if bow_gif:
        # Pass 1 전: trailing silence 감지
        print("\n=== voice.mp3 trailing silence 감지 ===")
        speech_end = detect_speech_end("voice.mp3")

        # Pass 1: 본편 (talk.gif + 오디오, -shortest)
        print("\n=== FFmpeg Pass 1: 본편 영상 합성 ===")
        cmd1 = build_cmd(mouth_gif, font_path)
        cmd1[-1] = TEMP_MAIN_FILE
        if speech_end:
            # -t를 출력 파일 직전에 삽입 (output option)
            cmd1[-1:-1] = ["-t", str(speech_end)]
        print("명령어:", " ".join(cmd1[:8]), "...")
        if not run_ffmpeg(cmd1, "Pass 1"):
            return

        # Pass 2: bow 클립 단독 생성 (t=0부터 -t BOW_DURATION으로 깔끔하게 자름)
        print(f"\n=== FFmpeg Pass 2: 인사 클립 {BOW_DURATION}초 생성 ===")
        cmd2 = build_cmd_bow_clip(bow_gif, font_path)
        print("명령어:", " ".join(cmd2[:8]), "...")
        if not run_ffmpeg(cmd2, "Pass 2"):
            return

        # Pass 3: 두 클립 concat
        print("\n=== FFmpeg Pass 3: 본편 + 인사 concat ===")
        cmd3 = build_cmd_concat(TEMP_MAIN_FILE, TEMP_BOW_FILE)
        print("명령어:", " ".join(cmd3[:8]), "...")
        if not run_ffmpeg(cmd3, "Pass 3"):
            return

        for tmp in (TEMP_MAIN_FILE, TEMP_BOW_FILE):
            try:
                os.remove(tmp)
            except Exception:
                pass
    else:
        print("\n=== FFmpeg 영상 합성 ===")
        cmd = build_cmd(mouth_gif, font_path)
        print("명령어:", " ".join(cmd[:8]), "...")
        if not run_ffmpeg(cmd, "합성"):
            return

    if os.path.exists(OUTPUT_FILE):
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        print(f"\n{OUTPUT_FILE} 생성 완료 ({size_mb:.1f}MB)")
    else:
        print("[에러] 출력 파일이 생성되지 않았습니다.")


if __name__ == "__main__":
    main()
