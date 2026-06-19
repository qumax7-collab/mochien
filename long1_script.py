"""롱폼 스크립트 생성 — 2단계: 한국어 원리형 초안(KO) → 일본어 변환(JA)

실행 방법:
  python long1_script.py              → KO + JA 자동 연속 실행 (run_longform.py / GitHub Actions)
  python long1_script.py --stage ko   → 한국어 초안만 생성 → long_script_ko.json
  python long1_script.py --stage ja   → 일본어 변환만 실행 → long_script.json + long_script_verify.json
  python long1_script.py --stage ko --revise "이 부분 더 쉽게" → 수정 요청 반영 재생성
  python long1_script.py --topic business-cycle --stage ko → topic 직접 지정 (기사 없이 생성)
"""
import sys
import json
import os
import shutil
import datetime
import argparse

from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 상수 =====
GPT_MODEL                 = "gpt-4.1"
GPT_TEMP                  = 0.7
TOPIC_BANK_FILE           = "topic_bank.json"
TOPIC_HISTORY_FILE        = "topic_history.json"
LONG_SCRIPT_FILE          = "long_script.json"
LONG_SCRIPT_KO_FILE       = "long_script_ko.json"
LONG_SCRIPT_KO_BAK_FILE   = "long_script_ko.bak.json"
LONG_SCRIPT_VERIFY_FILE   = "long_script_verify.json"
OUTPUT_DIR                = "output"
SLOTS                     = ["09", "18"]
JST                       = datetime.timezone(datetime.timedelta(hours=9))
TOPIC_COOLDOWN_DAYS       = 21
ISSUE_RETRY_MIN_CHARS     = 450
DATA_BLOCK_ALL_FAIL_ABORT = True   # data_sources 전체 fetch 실패 시 중단
BACKCHECK_TEMP            = 0.3    # backcheck 역직역 전용 temperature (낮을수록 안정)
DATA_BLOCK_DEFAULT_MONTHS = 60    # data_months 미지정 토픽의 fetch 기간
DATA_BLOCK_TREND_MONTHS   = 12    # 주 소스 추이 표시 개월수
DATA_BLOCK_HIST_MONTHS    = [12, 36, 60]  # 과거 비교 오프셋 (1년전, 3년전, 5년전)

def _inject_brief(prompt: str, brief_text: str) -> str:
    """JSON 출력 지시 직전에 기획 척추 텍스트를 주입한다."""
    if not brief_text:
        return prompt
    block = f"\n\n【기획 척추 — 반드시 준수】\n{brief_text}\n"
    marker = "JSON 출력:"
    if marker in prompt:
        return prompt.replace(marker, block + marker, 1)
    return prompt + block


def _brief_section_text(brief: dict, key: str) -> str:
    """brief 섹션 값을 텍스트로 추출.
    구 포맷(string) / 신 포맷({"narrative": ...}) 양쪽 수용."""
    val = brief.get(key) if brief else None
    if isinstance(val, dict):
        return val.get("narrative", "")
    return val or ""


CHART_TAG_RULES = """\
【차트 태그 규칙 — 이슈 전 섹션 공통】
배치 원칙 (한 문단 = 한 차트):
  · 차트가 필요한 주제는 그 주제만 다루는 독립 문단으로 분리한다.
  · 여는 태그(===차트[항목, 시점]===)는 해당 문단의 맨 첫 줄.
  · 닫는 태그(===차트끝===)는 해당 문단의 맨 끝 줄.
  · 한 문단의 내레이션 전체 = 그 차트의 음성 문장. 문단 중간에 태그를 끼워 넣지 않는다.
  · 한 문단 안에 여는 태그를 2개 이상 쓰지 않는다.

형식:
  ===차트[항목, 시점]===
  (이 차트 주제만 다루는 내레이션 문단)
  ===차트끝===

항목 표기:
  · 단일 항목: [食料, 시점]
  · 비교 차트: [A vs B, 시점]  ← 반드시 " vs " 로 연결. 콤마로 항목 나열 금지 (예: [食料, 総合, 시점] → 금지).

시점 표기:
  · 단일 시점: [항목, 2026-04]
  · 기간(추이): [항목, 2025-04→2026-04]  ← "→" 로 연결.

절대 금지:
  · 항목 없는 태그: ===차트=== 또는 ===차트[, 시점]=== — 항목이 비어 있으면 출력하지 않는다.
  · 짝 없는 태그: 여는 태그(===차트[…]===)에는 반드시 닫는 태그(===차트끝===)가 뒤따라야 한다.
  · 음성문장 없는 차트 태그: 차트 태그 내부(===차트끝=== 전)에 반드시 내레이션 문장을 포함할 것.
    내레이션 없이 비어 있는 차트 태그 금지. 음성문장이 채워진 차트 태그로 섹션을 시작하는 것은 허용.
  · 문단 중간 삽입: 차트 태그를 일반 문장 사이에 끼워 넣지 않는다. 태그는 반드시 문단 경계에만 위치.
  · raw 수치: 태그 [ ] 안과 내레이션에 숫자 수치를 직접 쓰지 않는다 (화면 차트가 담당).
  · 항목 임의 생성: data_block에 실존하는 항목명만 사용.\
"""


# ===== 일본어 변환 시스템 프롬프트 (JA 단계 — モチエン 페르소나) =====
SYSTEM_JA = """\
あなたはモチエンです。入力された韓国語の原稿を日本語に変換してください。

【モチエンとは】
経済初心者にもわかりやすく解説するマクロ経済の教養ナビゲーターです。
ニュースを「入口」として、その背後にある「なぜこうなるのか」という仕組みを説明します。
専門家には当たり前のことも、初心者には当たり前ではないという前提で、丁寧に説明します。

【人格・話し方】
- 一人称: 「モチエン」（私やボクは使わない）
- 落ち着いた中性的な語り口、煽らない。
- 視聴者を「あなた」で呼ぶ（皆さんは使わない）
- 数字を出すときは必ず一度立ち止まって解説する
- 経済の話を生活の手触りに翻訳する役割
- 政治的立場は取らない、事実と影響だけ語る
- です・ます調を統一する
- 実在の人物への言及・模倣はしない

【投資関連の絶対禁止事項】
- 投資の推奨や相場予想をしない
- 「儲かる」「損する」という直接表現は使わない
- 断定的な将来予測は使わない（「必ず〜になる」禁止）

【感情表現ルール】
- 「!」の多用禁止（1スクリプトに最大1回まで）
- 「!!」を2つ以上連続して使わないこと
- 断定的な未来予測禁止

【禁止語彙】
やばい / オワコン / 爆益 / 神回 / 草 / ガチで / マジで
ぶっちゃけ / めっちゃ / やっぱ / リアルに / ヤバすぎ / すごすぎ

【文章スタイル】
- 項目番号や見出しを含めないこと
- 「issue1」「issue2」「intro」「outro」などの内部セクションラベルを本文に書かないこと
  セクション間の接続は「先ほど見てきたように」などの自然な話し言葉で
- すべて自然な日本語の文章として統合すること
- 「背景として〜」「実はここがポイントです」などの繋ぎ言葉を使うこと
- 誤読しやすい漢字にはふりがなを括弧で併記すること（例：財務省（ざいむしょう））
- 1文の長さ: 日本語で40字以内を目安とする。
  複文・長文は意味の単位で分割し、短い文で書くこと。
  数値・データの正確性が優先 — 短くするために数値を省いたり意味を損なわないこと。
  機械的な分断は禁止。意味が完結する単位でのみ分割すること。
- アウトロの末尾は必ず以下の3行で締めること:
  「皆さんはどう思いますか？コメントで教えてください！
   以上、モチエンがお伝えしました！
   チャンネル登録お願いします！」

【話者視点 — 全セクション共通（永続ルール）】
モチエンは日本人の話者が日本の視聴者に語りかけるチャンネルです。
[禁止]「日本の場合」「日本では」のように自国を外部から分析するような表現。
[推奨]「私たちの生活では」「日本に住む私たちにとっては」/ 主語省略（例：「物価が上がると…」）。
[例外] 他国と明示的に比較する文脈でのみ「日本は〜」の使用可。

【変換ルール】
- 韓国語の「[출처: ○○]」タグは自然な日本語文章に溶け込ませるか削除
- 「===차트[...]===」「===차트끝===」タグは[ ]内の指定も含め、位置・内容をそのまま保持すること（翻訳・削除禁止）
- 内容（事実・論理構造）は忠実に保持し、語調だけモチエンペルソナに変換
- イントロは必ず視聴者の疑問を代弁する一文（コールドオープン）から始めること
- 原理型タイトル強制: 事件型（○○が起きた）禁止、原理型（なぜ○○なのか）推奨

出力はJSONのみ。マークダウン記号（``` 等）は絶対に使用禁止。\
"""

