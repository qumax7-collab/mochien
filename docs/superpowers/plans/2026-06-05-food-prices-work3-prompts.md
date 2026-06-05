# food-prices Work 3 — 섹션 역할 분리·화자 시점·화면 태그 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** long1_script.py의 섹션별 프롬프트를 정비(원리·데이터 분리, 콜드오픈 강화)하고, 자국민 화자 시점을 SYSTEM 상수에 영구 박으며, 이슈2 수치 구간에 Remotion 합성용 차트 태그를 추가한다.

**Architecture:** 모든 변경은 `long1_script.py`의 상수(SYSTEM_KO, SYSTEM_JA)와 인라인 f-string 프롬프트(intro/issue1/issue2/ja), 그리고 `long2_tts.py`의 `get_section_script()` 함수에만 집중. 별도 모듈 없음(YAGNI).

**Tech Stack:** Python 3.14 / OpenAI gpt-4.1 / 프롬프트 엔지니어링만

---

## 파일 변경 목록

| 파일 | 변경 위치 | 내용 |
|------|-----------|------|
| `long1_script.py` | `SYSTEM_KO` 상수 | Task C: 화자 시점 블록 삽입 |
| `long1_script.py` | `SYSTEM_JA` 상수 | Task C: 화자 시점 + Task D: 태그 보존 규칙 |
| `long1_script.py` | `intro_prompt` (stage_ko 내) | Task B: 콜드오픈 강화 |
| `long1_script.py` | `issue1_prompt` (stage_ko 내) | Task A: 원리 전담 명시 + Task D: 태그 지시 |
| `long1_script.py` | `issue2_prompt` (stage_ko 내) | Task A: 데이터 전담 명시 + Task D: 태그 지시 |
| `long1_script.py` | `ja_prompt` (stage_ja 내) | Task D: 태그 보존 주의사항 |
| `long2_tts.py` | `get_section_script()` | Task D: TTS 전송 전 차트 태그 제거 |

---

## Task AB: 섹션 역할 분리 + 인트로 콜드오픈

**Files:**
- Modify: `long1_script.py` (intro_prompt, issue1_prompt, issue2_prompt — stage_ko 함수 내)

Task A(섹션 역할)와 Task B(콜드오픈)는 동일 f-string들을 수정하므로 단일 커밋.

### Step 1: intro_prompt 규칙 교체

`long1_script.py`에서 `intro_prompt` 안의 규칙 블록을 교체:

OLD (616~636번 줄 내부):
```python
규칙:
- 시청자가 이미 품고 있는 의문을 화자가 대신 짚는 문장으로 시작하세요.
  예: "경기가 좋아지고 있다는 뉴스, 그런데 왜 나는 체감이 안 될까요."
- 인사·자기소개 금지 / 수치 나열 금지 / 3~5문장으로 간결하게
```

NEW:
```python
규칙:
- 데이터에서 나온 반직관적 의문으로 열 것.
  방향 예시: "에너지 가격은 내렸는데 왜 장바구니는 더 무거운가" 처럼 통계의 역설을 미끼로.
- 인트로에서 답·결론·수치를 주지 않는다. 의문을 던지고 끝까지 봐야 풀리게.
- 인사·자기소개 금지 / 3~5문장으로 간결하게
```

- [ ] **Step 1: intro_prompt 규칙 교체 (편집)**

`long1_script.py`의 해당 텍스트를 아래 Edit으로 교체:

```
old: "규칙:\n- 시청자가 이미 품고 있는 의문을 화자가 대신 짚는 문장으로 시작하세요.\n  예: \"경기가 좋아지고 있다는 뉴스, 그런데 왜 나는 체감이 안 될까요.\"\n- 인사·자기소개 금지 / 수치 나열 금지 / 3~5문장으로 간결하게"
new: "규칙:\n- 데이터에서 나온 반직관적 의문으로 열 것.\n  방향 예시: \"에너지 가격은 내렸는데 왜 장바구니는 더 무거운가\" 처럼 통계의 역설을 미끼로.\n- 인트로에서 답·결론·수치를 주지 않는다. 의문을 던지고 끝까지 봐야 풀리게.\n- 인사·자기소개 금지 / 3~5문장으로 간결하게"
```

