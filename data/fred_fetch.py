"""FRED API fetch 모듈 — 공공 1차 데이터 시계열 취득

사용법:
  # 모듈로 import
  from data.fred_fetch import fetch_series
  data = fetch_series("DEXJPUS")          # 기본 60개월
  data = fetch_series("JPCPIALLMINMEI", months=120)  # 10년

  # CLI 검증 실행
  python -m data.fred_fetch DEXJPUS
  python -m data.fred_fetch DEXJPUS --months 24
"""
import sys
import os
import json
import datetime
import argparse

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 상수 =====
FRED_BASE_URL        = "https://api.stlouisfed.org/fred/series"
CACHE_DIR            = os.path.join(os.path.dirname(__file__), "cache")
DEFAULT_MONTHS       = 60
REQUEST_TIMEOUT      = 30    # 초 (FRED API 응답 지연 대비)
MAX_RETRY            = 1     # _get() 내부 즉시 재시도 횟수
RETRYABLE_HTTP_CODES = {503, 504}   # 일시 장애 코드 — 코드·키 문제와 구분용


# ─────────────────────────────────────────
# 예외 클래스
# ─────────────────────────────────────────

class _FredTransientError(Exception):
    """FRED API 일시 장애 — 재시도 가능 (504 / ReadTimeout / ConnectionError)."""


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        print("[오류] FRED_API_KEY 환경변수가 설정되지 않았습니다.")
        print("       .env 파일에 FRED_API_KEY=<32자 키>를 추가하세요.")
        sys.exit(1)
    return key


def _cache_path(series_id: str) -> str:
    """캐시 파일 경로: data/cache/{series_id}_{YYYY-MM}.json"""
    month_tag = datetime.date.today().strftime("%Y-%m")
    return os.path.join(CACHE_DIR, f"{series_id}_{month_tag}.json")


