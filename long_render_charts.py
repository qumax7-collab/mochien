"""
롱폼 차트 클립 렌더 스크립트

long_chart_timestamps.json에서 필요한 차트 항목 목록을 추출 →
make_chart_json_from_item으로 데이터 fetch → Remotion NavyDark 렌더 →
long_chart_{key}.mp4 생성.

사용법:
  python long_render_charts.py          ← long_chart_timestamps.json 사용
  python long_render_charts.py --dry    ← 렌더 없이 필요 항목 목록만 출력
"""
import sys
import os
import json
import re
import subprocess
import argparse

NPX = "npx.cmd" if sys.platform == "win32" else "npx"

sys.stdout.reconfigure(encoding="utf-8")

TIMESTAMPS_FILE = "long_chart_timestamps.json"
CHART_ITEM_MAP  = "chart_item_map.json"
REMOTION_DIR    = os.path.join(os.path.dirname(__file__), "remotion")
CHART_DATA_DIR  = os.path.join(REMOTION_DIR, "public", "chart_data")
CHART_OUT_DIR   = os.path.join(REMOTION_DIR, "out")

# chart_render_seconds: Remotion 렌더 고정 길이 (NavyDark = 150프레임 / 30fps = 5초)
CHART_RENDER_SECONDS = 5.0
CHART_FPS            = 30
CHART_FRAMES         = 150          # NAVY_DARK_FRAMES


# ── 항목명 정규화 ─────────────────────────────────────────────

def _normalize_item(item: str, item_map: dict) -> str:
    """
    chart_item_map.json에서 항목명 조회 (대소문자·vs 순서 무관).
    직접 일치 → vs 역순 → 없으면 None 반환.
    """
    if item in item_map:
        return item

    # vs 비교 역순 시도: "総合 vs 食料" → "食料 vs 総合"
    vs_pat = re.compile(r'^(.+?)\s+vs\s+(.+)$', re.IGNORECASE)
    m = vs_pat.match(item)
    if m:
        reversed_key = f"{m.group(2).strip()} vs {m.group(1).strip()}"
        if reversed_key in item_map:
            return reversed_key

    return None


# ── list 블록 수집 ────────────────────────────────────────────

def _list_key(section: str, idx: int) -> str:
    return f"list_{section}_{idx}"


def collect_list_blocks(timestamps: dict) -> list:
    """
    long_chart_timestamps.json에서 type=="list"인 블록을 개별 수집.
    dedup 없음 — 내용이 매번 다름.
    points가 3개가 아니면 sys.exit(1).
    반환: [(section_key, block_index_in_ts, block, generated_key), ...]
    """
    result = []
    for section_key, blocks in timestamps.items():
        list_idx = 0
        for ts_idx, block in enumerate(blocks):
            if block["type"] != "list":
                continue
            points = block["points"]
            if len(points) != 3:
                print(
                    f"[오류] list 블록 포인트가 3개여야 합니다.\n"
                    f"  섹션: {section_key}, title: '{block['title']}'\n"
                    f"  포인트 수: {len(points)}  값: {points}"
                )
                sys.exit(1)
            key = _list_key(section_key, list_idx)
            result.append((section_key, ts_idx, block, key))
            list_idx += 1
    return result


# ── list props 직접 생성 ──────────────────────────────────────

def build_list_props(title: str, points: list) -> dict:
    """fetch 없이 title·points를 그대로 Remotion props로 변환."""
    return {
        "chartData": {
            "type":        "list",
            "titleJa":     title,
            "unitLabel":   "",
            "labels":      [],
            "values":      [],
            "yTicks":      [],
            "latestValue": 0,
            "latestLabel": "",
            "yMin":        0,
            "yMax":        1,
            "title":       title,
            "points":      points,
        }
    }


# ── 필요 항목 수집 ────────────────────────────────────────────

def collect_needed_items(timestamps: dict, item_map: dict) -> list:
    """
    long_chart_timestamps.json에서 type=="chart"인 항목을 중복 제거해 반환.
    (key: 정규화된 항목명, value: item_map 항목)
    미등록 항목 발견 시 sys.exit(1) — 폴백 없이 중단.
    """
    seen = {}

    for section_key, blocks in timestamps.items():
        for block in blocks:
            if block["type"] != "chart":
                continue
            raw_item = block["item"]
            norm = _normalize_item(raw_item, item_map)
            if norm is None:
                print(
                    f"[오류] '{raw_item}' → chart_item_map.json에 미등록 (섹션: {section_key}).\n"
                    f"  chart_item_map.json에 항목을 추가한 뒤 재실행하세요."
                )
                sys.exit(1)
            if norm not in seen:
                seen[norm] = item_map[norm]

    return list(seen.items())    # [(항목명, item_def), ...]


# ── 데이터 fetch + JSON 저장 ──────────────────────────────────

