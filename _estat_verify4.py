"""e-Stat 4개 통계 살아있음 검증 — 월별 + 2024년 이후 갱신 여부 확인"""
import sys, os, time, requests
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

APP_ID = os.environ.get("ESTAT_APP_ID", "")
BASE   = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList"
WAIT   = 10   # 高頻度アクセス 금지 — 검색 사이 대기

def ext(obj):
    return obj.get("$", "") if isinstance(obj, dict) else str(obj or "")

def search(word):
    params = {"appId": APP_ID, "searchWord": word}
    r = requests.get(BASE, params=params, timeout=60)
    data  = r.json()
    root  = data.get("GET_STATS_LIST", {})
    items = root.get("DATALIST_INF", {}).get("TABLE_INF", [])
    if not isinstance(items, list):
        items = [items] if items else []
    return items

def analyze(items, label):
    """월별·2024+ 갱신 기준으로 항목 분석."""
    total      = len(items)
    monthly    = [t for t in items if t.get("CYCLE") == "月次"]
    recent     = [t for t in items if str(t.get("UPDATED_DATE","")) >= "2024"]
    recent_mon = [t for t in recent if t.get("CYCLE") == "月次"]

    # 대표 ID: 2024+ 갱신 월별 우선, 없으면 2024+ 갱신 연차, 없으면 月次 최신 순
    if recent_mon:
        picks = sorted(recent_mon, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True)[:2]
    elif recent:
        picks = sorted(recent, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True)[:2]
    elif monthly:
        picks = sorted(monthly, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True)[:2]
    else:
        picks = sorted(items, key=lambda x: str(x.get("UPDATED_DATE","")), reverse=True)[:2]

    latest_upd = max((str(t.get("UPDATED_DATE","")) for t in items), default="N/A")

    usable = len(recent_mon) > 0 or (len(recent) > 0 and len(monthly) > 0)

    return {
        "label":       label,
        "total":       total,
        "monthly_cnt": len(monthly),
        "recent_cnt":  len(recent),
        "recent_mon":  len(recent_mon),
        "latest_upd":  latest_upd[:10],
        "picks":       picks,
        "usable":      usable,
    }

def print_report(res):
    label = res["label"]
    alive = "✅ 사용 가능" if res["usable"] else "❌ 불가 (2024+ 월별 없음)"
    print(f"\n{'='*65}")
    print(f"[{label}]")
    print(f"  검색 결과 수    : {res['total']}개")
    print(f"  月次 항목 수    : {res['monthly_cnt']}개")
    print(f"  2024+ 갱신     : {res['recent_cnt']}개 (月次 {res['recent_mon']}개)")
    print(f"  가장 최근 갱신  : {res['latest_upd']}")
    print(f"  결론           : {alive}")
    print(f"  대표 statsDataId:")
    for t in res["picks"]:
        sid   = t.get("@id","")
        upd   = str(t.get("UPDATED_DATE",""))[:10]
        cycle = t.get("CYCLE","")
        stat  = ext(t.get("STAT_NAME",{}))
        title = ext(t.get("TITLE",{}))
        label2 = (stat + " / " + title).strip(" /")[:55]
        print(f"    {sid}  갱신:{upd}  [{cycle}]  {label2}")

# ── 4개 검색 실행 ──────────────────────────
QUERIES = [
    ("消費者物価指数", "① 消費者物価指数 (CPI)"),
    ("家計調査",       "② 家計調査"),
    ("労働力調査",     "③ 労働力調査 (실업률)"),
    ("国際収支",       "④ 国際収支"),
]

results = []
for i, (word, label) in enumerate(QUERIES):
    print(f"[{i+1}/4] '{word}' 검색 중...")
    items = search(word)
    print(f"  -> {len(items)}건")
    results.append(analyze(items, label))
    if i < len(QUERIES) - 1:
        print(f"  ({WAIT}초 대기)")
        time.sleep(WAIT)

# ── 개별 보고 ──────────────────────────────
print("\n\n" + "="*65)
print("=== 개별 상세 보고 ===")
for res in results:
    print_report(res)

# ── 종합 표 ────────────────────────────────
print("\n\n" + "="*80)
print("=== 종합 표 ===")
print(f"{'통계명':<28} {'살아있음':<10} {'대표 statsDataId':<16} 비고")
print("-"*80)
for res in results:
    alive = "✅" if res["usable"] else "❌"
    sid   = res["picks"][0].get("@id","N/A") if res["picks"] else "N/A"
    upd   = str(res["picks"][0].get("UPDATED_DATE",""))[:7] if res["picks"] else ""
    mon   = f"月次{res['recent_mon']}건" if res["recent_mon"] > 0 else (
            f"2024+{res['recent_cnt']}건(年次)" if res["recent_cnt"] > 0 else
            f"最新:{res['latest_upd']}")
    print(f"{res['label']:<28} {alive:<10} {sid:<16} {mon} / 갱신:{upd}")
print("="*80)
