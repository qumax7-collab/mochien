"""e-Stat API fetch 모듈 — 일본 정부통계포털 공공 1차 데이터 시계열 취득

사용법:
  # 모듈로 import
  from data.estat_fetch import fetch_series, fetch_metadata

  # CLI
  python -m data.estat_fetch --meta <statsDataId>
  python -m data.estat_fetch <statsDataId> --cat01 <code> [--cat02 <code>]
  python -m data.estat_fetch <statsDataId> --cat01 <code> --months 60
  python -m data.estat_fetch <statsDataId> --cat01 <code> --no-cache
"""
import sys
import os
import json
import time
import hashlib
import datetime
import argparse

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 상수 =====
ESTAT_BASE_URL   = "https://api.e-stat.go.jp/rest/3.0/app/json"
CACHE_DIR        = os.path.join(os.path.dirname(__file__), "cache")
DEFAULT_MONTHS   = 60
REQUEST_TIMEOUT  = 30
RETRY_WAIT_SEC   = 30
MAX_RETRY        = 1
STATUS_OK        = 0       # e-Stat RESULT.STATUS 정상값
STATUS_WARN_MIN  = 100     # 100번대: 경고 (계속 진행)
STATUS_ERR_MIN   = 200     # 200번대: 오류 (종료)


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

def _app_id() -> str:
    key = os.environ.get("ESTAT_APP_ID", "")
    if not key:
        print("[오류] ESTAT_APP_ID 환경변수가 설정되지 않았습니다.")
        print("       .env 파일에 ESTAT_APP_ID=<appId>를 추가하세요.")
        sys.exit(1)
    return key


def _to_list(obj) -> list:
    """e-Stat API는 항목 1개면 dict, 여러 개면 list 반환 → 항상 list로 정규화."""
    if obj is None:
        return []
    return obj if isinstance(obj, list) else [obj]


def _normalize_time(t) -> str:
    """e-Stat 시간 코드 → 날짜 문자열.

    통계마다 월 코드 위치가 다름:
      구형 (매월근로통계 등): YYYY + MM + 00 + 00  (s[4:6] 에 월)
        예: 2024010000 → '2024-01'
      신형 (가계조사 등):    YYYY + 00 + MM + MM  (s[6:8] 에 월)
        예: 2026000303 → '2026-03'
      연간:                  YYYY + 00 + 00 + 00
        예: 2024000000 → '2024'
    """
    s = str(t).strip()
    if len(s) < 6:
        return s
    year = s[0:4]
    a    = s[4:6] if len(s) >= 6 else "00"
    b    = s[6:8] if len(s) >= 8 else "00"
    if a != "00":
        return f"{year}-{a}"    # 구형: 월이 s[4:6]
    if b != "00":
        return f"{year}-{b}"    # 신형: 월이 s[6:8]
    return year                 # 연간


def _filter_hash(filters: dict) -> str:
    """차원 필터 dict를 정렬 후 MD5 해시 앞 8자 — 캐시 키용."""
    key_str = json.dumps(sorted(filters.items()), ensure_ascii=False)
    return hashlib.md5(key_str.encode()).hexdigest()[:8]


def _cache_path_series(stats_data_id: str, filters: dict) -> str:
    month_tag = datetime.date.today().strftime("%Y-%m")
    fhash = _filter_hash(filters) if filters else "nofilter"
    return os.path.join(CACHE_DIR, f"estat_{stats_data_id}_{fhash}_{month_tag}.json")


def _cache_path_meta(stats_data_id: str) -> str:
    month_tag = datetime.date.today().strftime("%Y-%m")
    return os.path.join(CACHE_DIR, f"estat_meta_{stats_data_id}_{month_tag}.json")