def fetch_and_save(item_name: str, item_def: dict, months: int = 24, step: int = 2) -> str:
    """
    make_chart_json_from_item으로 props JSON 생성 → chart_data/{key}.json 저장.
    반환: 저장된 JSON 파일의 chart_data/ 기준 상대 경로 (Remotion --props 용).
    """
    from data.make_chart_json import make_chart_json_from_item

    props = make_chart_json_from_item(item_name, months=months, step=step)

    os.makedirs(CHART_DATA_DIR, exist_ok=True)
    key      = item_def["key"]
    out_path = os.path.join(CHART_DATA_DIR, f"{key}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    return f"public/chart_data/{key}.json"


# ── Remotion 렌더 ─────────────────────────────────────────────

def render_chart(item_def: dict, props_rel: str) -> str:
    """
    npx remotion render NavyDark → long_chart_{key}.mp4
    반환: 생성된 mp4 절대 경로.
    """
    key      = item_def["key"]
    out_mp4  = os.path.join(CHART_OUT_DIR, f"{key}.mp4")

    cmd = [
        NPX, "remotion", "render",
        "NavyDark",
        out_mp4,
        "--props", props_rel,
    ]
    print(f"    npx remotion render NavyDark {key}.mp4")
    result = subprocess.run(cmd, cwd=REMOTION_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Remotion 렌더 실패 ({key}):\n{result.stderr[-2000:]}"
        )
    return out_mp4


# ── 타임스탬프 항목명 정규화 덮어쓰기 ────────────────────────

def normalize_timestamps(timestamps: dict, item_map: dict) -> dict:
    """
    timestamps 내 item 값을 정규화된 항목명으로 덮어씀
    (vs 역순 수정 등 / long4_ffmpeg.py가 일치 여부 비교할 때 쓸 수 있도록).
    """
    for blocks in timestamps.values():
        for block in blocks:
            if block["type"] == "chart":
                norm = _normalize_item(block["item"], item_map)
                if norm:
                    block["item"] = norm
    return timestamps


# ── 메인 ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="롱폼 차트 클립 렌더")
    parser.add_argument("--dry",    action="store_true", help="렌더 없이 필요 항목만 출력")
    parser.add_argument("--months", type=int, default=24, help="fetch 기간 월수 (기본 24)")
    parser.add_argument("--step",   type=int, default=2,  help="서브샘플 간격 (기본 2)")
    args = parser.parse_args()

    if not os.path.exists(TIMESTAMPS_FILE):
        print(f"[오류] {TIMESTAMPS_FILE} 없음. long2_tts.py를 먼저 실행하세요.")
        sys.exit(1)

    with open(TIMESTAMPS_FILE, encoding="utf-8") as f:
        timestamps = json.load(f)

    with open(CHART_ITEM_MAP, encoding="utf-8") as f:
        item_map = json.load(f)

    needed      = collect_needed_items(timestamps, item_map)
    list_blocks = collect_list_blocks(timestamps)

    print(f"\n=== 필요 차트 항목 ({len(needed)}개) ===")
    for item_name, item_def in needed:
        print(f"  {item_name}  ({item_def['type']})  → {item_def['key']}.mp4")
    if list_blocks:
        print(f"\n=== list 블록 ({len(list_blocks)}개) ===")
        for section_key, ts_idx, block, key in list_blocks:
            print(f"  [{section_key}] '{block['title']}'  → {key}.mp4")

    if args.dry:
        print("\n[--dry] 렌더 스킵")
        return

    # 타임스탬프 항목명 정규화 + list 블록 key 주입 후 재저장
    timestamps = normalize_timestamps(timestamps, item_map)
    for section_key, ts_idx, block, key in list_blocks:
        timestamps[section_key][ts_idx]["key"] = key
    with open(TIMESTAMPS_FILE, "w", encoding="utf-8") as f:
        json.dump(timestamps, f, ensure_ascii=False, indent=2)
    print(f"  타임스탬프 정규화 저장 → {TIMESTAMPS_FILE}")

    print(f"\n=== 차트 렌더 시작 ===")
    os.makedirs(CHART_OUT_DIR, exist_ok=True)

    rendered = []
    for item_name, item_def in needed:
        key = item_def["key"]
        print(f"\n  [{item_name}]")
        props_rel = fetch_and_save(item_name, item_def, args.months, args.step)
        mp4_path  = render_chart(item_def, props_rel)
        rendered.append(mp4_path)
        print(f"    → {mp4_path}")

    for section_key, ts_idx, block, key in list_blocks:
        print(f"\n  [list] '{block['title']}' ({key})")
        props      = build_list_props(block["title"], block["points"])
        props_path = os.path.join(CHART_DATA_DIR, f"{key}.json")
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f, ensure_ascii=False, indent=2)
        props_rel = f"public/chart_data/{key}.json"
        mp4_path  = render_chart({"key": key}, props_rel)
        rendered.append(mp4_path)
        print(f"    → {mp4_path}")

    print(f"\n=== 완료: {len(rendered)}개 클립 생성 ===")
    for p in rendered:
        size_mb = os.path.getsize(p) / (1024 * 1024)
        print(f"  {os.path.basename(p)}  {size_mb:.1f}MB")


if __name__ == "__main__":
    main()
