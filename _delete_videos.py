import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CLIENT_SECRETS_PATH = "client_secrets.json"
TOKEN_PATH = "token.json"

VIDEO_IDS = [
    "tKI4AUHVRm0",
    "TGpeS9wrcVo",
]


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


def main():
    creds = authenticate()
    youtube = build("youtube", "v3", credentials=creds)

    for vid in VIDEO_IDS:
        try:
            youtube.videos().delete(id=vid).execute()
            print(f"삭제 완료: {vid}")
        except Exception as e:
            print(f"삭제 실패 ({vid}): {e}")


if __name__ == "__main__":
    main()
