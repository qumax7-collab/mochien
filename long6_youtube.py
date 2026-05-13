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
LONG_SCRIPT_PATH   = "long_script.json"
LONG_CHAPTERS_FILE = "long_chapters.json"
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

CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━\n"
    "毎日3回のショーツ＋毎晩21時に深掘り解説！\n"
    "チャンネル登録よろしくお願いします。"
)

# ===== 텔레그램 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


def load_chapters():
    if not os.path.exists(LONG_CHAPTERS_FILE):
        return []
    try:
        with open(LONG_CHAPTERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def format_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_chapter_text(chapters):
    return "\n".join(f"{format_time(ch['time'])} {ch['label']}" for ch in chapters)


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
    body = f"{hashtags}\n\n【本日の内容】\n{issues}{CHANNEL_FOOTER}"

    chapters = load_chapters()
    if chapters:
        return f"{build_chapter_text(chapters)}\n\n{body}"
    return body


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


def build_notification(long_script_data):
    """롱폼 단독 텔레그램 알림 메시지 생성."""
    title = long_script_data["title"]
    intro_script = long_script_data["intro"]["script"]
    hook = intro_script[:150] + ("..." if len(intro_script) > 150 else "")
    korean_summary = long_script_data.get("korean_summary", "")
    kr_line = f"\n🇰🇷 {korean_summary}" if korean_summary else ""
    return (
        f"📹 롱폼 예약 완료\n"
        f"제목: {title}\n"
        f"예약: 21:00 JST\n"
        f"\n📌 고정댓글:\n{hook}{kr_line}\n"
        f"\nYouTube Studio에서 달아주세요!"
    )


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

    msg = build_notification(data)
    tg_notify(msg)

    print(f"\n예약 완료!")
    print(f"동영상 ID : {video_id}")
    print(f"URL       : {result_url}")


if __name__ == "__main__":
    main()
