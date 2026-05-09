import os, requests, time, sys
from dotenv import load_dotenv
load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
print("30초간 메시지 대기 중... (@Mochien_Notify_bot 에게 아무 메시지나 보내세요)")
deadline = time.time() + 30
offset = None

while time.time() < deadline:
    params = {"timeout": 5, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=10)
    for u in r.json().get("result", []):
        offset = u["update_id"] + 1
        msg = u.get("message")
        if msg:
            chat = msg["chat"]
            name = chat.get("username") or chat.get("first_name", "")
            print(f"\nchat_id: {chat['id']}  ({chat['type']} / {name})")
            print(".env의 TELEGRAM_CHAT_ID에 위 숫자를 입력하세요.")
            sys.exit(0)

print("타임아웃: 메시지를 받지 못했습니다.")