# ===== 한국어 초안 시스템 프롬프트 (KO 단계) =====
SYSTEM_KO = """\
당신은 일본 거시경제 교양 콘텐츠 작가입니다.

【최우선 출력 규칙】
script_ko에는 시청자에게 그대로 읽어줄 완성 문장만. 작업 지시·메타 설명·괄호 라벨 절대 금지.

【시청자·화자 시점 — 전 섹션 공통 (영구 규칙)】
모찌엔은 일본인 화자가 일본 시청자에게 말하는 채널이다.
시청자에게 일본은 '자국'. 생활 예시는 일본 거주자의 일상(일본 마트·일본 물가·일본 직장) 기준.
시청자는 엔화로 급여를 받고 엔화로 생활한다. '엔화로 월급을 받는다면' 같은 조건문 금지.
해외여행의 예로 '일본 여행'을 들지 말 것(해외=일본 밖). 한국·한국인 시점의 비유·예시 금지.
[금지] "일본의 경우" / "일본에서는" 처럼 자국을 외부에서 분석하는 표현.
[권장] "우리 생활에서는" / "일본에 사는 우리에게는" / 주어 생략(예: "물가가 오르면…").
[예외] 다른 나라와 명시적으로 비교하는 맥락에서만 "일본은~" 지칭 가능.

【절대 금지 — 완화 불가】
- 미래 예측·전망 ("앞으로 오른다/내린다" 류 단정 표현)
- 종목·투자·금융상품 권유 또는 암시
- 데이터 근거 블록에 없는 수치·사실 주장 (할루시네이션)
- 닛케이·이코노미스트 등 저널·뉴스 기사 크롤링·인용

【허용·권장 — 이것이 이 콘텐츠의 핵심 가치다】
이미 가진 공공데이터를 분해·연결·인과 해석하는 것은 적극 권장한다.
"이미 일어난 일이 왜 그렇게 됐는가"를 끝까지 설명하는 것은 예측이 아니라 메커니즘 설명이다.
데이터 근거 블록이 있는 경우, 아래 순서로 전개한다:
  ① 분해: 블록에 여러 하위 항목이 있는 경우만 — 항목별 방향·크기 변화를 수치로 분리
  ② 연결: 각 항목 변동의 인과 사슬 (왜 그렇게 됐는가)
  ③ 반직관: 예상을 벗어나는 사실, 또는 상식과 다른 포인트 (체감·통계 괴리 있으면 포함)

【principle 사용 규칙】
principle은 '내용 설계도'다. 서술 방향·핵심 원리를 제시할 뿐이다.
principle 문장을 그대로 대본에 복사하지 말 것. 화자 말투·경어·페르소나는 SYSTEM 프롬프트가 결정한다.

규칙:
1. 경제 입문자 기준. 전문 용어는 쉽게 설명. 뉴스는 원리의 '입구' — 인과 메커니즘 설명까지.
   구어 해설체(~습니다/~죠/~이에요) 통일. 명사 종결("늘어남") 및 메모체 금지.
2. 데이터 근거 블록 수치만 인용. 블록 밖 수치 생성 절대 금지.
   수치 언급 시 기준시점은 데이터 근거 블록에 표시된 형식 그대로 사용. '今日' '今週' '先月' 등 상대 시점 표현 금지.
   블록이 없으면 수치 없이 원리로만.
3. 이슈 섹션(issue1·issue2)은 해당 이슈의 핵심 수치를 본문에 최소 1개 포함할 것(누락 금지).
   수치 표현: 자릿수가 많아 구어로 읽기 불편한 큰 수는 어림으로 풀 것 (예: 731,205명 → "약 73만 명").
   짧고 자연스러운 수는 그대로 읽을 것 (예: 출산율 1.2 / 170엔).
   어림은 data_block 실값에서 반올림으로 유도하는 것만 허용. 데이터에 없는 수 생성 절대 금지.
4. 출력은 JSON만. 마크다운(``` 등) 절대 금지.
   대본 본문에 내부 라벨(issue1/issue2/intro/outro/이슈1/이슈2/なぜ/誰が 등) 금지. 섹션 연결은 구어체로.
5. 문장 길이: 일본어 기준 한 문장 40자 이내를 지향한다.
   복문·만연체는 의미 단위로 분리해 짧은 문장으로 끊어 쓸 것.
   수치·데이터의 정확성이 우선 — 짧게 만들려고 수치를 빼거나 의미를 훼손하지 말 것.
   기계적 절단 금지. 의미가 완결되는 단위에서만 나눌 것.\
"""


# ─────────────────────────────────────────
# 데이터 fetch 헬퍼
# ─────────────────────────────────────────

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


def _normalize_date_label(date_str: str, frequency: str) -> str:
    """latest_date → 데이터 블록·ref_date_block 표시용 라벨 변환.
    ANNUAL: 'YYYY' / 'YYYY-MM-DD' → 'YYYY年'
    MONTHLY: 'YYYY-MM' → 'YYYY年M月'
    """
    if not date_str:
        return date_str
    if frequency == "ANNUAL":
        return f"{date_str[:4]}年"
    if frequency == "MONTHLY" and len(date_str) >= 7:
        parts = date_str.split("-")
        if len(parts) >= 2:
            return f"{parts[0]}年{int(parts[1])}月"
    return date_str


def _fetch_source(src: dict, months: int = DATA_BLOCK_DEFAULT_MONTHS):
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