### Step 2: issue1_prompt 역할 블록 추가

`long1_script.py`의 `issue1_prompt` f-string:

OLD (644~646번 줄):
```python
issue1_prompt = f"""\
롱폼 이슈1 섹션을 한국어로 작성하세요.{revise_prefix}
수치 사용 금지(수치는 이슈2에서만).

【이슈1 각도】{issue1_angle}
```

NEW:
```python
issue1_prompt = f"""\
롱폼 이슈1 섹션을 한국어로 작성하세요.{revise_prefix}

【이슈1 역할 — 원리 전담】
"왜 그런 일이 일어나는가"의 메커니즘·개념 설명 담당.
수치·데이터 사용 금지(수치는 이슈2에서만). 이슈2에서 나올 데이터를 앞서 서술하지 말 것.

【이슈1 각도】{issue1_angle}
```

- [ ] **Step 2: issue1_prompt 역할 블록 교체 (편집)**

### Step 3: issue2_prompt 역할 블록 추가 + 품목분해 지시 강화

`long1_script.py`의 `issue2_prompt` f-string:

OLD (681~695번 줄):
```python
issue2_prompt = f"""\
롱폼 이슈2 섹션을 한국어로 작성하세요.{revise_prefix}

【이슈2 각도】{issue2_angle}
이 각도 하나를 처음부터 끝까지 한 흐름으로 깊게 풀 것. 여러 갈래로 얕게 훑지 말 것.
분량 {ISSUE_RETRY_MIN_CHARS}자 이상이지만 길이 채우기가 목적이 아님. 밀도 우선.

【거시 원리 주제】{topic_ja}

{data_section}

수치 분석:
- 전년 동월 대비로 "작년 이맘때와 비교해 어떻게 달라졌는가"를 시청자 체감 장면으로.
- 전년 동월 없으면 직전 대비 또는 수준값으로만.
- 수치는 시청자 일상의 구체 장면으로 연결할 것.
```

NEW:
```python
issue2_prompt = f"""\
롱폼 이슈2 섹션을 한국어로 작성하세요.{revise_prefix}

【이슈2 역할 — 데이터 실증 전담】
이슈1이 설명한 원리를 실제 수치로 증명하는 섹션.
이슈1에서 이미 설명한 개념·원리를 반복하지 말 것. 수치 자체를 전면에 내세울 것.

【이슈2 각도】{issue2_angle}
이 각도 하나를 처음부터 끝까지 한 흐름으로 깊게 풀 것. 여러 갈래로 얕게 훑지 말 것.
분량 {ISSUE_RETRY_MIN_CHARS}자 이상이지만 길이 채우기가 목적이 아님. 밀도 우선.

【거시 원리 주제】{topic_ja}

{data_section}

수치 분석:
- 데이터 블록의 품목별 비교 스냅샷(総合/食料/エネルギー/穀類 등)을 분해하여 제시할 것.
- 전년 동월 대비로 "작년 이맘때와 비교해 어떻게 달라졌는가"를 시청자 체감 장면으로.
- 전년 동월 없으면 직전 대비 또는 수준값으로만.
- 수치는 시청자 일상의 구체 장면으로 연결할 것.
```

- [ ] **Step 3: issue2_prompt 역할 블록 교체 (편집)**

### Step 4: 검증 스크립트 작성·실행

- [ ] **Step 4: 변경 내용 구조 확인**

`_check_prompts.py` 작성:

```python
import sys, inspect
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import long1_script

src = inspect.getsource(long1_script.stage_ko)
assert "반직관적 의문으로 열 것" in src, "intro 콜드오픈 없음"
assert "끝까지 봐야 풀리게" in src, "intro 답 금지 없음"
assert "이슈1 역할 — 원리 전담" in src, "issue1 역할 없음"
assert "이슈2에서 나올 데이터를 앞서 서술하지 말 것" in src, "issue1 데이터 선취 금지 없음"
assert "이슈2 역할 — 데이터 실증 전담" in src, "issue2 역할 없음"
assert "이슈1에서 이미 설명한 개념·원리를 반복하지 말 것" in src, "issue2 반복 금지 없음"
assert "품목별 비교 스냅샷" in src, "issue2 품목분해 지시 없음"
print("OK — Task AB 프롬프트 구조 확인 완료")
```

