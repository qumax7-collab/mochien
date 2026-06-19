"""SRT(교정 완료) → ASS 재생성 → FFmpeg 번인. Whisper API 불호출."""
import re, sys, subprocess
sys.stdout.reconfigure(encoding="utf-8")

SRT_FILE   = "long_subtitle.srt"
ASS_FILE   = "long_subtitle.ass"
INPUT_VID  = "long_output_no_sub.mp4"
OUTPUT_VID = "long_output.mp4"
FONT_NAME  = "Yu Gothic"
FONT_SIZE  = 90
OUTLINE_SIZE = 4

def _tc(tc):
    h, mn, rest = tc.split(":")
    s, ms = rest.split(",")
    return int(h)*3600 + int(mn)*60 + int(s) + int(ms)/1000

def parse_srt(path):
    segs = []
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    pat = re.compile(
        r"\d+\r?\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\r?\n"
        r"(.*?)(?=\r?\n\r?\n\d+\r?\n|\Z)", re.DOTALL)
    for m in pat.finditer(raw):
        text = re.sub(r"\{[^}]+\}", "", m.group(3)).strip().replace("\n", " ")
        segs.append({"start": _tc(m.group(1)), "end": _tc(m.group(2)), "text": text})
    return segs

def to_ass_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def build_ass(segs):
    header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,{OUTLINE_SIZE},0,2,40,40,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
    events = [
        f"Dialogue: 0,{to_ass_time(s['start'])},{to_ass_time(s['end'])},Default,,0,0,0,,{{\\an2}}{s['text']}"
        for s in segs
    ]
    return header + "\n" + "\n".join(events)

print("=== SRT → ASS 변환 ===")
segs = parse_srt(SRT_FILE)
print(f"  세그먼트 {len(segs)}개 로드")

# 연도 잔존 확인
import re as _re
bad = {y for s in segs for y in _re.findall(r"201[0-9]年", s["text"])}
if bad:
    print(f"  [경고] 구 연도 잔존: {sorted(bad)}")
else:
    print("  연도 검증 통과 (2015/2016 없음)")

ass_text = build_ass(segs)
with open(ASS_FILE, "w", encoding="utf-8") as f:
    f.write(ass_text)
print(f"  {ASS_FILE} 저장 완료")

print("\n=== FFmpeg 번인 ===")
vf = f"ass={ASS_FILE}"
cmd = [
    "ffmpeg", "-y",
    "-i", INPUT_VID,
    "-vf", vf,
    "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
    "-c:a", "copy",
    OUTPUT_VID,
]
result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
if result.returncode != 0:
    print("[에러]", result.stderr.decode("utf-8", errors="replace")[-500:])
    sys.exit(1)

import os
size_mb = os.path.getsize(OUTPUT_VID) / 1024 / 1024
print(f"{OUTPUT_VID} 생성 완료 ({size_mb:.1f}MB)")
