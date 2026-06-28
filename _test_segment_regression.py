"""쇼츠 회귀 테스트 (읽기 전용 검증).
NEW subtitle_segment.segment_script(target=3,max=None,merge=0) 가
OLD step7 group_script_by_timing + _absorb_lone_punct 와 바이트 동일한지 검증.

OLD 함수는 step7_whisper_subtitle.py 484-549행을 verbatim 복사(핀 사본).
동일 입력(script_clean, anchor_map, anchor_seg)에 대해 두 결과 dict 리스트를 비교.
1건이라도 불일치 시 FAIL 출력 + 사례 덤프.
"""
import sys, json, os, random
sys.stdout.reconfigure(encoding="utf-8")

from subtitle_segment import segment_script

# step7 모듈 상수와 동일 (핀 사본이 참조)
PARTICLES = frozenset("はがをにへとのもでねよわ")
MIN_PARTICLE_FLUSH_LEN = 3
GAP_THRESHOLD = 0.4


# ════════════════════════════════════════════════════════════════
# OLD 참조 구현 — step7_whisper_subtitle.py 484-549행 verbatim
# ════════════════════════════════════════════════════════════════
def OLD_group_script_by_timing(script_clean, anchor_map, anchor_seg):
    segments  = []
    cur_text  = ""
    cur_start = None
    cur_end   = None
    cur_seg   = None

    for i, c in enumerate(script_clean):
        t = anchor_map[i]
        s = anchor_seg[i]

        gap_detected = (
            cur_end is not None and
            cur_seg is not None and s is not None and
            s != cur_seg and
            t - cur_end > GAP_THRESHOLD
        )
        has_punct    = cur_text.rstrip().endswith(("。", "、", "！", "？", "!"))
        has_particle = bool(cur_text) and cur_text[-1] in PARTICLES

        if has_particle and not gap_detected and not has_punct:
            if cur_text[-1] == 'が' and c in 'りる':
                has_particle = False
            elif cur_text[-1] == 'の' and c == 'か':
                has_particle = False
            elif len(cur_text) < MIN_PARTICLE_FLUSH_LEN:
                has_particle = False

        if (gap_detected or has_punct or has_particle) and cur_text:
            segments.append({"text": cur_text.strip(), "start": cur_start, "end": cur_end})
            cur_text  = ""
            cur_start = None
            cur_end   = None
            cur_seg   = None

        cur_text += c
        if cur_start is None:
            cur_start = t
        cur_end = t
        if s is not None:
            cur_seg = s

    if cur_text.strip():
        segments.append({"text": cur_text.strip(), "start": cur_start, "end": cur_end})

    return segments


def OLD_absorb_lone_punct(segments):
    LONE = frozenset("。、！？")
    result = []
    for seg in segments:
        if seg["text"] and all(c in LONE for c in seg["text"]) and result:
            result[-1]["text"] += seg["text"]
        else:
            result.append(seg)
    return result


def old_pipeline(script_clean, anchor_map, anchor_seg):
    segs = OLD_group_script_by_timing(script_clean, anchor_map, anchor_seg)
    return OLD_absorb_lone_punct(segs)


def new_pipeline(script_clean, anchor_map, anchor_seg):
    # 쇼츠 파라미터: target=3(=MIN_PARTICLE_FLUSH_LEN), 상한·병합 없음
    return segment_script(script_clean, anchor_map, anchor_seg,
                          target_chars=MIN_PARTICLE_FLUSH_LEN,
                          max_chars=None, merge_below=0,
                          gap_threshold=GAP_THRESHOLD)


# ════════════════════════════════════════════════════════════════
# 입력 합성: script → (anchor_map 단조증가, anchor_seg 패턴)
# ════════════════════════════════════════════════════════════════
def synth_inputs(script, rng):
    n = len(script)
    anchor_map = []
    t = 0.0
    seg = 0
    anchor_seg = []
    for i in range(n):
        # 단조증가 시간: 대부분 0.05~0.4, 가끔 큰 갭(>0.4) 삽입
        step = rng.choice([0.05, 0.1, 0.2, 0.3, 0.45, 0.6, 0.9])
        t += step
        anchor_map.append(round(t, 3))
        # Whisper 세그 인덱스: 가끔 증가, 가끔 None(보간)
        r = rng.random()
        if r < 0.12:
            seg += 1
        if r < 0.08:
            anchor_seg.append(None)   # 보간 위치
        else:
            anchor_seg.append(seg)
    return anchor_map, anchor_seg


