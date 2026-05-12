import json
import os
import sys
from datetime import datetime, timezone, timedelta

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
SRT_PATH = "subtitle.srt"
CLIENT_SECRETS_PATH = "client_secrets.json"
TOKEN_PATH = "token.json"

# ===== YouTube API 설정 =====
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
YOUTUBE_CATEGORY_ID = "25"   # News & Politics
YOUTUBE_LANGUAGE = "ja"

CAPTION_LANGUAGE = "ja"
CAPTION_NAME = "日本語"

JST = timezone(timedelta(hours=9))

# 슬롯별 예약 발행 시간 (JST 시각)
SLOT_PUBLISH_HOURS = {"09": 7, "13": 12, "18": 18}

CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━\n"
    "毎日3回、経済ニュースをわかりやすくお届け！\n"
    "チャンネル登録よろしくお願いします。"
)


def get_publish_at(slot):
    """슬롯 목표 시각 반환. 이미 지났으면 익일 동일 시각으로 예약."""
    hour = SLOT_PUBLISH_HOURS.get(slot, 18)
    now_jst = datetime.now(JST)
    publish_jst = now_jst.replace(hour=hour, minute=0, second=0, microsecond=0)
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


def upload_caption(youtube, video_id):
    if not os.path.exists(SRT_PATH):
        print("subtitle.srt 없음 → 자막 업로드 건너뜀")
        return
    body = {
        "snippet": {
            "videoId": video_id,
            "language": CAPTION_LANGUAGE,
            "name": CAPTION_NAME,
            "isDraft": False,
        }
    }
    media = MediaFileUpload(SRT_PATH, mimetype="application/octet-stream", resumable=False)
    youtube.captions().insert(part="snippet", body=body, media_body=media).execute()
    print(f"자막 업로드 완료 ({CAPTION_NAME})")


def build_description(hashtags):
    tags_str = " ".join(hashtags)
    return f"{tags_str}{CHANNEL_FOOTER}"


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


def main():
    if not os.path.exists(VIDEO_PATH):
        print(f"[오류] 영상 파일을 찾을 수 없습니다: {VIDEO_PATH}")
        sys.exit(1)

    with open(GPT_RESULT_PATH, encoding="utf-8") as f:
        gpt = json.load(f)

    title = gpt["title"]
    hashtags = gpt["hashtags"]
    slot = gpt.get("slot", "18")

    publish_at = get_publish_at(slot)
    description = build_description(hashtags)

    print(f"제목      : {title}")
    print(f"슬롯      : {slot}")
    print(f"예약 시간 : {publish_at}")

    creds = authenticate()
    youtube = build("youtube", "v3", credentials=creds)
    video_id = upload_video(youtube, title, description, hashtags, publish_at)
    upload_caption(youtube, video_id)

    result_url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"\n예약 완료!")
    print(f"동영상 ID : {video_id}")
    print(f"URL       : {result_url}")


if __name__ == "__main__":
    main()
