"""long_script_ko.json 검증: 분리축 + 섹션 글자수 확인"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

with open("long_script_ko.json", encoding="utf-8") as f:
    d = json.load(f)

print(f"\n토픽:     {d['topic_id']} / {d['topic_title_ja']}")
print(f"이슈1 각도: {d.get('issue1_angle', '(없음)')}")
print(f"이슈2 각도: {d.get('issue2_angle', '(없음)')}")
print()
print(f"인트로    : {len(d['intro']['script_ko'])}자")
print(f"이슈1     : {len(d['issues'][0]['script_ko'])}자  [{d['issues'][0]['title_ko']}]")
print(f"이슈2     : {len(d['issues'][1]['script_ko'])}자  [{d['issues'][1]['title_ko']}]")
print(f"아웃트로  : {len(d['outro']['script_ko'])}자")
