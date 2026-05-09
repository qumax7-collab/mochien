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
GPT_RESULT_PATH = "gpt_result.json"
VIDEO_PATH = "output_video_subtitled.mp4"
CLIENT_SECRETS_PATH = "client_secrets.json"
TOKEN_PATH = "token.json"

# ===== YouTube API 설정 =====
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
YOUTUBE_CATEGORY_ID = "25"   # News & Politics
YOUTUBE_LANGUAGE = "ja"

JST = timezone(timedelta(hours=9))

CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━\n"
    "毎日3回、経済ニュースをわかりやすくお届け！\n"
    "チャンネル登録よろしくお願いします。"
)

# ===== 텔레그램 설정 =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def tg_notify(text):
    """완료 알림 전송."""
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=10,
    )


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


def build_description(hashtags):
    tags_str = " ".join(hashtags)
    return f"{tags_str}{CHANNEL_FOOTER}"


def upload_video(youtube, title, description, tags):
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
            "privacyStatus": "public",
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


def post_comment(youtube, video_id, text):
    response = youtube.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {"textOriginal": text}
                },
            }
        },
    ).execute()
    print(f"댓글 등록 완료: {response['id']}")
    return response["id"]


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[오류] .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 입력하세요.")
        sys.exit(1)

    if not os.path.exists(VIDEO_PATH):
        print(f"[오류] 영상 파일을 찾을 수 없습니다: {VIDEO_PATH}")
        sys.exit(1)

    with open(GPT_RESULT_PATH, encoding="utf-8") as f:
        gpt = json.load(f)

    title = gpt["title"]
    hook = gpt["hook"]
    korean_summary = gpt["korean_summary"]
    hashtags = gpt["hashtags"]

    now_jst = datetime.now(JST).strftime("%m/%d %H:%M JST")
    description = build_description(hashtags)

    print(f"제목      : {title}")
    print(f"공개 시간 : {now_jst}")

    creds = authenticate()
    youtube = build("youtube", "v3", credentials=creds)
    video_id = upload_video(youtube, title, description, hashtags)
    post_comment(youtube, video_id, hook)

    result_url = f"https://www.youtube.com/watch?v={video_id}"

    tg_notify(
        f"✅ <b>업로드 완료!</b>\n\n"
        f"<b>제목:</b> {title}\n"
        f"<b>공개:</b> {now_jst}\n"
        f"<b>한국어 요약:</b> {korean_summary}\n\n"
        f"🎬 {result_url}"
    )

    print(f"\n업로드 완료!")
    print(f"동영상 ID : {video_id}")
    print(f"URL       : {result_url}")


if __name__ == "__main__":
    main()
