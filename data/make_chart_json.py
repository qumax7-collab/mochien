"""
차트용 JSON 생성 스크립트

사용법 A: topic_id 기반 (topic_bank.json primary source)
  python data/make_chart_json.py --topic yen-rate

사용법 B: 항목명 기반 (chart_item_map.json)
  python data/make_chart_json.py --item "食料 vs 総合"
  python data/make_chart_json.py --item "穀類" --months 24
"""
import sys
import os
import json
import math
import argparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from data.boj_fetch   import fetch_series as boj_fetch    # noqa: E402
from data.estat_fetch import fetch_series as estat_fetch  # noqa: E402
from data.fred_fetch  import fetch_series as fred_fetch   # noqa: E402

TOPIC_BANK     = os.path.join(_ROOT, "topic_bank.json")
CHART_ITEM_MAP = os.path.join(_ROOT, "chart_item_map.json")
OUTPUT_DIR     = os.path.join(_ROOT, "remotion", "public", "chart_data")

CHART_TITLE_JA = {"yen-rate": "円安の推移"}
CHART_UNIT_LABEL = {"yen-rate": "円"}


# ── 유틸리티 ──────────────────────────────────────────────────

def _to_label(ym: str) -> str:
    """'YYYY-MM' → \"'YY/M\""""
    year, month = ym.split("-")
    return f"'{year[2:]}/{int(month)}"


def _yrange(values: list) -> tuple:
    """±5 마진 후 5단위(범위≤20) 또는 10단위로 내림/올림."""
    min_v, max_v = min(values), max(values)
    span = max_v - min_v
    unit = 5 if span <= 20 else 10
    y_min = int(math.floor((min_v - 5) / unit)) * unit
    y_max = int(math.ceil((max_v + 5) / unit)) * unit
    return y_min, y_max


def _yticks(y_min: int, y_max: int) -> list:
    span = y_max - y_min
    interval = 5 if span <= 30 else (10 if span <= 80 else 20)
    start = int(math.ceil(y_min / interval)) * interval
    end   = int(math.floor(y_max / interval)) * interval
    return list(range(start, end + 1, interval))


def _resample_monthly(observations: list) -> dict:
    """일별 observations → {YYYY-MM: 월말 마지막 값} 딕셔너리."""
    monthly: dict = {}
    for obs in observations:
        ym = obs["date"][:7]
        monthly[ym] = obs["value"]
    return monthly


def _subsample(monthly: dict, step: int) -> list:
    """월 키 정렬 후 step 간격 서브샘플. 최신 월이 누락되면 추가."""
    all_months = sorted(monthly.keys())
    sampled = all_months[::step]
    if all_months[-1] not in sampled:
        sampled.append(all_months[-1])
    return sampled


# ── fetch 디스패치 ─────────────────────────────────────────────

def _fetch_one(src_def: dict, months: int) -> list:
    """source 정의 dict → observations 리스트. 실패 시 sys.exit."""
    src = src_def.get("source")
    if src == "boj":
        r = boj_fetch(src_def["db"], src_def["code"], months=months)
    elif src == "estat":
        r = estat_fetch(src_def["stats_data_id"],
                        filters=src_def.get("filters", {}),
                        months=months)
    elif src == "fred":
        r = fred_fetch(src_def["code"], months=months)
    else:
        print(f"[오류] 미지원 source: '{src}'")
        sys.exit(1)
    obs = r.get("observations", [])
    if not obs:
        print(f"[오류] fetch 결과 비어있음: {src_def}")
        sys.exit(1)
    return obs


# ── chart_item_map 기반 props 생성 ────────────────────────────

def _build_single(item_def: dict, months: int, step: int) -> dict:
    obs = _fetch_one(item_def["series"][0], months)
    monthly = _resample_monthly(obs)
    sampled = _subsample(monthly, step)
    values  = [monthly[m] for m in sampled]
    labels  = [_to_label(m) for m in sampled]
    y_min, y_max = _yrange(values)
    return {
        "chartData": {
            "type":        "single",
            "titleJa":     item_def["title_ja"],
            "unitLabel":   item_def["unit"],
            "labels":      labels,
            "values":      values,
            "yTicks":      _yticks(y_min, y_max),
            "latestValue": values[-1],
            "latestLabel": labels[-1],
            "yMin":        y_min,
            "yMax":        y_max,
        }
    }


