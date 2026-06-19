"""
2패스(구) vs 3패스(신) 테롭 매칭 전수 비교 — 조사 전용, 코드 변경 없음
"""
import re, json, os

TELOP_MIN_SEC = 2.5
TELOP_MAX_SEC = 6.0
SRT_FILE      = "long_subtitle.srt"
CHAPTERS_FILE = "long_chapters.json"
TIMESTAMPS_FILE = "long_chart_timestamps.json"

# ── SRT 파서 ───────────────────────────────────────────────
def _tc_to_sec(tc):
    h, mn, rest = tc.split(":")
    s, ms = rest.split(",")
    return int(h)*3600 + int(mn)*60 + int(s) + int(ms)/1000

def parse_srt(path):
    segs = []
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    pattern = re.compile(
        r"\d+\r?\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\r?\n"
        r"(.*?)(?=\r?\n\r?\n\d+\r?\n|\Z)", re.DOTALL)
    for m in pattern.finditer(raw):
        text = re.sub(r"\{[^}]+\}", "", m.group(3)).strip()
        segs.append({"start": _tc_to_sec(m.group(1)), "end": _tc_to_sec(m.group(2)), "text": text})
    return segs

# ── 토큰 헬퍼 ──────────────────────────────────────────────
def _bigrams(text):
    kanjis = re.findall(r"[一-龯々]", text)
    seen, r = set(), []
    for i in range(len(kanjis)-1):
        b = kanjis[i]+kanjis[i+1]
        if b not in seen:
            seen.add(b); r.append(b)
    return r

def _single_kanji_fallback(text):
    EXCLUDE = set("のはをがにでともかなもらてへ")
    return [c for c in re.findall(r"[一-龯]", text) if c not in EXCLUDE]

def _find_seg(toks, srt_segs, search_from):
    for seg in srt_segs:
        if seg["start"] < search_from - 0.01:
            continue
        for tok in toks:
            if tok in seg["text"]:
                return seg
    return None

# ── 구 2패스 매칭 ──────────────────────────────────────────
def find_old(text, srt_segs, search_from):
    kr   = re.findall(r"[一-龯々]{2,}", text)
    nums = re.findall(r"[0-9]{4}", text)
    kata = re.findall(r"[ァ-ヶ]{2,}", text)
    primary = list(dict.fromkeys(kr + nums + kata))
    seg = _find_seg(primary, srt_segs, search_from)
    if seg is None:
        seg = _find_seg(_bigrams(text), srt_segs, search_from)
    if seg is None:
        seg = _find_seg(_single_kanji_fallback(text), srt_segs, search_from)
    return seg

# ── 신 3패스 매칭 ──────────────────────────────────────────
def find_new(text, srt_segs, search_from):
    kr   = re.findall(r"[一-龯々]{2,}", text)
    nums = re.findall(r"[0-9]{4}", text)
    kata = re.findall(r"[ァ-ヶ]{2,}", text)
    long = [t for t in kr if len(t) >= 3]
    sht  = [t for t in kr if len(t) == 2]
    seg = (_find_seg(nums + long + kata, srt_segs, search_from) or
           _find_seg(sht, srt_segs, search_from) or
           _find_seg(_bigrams(text), srt_segs, search_from))
    return seg

# ── 오디오 길이 (ffprobe) ──────────────────────────────────
def audio_dur(path):
    import subprocess
    if not os.path.exists(path):
        return 30.0
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 30.0

# ── 표시 구간 계산 ─────────────────────────────────────────
def compute_display(telop_items_abs, section_abs, ts_list):
    """
    telop_items_abs: [(text, abs_start_sec or None), ...]
    ts_list: [{type,start,end}, ...] (section-relative)
    반환: [(text, video_start_abs, video_end_abs, dur, chunk_label), ...]
    """
    narr_blocks = [(i, ts) for i, ts in enumerate(ts_list) if ts["type"] == "narration"]
    # 먼저 chunk_dict 구성
    chunk_dict = {i: [] for i, _ in narr_blocks}
    for text, abs_s in telop_items_abs:
        if abs_s is None:
            continue
        sec_rel_s = abs_s - section_abs
        matched_chunk = None
        for ci, ts in narr_blocks:
            if ts["start"] <= sec_rel_s < ts["end"]:
                matched_chunk = (ci, ts); break
        if matched_chunk is None:
            for ci, ts in narr_blocks:
                if ts["end"] > sec_rel_s:
                    matched_chunk = (ci, ts); break
        if matched_chunk is None:
            matched_chunk = narr_blocks[-1]
        ci, ts = matched_chunk
        chunk_dur = ts["end"] - ts["start"]
        local_start = max(0.0, sec_rel_s - ts["start"])
        local_end   = min(chunk_dur, local_start + TELOP_MAX_SEC)
        if local_end - local_start < TELOP_MIN_SEC:
            local_end = min(chunk_dur, local_start + TELOP_MIN_SEC)
        chunk_dict[ci].append((text, local_start, local_end))

    # 2차: 다음 テロップ까지 표시 조정
    for ci in chunk_dict:
        items = chunk_dict[ci]
        if len(items) < 2:
            continue
        adj = []
        for k, (t, s, e) in enumerate(items):
            if k+1 < len(items):
                e = min(items[k+1][1], s + TELOP_MAX_SEC)
            adj.append((t, s, e))
        chunk_dict[ci] = adj

    # 절대 시각 변환
    result = []
    for ci, ts in narr_blocks:
        for (text, ls, le) in chunk_dict.get(ci, []):
            # 청크의 섹션 내 시작 시각 + local_start → 절대 시각
            video_s = section_abs + ts["start"] + ls
            video_e = section_abs + ts["start"] + le
            result.append((text, video_s, video_e, le - ls, f"narr_{ci}"))
    return result