def build_data_block(topic: dict) -> tuple:
    """
    topic의 data_sources를 fetch해서 GPT 주입용 데이터 근거 블록 텍스트 구성.
    반환: (block_text: str, issue1_ref_date: str)
    issue1_ref_date = primary 소스의 latest_date (없으면 첫 소스, 전체 실패면 "").
    전체 fetch 실패 시 ("", "") 반환.

    - 단일 소스 토픽: 기존 포맷 유지 (풍부 포맷 + 전년동월 비교)
    - 다중 소스 토픽: 비교 스냅샷 1줄 + 주 소스(과거 비교·추이) + 보조 소스(압축)
    topic.data_months 필드 있으면 해당 개월수로 fetch (없으면 DEFAULT_MONTHS).
    """
    sources = topic.get("data_sources", [])
    if not sources:
        return "", ""

    fetch_months = topic.get("data_months", DATA_BLOCK_DEFAULT_MONTHS)
    is_multi     = len(sources) > 1

    # fetch all sources
    fetched: list = []  # [(src_dict, data_dict)]
    for src in sources:
        desc = src.get("desc_ko", src.get("source", ""))
        data = _fetch_source(src, months=fetch_months)
        if data is None:
            print(f"  [경고] 소스 fetch 실패 → 건너뜀: {desc}")
            continue
        fetched.append((src, data))

    if not fetched:
        return "", ""

    primary_entry   = next(((s, d) for s, d in fetched if s.get("primary")), fetched[0])
    primary_freq    = primary_entry[1].get("frequency", "")
    issue1_ref_date = _normalize_date_label(
        primary_entry[1].get("latest_date", ""), primary_freq
    )

    if primary_freq == "ANNUAL":
        _time_rule = "연간 데이터 — 기준시점은 연도만 표기(예: '2024年時点'). 月 추가 금지."
    else:
        _time_rule = "기준시점은 연월 명시(예: '2026年4月時点')."

    header = [
        "【데이터 근거 블록】",
        "아래 수치를 근거로 대본 작성. 자연스러운 어림 허용(예: 727,288 → '약 73万'·'70万 중반'). 단 실제값과 다른 자릿수·구간으로 오해되는 표현 금지(예: 727,288을 '70万 조금 넘음' NG — 실제 73万 수준). 블록 밖 수치·주장·예측 생성 절대 금지.",
        f"에버그린 규칙: 수치 언급 시 기준시점 명시 필수. {_time_rule} 상대적 시점 표현 금지.",
        "",
    ]

    body: list[str] = []

    # ── 다중 소스: 비교 스냅샷 (한 줄) — 월차 데이터에서만 ──
    first_freq = fetched[0][1].get("frequency", "")
    if is_multi and len(fetched) > 1 and first_freq == "MONTHLY":
        snap_parts = []
        for src, data in fetched:
            desc_ko = src.get("desc_ko", "")
            parts   = desc_ko.split(" ")
            short   = parts[1].split("(")[0] if len(parts) > 1 else desc_ko[:8]
            val     = data.get("latest_value")
            snap_parts.append(f"{short}:{val:+.1f}")
        snap_date_label = _normalize_date_label(fetched[0][1].get("latest_date", ""), first_freq)
        body.append(f"품목별 비교 스냅샷 (前年同月比, {snap_date_label}기준): " + " / ".join(snap_parts))
        body.append("")

    # ── 소스별 상세 출력 ─────────────────────────────
    success = 0
    for src, data in fetched:
        tag    = "★ [주]  " if src.get("primary") else "  [보조] "
        desc   = src.get("desc_ko", src.get("source", ""))
        obs    = data.get("observations", [])
        latest = data.get("latest_value")
        ld       = data.get("latest_date", "")
        unit     = data.get("unit") or data.get("units", "")
        freq     = data.get("frequency", "")
        ld_label = _normalize_date_label(ld, freq)

        if src.get("primary") or not is_multi:
            # ── 풍부 포맷 (주 소스 또는 단일 소스) ──
            diff_str = ""
            if len(obs) >= 2:
                prev     = obs[-2]["value"]
                pd       = obs[-2]["date"]
                diff     = latest - prev
                sign     = "+" if diff >= 0 else ""
                pd_label = _normalize_date_label(pd, freq)
                diff_str = f" / 직전 대비: {sign}{diff:.2f} (직전값: {prev}, {pd_label})"

            body.append(f"{tag}{desc}")
            body.append(f"       최신값: {latest}  단위: {unit}  기준시점: {ld_label}{diff_str}")

            if is_multi and data.get("frequency") == "MONTHLY":
                # 과거 비교 (1년전, 3년전, 5년전) — 월차 다중 소스에서만
                for offset in DATA_BLOCK_HIST_MONTHS:
                    past_date = _offset_date(ld, offset)
                    past_val  = _get_obs_at(obs, past_date)
                    if past_val is not None:
                        label = f"{offset // 12}년전({past_date})"
                        diff  = latest - past_val
                        body.append(f"       {label}: {past_val:+.1f} → {latest:+.1f} ({diff:+.1f})")
                # 12개월 추이
                trend = _trend_line(obs, ld, DATA_BLOCK_TREND_MONTHS)
                body.append(f"       최근{DATA_BLOCK_TREND_MONTHS}개월 추이: {trend}")
            else:
                # 단일 소스: 기존 전년동월 비교
                if ld and len(ld) == 7:
                    try:
                        y, m    = ld.split("-")
                        yoy_key = f"{int(y)-1:04d}-{m}"
                        yoy_val = _get_obs_at(obs, yoy_key)
                        if yoy_val is not None:
                            yoy_diff = latest - yoy_val
                            yoy_sign = "+" if yoy_diff >= 0 else ""
                            body.append(
                                f"       전년 동월({yoy_key}): {yoy_val}"
                                f" → {latest} ({yoy_sign}{yoy_diff:.2f})"
                            )
                    except Exception:
                        pass

        else:
            # ── 압축 포맷 (다중 소스의 보조 소스) ───
            yoy_date = _offset_date(ld, 12)
            yoy_val  = _get_obs_at(obs, yoy_date)
            yoy_str  = (
                f" / 전년({yoy_date}):{yoy_val:+.1f}→{latest:+.1f}"
                if yoy_val is not None else ""
            )
            body.append(f"{tag}{desc}")
            body.append(f"       최신값: {latest}  기준시점: {ld_label}{yoy_str}")

        success += 1

    return ("\n".join(header + body), issue1_ref_date) if success > 0 else ("", "")


# ─────────────────────────────────────────
# 토픽 뱅크 & 히스토리
# ─────────────────────────────────────────

def load_topic_bank() -> list:
    with open(TOPIC_BANK_FILE, encoding="utf-8") as f:
        return json.load(f)["topics"]


