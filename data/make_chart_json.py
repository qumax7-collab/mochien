"""
차트용 JSON 생성 스크립트 — topic_bank.json의 primary data_source를 fetch해
Remotion --props 형식 JSON으로 변환·저장.

사용법:
  python data/make_chart_json.py yen-rate
  python data/make_chart_json.py yen-rate --months 48
  python data/make_chart_json.py yen-rate --step 2   # 2개월 간격 (기본 3 = 분기)
"""
import sys
import os
import json
import math
import argparse

# 프로젝트 루트를 sys.path에 추가 (실행 위치 불문)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from data.boj_fetch import fetch_series as boj_fetch_series   # noqa: E402

TOPIC_BANK = os.path.join(_ROOT, "topic_bank.json")
OUTPUT_DIR = os.path.join(_ROOT, "remotion", "public", "chart_data")

# 차트 표시용 단축 제목 (topic_bank title_ja는 길어서 별도 관리)
CHART_TITLE_JA = {
    "yen-rate": "円安の推移",
}

# 표시용 단위 오버라이드 (BOJ 원문 "￥／＄" 등을 시청자용 단위로 교체)
CHART_UNIT_LABEL = {
    "yen-rate": "円",
}


# ── 유틸리티 ──────────────────────────────────────────────
def _to_label(ym: str) -> str:
    """'YYYY-MM' → \"'YY/M\" (예: '2023-01' → \"'23/1\")"""
    year, month = ym.split("-")
    return f"'{year[2:]}/{int(month)}"


def _yrange(values: list) -> tuple:
    """Y_MIN/Y_MAX: ±5 마진 후 10단위 내림/올림
    범위 20 이하면 5단위. fetch 실패 시 조용히 처리하지 않고 호출측에서 검사할 것.
    """
    min_v, max_v = min(values), max(values)
    span = max_v - min_v
    unit = 5 if span <= 20 else 10
    y_min = int(math.floor((min_v - 5) / unit)) * unit
    y_max = int(math.ceil((max_v + 5) / unit)) * unit
    return y_min, y_max


def _yticks(y_min: int, y_max: int) -> list:
    """Y축 눈금 — 범위에 맞는 간격(5 or 10)으로 자동 계산"""
    span = y_max - y_min
    interval = 5 if span <= 30 else 10
    start = int(math.ceil(y_min / interval)) * interval
    end   = int(math.floor(y_max / interval)) * interval
    return list(range(start, end + 1, interval))


def _resample_monthly(observations: list) -> dict:
    """일별 observations → {YYYY-MM: 월말 마지막 거래일 값} 딕셔너리"""
    monthly: dict = {}
    for obs in observations:
        ym = obs["date"][:7]        # YYYY-MM
        monthly[ym] = obs["value"]  # 후기 값으로 덮어씀 → 월말 최종값
    return monthly


# ── 메인 처리 ──────────────────────────────────────────────
def make_chart_json(topic_id: str, months: int = 36, step: int = 3) -> dict:
    """
    topic_id 의 primary data_source 를 fetch 해 Remotion props 형식 dict 반환.
    step: 월별 리샘플 후 서브샘플 간격 (3 = 분기마다 1포인트).
    fetch 실패·데이터 없음 시 에러 출력 + sys.exit(1). 더미값 대체 금지.
    """
    # 1. topic_bank.json 에서 primary source 읽기
    with open(TOPIC_BANK, encoding="utf-8") as f:
        bank = json.load(f)
    topic_list = bank.get("topics", [])

    topic = next((t for t in topic_list if t.get("id") == topic_id), None)
    if topic is None:
        print(f"[오류] topic_id '{topic_id}'를 topic_bank.json에서 찾을 수 없습니다.")
        sys.exit(1)

    sources = topic.get("data_sources", [])
    primary = next((s for s in sources if s.get("primary")), None)
    if primary is None:
        print(f"[오류] '{topic_id}'에 primary=true data_source 가 없습니다.")
        sys.exit(1)

    # 2. fetch (BOJ のみ対応。fred/estat は次セッション追加)
    source_type = primary.get("source")
    if source_type == "boj":
        db, code = primary["db"], primary["code"]
        print(f"[fetch] BOJ {db}/{code} months={months} ...")
        result = boj_fetch_series(db, code, months=months)
    else:
        print(f"[오류] source='{source_type}'는 이번 세션 미구현 (BOJ만 대응).")
        sys.exit(1)

    observations = result.get("observations", [])
    if not observations:
        print("[오류] observations 가 비어있습니다. fetch 결과를 확인하세요.")
        sys.exit(1)

    # 3. 월별 리샘플 → step 간격 서브샘플
    monthly = _resample_monthly(observations)
    all_months = sorted(monthly.keys())

    sampled = all_months[::step]
    # 최신 달이 누락된 경우 추가
    if all_months[-1] not in sampled:
        sampled.append(all_months[-1])

    values = [monthly[m] for m in sampled]
    labels = [_to_label(m) for m in sampled]

    # 4. Y 범위·눈금
    y_min, y_max = _yrange(values)
    y_ticks = _yticks(y_min, y_max)

    # 5. 조립
    title_ja   = CHART_TITLE_JA.get(topic_id) or topic.get("title_ja", "")
    unit_label = CHART_UNIT_LABEL.get(topic_id) or result.get("unit", "円")
    chart_data = {
        "topicId":     topic_id,
        "titleJa":     title_ja,
        "unitLabel":   unit_label,
        "sourceLabel": primary.get("desc_ko", ""),
        "labels":      labels,
        "values":      values,
        "yTicks":      y_ticks,
        "latestValue": values[-1],
        "latestLabel": labels[-1],
        "yMin":        y_min,
        "yMax":        y_max,
    }
    return {"chartData": chart_data}


def main() -> None:
    parser = argparse.ArgumentParser(description="차트 JSON 생성 (Remotion --props 형식)")
    parser.add_argument("topic_id", help="topic_bank.json 의 id (예: yen-rate)")
    parser.add_argument("--months", type=int, default=36, help="fetch 기간 월수 (기본 36)")
    parser.add_argument("--step",   type=int, default=3,  help="서브샘플 간격 월수 (기본 3 = 분기)")
    args = parser.parse_args()

    props = make_chart_json(args.topic_id, args.months, args.step)
    cd = props["chartData"]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_id  = args.topic_id.replace("-", "_")
    out_path = os.path.join(OUTPUT_DIR, f"{safe_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False, indent=2)

    # 검수 표
    print()
    print("=" * 60)
    print(f"=== 차트 JSON 생성 완료 — {args.topic_id} ===")
    print("=" * 60)
    print(f"  포인트 수   : {len(cd['values'])}개")
    print(f"  최신값      : {cd['latestValue']} {cd['unitLabel']}")
    print(f"  최신 라벨   : {cd['latestLabel']}")
    print(f"  Y 범위      : {cd['yMin']} ~ {cd['yMax']}")
    print(f"  Y 틱        : {cd['yTicks']}")
    print(f"  첫 포인트   : {cd['labels'][0]} = {cd['values'][0]}")
    print(f"  저장 위치   : {out_path}")
    print("=" * 60)
    rel = os.path.join("public", "chart_data", f"{safe_id}.json")
    print(f"\n▶ 렌더 명령어 (C:\\mochien\\remotion 에서):")
    print(f"  npx remotion render NavyDark out/yen_rate_real.mp4 --props {rel}")


if __name__ == "__main__":
    main()
