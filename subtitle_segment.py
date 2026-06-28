"""자막 분절 공용 규칙 (쇼츠 step7 · 롱폼 _align 공유).

[설계 근거 — 2026-06-29 진단]
- step7의 검증된 분절기 group_script_by_timing()은 글자수 상한 없이
  조사·구두점·갭 경계에서만 끊는다 → 단어 중간 절단이 구조적으로 없다.
- 단 모든 조사에서 끊어 평균 ~5자(쇼츠). 롱폼은 더 긴 세그먼트(목표 16자)가 필요.
- step7의 MIN_PARTICLE_FLUSH_LEN(=3)이 사실상 "목표 글자수 누적 게이트"다.
  이 상수를 target_chars 파라미터로 일반화하면:
    · 쇼츠: target_chars=3  → 현행 동작 100% 재현 (회귀 테스트로 보장)
    · 롱폼: target_chars=16 → 목표 도달 후 가장 가까운 조사 경계에서 끊음
- max_chars(상한 강제분절)·merge_below(하한 병합)는 롱폼 전용.
  쇼츠는 max_chars=None·merge_below=0 → 해당 코드 경로 미진입 → 출력 불변.

[금지선] 글자수로 단어 중간 강제 절단 금지. 끊는 위치는 100% 조사·구두점·갭.
         max_chars 상한도 '가장 가까운 경계'로 끊는다(경계 없을 때만 최후 강제).
"""

import json
import re

# ── 경계 규칙 상수 (step7 계승, 단일 출처) ──────────────────────
# 의미 경계 조사 12종 (や·か 제외 — 형용사 어간 오매칭 방지)
PARTICLES = frozenset("はがをにへとのもでねよわ")
# 분절을 일으키는 구두점 (일본어 전용 / . , 는 소수점 오분절 방지로 제외)
PUNCT_FLUSH = ("。", "、", "！", "？", "!")
PUNCT_SET = frozenset("。、！？!")
GAP_THRESHOLD = 0.4  # 이 시간(초) 이상 공백이면 세그먼트 분리 (Whisper 세그 경계 한정)


def _seg(chars):
    """char 엔트리 리스트 [(char, time, seg_idx)] → 세그먼트 dict."""
    return {
        "text": "".join(e[0] for e in chars).strip(),
        "start": chars[0][1],
        "end": chars[-1][1],
    }


def segment_script(script_clean, anchor_map, anchor_seg, *,
                   target_chars, max_chars=None, merge_below=0,
                   gap_threshold=GAP_THRESHOLD, particles=PARTICLES,
                   protect_numbers=False, gap_clean_only=False):
    """스크립트 원문 + 글자별 타임코드(anchor_map) → 자막 세그먼트.

    경계: 조사(particles) · 구두점(PUNCT_FLUSH) · 갭(다른 Whisper 세그 + gap_threshold 초과).
    target_chars: 누적 텍스트가 이보다 짧으면 조사 경계를 만나도 끊지 않음(누적 계속).
    max_chars: (옵션) 경계 없이 이 길이 도달 시 가장 가까운 경계로 강제 분절.
    merge_below: (옵션) 이 글자수 이하 세그먼트를 인접 세그먼트에 병합.
    protect_numbers: (롱폼) 숫자 토큰(2026年1月·3,700円 등) 중간 갭 분절 금지.
    gap_clean_only: (롱폼) 갭 분절을 조사·구두점 경계에서만 허용 — 보간 구간 의사 갭이
        단어 중간(支|える·動|き)에 떨어지는 것 차단. 비경계 갭은 다음 경계로 연기.

    쇼츠는 두 가드 모두 기본값(off) → step7 현행 동작 100% 재현.
    텍스트는 script_clean 글자를 순서대로 누적 → 재조립 시 100% 원본 보존.
    """
    NUM_DIGITS = set("0123456789")
    NUM_EXT    = set(".,，%年月日円兆億万千")  # 숫자에 결합하는 단위·구분자

    def mid_number(prev, nxt):
        return (prev in NUM_DIGITS or prev in "，,") and (nxt in NUM_DIGITS or nxt in NUM_EXT)

    segments = []
    cur = []          # [(char, time, seg_idx)]
    cur_seg = None    # 마지막 non-None Whisper 세그 인덱스
    # 강제분절 임계는 상한−1: 종결 구두점(。、) 1자리를 남겨 외톨이 구두점 cue 방지.
    # absorb/merge 는 max_chars(상한)까지 허용 → 본문 ≤상한−1 + 종결구두점 = ≤상한.
    force_at = (max_chars - 1) if max_chars else None

    for i, c in enumerate(script_clean):
        t = anchor_map[i]
        s = anchor_seg[i]
        ct = "".join(e[0] for e in cur)

        # 갭: 다른 Whisper 세그로 넘어갈 때만 (보간 위치 s=None은 갭 감지 안 함)
        gap_detected = (
            bool(cur) and cur_seg is not None and s is not None and
            s != cur_seg and t - cur[-1][1] > gap_threshold
        )
        # 롱폼 갭 가드: 숫자 토큰 중간 / 비경계 위치의 갭 분절 억제
        if gap_detected and ct:
            if protect_numbers and mid_number(ct[-1], c):
                gap_detected = False
            elif gap_clean_only and not (ct.rstrip().endswith(PUNCT_FLUSH) or ct[-1] in particles):
                gap_detected = False
        has_punct    = ct.rstrip().endswith(PUNCT_FLUSH)
        has_particle = bool(ct) and ct[-1] in particles

        # 조사 분절 억제 (gap·punct는 항상 분절)
        if has_particle and not gap_detected and not has_punct:
            # ①がる/がり: 上がる·値上がり 동사 어간 속 が 보호
            if ct[-1] == 'が' and c in 'りる':
                has_particle = False
            # ②のか: 문말 「〜のか」 분리 억제
            elif ct[-1] == 'の' and c == 'か':
                has_particle = False
            # ③목표 글자수 미달: 누적 계속 (쇼츠 target=3 = 기존 MIN_PARTICLE_FLUSH_LEN)
            elif len(ct) < target_chars:
                has_particle = False

        if (gap_detected or has_punct or has_particle) and cur:
            segments.append(_seg(cur))
            cur = []
            cur_seg = None

        cur.append((c, t, s))
        if s is not None:
            cur_seg = s

        # 상한 보호 (롱폼 전용 / 쇼츠 max_chars=None이면 미진입)
        if force_at and len(cur) >= force_at:
            split = None
            for j in range(len(cur) - 1, 0, -1):   # 가장 가까운 경계(우→좌)
                if cur[j][0] in particles or cur[j][0] in PUNCT_SET:
                    split = j + 1
                    break
            if not split:
                split = len(cur)                   # 경계 없음 → 최후 강제 분절
            segments.append(_seg(cur[:split]))
            cur = cur[split:]
            cur_seg = next((e[2] for e in reversed(cur) if e[2] is not None), None)

    if cur and "".join(e[0] for e in cur).strip():
        segments.append(_seg(cur))

    segments = absorb_lone_punct(segments, max_chars=max_chars)
    if merge_below > 0:
        segments = merge_short(segments, merge_below, max_chars=max_chars)
    return segments


