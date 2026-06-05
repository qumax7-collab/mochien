# 롱폼 깊이 개선 Work 1 — 食料CPI 데이터 fetch 확장

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** e-Stat CPI 5개 분류(総合·食料·生鮮食品·エネルギー·コアコア·穀類)를 topic_bank.json에 추가하고, `build_data_block`이 12개월 추이·과거 비교를 포함한 풍부한 데이터 블록을 GPT에 전달하도록 long1_script.py를 확장한다.

**Architecture:**
- `topic_bank.json`: `food-prices` 토픽 추가 (status=hold, data_months=120, 6개 소스)
- `data/estat_fetch.py`: CLI에 `--tab` 인수 추가 (cdTab 필터 지원)
- `long1_script.py`: `build_data_block` 강화 — 단일 소스(기존 포맷 유지), 다중 소스(비교 스냅샷 + 추이 + 과거 비교)

**Tech Stack:** Python 3.14 / e-Stat API 3.0 (0003427113, cdTab=3 前年同月比) / OpenAI gpt-4.1 (장기 미변경)

---

## 사전 확인된 검증 결과 (라이브 fetch 완료)

모든 시리즈: statsDataId=0003427113, cdTab=3, cdArea=00000, 119개 observation(10년치), 2026-04 최신

| cdCat01 | 항목 | 최신값(2026-04) | 비고 |
|---------|------|----------------|------|
| 0001 | 総合 | +1.4% | 기존 inflation-deflation에 사용 중 |
| 0002 | 食料 | +3.5% | **[주] 장바구니 전체** |
| 0157 | 生鮮食品 | +0.3% | 신선식품, 기상·수입 변동 |
| 0167 | エネルギー | -3.9% | 에너지, 식품 생산비용 압력 |
| 0178 | コアコア (生鮮食品·エネルギー除く) | +1.9% | 국내 수요 기반 인플레 |
| 0003 | 穀類 | +1.2% (2025-12: 14.7%) | 쌀·밀가루 포함 |

---

## Task 1: estat_fetch.py CLI에 `--tab` 인수 추가

**Files:**
- Modify: `data/estat_fetch.py:512-534` (main() 함수 argparse 블록)

단일 시리즈 CLI 검증에 cdTab 필터가 없어 불편함. `--tab` 인수 추가로 완결된 필터 지정 가능.

- [ ] **Step 1: argparse에 --tab 추가**

`data/estat_fetch.py`의 argparse 블록 (`parser.add_argument("--area"...` 다음 줄) 에 추가:

```python
parser.add_argument("--tab", default=None, metavar="CODE",
                    help="cdTab 차원 코드 필터 (예: --tab 3 → 前年同月比)")
```

그리고 아래 filters 수집 루프 (`if getattr(args, "area", None):` 직후) 에 추가:

```python
if getattr(args, "tab", None):
    filters["cdTab"] = args.tab
```

- [ ] **Step 2: 동작 검증**

```
python -m data.estat_fetch 0003427113 --tab 3 --cat01 0002 --area 00000 --months 12
```

Expected (검수 표 마지막 줄):
```
최신값      : 3.5  (2026-04)
총 12개 observation
```

- [ ] **Step 3: Commit**

```bash
git add data/estat_fetch.py
git commit -m "feat: estat_fetch CLI에 --tab cdTab 필터 인수 추가"
```

---

## Task 2: topic_bank.json — food-prices 토픽 추가

**Files:**
- Modify: `topic_bank.json` (topics 배열 끝에 추가)

- [ ] **Step 1: food-prices 항목 추가**

`topic_bank.json`의 `cashless-society` 항목 닫는 `}` 다음 줄에 `,` 를 추가하고 아래 항목 삽입 (배열 마지막 항목):