# ── 메인 ───────────────────────────────────────────────────
srt_segs = parse_srt(SRT_FILE)
with open("brief_energy_dependency.json", encoding="utf-8") as f:
    brief = json.load(f)
with open(CHAPTERS_FILE, encoding="utf-8") as f:
    chapters = json.load(f)
with open(TIMESTAMPS_FILE, encoding="utf-8") as f:
    chart_timestamps = json.load(f)

section_abs = {
    "intro":  float(chapters[0]["time"]),
    "issue1": float(chapters[1]["time"]),
    "issue2": float(chapters[2]["time"]),
    "outro":  float(chapters[3]["time"]),
}

SEC_AUDIO = {
    "intro":  "long_voice_intro.mp3",
    "issue1": "long_voice_issue1.mp3",
    "issue2": "long_voice_issue2.mp3",
    "outro":  "long_voice_outro.mp3",
}

rows = []  # (sec, idx, text, old_abs, new_abs, changed, dur_old, dur_new)

for sec_key in ["intro", "issue1", "issue2", "outro"]:
    scr = brief.get(sec_key, {}).get("screen_text", [])
    if not scr:
        continue
    ts_list = chart_timestamps.get(sec_key, [])
    has_chart = any(t["type"] == "chart" for t in ts_list)
    sec_abs = section_abs[sec_key]

    if not ts_list or not (sec_key in ("issue1","issue2") and has_chart):
        dur = audio_dur(SEC_AUDIO[sec_key])
        ts_list = [{"type": "narration", "start": 0.0, "end": dur}]

    # 구 2패스 매칭
    old_abs_list, sf_old = [], sec_abs
    for txt in scr:
        seg = find_old(txt, srt_segs, sf_old)
        abs_s = seg["start"] if seg else None
        old_abs_list.append((txt, abs_s))
        if abs_s is not None:
            sf_old = abs_s + 0.05

    # 신 3패스 매칭
    new_abs_list, sf_new = [], sec_abs
    for txt in scr:
        seg = find_new(txt, srt_segs, sf_new)
        abs_s = seg["start"] if seg else None
        new_abs_list.append((txt, abs_s))
        if abs_s is not None:
            sf_new = abs_s + 0.05

    # 표시 구간 (절대 시각)
    old_display = {t: (vs, ve, d) for t, vs, ve, d, _ in compute_display(old_abs_list, sec_abs, ts_list)}
    new_display = {t: (vs, ve, d) for t, vs, ve, d, _ in compute_display(new_abs_list, sec_abs, ts_list)}

    for idx, txt in enumerate(scr):
        old_a = old_abs_list[idx][1]
        new_a = new_abs_list[idx][1]
        changed = (old_a != new_a)
        od = old_display.get(txt)
        nd = new_display.get(txt)
        rows.append((sec_key, idx+1, txt, old_a, new_a, changed, od, nd))

# ── 출력 ───────────────────────────────────────────────────
print("=" * 80)
print("테롭 매칭 전수 비교 — 2패스(구) vs 3패스(신)")
print("=" * 80)

changed_count = 0
for sec_key, idx, txt, old_a, new_a, changed, od, nd in rows:
    tag = "★변경" if changed else "  "
    old_s = f"{old_a:.2f}s" if old_a is not None else "FAIL"
    new_s = f"{new_a:.2f}s" if new_a is not None else "FAIL"
    dur_new = f"{nd[2]:.1f}s" if nd else "—"
    dur_old = f"{od[2]:.1f}s" if od else "—"

    # 비디오 표시 구간
    if nd:
        disp_rng = f"{nd[0]:.1f}~{nd[1]:.1f}s (dur {nd[2]:.1f}s)"
    else:
        disp_rng = "FAIL"

    print(f"\n[{sec_key}] #{idx:02d} {tag}")
    print(f"  문구  : {txt[:50]}")
    print(f"  구 매칭: {old_s}")
    print(f"  신 매칭: {new_s}")
    if changed:
        changed_count += 1
        direction = "개선" if (old_a is not None and new_a is not None and new_a > old_a) \
                    else ("회귀" if new_a is not None and old_a is not None and new_a < old_a else "변경")
        print(f"  → {direction} ({old_s} → {new_s})")
    print(f"  표시구간: {disp_rng}  (구 표시길이 {dur_old})")

print("\n" + "=" * 80)
print(f"총 {len(rows)}개 테롭 / 매칭 변경: {changed_count}개")

# ── 표시 길이 이상 항목 ────────────────────────────────────
print("\n── 표시 길이 점검 (신 기준) ──")
for sec_key, idx, txt, old_a, new_a, changed, od, nd in rows:
    if nd is None:
        print(f"  FAIL  [{sec_key}#{idx}] {txt[:40]}")
        continue
    dur = nd[2]
    flag = ""
    if dur < TELOP_MIN_SEC:
        flag = f"⚠ 짧음 ({dur:.1f}s < {TELOP_MIN_SEC}s)"
    elif dur >= TELOP_MAX_SEC - 0.05:
        flag = f"▲ 상한 ({dur:.1f}s ≈ {TELOP_MAX_SEC}s)"
    if flag:
        print(f"  {flag}  [{sec_key}#{idx}] {txt[:40]}")

print("\n── 완료 ──")