class AlignmentError(Exception):
    """정렬 하드 실패 (유효 앵커 없음 / 타임코드 역전). 호출측이 처리."""


def build_char_timing(segments):
    """교정 세그먼트 → (wt, time_at[], seg_idx_at[]).
    세그먼트 내부는 start~end 선형 보간. (step7 build_wt_timing 과 동일 로직)"""
    wt = ""
    time_at = []
    seg_idx_at = []
    for si, seg in enumerate(segments):
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


def align_script(script_clean, wt, time_at, seg_idx_at, *, max_skip=15):
    """스크립트 글자를 wt에서 단조 greedy 탐색 → (anchor_map, anchor_seg, unmapped_ratio).
    미매핑 구간은 전후 앵커 선형 보간. (step7 build_anchor_map 알고리즘 동일)
    유효 앵커 없음·타임코드 역전 시 AlignmentError. 미매핑 비율은 호출측이 임계 판단."""
    n_s = len(script_clean)
    anchor_map = [None] * n_s
    anchor_seg = [None] * n_s
    p_w = 0

    for i, c in enumerate(script_clean):
        window = wt[p_w : p_w + max_skip]
        pos = window.find(c)
        if pos >= 0:
            matched = p_w + pos
            anchor_map[i] = time_at[matched]
            anchor_seg[i] = seg_idx_at[matched]
            p_w = matched + 1

    unmapped = sum(1 for a in anchor_map if a is None)
    ratio = unmapped / n_s if n_s else 0

    first_valid = next((i for i, a in enumerate(anchor_map) if a is not None), None)
    if first_valid is None:
        raise AlignmentError("유효 앵커 없음")
    for i in range(first_valid):
        anchor_map[i] = anchor_map[first_valid]

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

    for i in range(1, n_s):
        if anchor_map[i] < anchor_map[i - 1] - 0.01:
            raise AlignmentError(
                f"타임코드 역전 at [{i}]='{script_clean[i]}' "
                f"({anchor_map[i-1]:.3f}s → {anchor_map[i]:.3f}s)")

    return anchor_map, anchor_seg, ratio


def absorb_lone_punct(segments, max_chars=None):
    """구두점 단독 세그먼트(。、！？)를 직전 세그먼트에 흡수. 타임코드 변경 없음.
    max_chars 지정 시 흡수 결과가 상한 초과면 흡수하지 않음(상한 하드룰 우선)."""
    LONE = frozenset("。、！？")
    result = []
    for seg in segments:
        if (seg["text"] and all(c in LONE for c in seg["text"]) and result
                and (max_chars is None or len(result[-1]["text"]) + len(seg["text"]) <= max_chars)):
            result[-1]["text"] += seg["text"]
        else:
            result.append(seg)
    return result


