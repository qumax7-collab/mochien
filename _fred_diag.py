import sys, os, requests
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

key = os.environ.get("FRED_API_KEY", "")

# observations 엔드포인트 직접 시도
url2 = "https://api.stlouisfed.org/fred/series/observations"
params2 = {
    "series_id": "DEXJPUS",
    "api_key": key,
    "file_type": "json",
    "limit": 5,
    "sort_order": "desc",
}
print("=== /series/observations 엔드포인트 ===")
try:
    r2 = requests.get(url2, params=params2, timeout=30)
    print(f"HTTP 상태: {r2.status_code}")
    print(f"응답 (앞 800자): {r2.text[:800]}")
except Exception as e:
    print(f"예외: {type(e).__name__}: {e}")
