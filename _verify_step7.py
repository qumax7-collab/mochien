"""
step7 의미단위 분절 검증 — 합성 타이밍으로 4문장 테스트
실제 Whisper 호출 없이 group_script_by_timing + _absorb_lone_punct + wrap_text 동작 확인.
타임스탬프는 기존 subtitle.srt에서 추출한 구간을 선형 분배.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from step7_whisper_subtitle import (
    group_script_by_timing,
    _absorb_lone_punct,
    wrap_text,
    build_srt,
)

# ------------------------------------------------------------------
# 4문장 + 기존 SRT에서 추출한 대략적 시간 구간
# seg_idx=문장번호 고정 → Whisper 갭 감지 없음 → 순수 조사/구두점 분절 테스트
# ------------------------------------------------------------------
SENTENCES = [
    # (라벨, 원문, t_start, t_end)
    ("①", "これがあなたの食費や生活費にどんな影響を与えるのか気になりませんか？", 4.699, 10.660),
    ("②", "物価が上がると食費の負担は増えますが、", 26.739, 29.739),
    ("③", "景気回復が緩やかで消費者需要が大幅に増えていないため、", 41.919, 48.860),
    ("④", "前年同月比で1.4%上昇しました。", 18.219, 21.819),
    # ★추가: が 동사 어간 케이스
    ("a", "食品が値上がりしています。", 55.000, 58.000),
    ("b", "株価が値下がりしました。", 60.000, 63.000),
]

def make_anchor(text, t_start, t_end, seg_idx):
    n = len(text)
    anchor_map = []
    anchor_seg = []
    for k in range(n):
        t = t_start + (k / max(n - 1, 1)) * (t_end - t_start)
        anchor_map.append(t)
        anchor_seg.append(seg_idx)  # 문장 내 전체 동일 seg_idx → gap 감지 없음
    return anchor_map, anchor_seg


def to_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def seg_to_srt_block(idx, seg):
    text = wrap_text(seg["text"], "\n")
    return (
        f"{idx}\n"
        f"{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}\n"
        f"{text}"
    )


# ------------------------------------------------------------------
# 실행
# ------------------------------------------------------------------
global_idx = 1
for label, script, t0, t1 in SENTENCES:
    anchor_map, anchor_seg = make_anchor(script, t0, t1, seg_idx=SENTENCES.index((label, script, t0, t1)))
    segs = group_script_by_timing(script, anchor_map, anchor_seg)
    segs = _absorb_lone_punct(segs)

    print(f"\n{'='*60}")
    print(f"{label}  원문: {script}")
    print(f"{'='*60}")
    for seg in segs:
        block = seg_to_srt_block(global_idx, seg)
        print(block)
        global_idx += 1
