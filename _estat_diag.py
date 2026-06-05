import sys, json, requests, os
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

app_id = os.environ.get("ESTAT_APP_ID", "")
url = "https://api.e-stat.go.jp/rest/3.0/app/json/getMetaInfo"
params = {"appId": app_id, "statsDataId": "0003138104"}

r = requests.get(url, params=params, timeout=30)
data = r.json()
root = data["GET_META_INFO"]
mi = root["METADATA_INF"]

print("METADATA_INF 키:", list(mi.keys()))

# TABLE_INF
ti = mi.get("TABLE_INF", {})
print("\nTABLE_INF 키:", list(ti.keys()) if isinstance(ti, dict) else type(ti))
print(json.dumps(ti, ensure_ascii=False, indent=2)[:1000])

# CLASS_INF
ci = mi.get("CLASS_INF", {})
print("\nCLASS_INF 키:", list(ci.keys()) if isinstance(ci, dict) else type(ci))

class_objs = ci.get("CLASS_OBJ", [])
if not isinstance(class_objs, list):
    class_objs = [class_objs]
print(f"CLASS_OBJ 수: {len(class_objs)}")
for obj in class_objs[:3]:
    print(f"\n--- {obj.get('@id')} / {obj.get('@name')} ---")
    cls = obj.get("CLASS", [])
    if not isinstance(cls, list): cls = [cls]
    print(f"  CLASS 수: {len(cls)}")
    print(f"  첫 3개: {json.dumps(cls[:3], ensure_ascii=False)}")
