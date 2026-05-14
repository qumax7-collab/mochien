"""
ElevenLabs Pronunciation Dictionary 업로드 스크립트.

pronunciation.json을 읽어 alias 규칙으로 변환 후 ElevenLabs API에 업로드한다.
업로드 후 출력된 ID를 .env / GitHub Secrets에 등록하면 TTS 호출 시 자동 적용된다.

실행: python upload_pronunciation_dict.py
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

PRONUNCIATION_PATH = "pronunciation.json"
DICT_NAME = "mochien_pronunciation"
API_URL = "https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-rules"


def load_pronunciation():
    if not os.path.exists(PRONUNCIATION_PATH):
        print(f"[오류] {PRONUNCIATION_PATH} 파일이 없습니다.")
        sys.exit(1)
    with open(PRONUNCIATION_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_rules(mapping):
    """kanji→hiragana 매핑을 ElevenLabs alias 규칙 배열로 변환."""
    rules = []
    for kanji, hira in mapping.items():
        rules.append({
            "type": "alias",
            "string_to_replace": kanji,
            "alias": hira,
        })
    return rules


def upload(api_key, rules):
    payload = {
        "name": DICT_NAME,
        "rules": rules,
    }
    resp = requests.post(
        API_URL,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("[오류] .env에 ELEVENLABS_API_KEY가 없습니다.")
        sys.exit(1)

    print(f"=== {PRONUNCIATION_PATH} 로드 ===")
    mapping = load_pronunciation()
    print(f"  항목 수: {len(mapping)}개")

    rules = build_rules(mapping)
    print(f"\n=== ElevenLabs Pronunciation Dictionary 업로드 중... ===")
    result = upload(api_key, rules)

    dict_id = result.get("id", "")
    version_id = result.get("version_id", "")

    print(f"\n✅ 업로드 완료")
    print(f"  Dictionary ID : {dict_id}")
    print(f"  Version ID    : {version_id}")
    print()
    print("=" * 60)
    print("아래 내용을 .env 파일에 추가하세요:")
    print(f"  ELEVENLABS_PD_ID={dict_id}")
    print(f"  ELEVENLABS_PD_VERSION_ID={version_id}")
    print()
    print("GitHub Secrets에도 동일하게 등록하세요:")
    print("  ELEVENLABS_PD_ID")
    print("  ELEVENLABS_PD_VERSION_ID")
    print("=" * 60)


if __name__ == "__main__":
    main()
