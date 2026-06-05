"""BOJ 시계열통계검색사이트 API fetch 모듈

사용법:
  # 모듈로 import
  from data.boj_fetch import fetch_series, fetch_metadata
  data = fetch_series("FM08", "FM08'FFCBKCBAM@MB")   # 기본 60개월
  meta = fetch_metadata("FM08")                        # DB 내 시리즈 목록

  # CLI
  python -m data.boj_fetch --meta FM08                 # Step A: 메타데이터 목록
  python -m data.boj_fetch FM08 <code>                 # Step B: 시계열 fetch
  python -m data.boj_fetch FM08 <code> --months 24
  python -m data.boj_fetch FM08 <code> --no-cache

주의: 高頻度アクセス 금지 (BOJ 매뉴얼 Ⅰ.2). --no-cache 남용 금지.
"""
import sys
import os
import re
import json
import time
import datetime
import argparse

import requests

sys.stdout.reconfigure(encoding="utf-8")

# ===== 상수 =====
BOJ_BASE_URL     = "https://www.stat-search.boj.or.jp/api/v1"
CACHE_DIR        = os.path.join(os.path.dirname(__file__), "cache")
DEFAULT_MONTHS   = 60
REQUEST_TIMEOUT  = 30        # 초
RETRY_WAIT_SEC   = 30        # 高頻度アクセス 금지 — 재시도 전 대기
MAX_RETRY        = 1
HEADERS          = {"Accept-Encoding": "gzip"}   # BOJ 매뉴얼 Ⅰ.2 권장