실행:
```
python _check_prompts.py
```

Expected:
```
OK — Task AB 프롬프트 구조 확인 완료
```

- [ ] **Step 5: Commit**

```bash
git add long1_script.py
git commit -m "feat: 섹션 역할 분리 + 콜드오픈 — 원리/데이터 분담 명시, 인트로 반직관 미끼"
```

---

## Task C: 화자 시점 규칙 (SYSTEM_KO + SYSTEM_JA)

**Files:**
- Modify: `long1_script.py` (SYSTEM_KO 상수, SYSTEM_JA 상수)

영구 규칙. food-prices 외 모든 롱폼에 적용.

### Step 1: SYSTEM_KO에 화자 시점 블록 삽입

`long1_script.py`의 SYSTEM_KO에서 `【시청자 전제 — 전 섹션 공통】` 블록 뒤 (빈 줄 포함), `【절대 금지 — 완화 불가】` 바로 앞에 삽입:

OLD:
```python
- 한국·한국인 시점의 비유·예시·환전 상황을 쓰지 말 것.

【절대 금지 — 완화 불가】
```

NEW:
```python
- 한국·한국인 시점의 비유·예시·환전 상황을 쓰지 말 것.

【화자 시점 — 전 섹션 공통 (영구 규칙)】
모찌엔은 일본인 화자가 일본 시청자에게 말하는 채널이다.
[금지] "일본의 경우" / "일본에서는" 처럼 자국을 외부에서 분석하는 표현.
[권장] "우리 식탁에서는" / "일본에 사는 우리에게는" / 주어 생략(예: "식품 가격이 오르면…").
[예외] 다른 나라와 명시적으로 비교하는 맥락에서만 "일본은~" 지칭 가능.

【절대 금지 — 완화 불가】
```

- [ ] **Step 1: SYSTEM_KO 화자 시점 블록 삽입 (편집)**

### Step 2: SYSTEM_JA에 화자 시점 블록 삽입

`long1_script.py`의 SYSTEM_JA에서 `【文章スタイル】` 블록의 마지막 줄(`チャンネル登録お願いします！」`) 뒤, `【変換ルール】` 바로 앞에 삽입:

OLD:
```python
  「以上、モチエンがお伝えしました！
   チャンネル登録お願いします！」

【変換ルール】
```

NEW:
```python
  「以上、モチエンがお伝えしました！
   チャンネル登録お願いします！」

【話者視点 — 全セクション共通（永続ルール）】
モチエンは日本人の話者が日本の視聴者に語りかけるチャンネルです。
[禁止]「日本の場合」「日本では」のように自国を外部から分析するような表現。
[推奨]「私たちの食卓では」「日本に住む私たちにとっては」/ 主語省略（例：「食料価格が上がると…」）。
[例外] 他国と明示的に比較する文脈でのみ「日本は〜」の使用可。

【変換ルール】
```

- [ ] **Step 2: SYSTEM_JA 화자 시점 블록 삽입 (편집)**

### Step 3: 검증 스크립트 작성·실행

- [ ] **Step 3: 변경 내용 구조 확인**

`_check_system_viewpoint.py` 작성:

```python
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from long1_script import SYSTEM_KO, SYSTEM_JA

assert "화자 시점 — 전 섹션 공통" in SYSTEM_KO, "SYSTEM_KO 화자 시점 없음"
assert "[금지]" in SYSTEM_KO and "일본의 경우" in SYSTEM_KO, "SYSTEM_KO 금지 표현 없음"
assert "話者視点" in SYSTEM_JA, "SYSTEM_JA 화자 시점 없음"
assert "日本の場合" in SYSTEM_JA, "SYSTEM_JA 금지 표현 없음"
print("OK — Task C 화자 시점 규칙 확인 완료")
```

실행:
```
python _check_system_viewpoint.py
```

Expected:
```
OK — Task C 화자 시점 규칙 확인 완료
```