```json
{
  "id": "food-prices",
  "title_ja": "【Work 2で確定】なぜ食料品の値段は下がらないのか",
  "title_ko": "【Work 2 확정 전 임시】왜 장바구니 물가는 계속 오르는가",
  "principle": "【Work 2 운영자 확정 필요】",
  "keywords_ja": ["物価", "食料品", "米", "インフレ", "家計", "輸入", "円安", "食費", "穀物"],
  "chart_type": "line",
  "fred_code": null,
  "status": "hold",
  "status_reason": "Work 1 데이터 준비 완료 — Work 2 대기: principle·제목 운영자 확정 필요",
  "data_months": 120,
  "data_sources": [
    {
      "source": "estat",
      "stats_data_id": "0003427113",
      "filters": {"cdTab": "3", "cdCat01": "0002", "cdArea": "00000"},
      "desc_ko": "CPI 食料 前年同月比 (%) — 장바구니 전체",
      "primary": true
    },
    {
      "source": "estat",
      "stats_data_id": "0003427113",
      "filters": {"cdTab": "3", "cdCat01": "0001", "cdArea": "00000"},
      "desc_ko": "CPI 総合 前年同月比 (%) — 전체 물가 비교 기준",
      "primary": false
    },
    {
      "source": "estat",
      "stats_data_id": "0003427113",
      "filters": {"cdTab": "3", "cdCat01": "0157", "cdArea": "00000"},
      "desc_ko": "CPI 生鮮食品 前年同月比 (%) — 신선식품 (기상·수입 변동)",
      "primary": false
    },
    {
      "source": "estat",
      "stats_data_id": "0003427113",
      "filters": {"cdTab": "3", "cdCat01": "0167", "cdArea": "00000"},
      "desc_ko": "CPI エネルギー 前年同月比 (%) — 에너지비용 (식품 생산·유통 압력)",
      "primary": false
    },
    {
      "source": "estat",
      "stats_data_id": "0003427113",
      "filters": {"cdTab": "3", "cdCat01": "0178", "cdArea": "00000"},
      "desc_ko": "CPI コアコア(生鮮食品·エネルギー除く) 前年同月比 (%) — 국내 수요 기반 인플레",
      "primary": false
    },
    {
      "source": "estat",
      "stats_data_id": "0003427113",
      "filters": {"cdTab": "3", "cdCat01": "0003", "cdArea": "00000"},
      "desc_ko": "CPI 穀類 前年同月比 (%) — 쌀·밀가루 등",
      "primary": false
    }
  ]
}
```

- [ ] **Step 2: JSON 형식 검증**

```bash
python -c "import json; json.load(open('topic_bank.json', encoding='utf-8')); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add topic_bank.json
git commit -m "feat: food-prices 토픽 추가 (Work 1 데이터 준비 / status=hold)"
```

---

## Task 3: long1_script.py — build_data_block 강화

**Files:**
- Modify: `long1_script.py:37-38` (상수 블록)
- Modify: `long1_script.py:125-145` (`_fetch_source` 함수)
- Modify: `long1_script.py:148-210` (`build_data_block` 함수)

**설계 원칙:**
- **단일 소스 토픽** (기존 yen-rate, business-cycle 등): 기존 포맷 그대로 유지 (소급 없음)
- **다중 소스 토픽** (food-prices 등): 비교 스냅샷 + 주 소스 풍부 포맷 + 보조 소스 압축 포맷
- `data_months` 필드 없는 토픽은 DEFAULT_MONTHS(60)로 fetch

### Step 1: 상수 추가

`long1_script.py` 상수 블록 (`DATA_BLOCK_ALL_FAIL_ABORT` 줄 다음) 에 추가:

```python
DATA_BLOCK_TREND_MONTHS   = 12   # 주 소스 추이 표시 개월수
DATA_BLOCK_HIST_MONTHS    = [12, 36, 60]  # 과거 비교 오프셋 (1년전, 3년전, 5년전)
```

- [ ] **Step 1: 상수 추가 (편집)**

`long1_script.py`의 `BACKCHECK_TEMP` 상수 다음 줄에 위 두 상수 삽입.

### Step 2: 헬퍼 함수 추가

`_fetch_source` 함수(125번째 줄) 바로 **위에** 세 개의 헬퍼 함수 삽입:

```python
def _offset_date(date_str: str, months: int) -> str:
    """YYYY-MM 에서 months 개월 전 날짜 반환."""
    y, m = int(date_str[:4]), int(date_str[5:7])
    m -= months
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def _get_obs_at(obs: list, date_str: str):
    """관측값 목록에서 특정 날짜(YYYY-MM) 값 반환. 없으면 None."""
    for o in obs:
        if o["date"] == date_str:
            return o["value"]
    return None


def _trend_line(obs: list, latest_date: str, n: int) -> str:
    """최근 n개월 값을 'YYYY-MM:±X.X' 목록 문자열로 반환."""
    tail = [o for o in obs if o["date"] <= latest_date][-n:]
    return " / ".join(f"{o['date']}:{o['value']:+.1f}" for o in tail)
```

- [ ] **Step 2: 헬퍼 함수 삽입 (편집)**

`long1_script.py` 121번째 줄 (`# ─── 데이터 fetch 헬퍼`) 바로 아래에 위 세 함수 삽입.

### Step 3: `_fetch_source` months 파라미터 추가

현재 `_fetch_source(src: dict)` → `_fetch_source(src: dict, months: int = DEFAULT_MONTHS)` 로 변경. 각 소스 타입의 fetch 호출에 `months` 전달:

