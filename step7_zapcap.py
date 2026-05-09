import sys
import os
import time
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

INPUT_FILE = "output_no_sub.mp4"
OUTPUT_FILE = "output_final.mp4"

BASE_URL = "https://api.zapcap.ai"
POLL_INTERVAL = 5
POLL_TIMEOUT = 600

# 자막 템플릿 (animated+highlighted → 단어별 팝업 스타일)
# 변경하려면 아래 ID를 교체:
#   Ella   e7e758de-4eb4-460f-aeca-b2801ac7f8cc  animated+highlighted
#   Beast  46d20d67-255c-4c6a-b971-31fddcfea7f0  animated+highlighted
#   Jordan dfe027d9-bd9d-4e55-a94f-d57ed368a060  animated+highlighted
TEMPLATE_ID = "e7e758de-4eb4-460f-aeca-b2801ac7f8cc"  # Ella


def get_api_key():
    key = os.environ.get("ZAPCAP_API_KEY")
    if not key or key == "여기에_키_입력":
        raise Exception("ZAPCAP_API_KEY가 .env에 설정되지 않았습니다.")
    return key


def upload_video(api_key):
    print(f"=== 영상 업로드 중: {INPUT_FILE} ===")
    with open(INPUT_FILE, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/videos",
            headers={"x-api-key": api_key},
            files={"file": (INPUT_FILE, f, "video/mp4")},
            timeout=120,
        )
    res.raise_for_status()
    data = res.json()
    video_id = data["id"]
    print(f"업로드 완료 (video_id: {video_id})")
    return video_id


def create_task(api_key, video_id):
    print(f"\n=== 자막 task 생성 중 (templateId: {TEMPLATE_ID}) ===")
    res = requests.post(
        f"{BASE_URL}/videos/{video_id}/task",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"templateId": TEMPLATE_ID, "language": "ja"},
        timeout=30,
    )
    res.raise_for_status()
    task_id = res.json()["taskId"]
    print(f"task 생성 완료 (task_id: {task_id})")
    return task_id


def approve_transcript(api_key, video_id, task_id):
    print(f"  트랜스크립션 승인 중...")
    res = requests.patch(
        f"{BASE_URL}/videos/{video_id}/task/{task_id}",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"transcriptApproved": True},
        timeout=30,
    )
    print(f"  승인 응답 ({res.status_code}): {res.text[:200]}")
    res.raise_for_status()


def poll_task(api_key, video_id, task_id):
    print(f"\n=== 처리 대기 중 ===")
    approved = False
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        res = requests.get(
            f"{BASE_URL}/videos/{video_id}/task/{task_id}",
            headers={"x-api-key": api_key},
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
        status = data.get("status", "")
        print(f"  [{elapsed}s] {status}")

        if data.get("downloadUrl"):
            print("  다운로드 URL 확인!")
            return data["downloadUrl"]

        # 트랜스크립션 완료 → 자동 승인 후 렌더링 시작
        if status == "transcriptionCompleted" and not approved:
            approve_transcript(api_key, video_id, task_id)
            approved = True

        if status in ("failed", "error"):
            raise Exception(f"ZapCap 처리 실패: {data}")

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise Exception(f"타임아웃: {POLL_TIMEOUT}초 초과")


def download_video(url, api_key):
    print(f"\n=== 최종 영상 다운로드 중 ===")
    res = requests.get(
        url,
        headers={"x-api-key": api_key},
        stream=True,
        timeout=120,
    )
    res.raise_for_status()

    total = int(res.headers.get("content-length", 0))
    downloaded = 0
    with open(OUTPUT_FILE, "wb") as f:
        for chunk in res.iter_content(chunk_size=1024 * 64):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                print(f"\r  {downloaded/total*100:.1f}% ({downloaded//1024}KB/{total//1024}KB)", end="")
    print()


def main():
    api_key = get_api_key()

    video_id = upload_video(api_key)
    task_id = create_task(api_key, video_id)
    download_url = poll_task(api_key, video_id, task_id)

    download_video(download_url, api_key)

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\n{OUTPUT_FILE} 저장 완료 ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