- [ ] **Step 4: Commit**

```bash
git add long1_script.py
git commit -m "feat: SYSTEM_KO/JA — 자국민 화자 시점 규칙 영구 추가"
```

---

## Task D: 화면 모드 차트 태그

**Files:**
- Modify: `long1_script.py` (issue1_prompt, issue2_prompt, ja_prompt)
- Modify: `long2_tts.py` (get_section_script 함수)

태그 형식 확정: `===차트===` (시작) / `===차트끝===` (종료).  
TTS 전송 전 태그만 제거, 내용 텍스트는 그대로 보존.

### Step 1: issue1_prompt 태그 지시 추가

`long1_script.py`의 issue1_prompt 안의 `규칙:` 블록에 1줄 추가:

OLD:
```python
규칙:
- 일상 비유 또는 구체 장면을 활용해 설명할 것.
```

NEW:
```python
규칙:
- 일상 비유 또는 구체 장면을 활용해 설명할 것.
- 이 섹션은 수치 금지이므로 차트 태그가 없는 것이 정상. 예외적으로 수치가 생기면 ===차트=== ... ===차트끝=== 으로 감쌀 것.
```

- [ ] **Step 1: issue1_prompt 태그 지시 추가 (편집)**

### Step 2: issue2_prompt 태그 지시 추가

`long1_script.py`의 issue2_prompt 안의 `수치 분석:` 마지막에 추가:

OLD (수치 분석 블록 끝):
```python
- 수치는 시청자 일상의 구체 장면으로 연결할 것.
```

NEW:
```python
- 수치는 시청자 일상의 구체 장면으로 연결할 것.
- 수치를 말하는 문장·구간은 ===차트=== 와 ===차트끝=== 으로 감싸 표시할 것.
  (한 수치 설명 구간이 끝나면 반드시 ===차트끝=== 으로 닫을 것)
```

- [ ] **Step 2: issue2_prompt 태그 지시 추가 (편집)**

### Step 3: ja_prompt 태그 보존 지시 추가

`long1_script.py`의 stage_ja 함수 내 `ja_prompt` f-string의 `변환 시 주의:` 블록에 추가:

OLD:
```python
변환 시 주의:
- 한국어 [출처: ○○] 태그는 자연스럽게 일본어 문장에 녹여 넣거나 삭제 (태그 그대로 남기지 말 것)
```

NEW:
```python
변환 시 주의:
- 한국어 [출처: ○○] 태그는 자연스럽게 일본어 문장에 녹여 넣거나 삭제 (태그 그대로 남기지 말 것)
- ===차트=== 와 ===차트끝=== 태그는 위치를 유지하며 그대로 보존할 것 (번역·삭제 금지)
```

- [ ] **Step 3: ja_prompt 태그 보존 지시 추가 (편집)**

### Step 4: SYSTEM_JA 태그 보존 규칙 추가

`long1_script.py`의 SYSTEM_JA `【変換ルール】` 첫 줄 뒤에 추가:

OLD:
```python
【変換ルール】
- 韓国語の「[출처: ○○]」タグは自然な日本語文章に溶け込ませるか削除
```

NEW:
```python
【変換ルール】
- 韓国語の「[출처: ○○]」タグは自然な日本語文章に溶け込ませるか削除
- 「===차트===」「===차트끝===」タグは位置を保ったままそのまま保持すること（翻訳・削除禁止）
```

- [ ] **Step 4: SYSTEM_JA 태그 보존 규칙 추가 (편집)**

### Step 5: long2_tts.py — get_section_script에 태그 제거 추가

`long2_tts.py`의 `get_section_script` 함수에서 `SECTION_LABEL_PAT.sub` 라인 바로 앞에 삽입:

OLD:
```python
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    text = SECTION_LABEL_PAT.sub('', text)
    return text.strip()
```

NEW:
```python
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    text = re.sub(r'===차트===|===차트끝===', '', text)
    text = SECTION_LABEL_PAT.sub('', text)
    return text.strip()
```

- [ ] **Step 5: long2_tts.py 태그 제거 추가 (편집)**

