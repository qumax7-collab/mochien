"""
telegram_trigger.py
모찌엔 파이프라인 수동 트리거 봇

JST 09:00 / 13:00 / 18:00 → 쇼츠 알람 + 실행 버튼
JST 21:00               → 롱폼 알람 + 실행 버튼
/메뉴                    → 언제든 즉시 버튼 표시

실행: python telegram_trigger.py  (터미널에서 상시 실행)
"""

import os
import time
import requests
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

load_dotenv()

# ── 상수 ──────────────────────────────────────────────────────
BOT_TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID           = str(os.getenv("TELEGRAM_CHAT_ID"))
GH_PAT            = os.getenv("GH_PAT")
GITHUB_OWNER      = "qumax7-collab"
GITHUB_REPO       = "mochien"
SHORTS_WORKFLOW   = "mochien.yml"
LONGFORM_WORKFLOW = "mochien_longform.yml"
GITHUB_REF        = "main"
JST               = pytz.timezone("Asia/Tokyo")
TELEGRAM_API      = f"https://api.telegram.org/bot{BOT_TOKEN}"
GITHUB_API_BASE   = "https://api.github.com"
POLL_TIMEOUT      = 30

# ── Telegram 헬퍼 ──────────────────────────────────────────────
def tg_send(text, reply_markup=None):
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)

def tg_edit(chat_id, message_id, text):
    requests.post(
        f"{TELEGRAM_API}/editMessageText",
        json={"chat_id": chat_id, "message_id": message_id,
              "text": text, "parse_mode": "HTML"},
        timeout=10,
    )

def tg_answer(callback_query_id, text=""):
    requests.post(
        f"{TELEGRAM_API}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=10,
    )

# ── 인라인 키보드 ───────────────────────────────────────────────
def alarm_keyboard(callback_data, label):
    return {
        "inline_keyboard": [
            [{"text": label,         "callback_data": callback_data}],
            [{"text": "⏭ 건너뛰기", "callback_data": "skip"}],
        ]
    }

def menu_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "▶ 쇼츠 파이프라인 실행", "callback_data": "run_shorts"}],
            [{"text": "▶ 롱폼 파이프라인 실행",  "callback_data": "run_longform"}],
        ]
    }

# ── GitHub Actions 트리거 ───────────────────────────────────────
def trigger_workflow(workflow_file):
    url = (f"{GITHUB_API_BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
           f"/actions/workflows/{workflow_file}/dispatches")
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(url, headers=headers,
                         json={"ref": GITHUB_REF}, timeout=10)
    return resp.status_code == 204  # 204 = 성공

# ── 알람 전송 (스케줄러 호출) ────────────────────────────────────
def send_shorts_alarm(slot):
    tg_send(
        f"⏰ <b>{slot}시 쇼츠 업로드 시간입니다!</b>\n"
        "아래 버튼으로 파이프라인을 실행하세요.",
        reply_markup=alarm_keyboard("run_shorts", f"▶ 쇼츠 {slot}시 실행"),
    )

def send_longform_alarm():
    tg_send(
        "⏰ <b>롱폼 영상 제작 시간입니다!</b>\n"
        "오늘 쇼츠 3개 완료 후 실행하세요.",
        reply_markup=alarm_keyboard("run_longform", "▶ 롱폼 실행"),
    )

# ── 콜백 처리 ──────────────────────────────────────────────────
def handle_callback(callback_query):
    data       = callback_query["data"]
    cq_id      = callback_query["id"]
    chat_id    = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]

    if data == "skip":
        tg_answer(cq_id, "건너뛰었습니다.")
        tg_edit(chat_id, message_id, "⏭ 건너뜀")
        return

    if data == "run_shorts":
        workflow = SHORTS_WORKFLOW
        label    = "쇼츠"
    elif data == "run_longform":
        workflow = LONGFORM_WORKFLOW
        label    = "롱폼"
    else:
        tg_answer(cq_id)
        return

    ok = trigger_workflow(workflow)
    if ok:
        tg_answer(cq_id, "✅ 트리거 성공!")
        tg_edit(
            chat_id, message_id,
            f"✅ <b>{label} GitHub Actions 실행 시작!</b>\n"
            f"진행 상황: https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/actions\n\n"
            "잠시 후 기사 선택 메시지가 도착합니다.",
        )
    else:
        tg_answer(cq_id, "❌ 트리거 실패")
        tg_edit(
            chat_id, message_id,
            "❌ <b>트리거 실패.</b> .env의 GH_PAT 키를 확인해주세요.",
        )

# ── 메시지 처리 ────────────────────────────────────────────────
def handle_message(message):
    text = message.get("text", "")
    if text in ("/start", "/menu", "/메뉴"):
        tg_send(
            "🎬 <b>모찌엔 파이프라인 메뉴</b>\n실행할 파이프라인을 선택하세요:",
            reply_markup=menu_keyboard(),
        )

# ── stale 업데이트 제거 ────────────────────────────────────────
def flush_updates():
    resp = requests.get(
        f"{TELEGRAM_API}/getUpdates",
        params={"offset": -1, "timeout": 0},
        timeout=10,
    )
    updates = resp.json().get("result", [])
    if updates:
        return updates[-1]["update_id"] + 1
    return 0

# ── 스케줄러 설정 ──────────────────────────────────────────────
def setup_scheduler():
    scheduler = BackgroundScheduler(timezone=JST)
    scheduler.add_job(
        lambda: send_shorts_alarm("09"),
        CronTrigger(hour=9,  minute=0, timezone=JST),
    )
    scheduler.add_job(
        lambda: send_shorts_alarm("18"),
        CronTrigger(hour=18, minute=0, timezone=JST),
    )
    scheduler.add_job(
        send_longform_alarm,
        CronTrigger(hour=21, minute=0, timezone=JST),
    )
    scheduler.start()
    print("스케줄러 시작 (JST 09:00 / 13:00 / 18:00 쇼츠 / 21:00 롱폼)")
    return scheduler

# ── 메인 폴링 루프 ──────────────────────────────────────────────
def run_bot():
    print("모찌엔 트리거 봇 시작. /메뉴 로 버튼 표시.")
    offset = flush_updates()

    while True:
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": offset, "timeout": POLL_TIMEOUT},
                timeout=POLL_TIMEOUT + 5,
            )
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback(update["callback_query"])
                elif "message" in update:
                    handle_message(update["message"])
        except Exception as e:
            print(f"[polling error] {e}")
            time.sleep(5)


if __name__ == "__main__":
    scheduler = setup_scheduler()
    try:
        run_bot()
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("봇 종료.")
