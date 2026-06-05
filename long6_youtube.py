import argparse
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

import longform_link

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 파일 경로 =====
LONG_SCRIPT_PATH    = "long_script.json"
LONG_CHAPTERS_FILE  = "long_chapters.json"
VIDEO_PATH          = "long_output.mp4"
CLIENT_SECRETS_PATH = "client_secrets.json"
TOKEN_PATH          = "token.json"
OUTPUT_DIR          = "output"
SLOTS               = ["09", "18"]

# ===== YouTube API 설정 =====
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
YOUTUBE_CATEGORY_ID = "25"   # News & Politics
YOUTUBE_LANGUAGE    = "ja"

JST = timezone(timedelta(hours=9))

CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━\n"
    "毎日2回のショーツ＋毎週日・木18時に深掘り解説！\n"
    "チャンネル登録よろしくお願いします。"
)

SOURCE_INST_JA = {
    "estat": "総務省統計局 e-Stat",
    "boj":   "日本銀行 時系列統計",
    "fred":  "米連邦準備制度（FRED）",
}
FALLBACK_SOURCE = "NHK ニュース / Yahoo Japan ビジネス"

CHANNEL_INFO_BLOCK = (
    "【このチャンネルについて】\n"
    "経済ニュースをモチエンキャラクターが解説するチャンネルです。\n"
    "一人で運営しています。\n"
    "個別銘柄や投資商品の推奨は行いません。"
)


def _source_line(slug_keyword: str) -> str:
    """topic_id → 실제 사용 데이터 소스 기관명. 토픽 없으면 뉴스 fallback."""
    try:
        with open("topic_bank.json", encoding="utf-8") as f:
            bank = json.load(f)["topics"]
        topic = next((t for t in bank if t["id"] == slug_keyword), None)
        if not topic or not topic.get("data_sources"):
            return FALLBACK_SOURCE
        seen: list[str] = []
        for src in topic["data_sources"]:
            inst = SOURCE_INST_JA.get(src.get("source", ""))
            if inst and inst not in seen:
                seen.append(inst)
        return " / ".join(seen) if seen else FALLBACK_SOURCE
    except Exception:
        return FALLBACK_SOURCE

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
    hashtags   = " ".join(data["hashtags"])
    issues     = "\n".join(f"▶ {iss['title']}" for iss in data["issues"])
    slug       = data.get("_slug_keyword", "")
    info_block = f"【参考データ】{_source_line(slug)}\n{CHANNEL_INFO_BLOCK}"
    body       = f"{hashtags}\n\n【本日の内容】\n{issues}\n\n{info_block}{CHANNEL_FOOTER}"

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
            "embeddable": True,
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


def load_slot_short_titles():
    """오늘 날짜 슬롯 파일에서 short_title 읽기. 없는 슬롯은 스킵."""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    titles = []
    for slot in SLOTS:
        path = os.path.join(OUTPUT_DIR, today, f"{slot}_gpt_result.json")
        try:
            with open(path, encoding="utf-8") as f:
                st = json.load(f).get("short_title", "").strip()
            if st:
                titles.append(st)
        except Exception:
            pass
    return titles


def build_notification(long_script_data, publish_at_jst: str):
    """롱폼 단독 텔레그램 알림 메시지 생성."""
    title = long_script_data["title"]

    short_titles = load_slot_short_titles()
    if short_titles:
        quoted = "」「".join(short_titles)
        first_line = f"🍡 今日は「{quoted}」の{len(short_titles)}つの経済ニュースをお届けしました。"
    else:
        first_line = "🍡 今日の経済ニュースはいかがでしたか？"

    pin_comment = (
        f"{first_line}\n"
        f"皆さんはどう感じましたか？コメント欄で教えてください！😊\n\n"
        f"※投資判断はご自身の責任でお願いいたします。"
    )

    return (
        f"📹 롱폼 예약 완료\n"
        f"제목: {title}\n"
        f"예약: {publish_at_jst}\n"
        f"\n📌 고정댓글:\n{pin_comment}\n"
        f"\nYouTube Studio에서 달아주세요!"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default="sun", choices=list(longform_link.SLOT_WEEKDAYS.keys()),
                        help="발행 슬롯 (sun=일요일 / thu=목요일, 기본: sun)")
    args = parser.parse_args()

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

    publish_at  = longform_link.next_publish_jst(args.slot)
    description = build_description(data)

    print(f"제목      : {title}")
    print(f"슬롯      : {args.slot}")
    print(f"예약 시간 : {publish_at}")

    creds   = authenticate()
    youtube = build("youtube", "v3", credentials=creds)
    video_id = upload_video(youtube, title, description, hashtags, publish_at)

    result_url = f"https://www.youtube.com/watch?v={video_id}"

    # long7_wordpress.py가 embed용으로 읽는 파일
    with open("long_youtube_url.txt", "w", encoding="utf-8") as f:
        f.write(result_url)

    # 발행 성공 → active_longform.json 기록
    longform_link.append_active({
        "topic_id":       data.get("_slug_keyword", ""),
        "topic_ja":       data.get("topic_title_ja", ""),
        "title_ja":       title,
        "url":            result_url,
        "publish_at_jst": publish_at,
    })
    print("active_longform.json 기록 완료")

    msg = build_notification(data, publish_at)
    tg_notify(msg)

    print(f"\n예약 완료!")
    print(f"동영상 ID : {video_id}")
    print(f"URL       : {result_url}")


if __name__ == "__main__":
    main()