def cmp_segments(a, b):
    if len(a) != len(b):
        return f"세그먼트 수 불일치 {len(a)} vs {len(b)}"
    for k, (x, y) in enumerate(zip(a, b)):
        if x["text"] != y["text"]:
            return f"seg{k} text 불일치: '{x['text']}' vs '{y['text']}'"
        if abs(x["start"] - y["start"]) > 1e-9:
            return f"seg{k} start 불일치: {x['start']} vs {y['start']}"
        if abs(x["end"] - y["end"]) > 1e-9:
            return f"seg{k} end 불일치: {x['end']} vs {y['end']}"
    return None


def load_real_scripts():
    cases = {}
    # 롱폼 대본
    if os.path.exists("long_script.json"):
        try:
            import re
            d = json.load(open("long_script.json", encoding="utf-8"))
            def clean(t):
                t = re.sub(r"===차트\[[^\]]*\]===", "", t)
                t = re.sub(r"===차트끝===", "", t)
                return t.replace("\n", "").replace("\r", "").strip()
            parts = [clean(d.get("intro", {}).get("script", ""))]
            for iss in d.get("issues", []):
                parts.append(clean(iss.get("script", "")))
            parts.append(clean(d.get("outro", {}).get("script", "")))
            cases["longform"] = "".join(parts)
        except Exception as e:
            print(f"  (long_script.json 로드 실패: {e})")
    # 쇼츠 대본
    if os.path.exists("gpt_result.json"):
        try:
            import re
            g = json.load(open("gpt_result.json", encoding="utf-8"))
            strip = lambda t: re.sub(r'[（(][^）)]*[）)]', '', t)
            hook = strip(g.get("hook", ""))
            scr = strip(g.get("script", ""))
            combined = (hook + scr).replace("　", "").strip()
            if combined:
                cases["shorts"] = combined
        except Exception as e:
            print(f"  (gpt_result.json 로드 실패: {e})")
    return cases


# 핸드크래프트 엣지케이스 (억제 규칙·구두점·갭 직격)
HANDCRAFTED = [
    "株価が上がる。",                 # がる 보호
    "値上がりが続く。",               # がり 보호
    "どうなのか分からない。",         # のか 억제
    "はがを。、！？",                 # 구두점·조사 연속
    "あ",                             # 1자
    "経済はとても複雑な仕組みです。", # 일반 문장
    "貿易収支は赤字でも経常収支は黒字。",  # 긴 문장
    "を",                             # 단독 조사
    "。",                             # 단독 구두점
    "ねよわでにへ",                   # 종결조사 연속
]


def run():
    rng = random.Random(20260629)
    total = 0
    fails = []

    def check(label, script, amap, aseg):
        nonlocal total
        total += 1
        diff = cmp_segments(old_pipeline(script, amap, aseg),
                            new_pipeline(script, amap, aseg))
        if diff:
            fails.append((label, script, diff))

    # 1) 핸드크래프트 (각 3가지 anchor_seg 패턴)
    for idx, sc in enumerate(HANDCRAFTED):
        for v in range(3):
            amap, aseg = synth_inputs(sc, rng)
            check(f"hand[{idx}]v{v}", sc, amap, aseg)

    # 2) 실제 대본
    for name, sc in load_real_scripts().items():
        for v in range(5):
            amap, aseg = synth_inputs(sc, rng)
            check(f"real[{name}]v{v}", sc, amap, aseg)
        print(f"  실제 대본 로드: {name} ({len(sc)}자)")

    # 3) 퍼즈 (랜덤 일본어 유사 문자열 500케이스)
    charset = list("はがをにへとのもでねよわかや。、！？あいうえおカキク経済貿易収支株価0123456789円年%上下りるのか")
    for f in range(500):
        length = rng.randint(1, 80)
        sc = "".join(rng.choice(charset) for _ in range(length))
        amap, aseg = synth_inputs(sc, rng)
        check(f"fuzz[{f}]", sc, amap, aseg)

    print(f"\n총 {total}케이스 검증")
    if fails:
        print(f"❌ FAIL {len(fails)}건 — 쇼츠 동작 변경됨. 통합 부적합. 중단.")
        for label, sc, diff in fails[:10]:
            print(f"  [{label}] {diff}")
            print(f"     입력: '{sc[:60]}'")
        sys.exit(1)
    print("✅ PASS — 모든 케이스에서 OLD == NEW. 쇼츠 출력 100% 동일.")


if __name__ == "__main__":
    run()
