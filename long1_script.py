"""롱폼 스크립트 생성 — 2단계: 한국어 원리형 초안(KO) → 일본어 변환(JA)

실행 방법:
  python long1_script.py              → KO + JA 자동 연속 실행 (run_longform.py / GitHub Actions)
  python long1_script.py --stage ko   → 한국어 초안만 생성 → long_script_ko.json
  python long1_script.py --stage ja   → 일본어 변환만 실행 → long_script.json + long_script_verify.json
  python long1_script.py --stage ko --revise "이 부분 더 쉽게" → 수정 요청 반영 재생성
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
GPT_MODEL               = "gpt-4.1"
GPT_TEMP                = 0.7
TOPIC_BANK_FILE         = "topic_bank.json"
TOPIC_HISTORY_FILE      = "topic_history.json"
LONG_SCRIPT_FILE        = "long_script.json"
LONG_SCRIPT_KO_FILE     = "long_script_ko.json"
LONG_SCRIPT_KO_BAK_FILE = "long_script_ko.bak.json"
LONG_SCRIPT_VERIFY_FILE = "long_script_verify.json"
OUTPUT_DIR              = "output"
SLOTS                   = ["09", "18"]
JST                     = datetime.timezone(datetime.timedelta(hours=9))
TOPIC_COOLDOWN_DAYS     = 21   # 이 기간 내 발행한 토픽은 GPT에 후순위로 전달
ISSUE_RETRY_MIN_CHARS   = 450  # KO 이슈 섹션 재시도 임계값: 미만이면 1회 재생성

# ===== 일본어 변환 시스템 프롬프트 (JA 단계 — モチエン 페르소나) =====
# 한국어 주석: 모찌엔 거시경제 교양 해설 페르소나. 뉴스를 입구로 원리를 설명.
SYSTEM_JA = """\
あなたはモチエンです。入力された韓国語の原稿を日本語に変換してください。

【モチエンとは】
経済初心者にもわかりやすく解説するマクロ経済の教養ナビゲーターです。
（경제 입문자도 이해할 수 있는 거시경제 교양 해설가입니다.）
ニュースを「入口」として、その背後にある「なぜこうなるのか」という仕組みを説明します。
（뉴스를 "입구"로 삼아 그 배후의 경제 원리를 설명합니다.）
専門家には当たり前のことも、初心者には当たり前ではないという前提で、丁寧に説明します。
（전문가에게 당연한 것도, 입문자에게는 당연하지 않다는 전제로 친절하게 설명합니다.）

【人格・話し方】
- 一人称: 「モチエン」（私やボクは使わない）
- 落ち着いた中性的な語り口、煽らない。（침착하고 중성적인 말투, 扇동 금지）
- 視聴者を「あなた」で呼ぶ（皆さんは使わない）
- 数字を出すときは必ず一度立ち止まって解説する
- 経済の話を生活の手触りに翻訳する役割
- 政治的立場は取らない、事実と影響だけ語る
- です・ます調を統一する
- 実在の人物への言及・模倣はしない（실존 인물 언급·흉내 금지）

【投資関連の絶対禁止事項】（투자 관련 절대 금지）
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
- 「issue1」「issue2」「intro」「outro」などの内部セクションラベルを本文に書かないこと（내부 섹션 라벨 금지）
  セクション間の接続は「先ほど見てきたように」などの自然な話し言葉で
- すべて自然な日本語の文章として統合すること
- 「背景として〜」「実はここがポイントです」などの繋ぎ言葉を使うこと
- 誤読しやすい漢字にはふりがなを括弧で併記すること（例：財務省（ざいむしょう））
- アウトロの末尾は必ず「以上、モチエンがお伝えしました！」で締めること

【変換ルール】
- 韓国語の「[출처: ○○]」タグは自然な日本語文章に溶け込ませるか削除（タグそのまま残さない）
- 内容（事実・論理構造）は忠実に保持し、語調だけモチエンペルソナに変換
- イントロは必ず視聴者を引き込む一文（フック）から始めること