```python
def _fetch_source(src: dict, months: int = DEFAULT_MONTHS):
    """단일 data_source dict를 fetch. 실패(sys.exit 포함) 시 None 반환."""
    try:
        s = src.get("source", "")
        if s == "fred":
            from data.fred_fetch import fetch_series as _fred
            return _fred(src["code"], months=months)
        elif s == "boj":
            from data.boj_fetch import fetch_series as _boj
            return _boj(src["db"], src["code"], months=months)
        elif s == "estat":
            from data.estat_fetch import fetch_series as _estat
            return _estat(src["stats_data_id"], src.get("filters", {}), months=months)
        else:
            print(f"  [경고] 알 수 없는 source 타입: {s}")
            return None
    except SystemExit:
        return None
    except Exception as e:
        print(f"  [경고] fetch 예외 ({src.get('desc_ko', '')}): {e}")
        return None
```

- [ ] **Step 3: `_fetch_source` 수정 (편집)**

`long1_script.py` `_fetch_source` 함수 전체를 위 코드로 교체.

### Step 4: `build_data_block` 강화

기존 `build_data_block` 함수를 아래로 **전체 교체**. 단일 소스 포맷은 기존과 동일하게 유지, 다중 소스에서만 추가 정보 표시:

```python
def build_data_block(topic: dict) -> str:
    """
    topic의 data_sources를 fetch해서 GPT 주입용 데이터 근거 블록 텍스트 구성.
    - 단일 소스 토픽: 기존 포맷 유지 (소급 없음)
    - 다중 소스 토픽: 비교 스냅샷 + 주 소스 풍부 포맷 + 보조 소스 압축 포맷
    topic.data_months 필드 있으면 해당 개월수로 fetch (없으면 DEFAULT_MONTHS).
    """
    sources = topic.get("data_sources", [])
    if not sources:
        return ""

    fetch_months = topic.get("data_months", DEFAULT_MONTHS)
    is_multi = len(sources) > 1

    header_lines = [
        "【데이터 근거 블록】",
        "아래 수치만 인용 가능. 블록 밖의 수치·주장·예측 생성 절대 금지.",
        "에버그린 규칙: 수치 언급 시 반드시 '○○年○月時点' 기준시점 명시. 상대적 시점 표현 금지.",
        "",
    ]

    fetched: list[tuple] = []  # (src_dict, data_dict)
    for src in sources:
        desc = src.get("desc_ko", src.get("source", ""))
        data = _fetch_source(src, months=fetch_months)
        if data is None:
            print(f"  [경고] 소스 fetch 실패 → 건너뜀: {desc}")
            continue
        fetched.append((src, data))

    if not fetched:
        return ""

    body_lines: list[str] = []

    # ── 다중 소스: 비교 스냅샷 (한 줄) ─────────────────
    if is_multi and len(fetched) > 1:
        snap_parts = []
        for src, data in fetched:
            short = src.get("desc_ko", "").split("(")[0].strip().split(" ")[-1]  # 마지막 단어
            val = data.get("latest_value")
            date = data.get("latest_date", "")
            snap_parts.append(f"{short}:{val:+.1f}%")
        snap_date = fetched[0][1].get("latest_date", "")
        body_lines.append(f"품목별 비교 스냅샷 (前年同月比, {snap_date}기준): " + " / ".join(snap_parts))
        body_lines.append("")

    # ── 소스별 상세 출력 ─────────────────────────────────
    success = 0
    for src, data in fetched:
        tag     = "★ [주]  " if src.get("primary") else "  [보조] "
        desc    = src.get("desc_ko", src.get("source", ""))
        obs     = data.get("observations", [])
        latest  = data.get("latest_value")
        ld      = data.get("latest_date", "")
        unit    = data.get("unit") or data.get("units", "")

        if src.get("primary") or not is_multi:
            # ── 풍부 포맷 (주 소스 또는 단일 소스) ──────
            diff_str = ""
            if len(obs) >= 2:
                prev = obs[-2]["value"]
                pd   = obs[-2]["date"]
                d    = latest - prev
                diff_str = f" / 직전 대비: {d:+.2f} (직전값: {prev}, {pd})"

            body_lines.append(f"{tag}{desc}")
            body_lines.append(f"       최신값: {latest}  단위: {unit}  기준시점: {ld}{diff_str}")

            # 과거 비교 (1년전, 3년전, 5년전)
            for offset in DATA_BLOCK_HIST_MONTHS:
                past_date = _offset_date(ld, offset)
                past_val  = _get_obs_at(obs, past_date)
                if past_val is not None:
                    label = f"{offset//12}년전({past_date})"
                    diff  = latest - past_val
                    body_lines.append(f"       {label}: {past_val:+.1f} → {latest:+.1f} ({diff:+.1f})")

            # 12개월 추이 (다중 소스 토픽에서만)
            if is_multi:
                trend = _trend_line(obs, ld, DATA_BLOCK_TREND_MONTHS)
                body_lines.append(f"       최근{DATA_BLOCK_TREND_MONTHS}개월 추이: {trend}")

        else:
            # ── 압축 포맷 (다중 소스의 보조 소스) ────────
            yoy_date = _offset_date(ld, 12)
            yoy_val  = _get_obs_at(obs, yoy_date)
            yoy_str  = f" / 전년({yoy_date}):{yoy_val:+.1f}→{latest:+.1f}" if yoy_val is not None else ""
            body_lines.append(f"{tag}{desc}")
            body_lines.append(f"       최신값: {latest}  기준시점: {ld}{yoy_str}")

        success += 1

    return "\n".join(header_lines + body_lines) if success > 0 else ""
```

