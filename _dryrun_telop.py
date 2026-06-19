import re, json

def _tc_to_sec(tc):
    h, mn, rest = tc.split(":")
    s, ms = rest.split(",")
    return int(h)*3600 + int(mn)*60 + int(s) + int(ms)/1000

def parse_srt(path):
    segs = []
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    pattern = re.compile(
        r"\d+\r?\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\r?\n(.*?)(?=\r?\n\r?\n\d+\r?\n|\Z)",
        re.DOTALL
    )
    for m in pattern.finditer(raw):
        text = re.sub(r"\{[^}]+\}", "", m.group(3)).strip()
        segs.append({"start": _tc_to_sec(m.group(1)), "end": _tc_to_sec(m.group(2)), "text": text})
    return segs

def _telop_bigrams(text):
    kanjis = re.findall(r"[一-龯々]", text)
    seen, result = set(), []
    for i in range(len(kanjis)-1):
        b = kanjis[i]+kanjis[i+1]
        if b not in seen:
            seen.add(b)
            result.append(b)
    return result

def _single_kanji_fallback(text):
    EXCLUDE = set("のはをがにでともかなもらてへ")
    return [c for c in re.findall(r"[一-龯]", text) if c not in EXCLUDE]

def _find_seg_priority(text, segs, search_from):
    _kr   = re.findall(r"[一-龯々]{2,}", text)
    _nums = re.findall(r"[0-9]{4}", text)
    _kata = re.findall(r"[ァ-ヶ]{2,}", text)
    _long = [t for t in _kr if len(t) >= 3]
    _sht  = [t for t in _kr if len(t) == 2]

    def _find(toks):
        for seg in segs:
            if seg["start"] < search_from - 0.01:
                continue
            for tok in toks:
                if tok in seg["text"]:
                    return seg
        return None

    return (
        _find(_nums + _long + _kata) or
        _find(_sht) or
        _find(_telop_bigrams(text)) or
        _find(_single_kanji_fallback(text))  # 4패스: 단일 한자
    )

srt_segs = parse_srt("long_subtitle.srt")
with open("brief_energy_dependency.json", encoding="utf-8") as f:
    brief = json.load(f)
with open("long_chapters.json", encoding="utf-8") as f:
    chapters = json.load(f)

section_abs = {
    "intro":  float(chapters[0]["time"]),
    "issue1": float(chapters[1]["time"]),
    "issue2": float(chapters[2]["time"]),
    "outro":  float(chapters[3]["time"]),
}

for sec_key in ["intro", "issue1", "issue2", "outro"]:
    scr = brief.get(sec_key, {}).get("screen_text", [])
    if not scr:
        continue
    search_from = section_abs[sec_key]
    print(f"\n=== {sec_key} (abs {search_from:.1f}s) ===")
    for i, txt in enumerate(scr):
        seg = _find_seg_priority(txt, srt_segs, search_from)
        if seg:
            rel = seg["start"] - section_abs[sec_key]
            print(f"  テロップ {i+1}: abs {seg['start']:.2f}s (+{rel:.2f}s) | SRT '{seg['text'][:20]}' | テロップ [{txt[:35]}]")
            search_from = seg["start"] + 0.05
        else:
            print(f"  テロップ {i+1}: ❌ 매칭 실패 | テロップ [{txt[:35]}]")
