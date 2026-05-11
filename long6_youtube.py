import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 파일 경로 =====
LONG_SCRIPT_PATH  = "long_script.json"
VIDEO_PATH        = "long_output.mp4"
CLIENT_SECRETS_PATH = "client_secrets.json"
TOKEN_PATH        = "token.json"
OUTPUT_DIR        = "output"

# ===== YouTube API 설정 =====
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
YOUTUBE_CATEGORY_ID = "25"   # News & Politics
YOUTUBE_LANGUAGE    = "ja"

JST = timezone(timedelta(hours=9))
LONGFORM_PUBLISH_HOUR = 21

# 슬롯별 텔레그램 표시 시간
SLOT_DISPLAY_TIMES = {"09": "07:00", "13": "12:00", "18": "18:00"}

CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━\n"
    "毎日3回のショーツ＋毎晩21時に深掘り解説！\n"
    "チャンネル登録よろしくお願いします。"
)

# ===== 텔레그램 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


def tg_notify(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def get_publish_at():
    """당일 21:00 JST 예약 시각(RFC 3339) 반환. 이미 지난 경우 익일로."""
    now_jst = datetime.now(JST)
    publish_jst = now_jst.replace(hour=LONGFORM_PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    if publish_jst <= now_jst:
        publish_jst += timedelta(days=1)
    return publish_jst.isoformat()


def authenticate():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds


def build_description(data):
    hashtags = " ".join(data["hashtags"])
    issues = "\n".join(
        f"▶ {iss['title']}" for iss in data["issues"]
    )
    return f"{hashtags}\n\n【本日の内容】\n{issues}{CHANNEL_FOOTER}"


def upload_video(youtube, title, description, tags, publish_at):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [tag.lstrip("#") for tag in tags],
            "categoryId": YOUTUBE_CATEGORY_ID,
            "defaultLanguage": YOUTUBE_LANGUAGE,
            "defaultAudioLanguage": YOUTUBE_LANGUAGE,
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    print("YouTube 업로드 중...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  진행: {int(status.progress() * 100)}%")
    return response["id"]


def build_combined_notification(long_script_data):
    """쇼츠 3개 + 롱폼 hook을 합산해 텔레그램 메시지 생성."""
    now_jst = datetime.now(JST)
    date_str = now_jst.strftime("%Y-%m-%d")
    out_dir = os.path.join(OUTPUT_DIR, date_str)

    lines = ["✅ 오늘 영상 4개 예약 완료\n"]

    slot_labels = [("09", "쇼츠1"), ("13", "쇼츠2"), ("18", "쇼츠3")]
    for slot, label in slot_labels:
        display_time = SLOT_DISPLAY_TIMES[slot]
        slot_file = os.path.join(out_dir, f"{slot}_gpt_result.json")
        if os.path.exists(slot_file):
            with open(slot_file, encoding="utf-8") as f:
                gpt = json.load(f)
            hook = gpt.get("hook", "(데이터 없음)")
            hook_korean = gpt.get("hook_korean", "")
        else:
            hook = "(데이터 없음)"
            hook_korean = ""
        kr_line = f"\n🇰🇷 {hook_korean}" if hook_korean else ""
        lines.append(f"📌 {label} 고정댓글 ({display_time} 업로드):\n{hook}{kr_line}\n")

    intro_script = long_script_data["intro"]["script"]
    longform_hook = intro_script[:150] + ("..." if len(intro_script) > 150 else "")
    longform_kr = long_script_data.get("korean_summary", "")
    kr_line = f"\n🇰🇷 {longform_kr}" if longform_kr else ""
    lines.append(f"📌 롱폼 고정댓글 (21:00 업로드):\n{longform_hook}{kr_line}\n")

    lines.append("시간날 때 YouTube Studio에서 달아주세요!")

    return "\n".join(lines)


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[오류] .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 입력하세요.")
        sys.exit(1)

    if not os.path.exists(VIDEO_PATH):
        print(f"[오류] 영상 파일을 찾을 수 없습니다: {VIDEO_PATH}")
        sys.exit(1)

    with open(LONG_SCRIPT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    title    = data["title"]
    hashtags = data["hashtags"]

    publish_at  = get_publish_at()
    description = build_description(data)

    print(f"제목      : {title}")
    print(f"예약 시간 : {publish_at}")

    creds   = authenticate()
    youtube = build("youtube", "v3", credentials=creds)
    video_id = upload_video(youtube, title, description, hashtags, publish_at)

    result_url = f"https://www.youtube.com/watch?v={video_id}"

    msg = build_combined_notification(data)
    tg_notify(msg)

    print(f"\n예약 완료!")
    print(f"동영상 ID : {video_id}")
    print(f"URL       : {result_url}")


if __name__ == "__main__":
    main()