- [ ] **Step 4: `build_data_block` 전체 교체 (편집)**

`long1_script.py`의 `build_data_block` 함수(148~210번째 줄) 전체를 위 코드로 교체.

### Step 5: 수동 확인 — data_block 출력 미리보기

```python
# _check_data_block.py (신규 임시 스크립트)
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from long1_script import build_data_block

with open("topic_bank.json", encoding="utf-8") as f:
    bank = json.load(f)["topics"]

topic = next(t for t in bank if t["id"] == "food-prices")
block = build_data_block(topic)
print(block)
```

- [ ] **Step 5: 확인 스크립트 작성 후 실행**

```
python _check_data_block.py
```

Expected output (핵심 확인 포인트):
```
【데이터 근거 블록】
...
품목별 비교 스냅샷 (前年同月比, 2026-04기준): 食料:+3.5% / 総合:+1.4% / 生鮮食品:+0.3% / エネルギー:-3.9% / コアコア:+1.9% / 穀類:+1.2%

★ [주]  CPI 食料 前年同月比 (%) — 장바구니 전체
       최신값: 3.5  단위: %  기준시점: 2026-04
       직전 대비: -0.1 (직전값: 3.6, 2026-03)
       1년전(2025-04): ...
       3년전(2023-04): ...
       5년전(2021-04): ...
       최근12개월 추이: 2025-05:+4.1 / ...

  [보조] CPI 総合 ...
  [보조] CPI 生鮮食品 ...
  [보조] CPI エネルギー ...
  [보조] CPI コアコア ...
  [보조] CPI 穀類 ...
```

- [ ] **Step 6: 기존 토픽 회귀 확인 — yen-rate**

```
python -c "
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from long1_script import build_data_block
with open('topic_bank.json', encoding='utf-8') as f:
    bank = json.load(f)['topics']
topic = next(t for t in bank if t['id'] == 'yen-rate')
print(build_data_block(topic))
"
```

Expected: 기존 포맷과 동일 (비교 스냅샷 없음, 단일 소스 풍부 포맷).

- [ ] **Step 7: Commit**

```bash
git add long1_script.py
git commit -m "feat: build_data_block — 다중 소스 비교 스냅샷·추이·과거 비교 출력 추가"
```

---

## Task 4: 임시 스크립트 정리

- [ ] **Step 1: 임시 파일 삭제**

```bash
rm _cpi_meta_search.py _verify_cpi.py _check_data_block.py
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: Work 1 임시 검증 스크립트 삭제"
```

---

## Self-Review

### Spec 커버리지 체크

| 요구사항 | 대응 Task |
|---------|----------|
| e-Stat CPI 새 출처 추가 금지 (기존 공공 1차만) | ✅ 모두 0003427113 |
| 시계열 10년치 | ✅ data_months=120, Task 2 |
| 품목 분해: 全体/食品/エネルギー 3분할 | ✅ 0001/0002/0167, Task 2 |
| 수입·국내 인플레 구분 | ✅ 0157(生鮮)+0167(エネルギー) = 외래 신호 / 0178(コアコア) = 국내 신호, Task 2 |
| data_block 구조 풍부화 | ✅ Task 3 |
| 라이브 fetch 검증 통과한 ID·셀만 확정 | ✅ 전 시리즈 검증 완료 (사양서 첨부) |
| 토픽뱅크 전체 일괄 변경 금지 | ✅ food-prices 1개만 추가 |
| 기존 토픽 회귀 없음 | ✅ 단일 소스 토픽은 기존 포맷 그대로 |

### Placeholder 검사
없음. 모든 코드 블록은 실행 가능한 완전한 코드.

### 타입 일관성
- `_fetch_source(src, months)` → Task 3 Step 3에서 정의, Task 3 Step 4 `build_data_block`에서 호출 ✅
- `_offset_date`, `_get_obs_at`, `_trend_line` → Task 3 Step 2에서 정의, Step 4에서 사용 ✅
- `DATA_BLOCK_TREND_MONTHS`, `DATA_BLOCK_HIST_MONTHS` → Task 3 Step 1에서 정의, Step 4에서 참조 ✅
- `data_months` 필드 → topic_bank.json Task 2에서 추가, `build_data_block`에서 `topic.get("data_months", DEFAULT_MONTHS)`로 읽음 ✅