def _build_compare(item_def: dict, months: int, step: int) -> dict:
    s1_def, s2_def = item_def["series"][0], item_def["series"][1]
    obs1 = _fetch_one(s1_def, months)
    obs2 = _fetch_one(s2_def, months)
    m1 = _resample_monthly(obs1)
    m2 = _resample_monthly(obs2)
    common  = sorted(set(m1) & set(m2))
    sampled = common[::step]
    if common[-1] not in sampled:
        sampled.append(common[-1])
    v1     = [m1[m] for m in sampled]
    v2     = [m2[m] for m in sampled]
    labels = [_to_label(m) for m in sampled]
    y_min, y_max = _yrange(v1 + v2)
    return {
        "chartData": {
            "type":      "compare",
            "titleJa":   item_def["title_ja"],
            "unitLabel": item_def["unit"],
            "labels":    labels,
            "series1": {
                "label":       s1_def["label"],
                "values":      v1,
                "latestValue": v1[-1],
                "latestLabel": labels[-1],
            },
            "series2": {
                "label":       s2_def["label"],
                "values":      v2,
                "latestValue": v2[-1],
                "latestLabel": labels[-1],
            },
            "yTicks": _yticks(y_min, y_max),
            "yMin":   y_min,
            "yMax":   y_max,
        }
    }


def _build_dual_item(item_def: dict, months: int, step: int) -> dict:
    """chart_item_map dual 항목 → 좌/우 독립 Y축 Remotion props."""
    s1_def, s2_def = item_def["series"][0], item_def["series"][1]
    obs1 = _fetch_one(s1_def, months)
    obs2 = _fetch_one(s2_def, months)
    m1   = _resample_monthly(obs1)
    m2   = _resample_monthly(obs2)

    # 두 시리즈의 공통 월만 사용 (1개월 시차 자동 처리)
    common  = sorted(set(m1) & set(m2))
    sampled = common[::step]
    if common[-1] not in sampled:
        sampled.append(common[-1])

    v1     = [m1[m] for m in sampled]
    v2     = [m2[m] for m in sampled]
    labels = [_to_label(m) for m in sampled]

    y_min1, y_max1 = _yrange(v1)
    y_min2, y_max2 = _yrange(v2)

    return {
        "chartData": {
            "type":       "dual",
            "titleJa":    item_def["title_ja"],
            "unitLabel":  item_def.get("unit",  "USD"),
            "unitLabel2": item_def.get("unit2", "%"),
            "labels":     labels,
            "yMin":   y_min1, "yMax":   y_max1, "yTicks":  _yticks(y_min1, y_max1),
            "yMin2":  y_min2, "yMax2":  y_max2, "yTicks2": _yticks(y_min2, y_max2),
            "series1": {
                "label":       s1_def.get("label", ""),
                "values":      v1,
                "latestValue": v1[-1],
                "latestLabel": labels[-1],
            },
            "series2": {
                "label":       s2_def.get("label", ""),
                "values":      v2,
                "latestValue": v2[-1],
                "latestLabel": labels[-1],
            },
        }
    }


def make_chart_json_from_item(item_name: str,
                               months: int = 24,
                               step: int = 2) -> dict:
    """
    chart_item_map.json 항목명 → Remotion props dict.
    파일 저장은 호출측(long_render_charts.py)에서 수행.
    """
    with open(CHART_ITEM_MAP, encoding="utf-8") as f:
        item_map = json.load(f)
    item_def = item_map.get(item_name)
    if not item_def:
        print(f"[오류] '{item_name}'을 chart_item_map.json에서 찾을 수 없습니다.")
        sys.exit(1)
    print(f"[fetch] {item_name} ({item_def['type']}) months={months} step={step}")
    if item_def["type"] == "single":
        return _build_single(item_def, months, step)
    elif item_def["type"] == "dual":
        return _build_dual_item(item_def, months, step)
    else:
        return _build_compare(item_def, months, step)


# ── topic_id 기반 (기존 yen-rate 호환) ───────────────────────

