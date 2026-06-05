# food-prices Work 5 — 이슈 역할 재조정 + 계단 구조 + 차트 전환 규칙

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** food-prices principle을 개정본으로 교체하고, 이슈1(원리+대표수치)·이슈2(세분화+반전)로 역할을 재조정하며, 인접 수치 구간을 하나의 차트 블록으로 묶는 규칙을 추가한다.

**Architecture:** `topic_bank.json` principle 필드 1개 교체 + `long1_script.py`의 issue1/issue2 프롬프트 3곳 편집. 별도 모듈·함수 추가 없음(YAGNI).

**Tech Stack:** Python 3.14 / OpenAI gpt-4.1 / 프롬프트 엔지니어링만

---

## 파일 변경 목록

| 파일 | 위치 | 내용 |
|------|------|------|
| `topic_bank.json` | food-prices.principle | 개정본으로 교체 |
| `long1_script.py` | issue1_prompt 역할 블록 | 원리+대표수치 허용으로 수정 |
| `long1_script.py` | issue1_prompt 규칙 블록 | 차트 1개 지시로 교체 |
| `long1_script.py` | issue2_prompt 역할 블록 | 세분화+반전으로 수정 |
| `long1_script.py` | issue2_prompt 수치분석 블록 | 품목분해+반전+차트 묶음 규칙으로 교체 |

---

## Task 0: topic_bank.json — principle 개정본 교체

**Files:**
- Modify: `topic_bank.json` (food-prices 항목)

- [ ] **Step 1: principle 필드 교체**

`topic_bank.json`의 food-prices `"principle"` 값을 아래로 교체:

```json
"principle": "물가는 하나의 숫자로 움직이지 않는다. 전체 물가지수(総合)가 잔잔해 보여도, 그 안에서 식품은 크게 오르고 에너지는 내리는 식으로 항목마다 방향이 갈린다. 가계가 \"물가가 올랐다\"고 체감하는 건 평균이 아니라 매일 사는 식품·곡물 같은 품목이 오르기 때문이다. 먼저 전체와 식품의 큰 차이를 보이고, 그 식품 안을 다시 품목별로 쪼개 들어가면, 평균만 봐서는 보이지 않던 사실(예: 곡물은 한때 급등했다 꺾이고, 에너지는 오히려 내렸다)이 드러난다. 따라서 체감과 통계의 괴리는 \"물가 평균\"이 아니라 \"무엇이 오르고 무엇이 내렸는가\"를 단계적으로 분해해야 보인다.",
```

- [ ] **Step 2: 검증 + 커밋**

```python
# _check_principle.py
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open("topic_bank.json", encoding="utf-8"))
fp = next(t for t in d["topics"] if t["id"] == "food-prices")
assert "단계적으로 분해해야 보인다" in fp["principle"], "개정본 미적용"
assert "먼저 전체와 식품의 큰 차이를 보이고" in fp["principle"], "추가 문장 없음"
print("OK —", fp["principle"][:40], "...")
```

실행:
```
python _check_principle.py
```

Expected:
```
OK — 물가는 하나의 숫자로 움직이지 않는다. 전체 물가지 ...
```

```bash
git add topic_bank.json
git commit -m "feat: food-prices principle 개정 — 계단 분해 구조 명시"
```

---

## Task 1: issue1_prompt — 원리 + 대표 수치 허용 + 차트 1개

**Files:**
- Modify: `long1_script.py` (stage_ko 함수 내 issue1_prompt)

- [ ] **Step 1: issue1 역할 블록 교체**

OLD:
```python
【이슈1 역할 — 원리 전담】
"왜 그런 일이 일어나는가"의 메커니즘·개념 설명 담당.
수치·데이터 사용 금지(수치는 이슈2에서만). 이슈2에서 나올 데이터를 앞서 서술하지 말 것.
```

NEW:
```python
【이슈1 역할 — 원리 + 대표 수치】
"왜 항목마다 방향이 갈리는가"의 메커니즘·개념 설명 담당.
큰 대표 수치 1~2개(예: 총합 vs 食料 전년동월비 대비)는 허용.
세부 품목 분해(穀類/生鮮食品/エネルギー 각각)는 이슈2에서 다룬다.
```

- [ ] **Step 2: issue1 차트 규칙 교체**

OLD:
```python
규칙:
- 일상 비유 또는 구체 장면을 활용해 설명할 것.
- 이 섹션은 수치 금지이므로 차트 태그가 없는 것이 정상. 예외적으로 수치가 생기면 ===차트=== ... ===차트끝=== 으로 감쌀 것.
```

NEW:
```python
규칙:
- 일상 비유 또는 구체 장면을 활용해 설명할 것.
- 대표 수치 구간(1~2개)은 ===차트=== ... ===차트끝=== 으로 감쌀 것.
  수치 없는 서술이 이어질 때만 닫는다 (짧은 깜빡임 금지).
```

- [ ] **Step 3: 검증 스크립트 + 커밋**

```python
# _check_issue1.py
import sys, inspect
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import long1_script
src = inspect.getsource(long1_script.stage_ko)
assert "이슈1 역할 — 원리 + 대표 수치" in src, "issue1 역할 블록 미적용"
assert "큰 대표 수치 1~2개" in src, "대표 수치 허용 없음"
assert "세부 품목 분해" in src, "이슈2 분리 없음"
assert "대표 수치 구간(1~2개)은 ===차트===" in src, "issue1 차트 규칙 없음"
assert "이 섹션은 수치 금지이므로" not in src, "구 규칙 잔존"
print("OK — issue1 역할 + 차트 규칙 확인 완료")
```

