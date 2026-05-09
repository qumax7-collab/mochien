import sys, os, requests, json, time
from dotenv import load_dotenv
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

key = os.environ.get("ZAPCAP_API_KEY")
base = "https://api.zapcap.ai"
video_id = "83c54b6d-3d4c-437f-aed7-2a478a223002"
task_id  = "3b7c8901-faae-4376-a37d-3bfd212e6db8"
h = {"x-api-key": key, "Content-Type": "application/json"}
hg = {"x-api-key": key}

# PUT 한 번 더 실행
requests.put(f"{base}/videos/{video_id}/task/{task_id}", headers=h, json={"transcriptApproved": True}, timeout=10)
print("PUT 완료. 10분간 폴링 시작...")

for i in range(60):
    r = requests.get(f"{base}/videos/{video_id}/task/{task_id}", headers=hg, timeout=10)
    d = r.json()
    status = d.get("status")
    dl = d.get("downloadUrl")
    print(f"  [{i*10}s] status={status}  downloadUrl={'있음' if dl else 'None'}")
    if dl:
        print(f"\n다운로드 URL: {dl}")
        break
    if status in ("failed", "error"):
        print("실패!")
        break
    time.sleep(10)
