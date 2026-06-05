import sys, json, requests
sys.stdout.reconfigure(encoding="utf-8")

url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
params = {"db": "FM08", "code": "FXERD01", "format": "json", "lang": "JP", "startDate": "202501"}
headers = {"Accept-Encoding": "gzip"}

r = requests.get(url, params=params, headers=headers, timeout=30)
data = r.json()

rs = data["RESULTSET"][0]
vals = rs["VALUES"]

print("VALUES 키:", list(vals.keys()))
print("SURVEY_DATES 앞 5개:", vals["SURVEY_DATES"][:5])
print("SURVEY_DATES 타입:", type(vals["SURVEY_DATES"][0]))

# 값 키 확인
for k in vals.keys():
    if k != "SURVEY_DATES":
        print(f"{k} 앞 5개:", vals[k][:5])
        print(f"{k} 타입:", type(vals[k][0]))

print("NEXTPOSITION:", data.get("NEXTPOSITION"))