# BOJ STATUS 코드
STATUS_OK        = 200
STATUS_PARAM_ERR = 400
STATUS_UNEXPECTED= 500
STATUS_DB_ERR    = 503


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _code_safe(code: str) -> str:
    """시리즈 코드의 특수문자(', @, / 등)를 _ 로 치환해 파일명 안전 문자열로."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", code)


def _cache_path_series(db: str, code: str) -> str:
    """시계열 캐시 파일 경로: data/cache/boj_{db}_{code_safe}_{YYYY-MM}.json"""
    month_tag = datetime.date.today().strftime("%Y-%m")
    return os.path.join(CACHE_DIR, f"boj_{db}_{_code_safe(code)}_{month_tag}.json")


def _cache_path_meta(db: str) -> str:
    """메타데이터 캐시 파일 경로: data/cache/boj_meta_{db}_{YYYY-MM}.json"""
    month_tag = datetime.date.today().strftime("%Y-%m")
    return os.path.join(CACHE_DIR, f"boj_meta_{db}_{month_tag}.json")


def _save_cache(path: str, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache(path: str):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _get(endpoint: str, params: dict) -> dict:
    """HTTP GET + STATUS=503/504/timeout 시 30초 대기 후 1회 재시도."""
    url = f"{BOJ_BASE_URL}/{endpoint}"
    last_err = None

    for attempt in range(MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()

            status = payload.get("STATUS", -1)
            if status == STATUS_DB_ERR:
                # BOJ STATUS=503: DB 접근 오류 → 재시도 대상
                if attempt < MAX_RETRY:
                    print(f"  [재시도] BOJ STATUS=503 — {RETRY_WAIT_SEC}초 대기 후 재시도...")
                    time.sleep(RETRY_WAIT_SEC)
                    continue
                print(f"[오류] BOJ STATUS=503: {payload.get('MESSAGE', '')}")
                sys.exit(1)

            if status == STATUS_PARAM_ERR:
                print(f"[오류] BOJ STATUS=400 파라미터 오류: {payload.get('MESSAGE', '')}")
                sys.exit(1)

            if status == STATUS_UNEXPECTED:
                print(f"[오류] BOJ STATUS=500 예기치 못한 오류: {payload.get('MESSAGE', '')}")
                sys.exit(1)

            return payload

        except requests.exceptions.Timeout:
            last_err = "ReadTimeout"
        except requests.exceptions.HTTPError as e:
            code_http = e.response.status_code if e.response else 0
            last_err = f"HTTP {code_http}"
            if code_http == 504 and attempt < MAX_RETRY:
                print(f"  [재시도] HTTP 504 — {RETRY_WAIT_SEC}초 대기 후 재시도...")
                time.sleep(RETRY_WAIT_SEC)
                continue
        except Exception as e:
            last_err = str(e)

        if attempt < MAX_RETRY:
            print(f"  [재시도] 네트워크 오류 ({last_err}) — {RETRY_WAIT_SEC}초 대기 후 재시도...")
            time.sleep(RETRY_WAIT_SEC)

    print(f"[오류] BOJ API 호출 실패: {last_err}")
    sys.exit(1)


def _normalize_date(raw: str) -> str:
    """BOJ 날짜 문자열을 가독성 있는 형식으로 정규화.
    6자리 YYYYMM   → YYYY-MM
    8자리 YYYYMMDD → YYYY-MM-DD
    그 외           → 원문 그대로
    """
    s = raw.strip()
    if len(s) == 6 and s.isdigit():
        return f"{s[:4]}-{s[4:]}"
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _start_date_str(months: int) -> str:
    """오늘로부터 months개월 전을 BOJ startDate 형식 YYYYMM으로 반환."""
    today = datetime.date.today()
    y = today.year - (months // 12)
    m = today.month - (months % 12)
    if m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}{m:02d}"


# ─────────────────────────────────────────
# 공개 함수
# ─────────────────────────────────────────

def fetch_metadata(db: str) -> list:
    """
    BOJ getMetadata API로 DB 내 시리즈 목록을 취득.
    캐시: 이번 달 캐시 있으면 API 호출 없이 즉시 반환.

    반환: [{"code", "name_j", "frequency", "unit_j"}, ...]
    """
    cache_path = _cache_path_meta(db)
    cached = _load_cache(cache_path)
    if cached:
        print(f"  [캐시] 메타데이터 {db} — {cache_path}")
        return cached

    print(f"  [BOJ] getMetadata DB={db} 취득 중...")
    payload = _get("getMetadata", {"db": db, "format": "json", "lang": "JP"})

    # 실제 응답: 최상위 RESULTSET 키 (DATA.SERIES_DEFINITION 아님)
    # SERIES_CODE 비어있는 항목은 카테고리 헤더행 → 제외
    raw_list = payload.get("RESULTSET", [])
    series_list = [s for s in raw_list if s.get("SERIES_CODE", "")]
    if not series_list:
        print(f"[오류] DB={db} 에서 시리즈를 찾을 수 없습니다. DB명을 확인하세요.")
        sys.exit(1)

    result = [
        {
            "code":      s.get("SERIES_CODE", ""),
            "name_j":    s.get("NAME_OF_TIME_SERIES_J", ""),
            "frequency": s.get("FREQUENCY", ""),
            "unit_j":    s.get("UNIT_J", ""),
        }
        for s in series_list
    ]

    _save_cache(cache_path, result)
    print(f"  [저장] {cache_path}")
    return result


def fetch_series(db: str, code: str, months: int = DEFAULT_MONTHS) -> dict:
    """
    BOJ getDataCode API로 시계열 데이터를 취득해 dict로 반환.
    이번 달 캐시가 있으면 캐시에서 즉시 반환 (API 호출 없음).

    반환 dict 구조 (FRED 호환 공통 스키마):
      series_id    : "{db}/{code}"
      db           : str
      code         : str
      title        : str (NAME_OF_TIME_SERIES_J 원문 — 번역 금지)
      frequency    : str
      unit         : str (UNIT_J 원문)
      fetched_at   : str (YYYY-MM-DD)
      latest_date  : str
      latest_value : float | None
      observations : list[{"date": str, "value": float}]
    """
    cache_path = _cache_path_series(db, code)
    cached = _load_cache(cache_path)
    if cached:
        print(f"  [캐시] {db}/{code} — {cache_path}")
        return cached

    start = _start_date_str(months)
    print(f"  [BOJ] getDataCode db={db} code={code} (start={start}) 取得中...")

    payload = _get(
        "getDataCode",
        {"db": db, "code": code, "format": "json", "lang": "JP", "startDate": start},
    )

    # 실제 응답: 최상위 RESULTSET 키
    series_list = payload.get("RESULTSET", [])
    if not series_list:
        print(f"[오류] db={db} code={code} — 데이터가 없습니다. 코드가 올바른지 확인하세요.")
        sys.exit(1)

    s = series_list[0]   # 단일 시리즈 요청이므로 [0] 확정

    # VALUES 딕셔너리 안에 SURVEY_DATES(정수 리스트)와 VALUES(값 리스트)가 중첩
    vals_block = s.get("VALUES", {})
    dates  = vals_block.get("SURVEY_DATES", [])
    values = vals_block.get("VALUES", [])

    # NEXTPOSITION은 최상위 키 (None이면 데이터 누락 없음)
    if payload.get("NEXTPOSITION") is not None:
        print(f"  [경고] NEXTPOSITION={payload['NEXTPOSITION']} — 데이터가 잘렸습니다. --months를 줄이거나 페이지네이션 구현을 검토하세요.")

    # null 결측값 제외 후 observations 구성
    # SURVEY_DATES는 정수(예: 20250101) → str 변환 후 _normalize_date 적용
    observations = []
    for d, v in zip(dates, values):
        if v is None:
            continue
        try:
            observations.append({"date": _normalize_date(str(d)), "value": float(v)})
        except (TypeError, ValueError):
            continue

    if not observations:
        print(f"[오류] db={db} code={code} — 유효한 observation이 없습니다.")
        sys.exit(1)

    latest = observations[-1]
    data = {
        "series_id":    f"{db}/{code}",
        "db":           db,
        "code":         code,
        "title":        s.get("NAME_OF_TIME_SERIES_J", ""),
        "frequency":    s.get("FREQUENCY", ""),
        "unit":         s.get("UNIT_J", ""),
        "fetched_at":   datetime.date.today().isoformat(),
        "latest_date":  latest["date"],
        "latest_value": latest["value"],
        "observations": observations,
    }

    _save_cache(cache_path, data)
    print(f"  [저장] {cache_path}")
    return data


# ─────────────────────────────────────────
# 콘솔 검수 표 출력
# ─────────────────────────────────────────

def print_meta_table(meta: list, db: str, filter_kw: str = None):
    """메타데이터 검수 표 출력. filter_kw 지정 시 name_j에 해당 키워드 포함 시리즈만."""
    if filter_kw:
        rows = [m for m in meta if filter_kw in m["name_j"]]
        label = f"(「{filter_kw}」포함 필터)"
    else:
        rows = meta
        label = ""

    print()
    print("=" * 80)
    print(f"=== BOJ 메타데이터 — DB: {db} {label} ===")
    print(f"총 {len(rows)}개 시리즈 표시 / 전체 {len(meta)}개")
    print("=" * 80)
    print(f"{'SERIES_CODE':<35} {'FREQ':<12} NAME_OF_TIME_SERIES_J")
    print("-" * 80)
    for m in rows:
        code_col = m["code"][:34]
        freq_col = m["frequency"][:11]
        name_col = m["name_j"]
        print(f"{code_col:<35} {freq_col:<12} {name_col}")
    print("=" * 80)


def print_review_table(data: dict):
    """시계열 검수 표 출력."""
    latest_5 = data["observations"][-5:]
    print()
    print("=" * 60)
    print("=== BOJ 검수 표 ===")
    print("=" * 60)
    print(f"db        : {data['db']}")
    print(f"code      : {data['code']}")
    print(f"title     : {data['title']}")
    print(f"frequency : {data['frequency']}")
    print(f"unit      : {data['unit']}")
    print(f"fetched_at: {data['fetched_at']}")
    print(f"최신값    : {data['latest_value']}  ({data['latest_date']})")
    print("최신 5개  :")
    for obs in latest_5:
        print(f"  {obs['date']}   {obs['value']}")
    print(f"총 {len(data['observations']):,}개 observation")
    cache = _cache_path_series(data["db"], data["code"])
    print(f"캐시      : {cache}")
    print("=" * 60)


# ─────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BOJ 시계열 fetch + 검수 표 출력")
    parser.add_argument("--meta", metavar="DB",
                        help="메타데이터 취득: DB 내 시리즈 목록 출력 (예: --meta FM08)")
    parser.add_argument("db", nargs="?", help="BOJ DB 코드 (예: FM08)")
    parser.add_argument("code", nargs="?", help="BOJ 시리즈 코드")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS,
                        help=f"취득 기간 개월수 (기본값: {DEFAULT_MONTHS})")
    parser.add_argument("--no-cache", action="store_true",
                        help="캐시 무시하고 강제 재fetch (高頻度アクセス 금지 주의)")
    args = parser.parse_args()

    # ── Step A: 메타데이터 모드 ──
    if args.meta:
        db = args.meta
        cache_path = _cache_path_meta(db)
        if args.no_cache and os.path.exists(cache_path):
            os.remove(cache_path)
            print(f"  [캐시 삭제] {cache_path}")
        meta = fetch_metadata(db)
        # FM08 실행 시 USD/JPY 후보 자동 필터 표시
        print_meta_table(meta, db, filter_kw="ドル")
        if not any("ドル" in m["name_j"] for m in meta):
            print("  ※ 「ドル」 포함 시리즈 없음 — 전체 목록:")
            print_meta_table(meta, db)
        return

    # ── Step B: 시계열 fetch 모드 ──
    if not args.db or not args.code:
        parser.print_help()
        sys.exit(1)

    cache_path = _cache_path_series(args.db, args.code)
    if args.no_cache and os.path.exists(cache_path):
        os.remove(cache_path)
        print(f"  [캐시 삭제] {cache_path}")

    data = fetch_series(args.db, args.code, months=args.months)
    print_review_table(data)


if __name__ == "__main__":
    main()