def _load_cache(path: str):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(path: str, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get(endpoint: str, params: dict) -> dict:
    """HTTP GET + HTTP 5xx 시 30초 대기 후 1회 재시도."""
    url = f"{ESTAT_BASE_URL}/{endpoint}"
    last_err = None
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            last_err = "ReadTimeout"
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response else 0
            last_err = f"HTTP {code}"
            if code >= 500 and attempt < MAX_RETRY:
                print(f"  [재시도] HTTP {code} — {RETRY_WAIT_SEC}초 대기...")
                time.sleep(RETRY_WAIT_SEC)
                continue
        except Exception as e:
            last_err = str(e)
        if attempt < MAX_RETRY:
            print(f"  [재시도] 오류 ({last_err}) — {RETRY_WAIT_SEC}초 대기...")
            time.sleep(RETRY_WAIT_SEC)
    print(f"[오류] e-Stat API 호출 실패: {last_err}")
    sys.exit(1)


def _check_status(result_block: dict, context: str = ""):
    """e-Stat RESULT 블록의 STATUS 검사. 200번대면 종료, 100번대면 경고 후 계속."""
    status = result_block.get("STATUS", -1)
    msg    = result_block.get("ERROR_MSG", "")
    if status == STATUS_OK:
        return
    if STATUS_WARN_MIN <= status < STATUS_ERR_MIN:
        print(f"  [경고] e-Stat STATUS={status} {context}: {msg}")
        return
    print(f"[오류] e-Stat STATUS={status} {context}: {msg}")
    sys.exit(1)


def _extract_title(table_inf: dict) -> str:
    """TABLE_INF에서 가독성 있는 제목 조합."""
    stat_name = table_inf.get("STAT_NAME", {})
    stat_str  = stat_name.get("$", "") if isinstance(stat_name, dict) else str(stat_name)
    title_obj = table_inf.get("TITLE", {})
    title_str = title_obj.get("$", "") if isinstance(title_obj, dict) else str(title_obj)
    if stat_str and title_str:
        return f"{stat_str} / {title_str}"
    return title_str or stat_str


# ─────────────────────────────────────────
# 공개 함수
# ─────────────────────────────────────────

def fetch_metadata(stats_data_id: str) -> dict:
    """
    e-Stat getMetaInfo API로 통계표 메타 정보 취득.
    캐시: 이번 달 캐시 있으면 API 호출 없이 즉시 반환.

    반환 dict:
      stats_data_id : str
      table_title   : str
      gov_org       : str
      updated_date  : str
      class_obj     : [{"id","name","unit","codes":[{"code","name"}]}]
    """
    cache_path = _cache_path_meta(stats_data_id)
    cached = _load_cache(cache_path)
    if cached:
        print(f"  [캐시] 메타 {stats_data_id} — {cache_path}")
        return cached

    print(f"  [e-Stat] getMetaInfo statsDataId={stats_data_id} 취득 중...")
    payload = _get("getMetaInfo", {"appId": _app_id(), "statsDataId": stats_data_id})

    root = payload.get("GET_META_INFO", {})
    _check_status(root.get("RESULT", {}), f"getMetaInfo {stats_data_id}")

    # 실제 응답: METADATA_INF (사양서의 STATISTICAL_DATA 아님)
    stat_data = root.get("METADATA_INF", {})
    table_inf = stat_data.get("TABLE_INF", {})

    gov_obj    = table_inf.get("GOV_ORG", {})
    gov_org    = gov_obj.get("$", "") if isinstance(gov_obj, dict) else str(gov_obj)
    updated    = table_inf.get("UPDATED_DATE", "")

    class_inf     = stat_data.get("CLASS_INF", {})
    class_obj_raw = _to_list(class_inf.get("CLASS_OBJ", []))

    class_obj = []
    for obj in class_obj_raw:
        codes = [
            {"code": c.get("@code", ""), "name": c.get("@name", "")}
            for c in _to_list(obj.get("CLASS", []))
        ]
        class_obj.append({
            "id":    obj.get("@id", ""),
            "name":  obj.get("@name", ""),
            "unit":  obj.get("@unit", ""),
            "codes": codes,
        })

    result = {
        "stats_data_id": stats_data_id,
        "table_title":   _extract_title(table_inf),
        "gov_org":       gov_org,
        "updated_date":  str(updated),
        "class_obj":     class_obj,
    }
    _save_cache(cache_path, result)
    print(f"  [저장] {cache_path}")
    return result


def fetch_series(stats_data_id: str, filters: dict,
                 months: int = DEFAULT_MONTHS) -> dict:
    """
    e-Stat getStatsData API로 시계열 데이터 취득.

    filters: {"cdCat01": "010", "cdCat02": "001", ...}
      → 차원당 코드 1개씩 지정. 동일 날짜에 값이 여러 개면 필터 부족 오류.

    반환 dict 구조 (FRED·BOJ 호환 공통 스키마):
      series_id    : "{statsDataId}/{filter_hash}"
      stats_data_id: str
      filters      : dict
      title        : str (일본어 원문)
      frequency    : "MONTHLY" | "ANNUAL"
      unit         : str (일본어 원문)
      fetched_at   : str
      latest_date  : str
      latest_value : float
      observations : [{"date": str, "value": float}]
    """
    cache_path = _cache_path_series(stats_data_id, filters)
    cached = _load_cache(cache_path)
    if cached:
        print(f"  [캐시] {stats_data_id} — {cache_path}")
        return cached

    print(f"  [e-Stat] getStatsData statsDataId={stats_data_id} filters={filters} 취득 중...")
    params = {"appId": _app_id(), "statsDataId": stats_data_id}
    params.update(filters)

    payload = _get("getStatsData", params)

    root = payload.get("GET_STATS_DATA", {})
    _check_status(root.get("RESULT", {}), f"getStatsData {stats_data_id}")

    # NEXT_KEY 경고 (데이터 잘림)
    if root.get("NEXT_KEY"):
        print(f"  [경고] NEXT_KEY={root['NEXT_KEY']} — 데이터가 잘렸습니다. 필터를 추가하거나 기간을 줄이세요.")

    stat_data  = root.get("STATISTICAL_DATA", {})
    table_inf  = stat_data.get("TABLE_INF", {})
    data_inf   = stat_data.get("DATA_INF", {})
    values_raw = _to_list(data_inf.get("VALUE", []))

    if not values_raw:
        print(f"[오류] statsDataId={stats_data_id} filters={filters}")
        print("       데이터가 없습니다. 필터 코드를 --meta로 확인 후 재지정하세요.")
        sys.exit(1)

    # unit 추출 (첫 번째 비어있지 않은 @unit)
    unit = ""
    for v in values_raw:
        u = v.get("@unit", "")
        if u:
            unit = u
            break

    # observations 구성 + 날짜 중복 검사
    obs_map: dict = {}
    duplicate_dates: set = set()
    for v in values_raw:
        raw_time = v.get("@time", "")
        raw_val  = v.get("$", None)
        if raw_val is None or raw_val in ("", "-"):
            continue
        try:
            val_float = float(raw_val)
        except (TypeError, ValueError):
            continue
        date_str = _normalize_time(raw_time)
        if date_str in obs_map:
            duplicate_dates.add(date_str)
        obs_map[date_str] = val_float

    if duplicate_dates:
        examples = sorted(duplicate_dates)[:3]
        print(f"[오류] 동일 날짜에 여러 값이 존재합니다 (필터 코드 부족).")
        print(f"  중복 날짜 예시: {examples}")
        print(f"  python -m data.estat_fetch --meta {stats_data_id} 로 차원 코드를 확인해 필터를 추가하세요.")
        sys.exit(1)

    # 날짜 오름차순 정렬
    observations = [{"date": d, "value": v} for d, v in sorted(obs_map.items())]

    # months 필터링 (Python side — 최근 N개월만 유지)
    if months and observations:
        today = datetime.date.today()
        cy = today.year - (months // 12)
        cm = today.month - (months % 12)
        if cm <= 0:
            cm += 12
            cy -= 1
        cutoff = f"{cy:04d}-{cm:02d}"
        observations = [
            o for o in observations
            if o["date"] >= cutoff or len(o["date"]) == 4  # 연간 데이터는 유지
        ]

    if not observations:
        print(f"[오류] 필터 후 유효한 observation이 없습니다.")
        sys.exit(1)

    # frequency 추론 — 원시 time 코드 대신 정규화된 날짜 길이로 판정
    # (time 코드 위치가 통계마다 달라 raw 코드 직접 파싱은 오판 위험)
    frequency = "ANNUAL" if observations and len(observations[0]["date"]) == 4 else "MONTHLY"

    latest = observations[-1]
    data = {
        "series_id":      f"{stats_data_id}/{_filter_hash(filters)}",
        "stats_data_id":  stats_data_id,
        "filters":        filters,
        "title":          _extract_title(table_inf),
        "frequency":      frequency,
        "unit":           unit,
        "fetched_at":     datetime.date.today().isoformat(),
        "latest_date":    latest["date"],
        "latest_value":   latest["value"],
        "observations":   observations,
    }
    _save_cache(cache_path, data)
    print(f"  [저장] {cache_path}")
    return data


# ─────────────────────────────────────────
# 통계표 검색
# ─────────────────────────────────────────

def search_stats_list(search_word: str, stats_code: str = None,
                      survey_years: str = None) -> list:
    """
    e-Stat getStatsList API로 통계표 목록 검색.

    search_word : 검색 키워드 (예: "実質賃金")
    stats_code  : 정부통계코드 필터 (예: "00450071")
    survey_years: 조사년월 필터 (예: "2025-2026" / None이면 전체)

    반환: [{stats_data_id, stat_name, title, gov_org, cycle,
             survey_date, updated_date}, ...]
    """
    params = {"appId": _app_id()}
    if search_word:
        params["searchWord"] = search_word
    if stats_code:
        params["statsCode"] = stats_code
    if survey_years:
        params["surveyYears"] = survey_years

    print(f"  [e-Stat] getStatsList 검색: word='{search_word}'"
          f"{' code=' + stats_code if stats_code else ''}"
          f"{' years=' + survey_years if survey_years else ''}")

    payload = _get("getStatsList", params)

    root     = payload.get("GET_STATS_LIST", {})
    _check_status(root.get("RESULT", {}), "getStatsList")

    datalist   = root.get("DATALIST_INF", {})
    tables_raw = _to_list(datalist.get("TABLE_INF", []))

    if not tables_raw:
        # 구조 불일치 시 진단 정보 출력
        print(f"  [진단] GET_STATS_LIST 키: {list(root.keys())}")
        print(f"  [진단] DATALIST_INF 키: {list(datalist.keys()) if isinstance(datalist, dict) else type(datalist)}")

    results = []
    for t in tables_raw:
        title_obj = t.get("TITLE", {})
        title     = title_obj.get("$", "") if isinstance(title_obj, dict) else str(title_obj)

        stat_name_obj = t.get("STAT_NAME", {})
        stat_name = stat_name_obj.get("$", "") if isinstance(stat_name_obj, dict) else str(stat_name_obj)

        gov_obj = t.get("GOV_ORG", {})
        gov_org = gov_obj.get("$", "") if isinstance(gov_obj, dict) else str(gov_obj)

        results.append({
            "stats_data_id": t.get("@id", ""),
            "stat_name":     stat_name,
            "title":         title,
            "gov_org":       gov_org,
            "cycle":         t.get("CYCLE", ""),
            "survey_date":   str(t.get("SURVEY_DATE", "")),
            "updated_date":  str(t.get("UPDATED_DATE", "")),
        })

    return results


# ─────────────────────────────────────────
# 콘솔 검수 표 출력
# ─────────────────────────────────────────

def print_search_table(results: list, search_word: str, stats_code: str = None):
    """통계표 검색 결과 표 출력."""
    label = f"'{search_word}'"
    if stats_code:
        label += f" (통계코드: {stats_code})"

    print()
    print("=" * 95)
    print(f"=== e-Stat 통계표 검색 결과: {label} ===")
    print(f"총 {len(results)}개")
    print("=" * 95)
    print(f"{'statsDataId':<14} {'갱신일':<12} {'기간':<10} {'月':<4} 표제")
    print("-" * 95)
    for r in results:
        sid      = r["stats_data_id"]
        upd      = str(r["updated_date"])[:10]
        survey   = str(r["survey_date"])[:9]
        is_month = "●" if r["cycle"] == "月次" else " "
        full_title = (r["stat_name"] + " / " + r["title"]).strip(" /")
        title_disp = full_title[:58] + ("…" if len(full_title) > 58 else "")
        print(f"{sid:<14} {upd:<12} {survey:<10} {is_month:<4} {title_disp}")
    print("=" * 95)
    print("● = 月次(월별)  / 선택 후: python -m data.estat_fetch --meta <statsDataId>")
    print("=" * 95)


def print_meta_table(meta: dict):
    """메타 검수 표 — 차원별 코드 목록 출력."""
    sid = meta["stats_data_id"]
    print()
    print("=" * 70)
    print(f"=== e-Stat メタ情報 — statsDataId: {sid} ===")
    print("=" * 70)
    print(f"제목   : {meta['table_title']}")
    print(f"기관   : {meta['gov_org']}")
    print(f"갱신일 : {meta['updated_date']}")

    for obj in meta["class_obj"]:
        oid   = obj["id"]
        oname = obj["name"]
        codes = obj["codes"]

        print()
        print(f"[{oid}] {oname} — 총 {len(codes)}개")

        if oid == "time":
            # 시간 차원: 최신 5개만 표시
            print(f"  (최신 5개)")
            for c in codes[-5:]:
                print(f"  {c['code']}  ->  {_normalize_time(c['code'])}  ({c['name']})")
        else:
            print(f"  {'코드':<14} 이름")
            print(f"  {'-'*13} {'-'*40}")
            for c in codes:
                print(f"  {c['code']:<14} {c['name']}")

    print()
    print("=" * 70)
    print(f"Step B 예시: python -m data.estat_fetch {sid} --cat01 <코드> --cat02 <코드> ...")
    print("=" * 70)


def print_review_table(data: dict):
    """시계열 검수 표 출력."""
    latest_5 = data["observations"][-5:]
    cache     = _cache_path_series(data["stats_data_id"], data["filters"])
    filters_str = ", ".join(f"{k}={v}" for k, v in data["filters"].items())

    print()
    print("=" * 60)
    print("=== e-Stat 검수 표 ===")
    print("=" * 60)
    print(f"statsDataId : {data['stats_data_id']}")
    print(f"filters     : {filters_str}")
    print(f"title       : {data['title']}")
    print(f"frequency   : {data['frequency']}")
    print(f"unit        : {data['unit']}")
    print(f"fetched_at  : {data['fetched_at']}")
    print(f"최신값      : {data['latest_value']}  ({data['latest_date']})")
    print("최신 5개    :")
    for obs in latest_5:
        print(f"  {obs['date']}   {obs['value']}")
    print(f"총 {len(data['observations']):,}개 observation")
    print(f"캐시        : {cache}")
    print("=" * 60)


# ─────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="e-Stat 시계열 fetch + 검수 표 출력")
    parser.add_argument("--search", metavar="KEYWORD",
                        help="통계표 검색 (예: --search 実質賃金)")
    parser.add_argument("--code", metavar="STATS_CODE", default=None,
                        help="정부통계코드 필터 (예: --code 00450071)")
    parser.add_argument("--meta", metavar="STATS_DATA_ID",
                        help="메타 정보 취득: 차원 코드 목록 출력")
    parser.add_argument("stats_data_id", nargs="?", help="통계표ID (10자리)")
    # cat01~cat09 차원 필터 (e-Stat 대부분 데이터셋에서 충분)
    for i in range(1, 10):
        cid = f"cat{i:02d}"
        parser.add_argument(f"--{cid}", default=None, metavar="CODE",
                            help=f"cdCat{i:02d} 차원 코드 필터")
    parser.add_argument("--area", default=None, metavar="CODE",
                        help="cdArea 지역 코드 필터 (예: --area 00000 全国)")
    parser.add_argument("--tab", default=None, metavar="CODE",
                        help="cdTab 차원 코드 필터 (예: --tab 3 → 前年同月比)")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS,
                        help=f"취득 기간 개월수 (기본값: {DEFAULT_MONTHS})")
    parser.add_argument("--no-cache", action="store_true",
                        help="캐시 무시하고 강제 재fetch")
    args = parser.parse_args()

    # ── 검색 모드 ─────────────────────────────
    if args.search:
        today = datetime.date.today()
        # surveyYears 형식: YYYYMM-YYYYMM (YYYY-YYYY는 STATUS=102 오류)
        survey_years = f"{today.year - 1}{today.month:02d}-{today.year}{today.month:02d}"
        results = search_stats_list(
            args.search,
            stats_code=args.code,
            survey_years=survey_years,
        )
        if not results:
            # 최근 1년 필터로 결과 없으면 필터 제거해 재시도
            print("  [재시도] surveyYears 필터 없이 전체 검색...")
            results = search_stats_list(args.search, stats_code=args.code)
        print_search_table(results, args.search, stats_code=args.code)
        return

    # ── Step A: 메타 모드 ──────────────────────
    if args.meta:
        sid = args.meta
        cache_path = _cache_path_meta(sid)
        if args.no_cache and os.path.exists(cache_path):
            os.remove(cache_path)
            print(f"  [캐시 삭제] {cache_path}")
        meta = fetch_metadata(sid)
        print_meta_table(meta)
        return

    # ── Step B: 시계열 fetch 모드 ──────────────
    if not args.stats_data_id:
        parser.print_help()
        sys.exit(1)

    # 차원 필터 수집
    filters = {}
    for i in range(1, 10):
        cid = f"cat{i:02d}"
        val = getattr(args, cid, None)
        if val:
            filters[f"cd{cid.capitalize()}"] = val  # cdCat01, cdCat02, ...

    # cdCatNN → 실제 파라미터명은 cdCat01 (대소문자)
    # argparse attribute: cat01 → cdCat01
    # capitalize() 가 'Cat01' → 'cdCat01' 이 되어야 함 → 수동 조합
    filters = {}
    for i in range(1, 10):
        attr = f"cat{i:02d}"
        val  = getattr(args, attr, None)
        if val:
            filters[f"cdCat{i:02d}"] = val
    if getattr(args, "area", None):
        filters["cdArea"] = args.area
    if getattr(args, "tab", None):
        filters["cdTab"] = args.tab

    sid = args.stats_data_id
    cache_path = _cache_path_series(sid, filters)
    if args.no_cache and os.path.exists(cache_path):
        os.remove(cache_path)
        print(f"  [캐시 삭제] {cache_path}")

    data = fetch_series(sid, filters, months=args.months)
    print_review_table(data)


if __name__ == "__main__":
    main()
