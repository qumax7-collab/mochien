"""
issue1 TTS 섹션만 재생성 + 전체 concat 갱신.
intro / issue2 / outro 음성 파일은 무변경 재사용.
"""
import sys
import os
import re

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import json
sys.path.insert(0, ".")

from long2_tts import (
    record_issue_tts,
    concat_audio,
    build_chapters,
    VOICE_LONG_FILE,
    LONG_CHART_TIMESTAMPS_FILE,
    LONG_SCRIPT_FILE,
)

REUSE_SECTIONS = ["long_voice_intro.mp3", "long_voice_issue2.mp3", "long_voice_outro.mp3"]

_PCT_PAT  = re.compile(r'\d+\.?\d*[%％]')
_YEAR_MON = re.compile(r'20\d{2}年\d*月?')


def check_outro_dirty():
    """outro에 issue 수치(%)·연월이 잔류하는지 검사. 경고만, 중단 없음."""
    if not os.path.exists(LONG_SCRIPT_FILE):
        print("[outro 검사 건너뜀] long_script.json 없음")
        return

    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    issue_text = " ".join(
        data.get(k, {}).get("script", "") for k in ["issue1", "issue2"]
    )
    outro_text = data.get("outro", {}).get("script", "")

    issue_pcts  = set(_PCT_PAT.findall(issue_text))
    outro_pcts  = set(_PCT_PAT.findall(outro_text))
    issue_dates = set(_YEAR_MON.findall(issue_text))
    outro_dates = set(_YEAR_MON.findall(outro_text))

    dirty_pcts  = outro_pcts  - issue_pcts
    dirty_dates = outro_dates - issue_dates

    if dirty_pcts or dirty_dates:
        print("\n[⚠ outro dirty 검사 — 불일치 발견]")
        if dirty_pcts:
            print(f"  비율(%) outro에만 있음: {sorted(dirty_pcts)}")
            print(f"  issue1·2 비율:         {sorted(issue_pcts)}")
        if dirty_dates:
            print(f"  연월 outro에만 있음:   {sorted(dirty_dates)}")
            print(f"  issue1·2 연월:         {sorted(issue_dates)}")
        print("  → outro에 구 수치 잔류 가능성. 대본 확인 후 outro TTS를 재생성하세요.")
    else:
        print("\n[outro 검사 OK] 비율(%)·연월 일치 확인")


def main():
    api_key  = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        print("[오류] ELEVENLABS_API_KEY 또는 ELEVENLABS_VOICE_ID 미설정")
        sys.exit(1)

    # 재사용 파일 존재 확인
    for f in REUSE_SECTIONS:
        if not os.path.exists(f):
            print(f"[오류] 재사용 음성 파일 없음: {f}")
            sys.exit(1)
    print("재사용 파일 확인:", REUSE_SECTIONS)

    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # 기존 타임스탬프 로드
    ts_all = {}
    if os.path.exists(LONG_CHART_TIMESTAMPS_FILE):
        with open(LONG_CHART_TIMESTAMPS_FILE, encoding="utf-8") as f:
            ts_all = json.load(f)

    # issue1만 재생성
    print("\n=== issue1 TTS 재생성 ===")
    ts = record_issue_tts("issue1", data, voice_id, api_key)
    ts_all["issue1"] = ts

    with open(LONG_CHART_TIMESTAMPS_FILE, "w", encoding="utf-8") as f:
        json.dump(ts_all, f, ensure_ascii=False, indent=2)
    print(f"  타임코드 갱신 → {LONG_CHART_TIMESTAMPS_FILE}")

    # 4섹션 concat (intro + issue1_new + issue2 + outro)
    print(f"\n=== 섹션 연결 → {VOICE_LONG_FILE} ===")
    concat_audio(VOICE_LONG_FILE)
    size_mb = os.path.getsize(VOICE_LONG_FILE) / (1024 * 1024)
    print(f"  연결 완료 ({size_mb:.1f}MB)")

    build_chapters()

    print("\n=== outro dirty 검사 ===")
    check_outro_dirty()
    print("\n=== issue1 TTS 재생성 완료 ===")


if __name__ == "__main__":
    main()