### Step 6: 검증 스크립트 작성·실행

`_check_chart_tags.py` 작성:

```python
import re, sys, inspect
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import long1_script, long2_tts

# issue1_prompt에 차트 태그 지시 있는지
src = inspect.getsource(long1_script.stage_ko)
assert "===차트===" in src, "issue 프롬프트에 차트 태그 지시 없음"
assert "===차트끝===" in src, "issue 프롬프트에 차트 태그끝 지시 없음"

# ja_prompt에 태그 보존 지시 있는지
ja_src = inspect.getsource(long1_script.stage_ja)
assert "===차트===" in ja_src, "ja_prompt에 태그 보존 지시 없음"

# SYSTEM_JA에 보존 규칙 있는지
assert "===차트===" in long1_script.SYSTEM_JA, "SYSTEM_JA 태그 규칙 없음"

# TTS 스트리핑 동작 확인
sample = "오늘 ===차트=== 食料は+3.5%です ===차트끝=== 라고 합니다."
result = re.sub(r'===차트===|===차트끝===', '', sample)
assert "===차트===" not in result, "TTS 태그 제거 실패"
assert "食料は+3.5%です" in result, "TTS 내용 보존 실패"

# get_section_script 함수에 태그 제거 코드 있는지
tts_src = inspect.getsource(long2_tts.get_section_script)
assert "===차트===" in tts_src, "get_section_script에 태그 제거 없음"

print("OK — Task D 차트 태그 구조 확인 완료")
print(f"  제거 샘플: '{sample}' → '{result.strip()}'")
```

실행:
```
python _check_chart_tags.py
```

Expected:
```
OK — Task D 차트 태그 구조 확인 완료
  제거 샘플: '오늘 ===차트=== 食料は+3.5%です ===차트끝=== 라고 합니다.' → '오늘  食料は+3.5%です  라고 합니다.'
```

- [ ] **Step 7: Commit**

```bash
git add long1_script.py long2_tts.py
git commit -m "feat: 차트 태그 ===차트===/===차트끝=== — 이슈 프롬프트 지시 + TTS 제거 안전망"
```

---

## Task Cleanup: 임시 스크립트 정리

- [ ] **Step 1: 임시 파일 삭제 + 커밋**

```bash
rm _check_prompts.py _check_system_viewpoint.py _check_chart_tags.py
git add -A
git commit -m "chore: Work 3 임시 검증 스크립트 삭제"
```

---

## Self-Review

### Spec 커버리지

| 요구사항 | Task |
|---------|------|
| 인트로: 미끼 질문만, 답 없음, 수치 금지 | ✅ Task AB Step 1 |
| 이슈1: 원리 전담, 수치 금지, 이슈2 데이터 선취 금지 | ✅ Task AB Step 2 |
| 이슈2: 데이터 전담, 이슈1 반복 금지, 품목 분해 지시 | ✅ Task AB Step 3 |
| 아웃트로: 현 수준 유지(과교정 금지) | ✅ outro_prompt 변경 없음 |
| SYSTEM_KO "일본의 경우" 금지 | ✅ Task C Step 1 |
| SYSTEM_JA 「日本の場合」 금지 | ✅ Task C Step 2 |
| 화자 시점 규칙 영구·전체 롱폼 적용 | ✅ SYSTEM 상수에 박음 |
| 이슈1·2 수치 구간 ===차트=== 태그 | ✅ Task D Step 1~2 |
| TTS 전송 전 태그 제거 안전망 | ✅ Task D Step 5 |
| JA 변환 시 태그 보존 | ✅ Task D Step 3~4 |
| 새 캐릭터 추가 없음 | ✅ 코드 변경 없음 |

### Placeholder 검사
없음. 모든 코드 블록은 실행 가능한 완전한 코드.

### 타입 일관성
- 태그 형식 `===차트===` / `===차트끝===` — Step 1~5 전체 동일 ✅
- regex `r'===차트===|===차트끝==='` — Step 5(TTS) + Step 6(검증) 동일 ✅
- `inspect.getsource(long1_script.stage_ko)` — stage_ko 함수 소스 전체를 문자열로 검색 ✅
