"""롱폼 대본 정렬 자막 생성 (공용 분절 함수 사용).

[2026-06-29 재설계] 기존 duration 비례 슬라이스(단어 중간 절단) 폐기.
쇼츠 step7 과 동일한 검증된 경로로 전환:
  섹션별 anchor 정렬(글자↔Whisper 시각) → subtitle_segment.segment_script(목표 16자)
  → 조사·구두점 경계에서만 분절 → 단어 중간 절단 0건.

- 입력(원천): Whisper 원본 SRT. .whisper.bak 가 있으면 그것(재실행 시 pristine),
  없으면 현재 SRT 를 원천으로 보고 .bak 백업 후 덮어씀.
- 섹션 경계(long_chapters.json)로 Whisper 세그를 4섹션에 배정 → 섹션 내부만 정렬(드리프트 방지).
- 타이밍=Whisper / 글자=대본 100% (segment_script 가 대본 글자를 순서대로 누적).
- 무결성: 섹션별 재조립 텍스트 == 대본 발화문. 불일치 시 sys.exit(1) 하드스톱.
"""
import re, sys, json, shutil, os
sys.stdout.reconfigure(encoding="utf-8")

from subtitle_segment import (
    build_char_timing, align_script, segment_script, AlignmentError,
)

SRT = "long_subtitle.srt"
BAK = SRT + ".whisper.bak"
SCRIPT = "long_script.json"
CHAPTERS = "long_chapters.json"

# ── 분절 파라미터 (롱폼) ────────────────────────────────────
TARGET_CHARS = 16   # 목표 세그먼트 글자수 (가독 14~18 범위 중앙)
MAX_CHARS    = 21   # 절대 상한 (1920px / 90px 기준 한 줄 최대) — 초과 시 가장 가까운 경계 강제분절
MERGE_BELOW  = 3    # 이 글자수 이하 세그먼트는 인접에 병합 (≤3자 단독 제거)


def clean_spoken(text: str) -> str:
    """차트 태그·개행 제거 → 발화문만."""
    text = re.sub(r"===차트\[[^\]]*\]===", "", text)
    text = re.sub(r"===차트끝===", "", text)
    return text.replace("\n", "").replace("\r", "").strip()


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
    """원천 SRT 파싱 → [{text, start, end}] (Whisper 텍스트+타이밍 보존)."""
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

# ── 대본 섹션 로드 ──────────────────────────────────────────
d = json.load(open(SCRIPT, encoding="utf-8"))
sections = [
    ("intro",  clean_spoken(d["intro"]["script"])),
    ("issue1", clean_spoken(d["issues"][0]["script"])),
    ("issue2", clean_spoken(d["issues"][1]["script"])),
    ("outro",  clean_spoken(d["outro"]["script"])),
]
for k, t in sections:
    print(f"  대본 {k}: {len(t)}자")

# ── 섹션 시간 경계 ──────────────────────────────────────────
chaps = json.load(open(CHAPTERS, encoding="utf-8"))
starts = [c["time"] for c in chaps]
assert len(starts) == 4, f"챕터 4개 기대, {len(starts)}개"

# ── 원천 Whisper 세그 → 섹션 배정 ───────────────────────────
wsegs = parse_whisper_srt(source)
print(f"  Whisper 세그먼트: {len(wsegs)}개")
last_end = max(s["end"] for s in wsegs)
bounds = starts + [last_end + 1]
sec_wsegs = {k: [] for k, _ in sections}
for s in wsegs:
    for i, (k, _) in enumerate(sections):
        if bounds[i] <= s["start"] < bounds[i + 1]:
            sec_wsegs[k].append(s)
            break

# ── 섹션별 정렬 + 분절 ──────────────────────────────────────
out_segments = []
problems = []
for k, text in sections:
    ws = sec_wsegs[k]
    if not ws:
        problems.append(f"섹션 '{k}': 배정된 Whisper 세그 0개 — 정렬 불가")
        continue
    wt, time_at, seg_idx_at = build_char_timing(ws)
    try:
        anchor_map, anchor_seg, ratio = align_script(text, wt, time_at, seg_idx_at)
    except AlignmentError as e:
        problems.append(f"섹션 '{k}': 정렬 실패 — {e}")
        continue
    seg = segment_script(
        text, anchor_map, anchor_seg,
        target_chars=TARGET_CHARS, max_chars=MAX_CHARS, merge_below=MERGE_BELOW,
        protect_numbers=True, gap_clean_only=True,
    )
    print(f"  [{k}] 미매핑 {ratio:.1%} / 세그먼트 {len(seg)}개")
    # 무결성: 섹션 재조립 == 대본
    rebuilt = "".join(s["text"] for s in seg)
    if rebuilt != text:
        problems.append(f"섹션 '{k}': 재조립≠대본 ({len(rebuilt)} vs {len(text)})")
        continue
    out_segments.extend(seg)

if problems:
    print("\n[정렬/무결성 실패 — 보고]")
    for p in problems:
        print("  " + p)
    sys.exit(1)

print(f"  무결성 OK — 모든 섹션 재조립 == 대본 / 총 {len(out_segments)} 세그먼트")

# ── 새 SRT 작성 ─────────────────────────────────────────────
lines = []
for i, s in enumerate(out_segments, 1):
    lines.append(str(i))
    lines.append(f"{sec2tc(s['start'])} --> {sec2tc(s['end'])}")
    lines.append(s["text"])
    lines.append("")
open(SRT, "w", encoding="utf-8").write("\n".join(lines))
print(f"\n새 SRT 저장: {SRT} ({len(out_segments)} 세그먼트)")