出力はJSONのみ。マークダウン記号（``` 等）は絶対に使用禁止。\
"""

# ===== 한국어 초안 시스템 프롬프트 (KO 단계) =====
SYSTEM_KO = """\
당신은 일본 거시경제 교양 콘텐츠 작가입니다.

규칙:
1. 입력된 기사 데이터(raw_summary_jp, title, korean_summary)에 있는 사실만 사용하세요.
   LLM 내부 지식으로 수치·주장을 추가 생성하는 것은 금지입니다.
2. 주요 수치나 사실을 언급할 때는 [출처: 기사1] 또는 [출처: 기사2] 형태로 근거를 표기하세요.
3. 독자는 경제 입문자입니다. 전문 용어는 반드시 쉽게 설명하세요.
4. 뉴스는 원리를 설명하는 '입구'입니다. 기사의 사실(사건)만 전달하고 끝내지 말고,
   반드시 "왜 그렇게 하는가"라는 인과 메커니즘을 설명하세요.
   단, 검증된 교과서적 원리에 한하며, 미래 전망·예측은 금지입니다.
5. 투자 권유, 시세 예측, 단정적 미래 예측은 절대 하지 마세요.
6. 출력은 JSON만. 마크다운(``` 등) 절대 금지.
7. 대본 본문에 'issue1', 'issue2', 'intro', 'outro', '이슈1', '이슈2' 같은
   내부 섹션 라벨을 절대 쓰지 말 것. 섹션 연결은 구어체로
   (예: '앞서 살펴봤듯이', '이어서', '여기서 한 가지 더').\
"""


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
    """
    토픽을 우선·후순위로 분류해 반환.
    최근 COOLDOWN 일 이내 발행된 토픽은 후순위 끝에 배치.
    이유: 같은 토픽 반복 없이 15개 토픽이 골고루 소비되도록.
    """
    today = datetime.datetime.now(JST).date()
    cutoff = today - datetime.timedelta(days=TOPIC_COOLDOWN_DAYS)

    priority, recent = [], []
    for t in bank:
        last = history.get(t["id"])
        if last and datetime.date.fromisoformat(last) > cutoff:
            recent.append(t)
        else:
            priority.append(t)

    return priority + recent  # 우선순위 토픽 먼저


def _fmt_topic_list(topics: list, history: dict) -> str:
    """GPT에 전달할 토픽 목록 텍스트 생성."""
    today = datetime.datetime.now(JST).date()
    cutoff = today - datetime.timedelta(days=TOPIC_COOLDOWN_DAYS)
    lines = []
    for t in topics:
        last = history.get(t["id"])
        suffix = ""
        if last and datetime.date.fromisoformat(last) > cutoff:
            suffix = f" ⚠️ 최근 발행({last}) — 가급적 제외"
        lines.append(f"- id: {t['id']} | 제목: {t['title_ja']} | 원리: {t['principle']}{suffix}")
    return "\n".join(lines)


# ─────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────

def load_today_results() -> dict:
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
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
            resp = client.chat.completions.create(
                model=GPT_MODEL,
                messages=messages,
                temperature=GPT_TEMP,
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

def call_mode_judge(client, r_list: list, bank: list, history: dict) -> dict:
    """어떤 거시 원리 토픽으로, 모드 A/B 중 어느 쪽인지 GPT가 판정."""
    available = get_available_topics(bank, history)
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
- 모드 B: 한 기사가 더 강한 원리를 담고 있으면 → 그 기사를 주축, 나머지는 intro에서 가볍게 언급

반드시 위 토픽 목록에서 id를 선택하세요.
JSON 출력:
{{
  "mode": "A" 또는 "B",
  "topic_id": "선택한 토픽의 id",
  "topic_title_ja": "선택한 토픽의 일본어 제목",
  "principle": "선택한 토픽의 원리 설명",
  "article_main": "09" 또는 "18",
  "article_sub": "09" 또는 "18" 또는 null,
  "reason_ko": "선택 이유 한 문장"
}}"""

    result, usage = call_gpt(
        client,
        [{"role": "system", "content": SYSTEM_KO}, {"role": "user", "content": prompt}],
        "mode_judge",
    )
    print(f"  모드 판정: {result.get('mode')} / 토픽: {result.get('topic_id')} / 이유: {result.get('reason_ko')}")
    return result, usage


def call_ko_section(client, name: str, prompt: str) -> tuple:
    """한국어 섹션 생성 공통 래퍼."""
    return call_gpt(
        client,
        [{"role": "system", "content": SYSTEM_KO}, {"role": "user", "content": prompt}],
        name,
    )


