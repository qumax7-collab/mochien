import os
import sys
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("[오류] .env에 TELEGRAM_BOT_TOKEN이 없습니다.")
    sys.exit(1)

resp = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getUpdates",
    timeout=10,
)
resp.raise_for_status()

updates = resp.json().get("result", [])

if not updates:
    print("메시지가 없습니다.")
    print("→ Telegram에서 이 봇에게 아무 메시지나 보낸 뒤 다시 실행하세요.")
    sys.exit(0)

seen = set()
for update in updates:
    msg = update.get("message") or update.get("callback_query", {}).get("message")
    if not msg:
        continue
    chat = msg["chat"]
    chat_id = chat["id"]
    if chat_id in seen:
        continue
    seen.add(chat_id)
    name = chat.get("username") or chat.get("first_name") or ""
    print(f"chat_id: {chat_id}  ({chat['type']} / {name})")

print("\n위 chat_id를 .env의 TELEGRAM_CHAT_ID에 입력하세요.")
