# food-prices Work 2 — プロンプト境界再設定・出처自動化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** food-prices 토픽을 활성화하고, SYSTEM_KO 프롬프트에서 "금지·허용" 경계를 분리하며, 영상 설명란·블로그 출처를 실제 사용 데이터 소스로 자동 표기한다.

**Architecture:** 3개 파일 수정만으로 완결. `topic_bank.json`에 확정 메타 반영, `long1_script.py` SYSTEM_KO 상수 교체, `long6_youtube.py`·`long7_wordpress.py`에 `_source_line()` 헬퍼 추가. 별도 모듈 없음(YAGNI).

**Tech Stack:** Python 3.14 / topic_bank.json / OpenAI gpt-4.1 (longform) / WordPress REST API

---

## 파일 변경 목록

| 파일 | 변경 내용 |
|------|-----------|
| `topic_bank.json` | food-prices: status→active, title_ja/ko, principle 확정 적용 |
| `long1_script.py` | `SYSTEM_KO` 상수 교체 (Task A + B 통합) |
| `long6_youtube.py` | `INFO_BLOCK` → `CHANNEL_INFO_BLOCK` + `_source_line()` 함수 신규 |
| `long7_wordpress.py` | `_source_line()` 함수 신규 + `build_html_body` 출처 줄 추가 |

---

## Task 0: food-prices 토픽 활성화

**Files:**
- Modify: `topic_bank.json` (food-prices 항목)

- [ ] **Step 1: food-prices 항목 수정**

`topic_bank.json`에서 `"id": "food-prices"` 항목의 아래 4개 필드를 교체:

```json
"title_ja": "なぜ物価は落ち着いたのに食卓は苦しいのか",
"title_ko": "왜 물가는 안정됐는데 식탁은 힘든가",
"principle": "물가는 하나의 숫자로 움직이지 않는다. 전체 물가지수(総合)가 잔잔해 보여도, 그 안에서 식품은 크게 오르고 에너지는 내리는 식으로 항목마다 방향이 갈린다. 가계가 '물가가 올랐다'고 체감하는 건 평균이 아니라 매일 사는 식품·곡물 같은 품목이 오르기 때문이다. 따라서 체감과 통계의 괴리는 '물가 평균'이 아니라 '무엇이 오르고 무엇이 내렸는가'를 분해해야 보인다.",
"status": "active",
"status_reason": null,
```

- [ ] **Step 2: JSON 형식 검증 + 필드 확인 스크립트 작성·실행**

`_check_food.py` 파일 생성:

```python
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
data = json.load(open("topic_bank.json", encoding="utf-8"))
fp = next(t for t in data["topics"] if t["id"] == "food-prices")
assert fp["status"] == "active", f"status={fp['status']}"
assert fp["title_ja"] == "なぜ物価は落ち着いたのに食卓は苦しいのか", "title_ja 불일치"
assert fp["principle"].startswith("물가는 하나의 숫자로"), "principle 불일치"
assert fp["status_reason"] is None, f"status_reason={fp['status_reason']}"
print("OK — food-prices active 전환 확인")
```

실행:
```
python _check_food.py
```

Expected:
```
OK — food-prices active 전환 확인
```

- [ ] **Step 3: Commit**

```bash
git add topic_bank.json
git commit -m "feat: food-prices 토픽 활성화 — title/principle/status 확정 반영"
```

---

## Task AB: SYSTEM_KO 프롬프트 경계 재설정 + principle 안전장치

**Files:**
- Modify: `long1_script.py:97-121` (`SYSTEM_KO` 상수)

이 Task는 Task A(금지·허용 분리)와 Task B(principle 사용 규칙)를 한 번에 교체한다.
두 변경은 같은 상수 `SYSTEM_KO` 안에 있어 별도 커밋으로 나누면 절반 상태가 생기므로 통합.

기존 SYSTEM_KO의 문제:
- 규칙 1("검증된 교과서 원리에 한함. ... 예측·투자 권유·시세 예측 금지.")이 "신뢰성 제한"과
  "표현 제한"을 뭉뚱그려, GPT가 메커니즘 설명까지 자제하고 일반론으로 빠짐.
- principle 복사 금지 안내 없음.

- [ ] **Step 1: SYSTEM_KO 상수 전체 교체**

