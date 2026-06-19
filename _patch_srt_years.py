"""SRT 연도 오인식 수동 패치: 2015→2025, 2016→2026."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

SRT = "long_subtitle.srt"

with open(SRT, encoding="utf-8") as f:
    text = f.read()

replacements = [
    ("2015年4月には補", "2025年4月には補"),
    ("2016年にはさらに", "2026年にはさらに"),
    ("2016年4月時点", "2026年4月時点"),
]

changed = 0
for old, new in replacements:
    if old in text:
        text = text.replace(old, new)
        print(f"  교정: '{old}' → '{new}'")
        changed += 1
    else:
        print(f"  [경고] 패턴 없음: '{old}'")

with open(SRT, "w", encoding="utf-8") as f:
    f.write(text)

print(f"\n총 {changed}건 교정 → {SRT} 저장 완료")

# 검증
import re
bad = re.findall(r"201[0-9]年", text)
if bad:
    print(f"[경고] 구 연도 잔존: {set(bad)}")
else:
    print("검증 통과: 2010년대 오인식 없음")
