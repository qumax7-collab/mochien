"""FRED fetch 모듈 — 코드 로직 + 출력 형태 검증 (모의 데이터)"""
import sys, json, datetime
sys.stdout.reconfigure(encoding="utf-8")

mock_data = {
    "series_id":    "DEXJPUS",
    "title":        "Japanese Yen to U.S. Dollar Spot Exchange Rate",
    "frequency":    "D",
    "units":        "Japanese Yen to One U.S. Dollar",
    "fetched_at":   datetime.date.today().isoformat(),
    "latest_date":  "2026-05-28",
    "latest_value": 144.08,
    "observations": [
        {"date": "2021-05-03", "value": 109.42},
        {"date": "2022-01-04", "value": 115.73},
        {"date": "2023-01-02", "value": 130.77},
        {"date": "2024-01-02", "value": 141.42},
        {"date": "2026-05-22", "value": 143.67},
        {"date": "2026-05-23", "value": 144.12},
        {"date": "2026-05-26", "value": 143.85},
        {"date": "2026-05-27", "value": 143.95},
        {"date": "2026-05-28", "value": 144.08},
    ]
}

# JSON 구조 출력
print("[JSON 구조 검증]")
print(json.dumps(mock_data, ensure_ascii=False, indent=2))

# 검수 표 (print_review_table 동일 로직)
data = mock_data
latest_5 = data["observations"][-5:]
print()
print("=" * 50)
print("=== FRED 검수 표 (모의 데이터) ===")
print("=" * 50)
print(f"series_id : {data['series_id']}")
print(f"title     : {data['title']}")
print(f"frequency : {data['frequency']}")
print(f"units     : {data['units']}")
print(f"fetched_at: {data['fetched_at']}")
print(f"최신값    : {data['latest_value']}  ({data['latest_date']})")
print("최신 5개  :")
for obs in latest_5:
    print(f"  {obs['date']}   {obs['value']}")
print(f"총 {len(data['observations']):,}개 observation")
print("=" * 50)