`long1_script.py`의 `SYSTEM_KO = """\` ~ `"""\` 블록 전체를 아래로 교체:

```python
# ===== 한국어 초안 시스템 프롬프트 (KO 단계) =====
SYSTEM_KO = """\
당신은 일본 거시경제 교양 콘텐츠 작가입니다.

【최우선 출력 규칙】
script_ko에는 시청자에게 그대로 읽어줄 완성 문장만. 작업 지시·메타 설명·괄호 라벨 절대 금지.

【시청자 전제 — 전 섹션 공통】
이 대본의 시청자는 일본에 사는 일본인이다. 다음을 전제로 쓴다:
- 시청자에게 일본은 '자국'. 해외여행의 예로 '일본 여행'을 들지 말 것(해외=일본 밖).
- 시청자는 엔화로 급여를 받고 엔화로 생활한다. '엔화로 월급을 받는다면' 같은 조건문 금지.
- 생활 예시는 일본 거주자의 일상(일본 마트·일본 물가·일본 직장) 기준.
- 한국·한국인 시점의 비유·예시·환전 상황을 쓰지 말 것.

【절대 금지 — 완화 불가】
- 미래 예측·전망 ("앞으로 오른다/내린다" 류 단정 표현)
- 종목·투자·금융상품 권유 또는 암시
- 데이터 근거 블록에 없는 수치·사실 주장 (할루시네이션)
- 닛케이·이코노미스트 등 저널·뉴스 기사 크롤링·인용

【허용·권장 — 이것이 이 콘텐츠의 핵심 가치다】
이미 가진 공공데이터를 분해·연결·인과 해석하는 것은 적극 권장한다.
"이미 일어난 일이 왜 그렇게 됐는가"를 끝까지 설명하는 것은 예측이 아니라 메커니즘 설명이다.
데이터 근거 블록이 있는 경우, 아래 순서로 전개한다:
  ① 분해: 무엇이 오르고 무엇이 내렸는지 수치로 분리
  ② 연결: 각 항목 변동의 인과 사슬 (왜 그렇게 됐는가)
  ③ 반직관: 체감과 통계의 괴리, 또는 상식과 다른 포인트

【principle 사용 규칙】
principle은 '내용 설계도'다. 서술 방향·핵심 원리를 제시할 뿐이다.
principle 문장을 그대로 대본에 복사하지 말 것. 화자 말투·경어·페르소나는 SYSTEM 프롬프트가 결정한다.

규칙:
1. 경제 입문자 기준. 전문 용어는 쉽게 설명. 뉴스는 원리의 '입구' — 인과 메커니즘 설명까지.
   구어 해설체(~습니다/~죠/~이에요) 통일. 명사 종결("늘어남") 및 메모체 금지.
2. 데이터 근거 블록 수치만 인용. 블록 밖 수치 생성 절대 금지.
   수치 언급 시 기준시점(예: '2026年3月時点') 명시. '今日' '今週' '先月' 등 상대 시점 표현 금지.
   블록이 없으면 수치 없이 원리로만.