def call_issue_retry(client, name: str, prompt: str, result: dict) -> tuple:
    """이슈 섹션 결과가 ISSUE_RETRY_MIN_CHARS 미만이면 1회 재시도.
    재시도 없으면 (result, None) / 재시도 시 (new_result, new_usage) 반환."""
    if len(result.get("script_ko", "")) >= ISSUE_RETRY_MIN_CHARS:
        return result, None
    chars = len(result.get("script_ko", ""))
    print(f"  [재시도] {name}: {chars}자 < {ISSUE_RETRY_MIN_CHARS}자 — 재생성")
    return call_ko_section(client, name + "_retry", prompt)


def stage_ko(client, r_list: list, bank: list, history: dict, revise: str = None) -> dict:
    """
    KO 단계: 한국어 거시 원리형 대본 생성 → long_script_ko.json 저장.
    revise: 수정 요청 텍스트 (웹 UI 재생성 시 사용).
    """
    total_tokens = 0

    # ── 1. 모드 판정 ──────────────────────────────────────
    print("[KO 1/5] 모드 판정 + 토픽 매칭 중...")
    judgment, u = call_mode_judge(client, r_list, bank, history)
    total_tokens += u.total_tokens

    mode         = judgment["mode"]
    topic_id     = judgment["topic_id"]
    topic_ja     = judgment["topic_title_ja"]
    principle    = judgment["principle"]
    main_slot    = judgment["article_main"]
    reason_ko    = judgment["reason_ko"]

    r_main = r_list[0] if main_slot == "09" else r_list[1]
    r_sub  = r_list[1] if main_slot == "09" else r_list[0]

    revise_prefix = f"\n\n【수정 요청】{revise}\n위 요청을 반영해 다시 작성하세요.\n" if revise else ""

    def _r_info(r):
        return (
            f"제목: {r['title']}\n"
            f"요약(한국어): {r.get('korean_summary', '')}\n"
            f"원문(일본어): {r.get('raw_summary_jp', r.get('korean_summary', ''))}"
        )

    # ── 2. 인트로 ─────────────────────────────────────────
    print("[KO 2/5] 인트로 한국어 초안 생성 중...")
    intro_prompt = f"""\
롱폼 영상의 인트로(서론)를 한국어로 작성하세요.{revise_prefix}

【거시 원리 주제】
{topic_ja}
설명 방향: {principle}

【오늘 기사 (입구)】
■ 기사1 (슬롯 09): {r_list[0]['title']} / {r_list[0].get('korean_summary', '')}
■ 기사2 (슬롯 18): {r_list[1]['title']} / {r_list[1].get('korean_summary', '')}

【모드】{mode} — {reason_ko}

필수 항목 (각 항목 3~4문장씩):
1. 오늘 뉴스로 시청자를 끌어들이는 훅 (충격적 수치, 혹은 "당신의 ○○이 바뀐다" 형식)
2. 이 뉴스가 시청자 생활과 왜 관련 있는지
3. 오늘 영상에서 배울 거시 원리 예고

기사에 있는 수치 사용 시 [출처: 기사1] 또는 [출처: 기사2] 표기.

JSON 출력:
{{
  "script_ko": "인트로 본문 (자연스러운 한국어)",
  "image_prompt": "Pexels 검색 영어 키워드 (장소·시간대 구체적으로)"
}}"""

    intro_result, u = call_ko_section(client, "ko_intro", intro_prompt)
    total_tokens += u.total_tokens
    print(f"      완료 ({len(intro_result.get('script_ko', ''))}자)")

    # ── 3. 이슈1 (주 기사 기반) ───────────────────────────
    print("[KO 3/5] 이슈1 한국어 초안 생성 중...")
    issue1_prompt = f"""\
롱폼 영상의 이슈1 섹션을 한국어로 작성하세요.{revise_prefix}

【거시 원리 주제】
{topic_ja}
설명 방향: {principle}

【담당 기사 원문】
{_r_info(r_main)}

【이전 섹션 흐름】인트로 요약: {intro_result.get('script_ko', '')[:150]}…

필수 항목 (각 항목 3~4문장씩) — 아래 3층 구조를 순서대로 채울 것:

【層1: 배경·현황】
1. 배경: 이 사건이 왜 지금 일어났는가 (시대적 맥락 포함)
2. 현황: 기사의 핵심 수치·고유명사 정확히 인용 [출처 표기]

【層2: 원리 해설】
3. 원리 기본: "왜 그렇게 하는가"의 인과 메커니즘 (비유 활용 / 입문자 눈높이)
4. 원리 심화: 같은 원리가 다른 경제 주체(기업·정부·가계)에게 어떻게 다르게 작용하는가

【層3: 생활 연결】
5. 생활 영향: 시청자 가계·일상에 미치는 구체적 변화 (금액·행동 단위로)
6. 관점 전환: "이 원리를 알면 이런 뉴스를 이렇게 다르게 읽을 수 있다"

기사에 없는 수치·주장 생성 금지.

JSON 출력:
{{
  "title_ko": "이슈1 섹션 제목 (14자 이내)",
  "script_ko": "이슈1 본문",
  "summary_ko": "다음 섹션으로 넘길 핵심 요점 2줄",
  "image_prompt": "Pexels 검색 영어 키워드 (인트로와 다른 장소·소재)"
}}"""

    issue1_result, u = call_ko_section(client, "ko_issue1", issue1_prompt)
    total_tokens += u.total_tokens
    issue1_result, u_retry = call_issue_retry(client, "ko_issue1", issue1_prompt, issue1_result)
    if u_retry is not None:
        total_tokens += u_retry.total_tokens
    print(f"      완료 ({len(issue1_result.get('script_ko', ''))}자)")

    # ── 4. 이슈2 (보조 기사 or 원리 다른 각도) ────────────
    print("[KO 4/5] 이슈2 한국어 초안 생성 중...")
    if mode == "A":
        issue2_src = f"【담당 기사 원문】\n{_r_info(r_sub)}"
        issue2_directive = "이슈1과 같은 원리를 다른 각도·사례로 보완 설명하세요."
    else:
        issue2_src = f"【주 기사 원문 (이슈1과 동일)】\n{_r_info(r_main)}"
        issue2_directive = "이슈1에서 다룬 원리를 한 단계 더 심화하세요 (역사적 맥락 또는 국제 비교)."

    issue2_prompt = f"""\
롱폼 영상의 이슈2 섹션을 한국어로 작성하세요.{revise_prefix}

【거시 원리 주제】{topic_ja}
{issue2_directive}

{issue2_src}

【이전 섹션 흐름】이슈1 요약: {issue1_result.get('summary_ko', '')}

【중복 금지】이슈1에서 이미 설명한 원리·사례·수치는 반복하지 말 것.
이슈1과 다른 각도(다른 경제 주체 / 역사·해외 사례 / 흔한 오해 짚기)로만 전개할 것.

필수 항목 (각 항목 3~4문장씩) — 아래 3층 구조를 순서대로 채울 것:

【層1: 연결·보강】
1. 이슈1 원리를 다른 사례·수치로 보강 (이슈1과 연결되지만 새로운 사례) [출처 표기]
2. 이 원리가 작동하는 또 다른 경제 영역 또는 계층에 미치는 영향

【層2: 원리 확장】
3. 역사적 사례 또는 해외 비교: 같은 원리가 다른 나라·시대에서 어떻게 나타났는가
4. 흔한 오해 짚기: 이 원리를 모르면 뉴스를 어떻게 오해하기 쉬운가

【層3: 시청자 메시지】
5. 원리가 시청자 생활·사회에 미치는 더 넓은 영향 (단기를 넘어선 관점)
6. "이 원리를 알면 앞으로 이런 뉴스가 나올 때 이렇게 반응할 수 있다"

기사에 없는 수치·주장 생성 금지.

JSON 출력:
{{
  "title_ko": "이슈2 섹션 제목 (14자 이내)",
  "script_ko": "이슈2 본문",
  "summary_ko": "다음 섹션으로 넘길 핵심 요점 2줄",
  "image_prompt": "Pexels 검색 영어 키워드 (앞 섹션들과 다른 소재)"
}}"""

    issue2_result, u = call_ko_section(client, "ko_issue2", issue2_prompt)
    total_tokens += u.total_tokens
    issue2_result, u_retry = call_issue_retry(client, "ko_issue2", issue2_prompt, issue2_result)
    if u_retry is not None:
        total_tokens += u_retry.total_tokens
    print(f"      완료 ({len(issue2_result.get('script_ko', ''))}자)")

    # ── 5. 아웃트로 ───────────────────────────────────────
    print("[KO 5/5] 아웃트로 한국어 초안 생성 중...")
    outro_prompt = f"""\
롱폼 영상의 아웃트로(결론)를 한국어로 작성하세요.{revise_prefix}

【거시 원리 주제】{topic_ja}

【전체 흐름 요약】
이슈1: {issue1_result.get('summary_ko', '')}
이슈2: {issue2_result.get('summary_ko', '')}

필수 항목 (각 항목 3~4문장씩):
1. 오늘 영상에서 다룬 거시 원리 핵심 정리 (인트로에서 던진 질문에 답하는 형식)
2. "이 원리를 알면 이런 뉴스를 이렇게 다르게 읽을 수 있다"는 통찰
3. 앞으로 관련 뉴스가 나올 때 주목할 포인트 한 가지
4. 채널 구독·댓글 유도 (자연스럽게 / 1~2문장)

JSON 출력:
{{
  "script_ko": "아웃트로 본문",
  "image_prompt": "Pexels 검색 영어 키워드"
}}"""

    outro_result, u = call_ko_section(client, "ko_outro", outro_prompt)
    total_tokens += u.total_tokens
    print(f"      완료 ({len(outro_result.get('script_ko', ''))}자)")

    # ── 저장 ──────────────────────────────────────────────
    ko_data = {
        "mode":          mode,
        "topic_id":      topic_id,
        "topic_title_ja": topic_ja,
        "principle":     principle,
        "article_main":  main_slot,
        "reason_ko":     reason_ko,
        "intro": {
            "script_ko":    intro_result.get("script_ko", ""),
            "image_prompt": intro_result.get("image_prompt", "japanese economy"),
        },
        "issues": [
            {
                "title_ko":    issue1_result.get("title_ko", "トピック①"),
                "script_ko":   issue1_result.get("script_ko", ""),
                "summary_ko":  issue1_result.get("summary_ko", ""),
                "image_prompt": issue1_result.get("image_prompt", "japanese economy"),
            },
            {
                "title_ko":    issue2_result.get("title_ko", "トピック②"),
                "script_ko":   issue2_result.get("script_ko", ""),
                "summary_ko":  issue2_result.get("summary_ko", ""),
                "image_prompt": issue2_result.get("image_prompt", "japanese economy"),
            },
        ],
        "outro": {
            "script_ko":    outro_result.get("script_ko", ""),
            "image_prompt": outro_result.get("image_prompt", "japanese economy"),
        },
    }

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
- 한국어 [출처: ○○] 태그는 자연스럽게 일본어 문장에 녹여 넣거나 삭제 (태그 그대로 남기지 말 것)
- 내용(사실·논리 구조)은 충실히 보존하고 어조만 モチエン 페르소나로 변환
- 인트로 첫 문장은 반드시 시청자를 끌어들이는 훅
- 아웃트로 마지막은 「以上、モチエンがお伝えしました！」로 끝낼 것
- 원리형 제목 강제: 사건형(○○が起きた) 금지, 원리형(なぜ○○なのか) 권장

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

    # long_script.json 저장 (long2~6이 이 파일을 읽음)
    with open(LONG_SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(ja_result, f, ensure_ascii=False, indent=2)

    # topic_history 업데이트 (발행 토픽 기록)
    save_topic_history(ko.get("topic_id", "unknown"))

    # ── 2. 역직역 (한국어로 돌려번역 — 의도대로 들어갔는지 확인용) ──
    print("[JA 2/2] 역직역(한국어 확인용) 생성 중...")
    backcheck_prompt = f"""\
아래 일본어 대본을 한국어로 역번역하세요. (검증용)
일본어 원문의 뜻을 그대로 전달하되, 자연스러운 한국어로 번역하세요.

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

    verify_result, u = call_gpt(
        client,
        [{"role": "system", "content": "일본어를 한국어로 역번역합니다. JSON만 출력."},
         {"role": "user", "content": backcheck_prompt}],
        "backcheck",
    )
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
    args = parser.parse_args()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    if args.stage == "ja":
        print("=== [JA 단계] 일본어 변환 ===")
        stage_ja(client)
        print(f"\n{LONG_SCRIPT_FILE} 저장 완료")
        print(f"{LONG_SCRIPT_VERIFY_FILE} 저장 완료")
        return

    # KO 단계 (--stage ko 또는 자동 모드)
    print("=== 당일 쇼츠 gpt_result 로드 ===")
    results = load_today_results()
    r_list = [results["09"], results["18"]]

    bank    = load_topic_bank()
    history = load_topic_history()

    print("\n=== [KO 단계] 한국어 거시 원리형 초안 생성 ===")
    stage_ko(client, r_list, bank, history, revise=args.revise)
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
