"""기존 롱폼 영상 embeddable 일괄 활성화 — 1회용 패치 스크립트

블로그 WordPress embed가 깨진 롱폼 영상의 embeddable 설정을 True로 변경한다.
privacyStatus / publishAt 등 기존 값은 절대 건드리지 않는다 (예약 영상 강제 공개 방지).
"""
import os
import sys

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 상수 =====
CLIENT_SECRETS_PATH = "client_secrets.json"
TOKEN_PATH          = "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# 블로그 embed가 깨진 롱폼 영상 ID 목록
VIDEO_IDS = [
    "sfAdFiEbUHY",  # long_youtube_url.txt — 최신 롱폼
    "GXwBeZFBh-g",  # run_all_log.txt — 직전 롱폼
]


# ─────────────────────────────────────────
# 인증
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# 2단계 패치: 읽기 → 최소 변경 업데이트
# ─────────────────────────────────────────

def patch_embeddable(youtube, video_id: str):
    """Step 1: 현재 status 읽기 → Step 2: embeddable만 True로 변경, 나머지 보존."""

    # Step 1 — 현재 status 읽기
    resp  = youtube.videos().list(part="status", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        print(f"  [건너뜀] {video_id} — 채널에서 찾을 수 없음 (삭제됐거나 타 채널 영상)")
        return

    current = items[0]["status"]
    privacy       = current.get("privacyStatus", "private")
    made_for_kids = current.get("selfDeclaredMadeForKids", False)
    publish_at    = current.get("publishAt")   # 예약 영상에만 존재
    already       = current.get("embeddable", False)

    if already:
        print(f"  [스킵] {video_id} — 이미 embeddable=True (privacyStatus={privacy})")
        return

    # Step 2 — embeddable=True, 나머지 필드 원본 유지
    new_status: dict = {
        "embeddable":              True,
        "privacyStatus":           privacy,
        "selfDeclaredMadeForKids": made_for_kids,
    }
    if publish_at:
        # 예약 영상: publishAt 유지 (누락 시 YouTube가 즉시 공개로 처리할 수 있음)
        new_status["publishAt"] = publish_at

    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": new_status},
    ).execute()

    print(f"  [완료] {video_id} — embeddable=True 적용")
    print(f"         privacyStatus={privacy} 유지"
          + (f" / publishAt={publish_at}" if publish_at else ""))


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def main():
    print(f"처리 대상 영상: {VIDEO_IDS}\n")
    creds   = authenticate()
    youtube = build("youtube", "v3", credentials=creds)

    for vid in VIDEO_IDS:
        print(f"처리 중: {vid}")
        try:
            patch_embeddable(youtube, vid)
        except Exception as e:
            print(f"  [오류] {vid} — {e}")

    print("\n전체 완료")


if __name__ == "__main__":
    main()