def merge_short(segments, threshold, max_chars=None):
    """threshold 이하 글자수 세그먼트를 인접 세그먼트에 병합 (글자·순서 보존).
    원칙: 직전에 붙임. 선두 세그먼트가 짧으면 다음 세그먼트 앞에 붙임.
    단 max_chars 지정 시 병합 결과가 상한 초과면 병합하지 않음(상한이 하드룰 — 짧은 세그 잔존 허용)."""
    if not segments:
        return segments

    def fits(a, b):
        return max_chars is None or len(a) + len(b) <= max_chars

    out = []
    for seg in segments:
        seg = dict(seg)
        if out and len(seg["text"]) <= threshold and fits(out[-1]["text"], seg["text"]):
            out[-1]["text"] += seg["text"]
            out[-1]["end"] = seg["end"]
        else:
            out.append(seg)
    # 선두 잔여 짧음 → 다음으로 forward 병합 (상한 내에서만)
    if len(out) >= 2 and len(out[0]["text"]) <= threshold and fits(out[0]["text"], out[1]["text"]):
        out[1]["text"] = out[0]["text"] + out[1]["text"]
        out[1]["start"] = out[0]["start"]
        out = out[1:]
    return out


# ════════════════════════════════════════════════════════════════
# 롱폼 정렬+분절 (long5_whisper · _align_subtitle 공용 — 단일 출처)
# ════════════════════════════════════════════════════════════════
# 롱폼 분절 파라미터 기본값
LONGFORM_TARGET_CHARS = 16   # 목표 세그먼트 글자수 (가독 14~18 중앙)
LONGFORM_MAX_CHARS    = 21   # 절대 상한 (1920px / 90px 한 줄)
LONGFORM_MERGE_BELOW  = 3    # 이 글자수 이하 세그먼트 인접 병합


def clean_spoken(text: str) -> str:
    """차트 태그·개행 제거 → 발화문만 (롱폼 대본 정제)."""
    text = re.sub(r"===차트\[[^\]]*\]===", "", text)
    text = re.sub(r"===차트끝===", "", text)
    return text.replace("\n", "").replace("\r", "").strip()


def load_longform_sections(script_path: str):
    """long_script.json → [(섹션키, 발화문)] 4섹션 (intro/issue1/issue2/outro)."""
    d = json.load(open(script_path, encoding="utf-8"))
    return [
        ("intro",  clean_spoken(d["intro"]["script"])),
        ("issue1", clean_spoken(d["issues"][0]["script"])),
        ("issue2", clean_spoken(d["issues"][1]["script"])),
        ("outro",  clean_spoken(d["outro"]["script"])),
    ]


def load_chapter_starts(chapters_path: str):
    """long_chapters.json → 섹션 시작 시간 리스트 [0, 21, 132, 219]."""
    chaps = json.load(open(chapters_path, encoding="utf-8"))
    return [c["time"] for c in chaps]


def build_aligned_segments(whisper_segs, sections, section_starts, *,
                           target_chars=LONGFORM_TARGET_CHARS,
                           max_chars=LONGFORM_MAX_CHARS,
                           merge_below=LONGFORM_MERGE_BELOW,
                           protect_numbers=True, gap_clean_only=True):
    """Whisper 세그(텍스트+타이밍) + 대본 섹션 → 정렬·분절된 출력 세그먼트.

    섹션 경계로 Whisper 세그를 배정 → 섹션 내부만 anchor 정렬(드리프트 방지)
    → segment_script(목표/상한/병합). 타이밍=Whisper / 글자=대본 100%.
    반환 (out_segments, problems, stats). problems 비어있지 않으면 호출측이 처리(보통 sys.exit).
    long5_whisper(파이프라인)·_align_subtitle(수동) 공용 단일 출처.
    """
    if len(section_starts) != len(sections):
        return [], [f"섹션 수 불일치: 챕터 {len(section_starts)} vs 대본 {len(sections)}"], []
    if not whisper_segs:
        return [], ["Whisper 세그먼트 0개"], []

    last_end = max(s["end"] for s in whisper_segs)
    bounds = list(section_starts) + [last_end + 1]

    sec_ws = {k: [] for k, _ in sections}
    for s in whisper_segs:
        for i, (k, _) in enumerate(sections):
            if bounds[i] <= s["start"] < bounds[i + 1]:
                sec_ws[k].append(s)
                break

    out, problems = [], []
    stats = []
    for k, text in sections:
        ws = sec_ws[k]
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
            target_chars=target_chars, max_chars=max_chars, merge_below=merge_below,
            protect_numbers=protect_numbers, gap_clean_only=gap_clean_only,
        )
        rebuilt = "".join(s["text"] for s in seg)
        if rebuilt != text:
            problems.append(f"섹션 '{k}': 재조립≠대본 ({len(rebuilt)} vs {len(text)})")
            continue
        stats.append((k, ratio, len(seg)))
        out.extend(seg)

    return out, problems, stats