def load_topic_history() -> dict:
    """topic_id → 마지막 발행일(YYYY-MM-DD) 딕셔너리. 파일 없으면 빈 dict."""
    if not os.path.exists(TOPIC_HISTORY_FILE):
        return {}
    try:
        with open(TOPIC_HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_topic_history(topic_id: str):
    """발행 완료된 topic_id와 오늘 날짜를 기록한다."""
    history = load_topic_history()
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    history[topic_id] = today
    with open(TOPIC_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"  topic_history 갱신: {topic_id} → {today}")


def get_available_topics(bank: list, history: dict) -> list:
    today  = datetime.datetime.now(JST).date()
    cutoff = today - datetime.timedelta(days=TOPIC_COOLDOWN_DAYS)
    priority, recent = [], []
    for t in bank:
        last = history.get(t["id"])
        if last and datetime.date.fromisoformat(last) > cutoff:
            recent.append(t)
        else:
            priority.append(t)
    return priority + recent


def _fmt_topic_list(topics: list, history: dict) -> str:
    today  = datetime.datetime.now(JST).date()
    cutoff = today - datetime.timedelta(days=TOPIC_COOLDOWN_DAYS)
    lines  = []
    for t in topics:
        last   = history.get(t["id"])
        suffix = ""
        if last and datetime.date.fromisoformat(last) > cutoff:
            suffix = f" ⚠️ 최근 발행({last}) — 가급적 제외"
        lines.append(
            f"- id: {t['id']} | 제목: {t['title_ja']} | 원리: {t['principle']}{suffix}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────

def load_today_results() -> dict:
    today    = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    date_dir = os.path.join(OUTPUT_DIR, today)

    if not os.path.exists(date_dir):
        raise Exception(
            f"오늘 날짜 폴더가 없습니다: {date_dir}\n"
            "쇼츠 파이프라인(step2_select.py)이 먼저 실행되어야 합니다."
        )

    results = {}
    for slot in SLOTS:
        path = os.path.join(date_dir, f"{slot}_gpt_result.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                results[slot] = json.load(f)
            print(f"  ✅ {slot}_gpt_result.json 로드")
        else:
            print(f"  ⚠️  {slot}_gpt_result.json 없음")

    if len(results) < 2:
        raise Exception(f"쇼츠 결과 파일 부족: {len(results)}개 (최소 2개 필요)")
    return results


# ─────────────────────────────────────────
# GPT 호출 공통
# ─────────────────────────────────────────

def call_gpt(client, messages: list, name: str) -> tuple:
    """JSON 파싱 포함. 실패 시 1회 재시도."""
    last_err = None
    for attempt in range(2):
        try:
            resp   = client.chat.completions.create(
                model=GPT_MODEL, messages=messages, temperature=GPT_TEMP,
            )
            result = json.loads(resp.choices[0].message.content.strip())
            return result, resp.usage
        except Exception as e:
            last_err = e
            if attempt == 0:
                print(f"  [재시도] {name} 실패 ({type(e).__name__})")
    print(f"  [오류] {name} 최종 실패: {last_err}")
    sys.exit(1)


# ─────────────────────────────────────────
# KO 단계
# ─────────────────────────────────────────

def call_mode_judge(client, r_list: list, bank: list, history: dict) -> tuple:
    """어떤 거시 원리 토픽으로, 모드 A/B 중 어느 쪽인지 GPT가 판정."""
    available   = get_available_topics(bank, history)
    topics_text = _fmt_topic_list(available, history)

    prompt = f"""\
아래 2개 기사와 사용 가능한 거시 토픽 목록을 보고, 오늘 롱폼 영상의 방향을 결정하세요.

【사용 가능한 거시 토픽】(⚠️ 최근 발행 표시된 항목은 가급적 제외)
{topics_text}

【기사 1 (슬롯 09)】
제목: {r_list[0]['title']}
요약: {r_list[0].get('korean_summary', '')}

【기사 2 (슬롯 18)】
제목: {r_list[1]['title']}
요약: {r_list[1].get('korean_summary', '')}

판정 기준:
- 모드 A: 두 기사가 같은 거시 원리를 보여주면 → 하나의 원리로 통합 설명
- 모드 B: 한 기사가 더 강한 원리를 담고 있으면 → 그 기사를 주축

반드시 위 토픽 목록에서 id를 선택하세요.
토픽 선정 후, 이슈1·이슈2가 다룰 각도를 각각 한 줄로 정하세요.
두 각도는 서로 분명히 겹치지 않는 분리축이어야 합니다.
(예: 원리·메커니즘 / 가계 생활 체감 / 기업·정부 입장 / 단기·장기 영향)

JSON 출력:
{{
  "mode": "A" 또는 "B",
  "topic_id": "선택한 토픽의 id",
  "topic_title_ja": "선택한 토픽의 일본어 제목",
  "principle": "선택한 토픽의 원리 설명",
  "article_main": "09" 또는 "18",
  "article_sub": "09" 또는 "18" 또는 null,
  "reason_ko": "선택 이유 한 문장",
  "issue1_angle": "이슈1이 다룰 각도 (한 줄 / 이 토픽에 자연스러운 분리축)",
  "issue2_angle": "이슈2가 다룰 각도 (이슈1과 분명히 다른 각도)"
}}"""

    result, usage = call_gpt(
        client,
        [{"role": "system", "content": SYSTEM_KO}, {"role": "user", "content": prompt}],
        "mode_judge",
    )
    print(f"  모드 판정: {result.get('mode')} / 토픽: {result.get('topic_id')} / 이유: {result.get('reason_ko')}")
    print(f"  분리축: 이슈1={result.get('issue1_angle')} / 이슈2={result.get('issue2_angle')}")
    return result, usage


def call_angle_judge(client, topic_entry: dict) -> tuple:
    """topic_override 경로: 이슈1·이슈2 분리축만 결정 (GPT 1회)."""
    prompt = f"""\
다음 거시 토픽의 롱폼 영상에서 이슈1과 이슈2가 다룰 각도를 정하세요.

【토픽】
id: {topic_entry['id']}
제목(일본어): {topic_entry['title_ja']}
설명 방향(principle): {topic_entry['principle']}

조건:
- 두 각도가 서로 분명히 겹치지 않을 것.
- 이 토픽에 가장 자연스러운 분리축을 선택할 것.
  (예: 원리·메커니즘 / 가계 생활 체감 / 기업·정부 입장 / 단기·장기 영향)

JSON 출력:
{{
  "issue1_angle": "이슈1이 다룰 각도 (한 줄, 한국어)",
  "issue2_angle": "이슈2가 다룰 각도 (한 줄, 한국어)"
}}"""

    result, usage = call_gpt(
        client,
        [{"role": "system", "content": SYSTEM_KO}, {"role": "user", "content": prompt}],
        "angle_judge",
    )
    print(f"  분리축: 이슈1={result.get('issue1_angle')} / 이슈2={result.get('issue2_angle')}")
    return result, usage


def call_backcheck(client, prompt: str):
    """backcheck 역직역 전용. temperature 낮춤. 2회 실패 시 sys.exit(1) — 이전본 잔류 금지."""
    messages = [
        {"role": "system", "content": "일본어를 한국어로 역번역합니다. JSON만 출력."},
        {"role": "user",   "content": prompt},
    ]
    last_err = None
    for attempt in range(2):
        try:
            resp    = client.chat.completions.create(
                model=GPT_MODEL, messages=messages, temperature=BACKCHECK_TEMP,
            )
            content = (resp.choices[0].message.content or "").strip()
            # 마크다운 코드 블록 제거
            if content.startswith("```"):
                lines   = content.splitlines()
                end_idx = -1 if lines[-1].strip() == "```" else len(lines)
                content = "\n".join(lines[1:end_idx]).strip()
            if not content:
                raise ValueError(
                    f"빈 응답 (finish_reason={resp.choices[0].finish_reason})"
                )
            result = json.loads(content)
            return result, resp.usage
        except Exception as e:
            last_err = e
            if attempt == 0:
                print(f"  [재시도] backcheck 실패 ({type(e).__name__}: {e})")
    print(f"  [오류] backcheck 최종 실패: {last_err}")
    sys.exit(1)


def call_ko_section(client, name: str, prompt: str) -> tuple:
    return call_gpt(
        client,
        [{"role": "system", "content": SYSTEM_KO}, {"role": "user", "content": prompt}],
        name,
    )


def call_issue_retry(client, name: str, prompt: str, result: dict) -> tuple:
    if len(result.get("script_ko", "")) >= ISSUE_RETRY_MIN_CHARS:
        return result, None
    chars = len(result.get("script_ko", ""))
    print(f"  [재시도] {name}: {chars}자 < {ISSUE_RETRY_MIN_CHARS}자 — 재생성")
    return call_ko_section(client, name + "_retry", prompt)


def _validate_numerics(ko_data: dict) -> None:
    """
    이슈 섹션 script_ko의 단위 붙은 수치(%, 円, 万, 兆, 億)가
    _data_block에서 역추적 가능한지 검사.
    역추적 불가 수치 발견 시 sys.exit(1). 과검출 우선(안전측).
    data_block 없으면 건너뜀.
    """
    import re as _re

    data_block = ko_data.get("_data_block", "")
    if not data_block:
        print("  [수치 검증 건너뜀] _data_block 없음")
        return

    # data_block에서 모든 숫자 수집 (정수·소수 포함)
    block_nums = set(_re.findall(r"\d+(?:\.\d+)?", data_block))

    # 단위 붙은 수치 패턴 (년/월/일 문맥 제외)
    _date_ctx = _re.compile(r"\d{4}[年]\d{1,2}[月](?:\d{1,2}[日])?|\d{4}[年]")
    _num_unit  = _re.compile(r"(\d+(?:\.\d+)?)\s*[%％円万兆億]")

    flagged = []
    for idx, issue in enumerate(ko_data.get("issues", []), 1):
        text = issue.get("script_ko", "")
        # 날짜 문맥 제거 후 수치 추출
        text_stripped = _date_ctx.sub("", text)
        for m in _num_unit.finditer(text_stripped):
            num_str = m.group(1)
            if num_str in block_nums:
                continue
            flagged.append(
                f"  issue{idx}: '{m.group(0)}' — _data_block 미포함 (data_block 외 수치 생성 의심)"
            )

    if flagged:
        print("\n[수치 검증 실패] data_block 밖 수치 검출:")
        for f in flagged:
            print(f)
        print("  → data_block에 없는 수치는 발화 금지. --stage ko 재생성 또는 수동 수정 필요.")
        sys.exit(1)

    print(f"  [수치 검증 OK] 이슈 수치 → data_block 역추적 완료")


def _check_outro_dirty(ko_data: dict) -> None:
    """
    outro script_ko에 issue1·2 수치(%)·연월이 잔류하는지 검사.
    잔류 탐지·경고까지만. 자동 재생성 금지.
    """
    import re as _re
    _pct  = _re.compile(r'\d+\.?\d*[%％]')
    _year = _re.compile(r'20\d{2}年\d*月?')

    issues = ko_data.get("issues", [])
    issue_text = " ".join(i.get("script_ko", "") for i in issues)
    outro_text = ko_data.get("outro", {}).get("script_ko", "")

    issue_pcts  = set(_pct.findall(issue_text))
    outro_pcts  = set(_pct.findall(outro_text))
    issue_dates = set(_year.findall(issue_text))
    outro_dates = set(_year.findall(outro_text))

    dirty_pcts  = outro_pcts  - issue_pcts
    dirty_dates = outro_dates - issue_dates

    if dirty_pcts or dirty_dates:
        print("\n  [⚠ outro dirty 검사 — 불일치 발견]")
        if dirty_pcts:
            print(f"    비율(%) outro에만 있음: {sorted(dirty_pcts)}")
            print(f"    issue1·2 비율:         {sorted(issue_pcts)}")
        if dirty_dates:
            print(f"    연월 outro에만 있음:   {sorted(dirty_dates)}")
            print(f"    issue1·2 연월:         {sorted(issue_dates)}")
        print("    → outro에 구 수치 잔류 가능성. --stage ko 재실행 또는 수동 수정 필요.")
    else:
        print("  [outro dirty 검사 OK] 비율(%)·연월 일치 확인")


def validate_ko_issues(ko_data: dict) -> None:
    """
    각 이슈 섹션 첫 차트 태그 내부 음성문장이 비어 있으면 sys.exit(1).
    음성문장이 채워진 차트 태그로 시작하는 것은 정상(통과).
    """
    import re as _re
    chart_pat = _re.compile(
        r'===차트\[([^\]]+)\]===[ \t]*\n?(.*?)\n?[ \t]*===차트끝===',
        _re.DOTALL,
    )
    errors = []
    for idx, issue in enumerate(ko_data.get("issues", []), 1):
        script = issue.get("script_ko", "")
        m = chart_pat.search(script)
        if m and not m.group(2).strip():
            errors.append(
                f"  issue{idx}: 첫 차트 태그 [{m.group(1).strip()}] 내부 음성문장 비어있음"
            )
    if errors:
        print("\n[검증 실패] 음성문장 없는 차트 태그 검출:")
        for e in errors:
            print(e)
        print("  → --stage ko를 다시 실행하거나 long_script_ko.json을 직접 수정하세요.")
        sys.exit(1)
    print("  [검증 통과] 이슈 섹션 첫 차트 내레이션 확인 완료")
    _validate_numerics(ko_data)
    _check_outro_dirty(ko_data)


def stage_ko(client, r_list, bank, history, revise=None, topic_override=None, brief: dict = None) -> dict:
    """
    KO 단계: 한국어 거시 원리형 대본 생성 → long_script_ko.json 저장.

    topic_override : topic_bank의 topic dict. 지정 시 mode_judge 건너뜀.
    r_list         : 기사 결과 [09, 18]. topic_override 사용 시 None 가능.
    revise         : 수정 요청 텍스트 (웹 UI 재생성 시).
    """
    total_tokens = 0

    # ── 1. 토픽 결정 + 분리축 결정 ──────────────────────────────────────
    if topic_override:
        topic_entry  = topic_override
        mode         = "topic-direct"
        topic_id     = topic_entry["id"]
        topic_ja     = topic_entry["title_ja"]
        principle    = topic_entry["principle"]
        reason_ko    = "topic 직접 지정"
        article_main = None
        print(f"[KO 1/5] topic 직접 지정: {topic_id} — 분리축 결정 중...")
        angles, u    = call_angle_judge(client, topic_entry)
        total_tokens += u.total_tokens
    else:
        print("[KO 1/5] 모드 판정 + 토픽 매칭 + 분리축 결정 중...")
        judgment, u  = call_mode_judge(client, r_list, bank, history)
        total_tokens += u.total_tokens
        mode         = judgment["mode"]
        topic_id     = judgment["topic_id"]
        topic_ja     = judgment["topic_title_ja"]
        principle    = judgment["principle"]
        reason_ko    = judgment["reason_ko"]
        article_main = judgment.get("article_main")
        topic_entry  = next((t for t in bank if t["id"] == topic_id), None)
        if not topic_entry:
            print(f"  [경고] topic_id '{topic_id}'가 topic_bank에 없습니다.")
        angles = judgment

    issue1_angle     = angles.get("issue1_angle", "원리·메커니즘")
    exp_dist         = (topic_entry or {}).get("experience_distance", "indirect")
    data_struct      = (topic_entry or {}).get("data_structure",      "single-series")
    _issue2_fallback = "가계 생활 체감" if exp_dist == "direct" else "세부 영향·구조 분석"
    issue2_angle     = angles.get("issue2_angle", _issue2_fallback)

    if brief and brief.get("forced_angles"):
        fa = brief["forced_angles"]
        if fa.get("issue1"):
            issue1_angle = fa["issue1"]
            print(f"  [기획 척추] 이슈1 각도 강제: {issue1_angle}")
        if fa.get("issue2"):
            issue2_angle = fa["issue2"]
            print(f"  [기획 척추] 이슈2 각도 강제: {issue2_angle}")

    # ── 데이터 근거 블록 fetch ────────────────────────────
    print("  데이터 근거 블록 fetch 중...")
    data_block, issue1_ref_date = build_data_block(topic_entry) if topic_entry else ("", "")
    if not data_block:
        if DATA_BLOCK_ALL_FAIL_ABORT:
            print("[오류] 데이터 근거 블록 fetch 전체 실패.")
            print("       네트워크 상태 확인 후 재실행하세요. 임의 수치 생성 방지를 위해 중단합니다.")
            sys.exit(1)
        print("  [경고] 데이터 블록 없음. 수치 없이 원리만으로 진행.")
    else:
        src_count = data_block.count("[주]") + data_block.count("[보조]")
        print(f"  데이터 블록 구성 완료 ({src_count}개 소스)")

    revise_prefix = (
        f"\n\n【수정 요청】{revise}\n위 요청을 반영해 다시 작성하세요.\n" if revise else ""
    )

    # 기사 블록 (intro에서만 선택적으로 사용)
    if r_list:
        article_block = (
            "【오늘 기사 (입구 소재)】\n"
            "기사는 '왜 이 원리를 지금 설명하는가'의 입구 소재로만 씁니다. 기사 내용 상세 전달 금지.\n"
            f"■ 기사1: {r_list[0]['title']} / {r_list[0].get('korean_summary', '')}\n"
            f"■ 기사2: {r_list[1]['title']} / {r_list[1].get('korean_summary', '')}"
        )
    else:
        if exp_dist == "direct":
            article_block = (
                "【기사 없음】\n"
                "이 원리가 시청자 일상에서 언제 체감되는지를 도입 소재로 쓰세요.\n"
                "(예: 장바구니 가격이 오를 때, 전기료 고지서를 받을 때 드는 의문)"
            )
        else:
            article_block = (
                "【기사 없음】\n"
                "이 원리가 뉴스·통계에서 어떻게 드러나는지를 도입 소재로 쓰세요.\n"
                "일상 체감 장면을 억지로 붙이지 않아도 됨. 통계 수치나 원리적 의문 활용 권장.\n"
                "(예: 경기가 좋다/나쁘다는 뉴스가 나올 때 느끼는 막연한 의문)"
            )

    # ── 2. 인트로 — 첫 15초 콜드오픈 (질문형) ───────────
    _intro_hook_hint = (
        "방향 예시: 체감 사례와 통계의 역설을 연결하는 의문으로. "
        "예: \"에너지 가격은 내렸는데 왜 장바구니는 더 무거운가\""
        if exp_dist == "direct" else
        "방향 예시: 통계 수치나 원리 자체에서 나오는 의문으로. 일상 체감 장면을 억지로 붙이지 않아도 됨."
    )
    print("[KO 2/5] 인트로 한국어 초안 생성 중...")
    intro_prompt = f"""\
롱폼 영상의 인트로(첫 15초 콜드오픈)를 한국어로 작성하세요.{revise_prefix}

【거시 원리 주제】
{topic_ja}
설명 방향: {principle}

{article_block}

규칙:
- 데이터에서 나온 반직관적 의문으로 열 것.
  {_intro_hook_hint}
- 인트로에서 답·결론·수치를 주지 않는다. 의문을 던지고 끝까지 봐야 풀리게.
- 인사·자기소개 금지 / 3~5문장으로 간결하게

JSON 출력:
{{
  "script_ko": "인트로 본문 (한국어 / 3~5문장)",
  "image_prompt": "Pexels 검색 영어 키워드 (장소·시간대 구체적으로)"
}}"""

    if brief and _brief_section_text(brief, "intro"):
        intro_prompt = _inject_brief(intro_prompt, _brief_section_text(brief, "intro"))
    intro_result, u = call_ko_section(client, "ko_intro", intro_prompt)
    total_tokens += u.total_tokens
    print(f"      완료 ({len(intro_result.get('script_ko', ''))}자)")

    # ── 3. 이슈1 — 「なぜ」: 인과 메커니즘 설명 ─────────
    _issue1_scene_rule = (
        "- 일상 비유 또는 구체 장면을 활용해 설명할 것."
        if exp_dist == "direct" else
        "- 원리·인과 구조 중심으로 설명할 것. 자연스러운 일상 예시는 활용 가능하지만 억지 장면 금지."
    )
    print("[KO 3/5] 이슈1(なぜ) 한국어 초안 생성 중...")
    ref_date_block = (
        f"\n\n【이슈1 기준 시점 — 코드 확정값】\n"
        f"대표 수치 기준시점: {issue1_ref_date}\n"
        f"이 시점을 대본 내러티브와 차트 태그 양쪽에 그대로 사용할 것."
        if issue1_ref_date else ""
    )
    issue1_prompt = f"""\
롱폼 이슈1 섹션을 한국어로 작성하세요.{revise_prefix}

【이슈1 역할 — 원리 + 대표 수치】
principle이 제시한 메커니즘·인과 구조를 설명하는 섹션.
data_block에서 큰 대비를 보여주는 대표 수치 1~2개는 허용.
세부 항목 분해는 이슈2에서 다룬다.

【이슈1 각도】{issue1_angle}
이 각도 하나를 처음부터 끝까지 한 흐름으로 깊게 풀 것. 여러 갈래로 얕게 훑지 말 것.
분량 {ISSUE_RETRY_MIN_CHARS}자 이상이지만 길이 채우기가 목적이 아님. 밀도 우선.

【거시 원리 주제】
{topic_ja}
설명 방향: {principle}

【인트로 핵심 질문 — 컨텍스트 전용, 반복 금지】
{intro_result.get('script_ko', '')}{ref_date_block}

규칙:
- 인트로 본문을 그대로 반복하지 말 것. 이슈1은 인트로 다음 내용부터 시작할 것.
{_issue1_scene_rule}

{CHART_TAG_RULES}

JSON 출력:
{{
  "title_ko": "이슈1 섹션 제목 (14자 이내)",
  "script_ko": "이슈1 본문",
  "summary_ko": "이슈1 핵심 요점 2줄 (아웃트로 컨텍스트용)",
  "image_prompt": "Pexels 검색 영어 키워드"
}}"""

    if brief and _brief_section_text(brief, "issue1"):
        issue1_prompt = _inject_brief(issue1_prompt, _brief_section_text(brief, "issue1"))
    issue1_result, u = call_ko_section(client, "ko_issue1", issue1_prompt)
    total_tokens += u.total_tokens
    issue1_result, u_retry = call_issue_retry(client, "ko_issue1", issue1_prompt, issue1_result)
    if u_retry is not None:
        total_tokens += u_retry.total_tokens
    print(f"      완료 ({len(issue1_result.get('script_ko', ''))}자)")

    # ── 4. 이슈2 — 「誰が」: 데이터 근거 영향 설명 ──────
    if data_struct == "multi-item":
        _issue2_role = (
            "【이슈2 역할 — 세분화 + 의미 반전】\n"
            "이슈1의 대표 수치를 data_block의 세부 항목별로 분해하고, 예상과 다른 사실(반전)을 드러내는 섹션.\n"
            "이슈1에서 설명한 원리·개념을 반복하지 말 것. 세부 항목 수치 분해가 이 섹션의 핵심."
        )
    else:
        _issue2_role = (
            "【이슈2 역할 — 심화 + 의미 반전】\n"
            "이슈2 각도에서 이슈1의 원리를 다른 층위로 심화하는 섹션.\n"
            "이슈1에서 설명한 원리·개념을 반복하지 말 것. 이슈2 각도에서 새로운 반전 포인트를 드러내는 것이 핵심."
        )
    _issue2_scene_rule = (
        "- 수치 변화를 시청자 일상의 구체 장면으로 연결할 것."
        if exp_dist == "direct" else
        "- 수치 변화의 경제·사회적 영향을 원리적으로 설명할 것. 억지 일상 장면 금지."
    )
    print("[KO 4/5] 이슈2(誰が) 한국어 초안 생성 중...")
    data_section = data_block if data_block else "(데이터 블록 없음 — 수치 없이 원리로만 설명)"

    issue2_prompt = f"""\
롱폼 이슈2 섹션을 한국어로 작성하세요.{revise_prefix}

{_issue2_role}

【이슈2 각도】{issue2_angle}
이 각도 하나를 처음부터 끝까지 한 흐름으로 깊게 풀 것. 여러 갈래로 얕게 훑지 말 것.
분량 {ISSUE_RETRY_MIN_CHARS}자 이상이지만 길이 채우기가 목적이 아님. 밀도 우선.

【거시 원리 주제】{topic_ja}

{data_section}

수치 분석:
- data_block의 주요 항목을 분해해 각각의 방향·크기 변화를 제시할 것.
- 이슈1의 대표 수치와 다른 방향이거나 예상을 벗어나는 항목이 있다면 반전 포인트로 강조.
{_issue2_scene_rule}

【앞 섹션 요약】
{issue1_result.get('summary_ko', '')}

{CHART_TAG_RULES}

JSON 출력:
{{
  "title_ko": "이슈2 섹션 제목 (14자 이내)",
  "script_ko": "이슈2 본문",
  "summary_ko": "다음 섹션으로 넘길 핵심 요점 2줄",
  "image_prompt": "Pexels 검색 영어 키워드"
}}"""

    if brief and _brief_section_text(brief, "issue2"):
        issue2_prompt = _inject_brief(issue2_prompt, _brief_section_text(brief, "issue2"))
    issue2_result, u = call_ko_section(client, "ko_issue2", issue2_prompt)
    total_tokens += u.total_tokens
    issue2_result, u_retry = call_issue_retry(client, "ko_issue2", issue2_prompt, issue2_result)
    if u_retry is not None:
        total_tokens += u_retry.total_tokens
    print(f"      완료 ({len(issue2_result.get('script_ko', ''))}자)")

    # ── 5. 아웃트로 — 「私たちは」 ───────────────────────
    print("[KO 5/5] 아웃트로(私たちは) 한국어 초안 생성 중...")
    outro_prompt = f"""\
롱폼 아웃트로(결론)를 한국어로 작성하세요.{revise_prefix}
역할: 「私たちは？」— 인트로 질문에 답하고 일상에서의 활용 포인트 제시.

【거시 원리 주제】{topic_ja}

【인트로 핵심 질문】
{intro_result.get('script_ko', '')}

【전체 흐름 요약】
이슈1: {issue1_result.get('summary_ko', '')}
이슈2: {issue2_result.get('summary_ko', '')}

구성:
1. 이슈1·이슈2에서 설명한 내용을 근거로 삼아, 인트로가 던진 바로 그 질문에 대한 답으로 시작할 것.
   질문 형태에 맞춰 답하고, 고정 문구("왜 이런 현상이 일어나는지는 ○○이기 때문입니다" 류)를 쓰지 말 것.
2. 오늘 원리를 알면 이런 뉴스를 다르게 읽을 수 있는 포인트 1가지
3. 아래 사인오프로 끝낼 것 (한 글자도 변경 금지):
   「여러분은 어떻게 생각하시나요？ 댓글로 알려주세요！
    이상, 모찌엔이 전해드렸습니다！
    채널 구독 부탁드립니다！」

JSON 출력:
{{
  "script_ko": "아웃트로 본문",
  "image_prompt": "Pexels 검색 영어 키워드"
}}"""

    if brief and _brief_section_text(brief, "outro"):
        outro_prompt = _inject_brief(outro_prompt, _brief_section_text(brief, "outro"))
    outro_result, u = call_ko_section(client, "ko_outro", outro_prompt)
    total_tokens += u.total_tokens
    print(f"      완료 ({len(outro_result.get('script_ko', ''))}자)")

    # ── 저장 ──────────────────────────────────────────────
    ko_data = {
        "mode":           mode,
        "topic_id":       topic_id,
        "topic_title_ja": topic_ja,
        "principle":      principle,
        "article_main":   article_main,
        "reason_ko":      reason_ko,
        "issue1_angle":   issue1_angle,
        "issue2_angle":   issue2_angle,
        "intro": {
            "script_ko":    intro_result.get("script_ko", ""),
            "image_prompt": intro_result.get("image_prompt", "japanese economy"),
        },
        "issues": [
            {
                "title_ko":     issue1_result.get("title_ko", "なぜ"),
                "script_ko":    issue1_result.get("script_ko", ""),
                "summary_ko":   issue1_result.get("summary_ko", ""),
                "image_prompt": issue1_result.get("image_prompt", "japanese economy"),
            },
            {
                "title_ko":     issue2_result.get("title_ko", "誰が"),
                "script_ko":    issue2_result.get("script_ko", ""),
                "summary_ko":   issue2_result.get("summary_ko", ""),
                "image_prompt": issue2_result.get("image_prompt", "japanese economy"),
            },
        ],
        "outro": {
            "script_ko":    outro_result.get("script_ko", ""),
            "image_prompt": outro_result.get("image_prompt", "japanese economy"),
        },
    }

    ko_data["_data_block"] = data_block   # 수치 역추적 검증용

    if os.path.exists(LONG_SCRIPT_KO_FILE):
        shutil.copy2(LONG_SCRIPT_KO_FILE, LONG_SCRIPT_KO_BAK_FILE)
        print(f"  백업: {LONG_SCRIPT_KO_BAK_FILE}")

    with open(LONG_SCRIPT_KO_FILE, "w", encoding="utf-8") as f:
        json.dump(ko_data, f, ensure_ascii=False, indent=2)

    total_chars = (
        len(ko_data["intro"]["script_ko"])
        + len(ko_data["issues"][0]["script_ko"])
        + len(ko_data["issues"][1]["script_ko"])
        + len(ko_data["outro"]["script_ko"])
    )
    print(f"\n  KO 완료 | 총 {total_chars}자 | 토큰 {total_tokens:,} | 토픽: {topic_id}")
    validate_ko_issues(ko_data)
    return ko_data


# ─────────────────────────────────────────
# JA 단계
# ─────────────────────────────────────────

def stage_ja(client) -> dict:
    """
    JA 단계: long_script_ko.json 로드 → 일본어 변환 → long_script.json 저장.
    + 역직역(한국어) → long_script_verify.json 저장.
    """
    if not os.path.exists(LONG_SCRIPT_KO_FILE):
        raise Exception(f"{LONG_SCRIPT_KO_FILE} 없음. --stage ko를 먼저 실행하세요.")

    with open(LONG_SCRIPT_KO_FILE, encoding="utf-8") as f:
        ko = json.load(f)

    total_tokens = 0

    # ── 1. 일본어 변환 ────────────────────────────────────
    print("[JA 1/2] 일본어 변환 중...")
    ko_draft_text = json.dumps(ko, ensure_ascii=False, indent=2)

    ja_prompt = f"""\
아래 한국어 대본을 モチエン 일본어 대본으로 변환하세요.

변환 시 주의:
- 내용(사실·논리 구조)은 충실히 보존하고 어조만 モチエン 페르소나로 변환

【한국어 대본】
{ko_draft_text}

JSON 출력:
{{
  "title": "동영상 제목 (일본어 40자 이내 / 원리형)",
  "short_title": "6~10자 핵심 키워드 (일본어)",
  "hashtags": ["#経済ニュース", "#モチエン", "#日本経済", "... (#Shortsは含めないこと)"],
  "korean_summary": "한국어 1줄 요약",
  "_slug_keyword": "{ko.get('topic_id', 'economy')}",
  "intro": {{
    "script": "인트로 일본어 대본",
    "image_prompt": "{ko['intro']['image_prompt']}"
  }},
  "issues": [
    {{
      "title": "이슈1 섹션 제목 (일본어 14자 이내)",
      "script": "이슈1 일본어 대본",
      "image_prompt": "{ko['issues'][0]['image_prompt']}"
    }},
    {{
      "title": "이슈2 섹션 제목 (일본어 14자 이내)",
      "script": "이슈2 일본어 대본",
      "image_prompt": "{ko['issues'][1]['image_prompt']}"
    }}
  ],
  "outro": {{
    "script": "아웃트로 일본어 대본",
    "image_prompt": "{ko['outro']['image_prompt']}"
  }}
}}"""

    ja_result, u = call_gpt(
        client,
        [{"role": "system", "content": SYSTEM_JA}, {"role": "user", "content": ja_prompt}],
        "ja_convert",
    )
    total_tokens += u.total_tokens
    print(f"      변환 완료 (토큰 {u.total_tokens:,})")

    with open(LONG_SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(ja_result, f, ensure_ascii=False, indent=2)

    save_topic_history(ko.get("topic_id", "unknown"))

    # ── 2. 역직역 (검증용) ────────────────────────────────
    print("[JA 2/2] 역직역(한국어 확인용) 생성 중...")
    backcheck_prompt = f"""\
아래 일본어 대본을 한국어로 역번역하세요. (검증용)

(인트로) {ja_result['intro']['script']}

(이슈1) {ja_result['issues'][0]['script']}

(이슈2) {ja_result['issues'][1]['script']}

(아웃트로) {ja_result['outro']['script']}

JSON 출력:
{{
  "intro_ko": "...",
  "issue1_ko": "...",
  "issue2_ko": "...",
  "outro_ko": "..."
}}"""

    verify_result, u = call_backcheck(client, backcheck_prompt)
    total_tokens += u.total_tokens
    with open(LONG_SCRIPT_VERIFY_FILE, "w", encoding="utf-8") as f:
        json.dump(verify_result, f, ensure_ascii=False, indent=2)

    print(f"\n  JA 완료 | 토큰 {total_tokens:,}")
    print(f"  제목: {ja_result.get('title', '')}")
    print(f"  slug: {ja_result.get('_slug_keyword', '')}")
    return ja_result


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="롱폼 스크립트 생성")
    parser.add_argument("--stage", choices=["ko", "ja"], default=None,
                        help="ko: 한국어 초안만 / ja: 일본어 변환만 / 없으면 양쪽 자동 실행")
    parser.add_argument("--revise", type=str, default=None,
                        help="KO 재생성 시 수정 요청 텍스트")
    parser.add_argument("--topic", type=str, default=None,
                        help="topic_id 직접 지정 (기사 없이 생성 / 예: --topic business-cycle)")
    parser.add_argument("--brief-file", type=str, default=None,
                        help="섹션별 기획 척추 JSON 파일 (예: brief_energy_dependency.json)")
    args = parser.parse_args()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    brief = None
    if args.brief_file:
        with open(args.brief_file, encoding="utf-8") as f:
            brief = json.load(f)
        print(f"  [기획 척추] {args.brief_file} 로드 완료 (topic: {brief.get('_topic_id', '?')})")

    if args.stage == "ja":
        print("=== [JA 단계] 일본어 변환 ===")
        stage_ja(client)
        print(f"\n{LONG_SCRIPT_FILE} 저장 완료")
        print(f"{LONG_SCRIPT_VERIFY_FILE} 저장 완료")
        return

    # ── KO 단계 ───────────────────────────────────────────
    bank    = load_topic_bank()
    history = load_topic_history()

    if args.topic:
        # topic 직접 지정 경로 — 기사 불필요
        topic_entry = next((t for t in bank if t["id"] == args.topic), None)
        if not topic_entry:
            print(f"[오류] topic_id '{args.topic}'를 topic_bank.json에서 찾을 수 없습니다.")
            print(f"       사용 가능한 id: {[t['id'] for t in bank if t['status'] == 'active']}")
            sys.exit(1)
        if topic_entry.get("status") != "active":
            print(f"[오류] topic '{args.topic}'의 status가 active가 아닙니다: {topic_entry.get('status')}")
            sys.exit(1)
        print(f"\n=== [KO 단계] topic 직접 지정: {args.topic} ===")
        stage_ko(client, r_list=None, bank=bank, history=history,
                 revise=args.revise, topic_override=topic_entry, brief=brief)
    else:
        # 기존 기사 기반 경로
        print("=== 당일 쇼츠 gpt_result 로드 ===")
        results = load_today_results()
        r_list  = [results["09"], results["18"]]
        print("\n=== [KO 단계] 한국어 거시 원리형 초안 생성 ===")
        stage_ko(client, r_list, bank, history, revise=args.revise, brief=brief)

    print(f"\n{LONG_SCRIPT_KO_FILE} 저장 완료")

    if args.stage == "ko":
        return  # 웹 UI 모드: 여기서 멈추고 검토 대기

    # 자동 모드: JA 단계도 연속 실행
    print("\n=== [JA 단계] 일본어 변환 ===")
    stage_ja(client)
    print(f"\n{LONG_SCRIPT_FILE} 저장 완료")
    print(f"{LONG_SCRIPT_VERIFY_FILE} 저장 완료")


if __name__ == "__main__":
    main()
