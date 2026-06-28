"""롱폼 대본 정렬 자막 생성 (수동 재실행용 / 공용 함수 사용).

[2026-06-29] 핵심 정렬·분절 로직은 subtitle_segment.build_aligned_segments 로 통합.
이 스크립트는 .bak(원본 Whisper SRT)에서 수동 재생성할 때 쓰는 얇은 래퍼.
파이프라인(long5_whisper.py)도 동일 함수를 호출 → 결과 동일(단일 출처).

- 입력(원천): Whisper 원본 SRT. .whisper.bak 있으면 그것(pristine), 없으면 현재 SRT 백업 후 사용.
- 무결성: 섹션 재조립 == 대본. 불일치 시 sys.exit(1).
"""
import re, sys, shutil, os
sys.stdout.reconfigure(encoding="utf-8")

from subtitle_segment import (
    build_aligned_segments, load_longform_sections, load_chapter_starts,
)

SRT = "long_subtitle.srt"
BAK = SRT + ".whisper.bak"
SCRIPT = "long_script.json"
CHAPTERS = "long_chapters.json"


def tc2sec(tc):
    h, mn, rest = tc.split(":"); s, ms = rest.split(",")
    return int(h) * 3600 + int(mn) * 60 + int(s) + int(ms) / 1000


def sec2tc(sec):
    h = int(sec // 3600); m = int((sec % 3600) // 60)
    s = int(sec % 60);   ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        s += 1; ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_whisper_srt(path):
    """원천 SRT 파싱 → [{text, start, end}] (Whisper 텍스트+타이밍)."""
    raw = open(path, encoding="utf-8").read()
    pat = re.compile(
        r"\d+\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
        re.DOTALL,
    )
    segs = []
    for m in pat.finditer(raw):
        segs.append({
            "text": m.group(3).strip().replace("\n", ""),
            "start": tc2sec(m.group(1)),
            "end": tc2sec(m.group(2)),
        })
    return segs


# ── 원천 결정 + 백업 ────────────────────────────────────────
if os.path.exists(BAK):
    source = BAK
    print(f"  원천: {BAK} (pristine Whisper)")
else:
    source = SRT
    shutil.copy(SRT, BAK)
    print(f"  원천: {SRT} → 백업 {BAK} 생성")

sections = load_longform_sections(SCRIPT)
starts   = load_chapter_starts(CHAPTERS)
for k, t in sections:
    print(f"  대본 {k}: {len(t)}자")

wsegs = parse_whisper_srt(source)
print(f"  Whisper 세그먼트: {len(wsegs)}개")

out_segments, problems, stats = build_aligned_segments(wsegs, sections, starts)
for k, ratio, n in stats:
    print(f"  [{k}] 미매핑 {ratio:.1%} / 세그먼트 {n}개")

if problems:
    print("\n[정렬/무결성 실패 — 보고]")
    for p in problems:
        print("  " + p)
    sys.exit(1)

print(f"  무결성 OK — 모든 섹션 재조립 == 대본 / 총 {len(out_segments)} 세그먼트")

lines = []
for i, s in enumerate(out_segments, 1):
    lines.append(str(i))
    lines.append(f"{sec2tc(s['start'])} --> {sec2tc(s['end'])}")
    lines.append(s["text"])
    lines.append("")
open(SRT, "w", encoding="utf-8").write("\n".join(lines))
print(f"\n새 SRT 저장: {SRT} ({len(out_segments)} 세그먼트)")
