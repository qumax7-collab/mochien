"""
step8 thumb_headline 수치 검증 게이트 판정 테스트.
실제 gpt_result.json 사용 / Whisper·OpenAI Images API 호출 없음.
텔레그램은 Case A에서 실제 전송 (운영자 수신 확인용).
"""
import sys
import json
import copy

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from step8_thumbnail import validate_thumb_numerics, extract_num_tokens

with open("gpt_result.json", encoding="utf-8") as f:
    gpt = json.load(f)

print("=" * 60)
print(f"원본 thumb_headline : {gpt.get('thumb_headline')}")
print(f"추출 thumb 수치     : {sorted(extract_num_tokens(gpt.get('thumb_headline', '')))}")
ref_text = gpt.get("script", "") + " " + gpt.get("hook", "")
print(f"추출 ref 수치(일부) : {sorted(extract_num_tokens(ref_text))[:8]}")
print("=" * 60)

# ── Case A: 불일치 (5月物価14安定 → "14" ≠ "1.4%") ──────────
print("\n[Case A] thumb='5月物価14安定' → sys.exit(1) 발동 기대")
try:
    validate_thumb_numerics(gpt)
    print("  결과: [FAIL] sys.exit(1) 발동 안 됨 ← 버그")
except SystemExit as e:
    print(f"  결과: [OK] sys.exit({e.code}) 발동 ✅")

# ── Case B: 일치 (1.4%安定 → "1.4%" ∈ ref) ──────────────────
print("\n[Case B] thumb='1.4%安定' → 통과 기대")
gpt_b = copy.deepcopy(gpt)
gpt_b["thumb_headline"] = "1.4%安定"
print(f"  thumb 수치: {sorted(extract_num_tokens('1.4%安定'))}")
try:
    validate_thumb_numerics(gpt_b)
    print("  결과: [OK] 통과 (sys.exit 없음) ✅")
except SystemExit as e:
    print(f"  결과: [FAIL] 잘못된 sys.exit({e.code}) 발동 ← 버그")