3. 출력은 JSON만. 마크다운(``` 등) 절대 금지.
   대본 본문에 내부 라벨(issue1/issue2/intro/outro/이슈1/이슈2/なぜ/誰が 등) 금지. 섹션 연결은 구어체로.
4. 기사 수치·고유명사 인용 시 [출처: 기사1] 또는 [출처: 기사2] 표기.\
"""
```

- [ ] **Step 2: 변경 내용 구조 확인**

```python
# _check_system_ko.py
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from long1_script import SYSTEM_KO

assert "절대 금지" in SYSTEM_KO, "절대 금지 섹션 없음"
assert "허용·권장" in SYSTEM_KO, "허용·권장 섹션 없음"
assert "분해:" in SYSTEM_KO, "분해 순서 없음"
assert "반직관:" in SYSTEM_KO, "반직관 순서 없음"
assert "principle은 '내용 설계도'" in SYSTEM_KO, "principle 안전장치 없음"
assert "검증된 교과서 원리에 한함" not in SYSTEM_KO, "기존 뭉뚱그린 규칙 잔존"
print("OK — SYSTEM_KO 구조 확인 완료")
print(f"  길이: {len(SYSTEM_KO)}자")
```

실행:
```
python _check_system_ko.py
```

Expected:
```
OK — SYSTEM_KO 구조 확인 완료
  길이: (숫자)자
```

- [ ] **Step 3: Commit**

```bash
git add long1_script.py
git commit -m "feat: SYSTEM_KO — 금지/허용 분리 + 데이터 분해순서 + principle 안전장치"
```

---

## Task C1: long6_youtube.py 출처 자동화

**Files:**
- Modify: `long6_youtube.py:45-51` (`INFO_BLOCK` 상수 → 분리 + `_source_line` 함수)
- Modify: `long6_youtube.py:105-115` (`build_description` 함수)

현재 `INFO_BLOCK` = 뉴스 출처 하드코딩. topic의 실제 data_sources를 읽어 기관명 자동 생성으로 교체.
`json` 모듈은 이미 `long6_youtube.py` 상단에 임포트되어 있음 (`import json` line 2).

- [ ] **Step 1: INFO_BLOCK 교체 + 헬퍼 추가**

`long6_youtube.py`의 `INFO_BLOCK = (` ~ `)` 블록 전체를 아래로 교체:

```python
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
```

- [ ] **Step 2: build_description 수정**

`long6_youtube.py`의 `build_description` 함수 전체를 아래로 교체:

```python
def build_description(data):
    hashtags  = " ".join(data["hashtags"])
    issues    = "\n".join(f"▶ {iss['title']}" for iss in data["issues"])
    slug      = data.get("_slug_keyword", "")
    info_block = f"【参考データ】{_source_line(slug)}\n{CHANNEL_INFO_BLOCK}"
    body      = f"{hashtags}\n\n【本日の内容】\n{issues}\n\n{info_block}{CHANNEL_FOOTER}"

    chapters = load_chapters()
    if chapters:
        return f"{build_chapter_text(chapters)}\n\n{body}"
    return body
```

- [ ] **Step 3: 출력 검증 스크립트 작성·실행**

`_check_desc.py` 파일 생성:

```python
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

# long6_youtube를 임포트하되 구글 인증·requests 불필요 — 함수만 호출
from long6_youtube import _source_line, build_description

# food-prices (estat 소스) → 총무성 표기
attr = _source_line("food-prices")
assert "総務省統計局 e-Stat" in attr, f"food-prices 출처 오류: {attr}"

# yen-rate (BOJ + FRED) → 두 기관 모두 표기
attr2 = _source_line("yen-rate")
assert "日本銀行 時系列統計" in attr2, f"yen-rate BOJ 누락: {attr2}"
assert "米連邦準備制度" in attr2, f"yen-rate FRED 누락: {attr2}"

# 없는 토픽 → fallback
attr3 = _source_line("nonexistent-topic")
assert attr3 == "NHK ニュース / Yahoo Japan ビジネス", f"fallback 오류: {attr3}"

print("OK — _source_line 검증 통과")
print(f"  food-prices: {attr}")
print(f"  yen-rate:    {attr2}")
print(f"  fallback:    {attr3}")
```

실행:
```
python _check_desc.py
```

Expected:
```
OK — _source_line 검증 통과
  food-prices: 総務省統計局 e-Stat
  yen-rate:    日本銀行 時系列統計 / 米連邦準備制度（FRED）
  fallback:    NHK ニュース / Yahoo Japan ビジネス
```

- [ ] **Step 4: Commit**

```bash
git add long6_youtube.py
git commit -m "feat: long6 설명란 출처 — 하드코딩 제거, topic data_sources 기반 자동 표기"
```

---

## Task C2: long7_wordpress.py 출처 자동화

**Files:**
- Modify: `long7_wordpress.py` (상수 블록 끝 부분 + `build_html_body` 함수)

- [ ] **Step 1: SOURCE_INST_JA + _source_line 추가**

`long7_wordpress.py`의 `FURIGANA_PAT   = re.compile(...)` 줄 **바로 위에** 아래 코드 삽입:

```python
SOURCE_INST_JA = {
    "estat": "総務省統計局 e-Stat",
    "boj":   "日本銀行 時系列統計",
    "fred":  "米連邦準備制度（FRED）",
}
FALLBACK_SOURCE = "NHK ニュース / Yahoo Japan ビジネス"


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

```

- [ ] **Step 2: build_html_body에 출처 줄 추가**

`long7_wordpress.py`의 `build_html_body` 함수 내, `html = (` 블록을 아래로 교체:

```python
    source_attr  = _source_line(data.get("_slug_keyword", ""))
    source_block = (
        f'<p><small><strong>参考データ</strong>：{source_attr}</small></p>\n'
    )

    html = (
        f"<h2>今日のニュース</h2>\n"
        f"{intro_html}\n\n"
        f"{embed_block}\n\n"
        f"<h2>{issue1['title']}</h2>\n"
        f"{img_block('issue1', issue1['title'])}"
        f"{to_paragraphs(issue1['script'])}\n\n"
        f"{AD_SLOT_2}\n\n"
        f"<h2>{issue2['title']}</h2>\n"
        f"{img_block('issue2', issue2['title'])}"
        f"{to_paragraphs(issue2['script'])}\n\n"
        f"<h2>まとめ</h2>\n"
        f"{to_paragraphs(outro_script)}\n"
        f"{source_block}"
        f"{blog_outro}\n"
        f"{AD_SLOT_3}\n"
    )
    return html
```

- [ ] **Step 3: 출처 블록 출력 검증**

`_check_wp_source.py` 파일 생성:

```python
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from long7_wordpress import _source_line

attr = _source_line("food-prices")
assert "総務省統計局 e-Stat" in attr, f"food-prices 출처 오류: {attr}"
attr2 = _source_line("yen-rate")
assert "日本銀行" in attr2, f"yen-rate BOJ 누락: {attr2}"
attr3 = _source_line("nonexistent")
assert attr3 == "NHK ニュース / Yahoo Japan ビジネス", f"fallback 오류: {attr3}"
print("OK — long7 _source_line 검증 통과")
print(f"  food-prices: {attr}")
print(f"  yen-rate:    {attr2}")
print(f"  fallback:    {attr3}")
```

실행:
```
python _check_wp_source.py
```

Expected:
```
OK — long7 _source_line 검증 통과
  food-prices: 総務省統計局 e-Stat
  yen-rate:    日本銀行 時系列統計 / 米連邦準備制度（FRED）
  fallback:    NHK ニュース / Yahoo Japan ビジネス
```

- [ ] **Step 4: Commit**

```bash
git add long7_wordpress.py
git commit -m "feat: long7 블로그 출처 — topic data_sources 기반 자동 표기 추가"
```

---

## Task Cleanup: 임시 스크립트 정리

- [ ] **Step 1: 임시 파일 삭제 + 커밋**

```bash
rm _check_food.py _check_system_ko.py _check_desc.py _check_wp_source.py
git add -A
git commit -m "chore: Work 2 임시 검증 스크립트 삭제"
```

---

## Self-Review

### Spec 커버리지

| 요구사항 | Task |
|---------|------|
| food-prices status: hold → active | ✅ Task 0 |
| title_ja/ko, principle 확정 적용 | ✅ Task 0 |
| 절대 금지 항목 분리 명시 | ✅ Task AB |
| 허용·권장 (인과 해석) 명시 | ✅ Task AB |
| 분해→연결→반직관 순서 유도 | ✅ Task AB |
| principle 복사 금지 안전장치 | ✅ Task AB |
| 설명란 출처 자동화 (하드코딩 금지) | ✅ Task C1 |
| 블로그 출처 자동화 | ✅ Task C2 |
| 투자권유 없음 문구 존치 | ✅ Task C1 (CHANNEL_INFO_BLOCK에 포함) |
| 토픽뱅크 일괄 변경 금지 | ✅ food-prices 1개만 수정 |

### Placeholder 검사
없음. 모든 코드 블록은 실행 가능한 완전한 코드.

### 타입 일관성
- `_source_line(slug_keyword: str) -> str` — C1·C2 동일 시그니처 ✅
- `SOURCE_INST_JA`, `FALLBACK_SOURCE` — C1·C2 동일 상수값 ✅
- `data.get("_slug_keyword", "")` — `long_script.json`에 `_slug_keyword` 필드 존재 확인 ✅
- `CHANNEL_INFO_BLOCK` — C1에서 정의, C1 `build_description`에서만 사용 ✅
- `source_block` — C2 `build_html_body` 지역변수, `html` f-string에서 사용 ✅