def _load_cache(series_id: str) -> dict | None:
    """이번 달 캐시 있으면 반환, 없으면 None."""
    path = _cache_path(series_id)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(series_id: str, data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(series_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get(url: str, params: dict) -> dict:
    """HTTP GET + 즉시 재시도 1회.

    재시도 가능 오류(504/ReadTimeout/ConnectionError)가 모든 재시도 후에도
    해결되지 않으면 _FredTransientError를 raise.
    코드·키 문제(400/401/403/404)는 즉시 sys.exit(1).
    """
    last_err: str = ""
    is_transient = False

    for attempt in range(MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            last_err = "ReadTimeout"
            is_transient = True

        except requests.exceptions.ConnectionError as e:
            last_err = f"ConnectionError ({e})"
            is_transient = True

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response else 0
            last_err = f"HTTP {code}"
            if code in RETRYABLE_HTTP_CODES:
                is_transient = True
            else:
                # 400/401/403/404 — 키·코드 문제, 재시도 무의미
                print(f"[오류] FRED API 호출 실패: {last_err}")
                sys.exit(1)

        except Exception as e:
            last_err = str(e)
            is_transient = False

        if attempt < MAX_RETRY:
            print(f"  [재시도] {last_err} - 재시도 중...")

    # 모든 즉시 재시도 소진
    if is_transient:
        raise _FredTransientError(last_err)
    print(f"[오류] FRED API 호출 실패: {last_err}")
    sys.exit(1)


def _fetch_meta(series_id: str, api_key: str) -> dict:
    """시리즈 메타정보(title, frequency, units) 취득."""
    payload = _get(
        f"{FRED_BASE_URL}",
        {"series_id": series_id, "api_key": api_key, "file_type": "json"},
    )
    if "error_message" in payload:
        print(f"[오류] FRED 시리즈 오류: {payload['error_message']}")
        print(f"       series_id '{series_id}' 가 존재하지 않거나 오타일 수 있습니다.")
        sys.exit(1)
    srs = payload["seriess"][0]
    return {
        "title":     srs["title"],
        "frequency": srs["frequency_short"],
        "units":     srs["units"],
    }


def _fetch_observations(series_id: str, api_key: str, observation_start: str) -> list:
    """observation_start 이후 전체 시계열 취득. 결측값(.)은 제외."""
    payload = _get(
        f"{FRED_BASE_URL}/observations",
        {
            "series_id":         series_id,
            "api_key":           api_key,
            "file_type":         "json",
            "observation_start": observation_start,
            "sort_order":        "asc",
        },
    )
    if "error_message" in payload:
        print(f"[오류] FRED observations 오류: {payload['error_message']}")
        sys.exit(1)

    return [
        {"date": obs["date"], "value": float(obs["value"])}
        for obs in payload["observations"]
        if obs["value"] != "."          # FRED 결측값은 문자열 "." 로 표시됨
    ]


# ─────────────────────────────────────────
# 공개 함수
# ─────────────────────────────────────────

def fetch_series(series_id: str, months: int = DEFAULT_MONTHS) -> dict:
    """
    FRED 시계열 데이터를 취득해 dict로 반환.
    이번 달 캐시가 있으면 캐시에서 즉시 반환 (API 호출 없음).

    반환 dict 구조:
      series_id    : str
      title        : str (FRED 원문 영어 — 번역 금지)
      frequency    : str ("D" / "M" / "Q" / "A" 등)
      units        : str
      fetched_at   : str (YYYY-MM-DD)
      latest_date  : str
      latest_value : float
      observations : list[{"date": str, "value": float}]
    """
    cached = _load_cache(series_id)
    if cached:
        print(f"  [캐시] {series_id} — data/cache/{series_id}_{datetime.date.today().strftime('%Y-%m')}.json")
        return cached

    api_key = _api_key()

    today = datetime.date.today()
    start_year  = today.year - (months // 12)
    start_month = today.month - (months % 12)
    if start_month <= 0:
        start_month += 12
        start_year  -= 1
    observation_start = f"{start_year:04d}-{start_month:02d}-01"

    print(f"  [FRED] {series_id} fetch 중... (start: {observation_start})")

    try:
        meta = _fetch_meta(series_id, api_key)
        obs  = _fetch_observations(series_id, api_key, observation_start)
    except _FredTransientError as e:
        print(f"FRED API 일시 장애로 보임 ({e}). 잠시 후 python -m data.fred_fetch {series_id} 재실행하세요.")
        sys.exit(1)

    if not obs:
        print(f"[오류] {series_id}: 해당 기간에 데이터가 없습니다 (start={observation_start}).")
        sys.exit(1)

    latest = obs[-1]
    data = {
        "series_id":    series_id,
        "title":        meta["title"],
        "frequency":    meta["frequency"],
        "units":        meta["units"],
        "fetched_at":   today.isoformat(),
        "latest_date":  latest["date"],
        "latest_value": latest["value"],
        "observations": obs,
    }

    _save_cache(series_id, data)
    print(f"  [저장] {_cache_path(series_id)}")
    return data


# ─────────────────────────────────────────
# 콘솔 검수 표 출력
# ─────────────────────────────────────────

def print_review_table(data: dict):
    """운영자 검수용 콘솔 출력."""
    latest_5 = data["observations"][-5:]
    print()
    print("=" * 50)
    print("=== FRED 검수 표 ===")
    print("=" * 50)
    print(f"series_id : {data['series_id']}")
    print(f"title     : {data['title']}")
    print(f"frequency : {data['frequency']}")
    print(f"units     : {data['units']}")
    print(f"fetched_at: {data['fetched_at']}")
    print(f"최신값    : {data['latest_value']}  ({data['latest_date']})")
    print(f"최신 5개  :")
    for obs in latest_5:
        print(f"  {obs['date']}   {obs['value']}")
    print(f"총 {len(data['observations']):,}개 observation")
    print(f"캐시      : {_cache_path(data['series_id'])}")
    print("=" * 50)


# ─────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FRED 시계열 fetch + 검수 표 출력")
    parser.add_argument("series_id", help="FRED 시리즈 ID (예: DEXJPUS)")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS,
                        help=f"취득 기간(개월, 기본값: {DEFAULT_MONTHS})")
    parser.add_argument("--no-cache", action="store_true",
                        help="캐시 무시하고 강제 재fetch")
    args = parser.parse_args()

    if args.no_cache:
        path = _cache_path(args.series_id)
        if os.path.exists(path):
            os.remove(path)
            print(f"  [캐시 삭제] {path}")

    data = fetch_series(args.series_id, months=args.months)
    print_review_table(data)


if __name__ == "__main__":
    main()