실행:
```
python _check_issue1.py
```

Expected:
```
OK — issue1 역할 + 차트 규칙 확인 완료
```

```bash
git add long1_script.py
git commit -m "feat: issue1 역할 — 대표 수치 허용 + 차트 1개 규칙"
```

---

## Task 2: issue2_prompt — 세분화·반전 + 차트 묶음 규칙

**Files:**
- Modify: `long1_script.py` (stage_ko 함수 내 issue2_prompt)

- [ ] **Step 1: issue2 역할 블록 교체**

OLD:
```python
【이슈2 역할 — 데이터 실증 전담】
이슈1이 설명한 원리를 실제 수치로 증명하는 섹션.
이슈1에서 이미 설명한 개념·원리를 반복하지 말 것. 수치 자체를 전면에 내세울 것.
```

NEW:
```python
【이슈2 역할 — 세분화 + 의미 반전】
이슈1에서 보인 큰 대비를 식품 내부 품목별로 쪼개고, 예상과 다른 사실(반전)을 드러내는 섹션.
이슈1에서 설명한 원리·개념을 반복하지 말 것. 세부 품목 수치 분해가 이 섹션의 핵심.
```

- [ ] **Step 2: issue2 수치분석 + 차트 묶음 규칙 교체**

OLD:
```python
수치 분석:
- 데이터 블록의 품목별 비교 스냅샷(総合/食料/エネルギー/穀類 등)을 분해하여 제시할 것.
- 전년 동월 대비로 "작년 이맘때와 비교해 어떻게 달라졌는가"를 시청자 체감 장면으로.
- 전년 동월 없으면 직전 대비 또는 수준값으로만.
- 수치는 시청자 일상의 구체 장면으로 연결할 것.
- 수치를 말하는 문장·구간은 ===차트=== 와 ===차트끝=== 으로 감싸 표시할 것.
  (한 수치 설명 구간이 끝나면 반드시 ===차트끝=== 으로 닫을 것)
```

NEW:
```python
수치 분석:
- 食料 내부 품목별 분해: 穀類/生鮮食品/エネルギー 각각의 전년동월비를 제시할 것.
- 반전 포인트 강조: 穀類(곡물)은 한때 급등했다 꺾임 / エネルギーは오히려 하락 중 등.
- 전년 동월 대비로 "작년 이맘때와 비교해 어떻게 달라졌는가"를 시청자 체감 장면으로.
- 수치는 시청자 일상의 구체 장면으로 연결할 것.

차트 태그 원칙:
- 수치가 연달아 나오는 구간은 하나의 ===차트=== 블록으로 크게 묶는다 (짧은 깜빡임 금지).
- 수치 없는 서술이 이어질 때만 ===차트끝=== 으로 닫는다. 바로 다음에 수치가 이어지면 닫지 않는다.
- ===차트=== / ===차트끝=== 은 반드시 문장 경계에서만 열고 닫는다 (단어 중간 금지).
- 차트 블록 개수 제한 없음. 수치 구간이 여럿이면 블록도 여럿 가능.
```

- [ ] **Step 3: 검증 스크립트 + 커밋**

```python
# _check_issue2.py
import sys, inspect
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import long1_script
src = inspect.getsource(long1_script.stage_ko)
assert "이슈2 역할 — 세분화 + 의미 반전" in src, "issue2 역할 블록 미적용"
assert "반전 포인트 강조" in src, "반전 지시 없음"
assert "차트 태그 원칙" in src, "차트 묶음 원칙 없음"
assert "짧은 깜빡임 금지" in src, "깜빡임 방지 규칙 없음"
assert "바로 다음에 수치가 이어지면 닫지 않는다" in src, "연속 수치 묶음 규칙 없음"
assert "데이터 실증 전담" not in src, "구 역할 잔존"
print("OK — issue2 역할 + 차트 묶음 규칙 확인 완료")
```

실행:
```
python _check_issue2.py
```

Expected:
```
OK — issue2 역할 + 차트 묶음 규칙 확인 완료
```

```bash
git add long1_script.py
git commit -m "feat: issue2 역할 — 세분화·반전 + 차트 인접 구간 묶음 규칙"
```

---

## Task Cleanup

- [ ] **Step 1: 임시 파일 삭제 + 커밋**

```bash
rm _check_principle.py _check_issue1.py _check_issue2.py
git add -A
git commit -m "chore: Work 5 임시 검증 스크립트 삭제"
```

---

## Self-Review

### Spec 커버리지

| 요구사항 | Task |
|---------|------|
| principle 개정본 교체 | ✅ Task 0 |
| 이슈1 = 원리 + 대표 수치 1~2개 + 차트 1개 | ✅ Task 1 |
| 이슈2 = 세분화 + 의미 반전 + 차트 다수 | ✅ Task 2 |
| 차트 인접 구간 하나로 묶기 (깜빡임 방지) | ✅ Task 2 Step 2 |
| 문장 경계에서만 태그 | ✅ Task 2 Step 2 |
| TTS 안전망 유지 (long2_tts.py 변경 없음) | ✅ 변경 없음 |
| 인트로·아웃트로 차트 태그 없음 | ✅ 변경 없음 |

### Placeholder 검사
없음. 모든 검증 코드는 실행 가능.

### 타입 일관성
`inspect.getsource(long1_script.stage_ko)` — stage_ko 함수 소스 전체 포함 확인 가능 ✅