def make_chart_json(topic_id: str, months: int = 36, step: int = 3) -> dict:
    """topic_bank.json primary source → Remotion props dict (BOJ/FRED/e-Stat 지원)."""
    with open(TOPIC_BANK, encoding="utf-8") as f:
        bank = json.load(f)
    topic = next((t for t in bank.get("topics", []) if t.get("id") == topic_id), None)
    if topic is None:
        print(f"[오류] topic_id '{topic_id}'를 topic_bank.json에서 찾을 수 없습니다.")
        sys.exit(1)

    primary = next((s for s in topic.get("data_sources", []) if s.get("primary")), None)
    if primary is None:
        print(f"[오류] '{topic_id}'에 primary=true data_source가 없습니다.")
        sys.exit(1)

    print(f"[fetch] {topic_id} / {primary.get('source')} months={months}")
    obs = _fetch_one(primary, months)
    monthly = _resample_monthly(obs)
    sampled = _subsample(monthly, step)
    values  = [monthly[m] for m in sampled]
    labels  = [_to_label(m) for m in sampled]
    y_min, y_max = _yrange(values)

    title_ja   = CHART_TITLE_JA.get(topic_id) or topic.get("title_ja", "")
    unit_label = CHART_UNIT_LABEL.get(topic_id) or "%"
    return {
        "chartData": {
            "type":        "single",
            "topicId":     topic_id,
            "titleJa":     title_ja,
            "unitLabel":   unit_label,
            "labels":      labels,
            "values":      values,
            "yTicks":      _yticks(y_min, y_max),
            "latestValue": values[-1],
            "latestLabel": labels[-1],
            "yMin":        y_min,
            "yMax":        y_max,
        }
    }


# ── CLI ───────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="차트 JSON 생성 (Remotion --props 형식)")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topic", metavar="TOPIC_ID",
                     help="topic_bank.json ID (예: yen-rate)")
    grp.add_argument("--item",  metavar="ITEM_NAME",
                     help="chart_item_map.json 항목명 (예: '食料 vs 総合')")
    parser.add_argument("--months", type=int, default=None,
                        help="fetch 기간 월수 (--topic 기본 36, --item 기본 24)")
    parser.add_argument("--step",   type=int, default=None,
                        help="서브샘플 간격 (--topic 기본 3, --item 기본 2)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.topic:
        months = args.months or 36
        step   = args.step   or 3
        props  = make_chart_json(args.topic, months, step)
        safe   = args.topic.replace("-", "_")
    else:
        months = args.months or 24
        step   = args.step   or 2
        props  = make_chart_json_from_item(args.item, months, step)
        with open(CHART_ITEM_MAP, encoding="utf-8") as f:
            safe = json.load(f)[args.item]["key"]

    out_path = os.path.join(OUTPUT_DIR, f"{safe}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    cd = props["chartData"]
    print()
    print("=" * 60)
    print(f"=== 차트 JSON 완료 — {args.topic or args.item} ===")
    print("=" * 60)
    print(f"  타입        : {cd['type']}")
    if cd["type"] == "single":
        print(f"  포인트      : {len(cd['values'])}개")
        print(f"  최신값      : {cd['latestValue']} {cd['unitLabel']}")
        print(f"  Y 범위      : {cd['yMin']} ~ {cd['yMax']}")
    elif cd["type"] == "dual":
        print(f"  포인트      : {len(cd['labels'])}개")
        print(f"  {cd['series1']['label']} 최신: {cd['series1']['latestValue']} {cd['unitLabel']}  (좌축 {cd['yMin']}~{cd['yMax']})")
        print(f"  {cd['series2']['label']} 최신: {cd['series2']['latestValue']} {cd['unitLabel2']}  (우축 {cd['yMin2']}~{cd['yMax2']})")
    else:
        print(f"  포인트      : {len(cd['labels'])}개")
        print(f"  {cd['series1']['label']} 최신: {cd['series1']['latestValue']} {cd['unitLabel']}")
        print(f"  {cd['series2']['label']} 최신: {cd['series2']['latestValue']} {cd['unitLabel']}")
        print(f"  Y 범위      : {cd['yMin']} ~ {cd['yMax']}")
    print(f"  저장        : {out_path}")
    print("=" * 60)
    print(f"\n▶ 렌더 (remotion 폴더에서):")
    print(f"  npx remotion render NavyDark out/{safe}.mp4 --props public/chart_data/{safe}.json")


if __name__ == "__main__":
    main()
