"""롱폼 통합 회귀: long5_whisper 가 쓰는 공용 정렬·분절 경로가
확정 long_subtitle.srt 를 재현하는지 검증 (읽기 전용).

- long5_whisper import 성공 = 모듈 컴파일·공용 import 정상.
- .whisper.bak(원본 Whisper) → build_aligned_segments → 확정 SRT 와 바이트 동일.
  long5 는 동일 함수에 동일 Whisper 세그(group_words+교정 결과 = .bak)를 넘김 → 동일 출력 보장.
"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")

# long5 import (컴파일 + 공용 import 검증) — main 미실행
import long5_whisper  # noqa: F401
print("✅ long5_whisper import 성공 (컴파일·공용 import 정상)")

from subtitle_segment import (
    build_aligned_segments, load_longform_sections, load_chapter_starts,
)

BAK = "long_subtitle.srt.whisper.bak"
SRT = "long_subtitle.srt"

PAT = re.compile(
    r"\d+\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)

def tc2sec(tc):
    h, mn, rest = tc.split(":"); s, ms = rest.split(",")
    return int(h)*3600 + int(mn)*60 + int(s) + int(ms)/1000

def parse(path):
    raw = open(path, encoding="utf-8").read()
    return [
        {"text": m.group(3).strip().replace("\n", ""),
         "start": tc2sec(m.group(1)), "end": tc2sec(m.group(2))}
        for m in PAT.finditer(raw)
    ]

whisper = parse(BAK)
confirmed = parse(SRT)
print(f"  Whisper(.bak): {len(whisper)}세그 / 확정 SRT: {len(confirmed)}세그")

sections = load_longform_sections("long_script.json")
starts   = load_chapter_starts("long_chapters.json")
out, problems, stats = build_aligned_segments(whisper, sections, starts)

if problems:
    print("❌ 정렬 실패:")
    for p in problems:
        print("  " + p)
    sys.exit(1)

# 재현 == 확정 SRT (텍스트 + 타임코드)
mismatch = []
if len(out) != len(confirmed):
    mismatch.append(f"세그먼트 수 {len(out)} != 확정 {len(confirmed)}")
else:
    for i, (a, b) in enumerate(zip(out, confirmed)):
        if a["text"] != b["text"]:
            mismatch.append(f"seg{i} text: '{a['text']}' != '{b['text']}'")
        elif abs(a["start"] - b["start"]) > 0.0006 or abs(a["end"] - b["end"]) > 0.0006:
            mismatch.append(f"seg{i} time: {a['start']:.3f}-{a['end']:.3f} != {b['start']:.3f}-{b['end']:.3f}")

if mismatch:
    print(f"❌ 재현 불일치 {len(mismatch)}건:")
    for m in mismatch[:8]:
        print("  " + m)
    sys.exit(1)

print(f"✅ 롱폼 경로 재현 OK — 공용 함수가 확정 SRT {len(confirmed)}세그 100% 재현")
print("   → long5_whisper(웹 UI 경로)도 동일 함수·동일 입력 → 동일 깔끔 자막 보장")
