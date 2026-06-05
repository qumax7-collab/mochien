"""
KO 대본 토막 → scene list JSON 변환기
입력 형식(poc_input.txt):
  - 1줄 = 1슬라이드 문장
  - [keyword] 로 강조 단어 마킹 (표시 텍스트에서 브래킷 제거, keywords 배열 추출)
  - ===차트=== 로 차트 슬라이드 위치 지정 (1줄 단독)

사용법:
  python data/make_slide_json.py \\
    --input  data/poc_yen_rate.txt \\
    --chart  remotion/public/chart_data/yen_rate.json \\
    --output remotion/public/slides/issue1_poc.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

CHART_MARKER = "===차트==="
CHART_DURATION_SEC = 5.8
FPS = 30


def calc_duration(text: str) -> float:
    """Q1=B: 문장 길이 비례 (20자→3.0s, 40자→4.0s, 60자→5.0s), clamp [3.0, 6.0]"""
    n = len(text)
    if n <= 20:
        return 3.0
    sec = 3.0 + 0.05 * (n - 20)
    return round(min(max(sec, 3.0), 6.0), 2)


def parse_line(raw: str) -> tuple[str, list[str]]:
    """[keyword] → keywords 추출 + 브래킷 제거"""
    keywords: list[str] = re.findall(r'\[([^\]]+)\]', raw)
    text = re.sub(r'\[([^\]]+)\]', r'\1', raw).strip()
    return text, keywords


def validate(slides: list[dict], chart_marker_count: int) -> None:
    """검증: === 잔여 없음 + 차트 마커 수 == chart 슬라이드 수"""
    chart_slide_count = sum(1 for s in slides if s["type"] == "chart")
    if chart_marker_count != chart_slide_count:
        sys.exit(
            f"[ERROR] 차트 마커 수({chart_marker_count}) ≠ "
            f"chart 슬라이드 수({chart_slide_count})"
        )
    for s in slides:
        if s["type"] == "text" and "===" in s["text"]:
            sys.exit(f"[ERROR] 텍스트에 === 잔여: {s['text']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="KO 대본 → scene list JSON")
    ap.add_argument("--input",  required=True, help="입력 텍스트 파일")
    ap.add_argument("--chart",  required=True, help="차트 데이터 JSON (yen_rate.json)")
    ap.add_argument("--output", required=True, help="출력 scene list JSON")
    args = ap.parse_args()

    input_path  = Path(args.input)
    chart_path  = Path(args.chart)
    output_path = Path(args.output)

    if not input_path.exists():
        sys.exit(f"[ERROR] 입력 파일 없음: {input_path}")
    if not chart_path.exists():
        sys.exit(f"[ERROR] 차트 JSON 없음: {chart_path}")

    # 차트 데이터 로드 (chartData 래퍼 or 직접)
    chart_raw = json.loads(chart_path.read_text(encoding="utf-8"))
    chart_data = chart_raw.get("chartData", chart_raw)

    # 입력 파싱
    lines = input_path.read_text(encoding="utf-8").splitlines()
    slides: list[dict] = []
    chart_marker_count = 0

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line == CHART_MARKER:
            chart_marker_count += 1
            slides.append({
                "type":         "chart",
                "chart_data":   chart_data,
                "duration_sec": CHART_DURATION_SEC,
            })
        else:
            text, keywords = parse_line(line)
            if not text:
                continue
            slides.append({
                "type":         "text",
                "text":         text,
                "keywords":     keywords,
                "duration_sec": calc_duration(text),
            })

    validate(slides, chart_marker_count)

    total_frames = sum(round(s["duration_sec"] * FPS) for s in slides)
    out: dict = {
        "topic_id":     "yen-rate",
        "fps":          FPS,
        "total_frames": total_frames,
        "total_sec":    round(total_frames / FPS, 2),
        "slides":       slides,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 결과 출력
    print(f"[OK] {len(slides)}장 슬라이드 / {out['total_sec']}초 ({total_frames}프레임)")
    print(f"     출력: {output_path}")
    print()
    for i, s in enumerate(slides):
        if s["type"] == "text":
            preview = s["text"][:28] + ("..." if len(s["text"]) > 28 else "")
            kw = s["keywords"]
            print(f"  [{i+1:02d}] TEXT  {s['duration_sec']:4.2f}s  \"{preview}\"  kw={kw}")
        else:
            print(f"  [{i+1:02d}] CHART {s['duration_sec']:4.2f}s  (yen_rate 차트)")


if __name__ == "__main__":
    main()
