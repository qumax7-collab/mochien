"""3개 키워드 통합 검색 — 최신 갱신·월별·실질임금 후보만 추출"""
import sys, json, os, requests
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

APP_ID = os.environ.get("ESTAT_APP_ID", "")
BASE   = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"

def search(word, code=None):
    params = {"appId": APP_ID, "searchWord": word}
    if code:
        params["statsCode"] = code
    r = requests.get(BASE, params=params, timeout=60)
    data = r.json()
    root     = data.get("GET_STATS_LIST", {})
    datalist = root.get("DATALIST_INF", {})
    items    = datalist.get("TABLE_INF", [])
    if not isinstance(items, list):
        items = [items] if items else []
    return items

def ext(obj):
    return obj.get("$", "") if isinstance(obj, dict) else str(obj or "")

# ── 3개 검색 ──────────────────────────────
print("[1/3] 実質賃金 月次 검색...")
r1 = search("実質賃金 月次")
print(f"  {len(r1)}건")

print("[2/3] 実質賃金 검색...")
r2 = search("実質賃金")
print(f"  {len(r2)}건")

print("[3/3] 勤労統計 검색...")
r3 = search("勤労統計")
print(f"  {len(r3)}건")

# ── 중복 제거 통합 ─────────────────────────
seen: dict = {}
for item in r1 + r2 + r3:
    sid = item.get("@id", "")
    if sid and sid not in seen:
        seen[sid] = item

all_items = list(seen.values())
print(f"\n통합 고유 statsDataId: {len(all_items)}개\n")

# ── 필터 1: 2022년 이후 갱신 ──────────────
recent = [t for t in all_items if str(t.get("UPDATED_DATE","")) >= "2022"]
print(f"[갱신일 2022+] {len(recent)}개")
for t in sorted(recent, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True):
    sid   = t.get("@id","")
    upd   = str(t.get("UPDATED_DATE",""))[:10]
    cycle = t.get("CYCLE","")
    moon  = "●" if cycle == "月次" else "  "
    stat  = ext(t.get("STAT_NAME",{}))
    title = ext(t.get("TITLE",{}))
    stat_code = t.get("STAT_NAME",{}).get("@code","") if isinstance(t.get("STAT_NAME"),dict) else ""
    label = (stat + " / " + title).strip(" /")[:60]
    print(f"  {sid} {upd} {moon} [{stat_code}] {label}")

# ── 필터 2: 月次 + 実質賃金 키워드 포함 ───
print()
wage_monthly = [
    t for t in all_items
    if t.get("CYCLE") == "月次"
    and ("実質賃金" in ext(t.get("TITLE","")) or "実質賃金" in ext(t.get("STAT_NAME","")))
]
print(f"[月次 + 実質賃金 포함] {len(wage_monthly)}개")
for t in sorted(wage_monthly, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True):
    sid   = t.get("@id","")
    upd   = str(t.get("UPDATED_DATE",""))[:10]
    stat  = ext(t.get("STAT_NAME",{}))
    title = ext(t.get("TITLE",{}))
    stat_code = t.get("STAT_NAME",{}).get("@code","") if isinstance(t.get("STAT_NAME"),dict) else ""
    open_d = str(t.get("OPEN_DATE",""))[:10]
    label = (stat + " / " + title).strip(" /")[:55]
    print(f"  {sid} 갱신:{upd} 공개:{open_d} [{stat_code}] {label}")

# ── 필터 3: 00450071 이외의 statsCode ─────
print()
other_codes = [
    t for t in all_items
    if isinstance(t.get("STAT_NAME"), dict)
    and t["STAT_NAME"].get("@code","") not in ("00450071", "")
]
code_set = set(
    t["STAT_NAME"]["@code"]
    for t in other_codes
    if isinstance(t.get("STAT_NAME"), dict)
)
print(f"[00450071 이외 통계코드] {len(code_set)}개: {sorted(code_set)}")
for t in sorted(other_codes, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True)[:20]:
    sid   = t.get("@id","")
    upd   = str(t.get("UPDATED_DATE",""))[:10]
    cycle = t.get("CYCLE","")
    moon  = "●" if cycle == "月次" else "  "
    stat  = ext(t.get("STAT_NAME",{}))
    title = ext(t.get("TITLE",{}))
    stat_code = t.get("STAT_NAME",{}).get("@code","") if isinstance(t.get("STAT_NAME"),dict) else ""
    label = (stat + " / " + title).strip(" /")[:55]
    print(f"  {sid} {upd} {moon} [{stat_code}] {label}")
