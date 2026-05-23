"""쇼츠 대본 2단계 생성 — KO(한국어 초안) → JA(일본어 변환 + 역직역)

  인수 없음    : KO+JA 자동 연속 실행 (GitHub Actions 비대화형 모드)
  --stage ko  : 한국어 초안만 생성 → shorts_script_ko.json
  --stage ja  : 일본어 변환만 실행 → gpt_result.json  (shorts_script_ko.json 필수)
"""
import argparse
import json
import os
import re
import sys

from openai import OpenAI
from dotenv import load_dotenv

import longform_link

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 파일 경로 =====
ARTICLE_FILE               = "article.json"
SHORTS_SCRIPT_KO_FILE      = "shorts_script_ko.json"
SHORTS_SCRIPT_VERIFY_FILE  = "shorts_script_verify.json"
GPT_RESULT_FILE            = "gpt_result.json"

# ===== 모델 =====
GPT_MODEL = "gpt-4.1-mini"

# ===== 사인오프 (코드가 부착 / GPT 생성 대상 아님) =====
SIGNOFF_DEFAULT_KO = "이상, 모찌엔이었습니다!"
SIGNOFF_DEFAULT_JA = "以上、モチエンがお伝えしました！"
SIGNOFF_FUNNEL_JA  = "もっと深く知るには、コメント欄へ。以上、モチエンでした。"

# strip 대상: 위 3개 + 레거시 변형 패턴
_SIGNOFF_PATTERNS = [
    re.escape(SIGNOFF_DEFAULT_KO),
    re.escape(SIGNOFF_DEFAULT_JA),
    re.escape(SIGNOFF_FUNNEL_JA),
    r"以上、モチエンが[^。！]*[。！]",   # JA 변형 대비
    r"이상,?\s*모찌엔이었습니다[!！]?",  # KO 변형 대비
]
_SIGNOFF_RE = re.compile(
    r"(?:" + "|".join(_SIGNOFF_PATTERNS) + r")\s*$",
    re.MULTILINE,
)

# ===== 허용 emotion 값 =====
VALID_EMOTIONS = {
    "smile", "happy", "surprised", "shocked", "worried",
    "angry", "anxious", "sad", "neutral", "shy", "embarrassed", "sleepy",
}

# ===== KO 단계: 시스템 프롬프트 =====
SYSTEM_PROMPT_KO = """\
당신은 JSON만 출력하는 AI입니다.
출력은 반드시 { 로 시작하고 } 로 끝나는 순수 JSON만 출력하세요.
```json 같은 마크다운 기호는 절대 금지.
아래 키 외에는 절대 추가하지 마세요:
  title_ko, hook_ko, script_ko, korean_summary, image_prompt, emotion, short_title

【톤 가드 규칙】
금지 어휘: 충격 / 경고 / 위기 / 폭락 / 폭등 / 긴급
"확실히" / "반드시"는 단정적 미래 예측 맥락에서만 금지 (일상 표현은 허용)
  금지 예: "물가가 반드시 오를 것입니다"
  허용 예: "반드시 확인해보세요"
"!" 는 hook_ko + script_ko 전체 합산 최대 1회
단정적 미래 예측 금지: "~할 것입니다" → "~할 수 있습니다" / "~가능성이 있습니다"
40~60대를 위한 차분하고 신뢰감 있는 어조 유지
"""

# ===== KO 단계: 유저 프롬프트 본체 (기사 정보는 별도 append) =====
USER_PROMPT_KO_BODY = """\
일본 경제 뉴스 기사를 한국어 쇼츠 대본으로 만들어주세요.

【출력 필드】
- title_ko      : 30자 이내 한국어 제목 (시청자 생활·손득·놀라움 직결 / 숫자·질문형 우선)
- hook_ko       : 시청자 생활 직결 첫 후킹 문장 한국어 (아래 ①② 규칙 적용 / 2~3문장)
- script_ko     : 전체 스크립트 한국어 (300~400자 / 마지막 문장은 반드시 "이상, 모찌엔이었습니다!")
- korean_summary: 한국어 1줄 요약 (50자 이내)
- image_prompt  : Pexels 검색용 영어 키워드 (장소·시간대·앵글·소재 중 2~3개 명시 / "no people b-roll" 추가)
- emotion       : smile / happy / surprised / shocked / worried / angry / anxious / sad / neutral / shy / embarrassed / sleepy 중 1개
- short_title   : 6~10자 핵심 키워드 한국어

【① hook_ko 규칙 — 간결·임팩트·궁금증】
다음 5개 규칙을 순서대로 모두 지킬 것.

1. 간결: 첫 문장은 한 호흡에 읽힐 것. 반드시 한 문장으로 끝낼 것.
   (글자 수 제한 없음 — 짧더라도 임팩트가 있으면 좋음)

2. 임팩트: 첫 단어부터 강하게. 핵심 키워드·숫자를 문장 앞에 배치.
   금지 시작 패턴: "최근", "사실은", "그런데", "이번에", "~에서는", "~입니다" 류의 차분한 도입·접속사

3. 궁금증: 결론을 첫 문장에 모두 주지 말 것. 이유·배경·영향은 script에서 답하게 미룸.
   시청자가 "그래서 왜? 어떻게?" 하고 본문을 보게 만들 것.

4. 본문이 답한다 (낚시 방지): hook에서 던진 궁금증을 script가 반드시 해소할 것.
   script가 답하지 못하는 hook은 생성하지 말 것.

5. 거짓·과장 단정만 금지: 허위 사실·단정적 미래 예측("확실히 폭락" 류)만 금지.
   궁금증 자체는 허용. 40~60대 신뢰 톤 유지하되 첫 문장만은 강하게.

【Bad vs Good 예시】
  ❌ "다우지수가 3개월 만에 400달러 올랐는데, 당신의 예금이자나 환율에 어떤 변화가 있을까요?"
     → 결론을 다 줌 + 길다 (2가지 위반)
  ✅ "당신 예금, 지금 손해일지도 모릅니다."
     → 궁금증 유발 / 임팩트 / script가 이유를 답함
  ✅ "뉴욕에서 벌어진 일이 당신 지갑을 바꿉니다."
     → 임팩트 + 궁금증 / 무엇이 어떻게 바꾸는지는 script에서 답함

【② 생활 각도 강제】
- hook_ko와 script_ko에서 아래 생활 각도 중 1개 이상 반드시 연결
  전기요금 / 식비·물가 / 급여·보너스 / 환율·해외여행 / 예금이자·금리 / 연금·노후자금 / 세금 / 고용·취업
- 경제 지표를 그대로 나열하지 말고 시청자 생활로 번역
  ❌ "다우지수가 3개월 만에 최고치를 기록했습니다" (지표 나열)
  ✅ "미국 증시 급등이 당신의 환율과 예금 금리에 영향을 줄 수 있습니다" (생활 번역)

【③ 랭킹 포맷 옵션 (조건부 허용)】
- 원인·영향이 2~3개로 명확히 구분될 때 "당신이 알아야 할 N가지" 형식 선택 가능
- script_ko에서 ①②③ 기호로 항목 열거 가능
- 억지로 나누지 말 것: 항목 내용이 실제로 다를 때만 적용

【script_ko 규칙】
- hook_ko 내용으로 시작 (별도 인사 금지)
- 경제 전문용어는 쉬운 말로 바꾸기
- 사인오프(마무리 멘트)는 포함하지 말 것 — 코드가 자동으로 추가함

【④ 궁금증 해소 방식 — 메커니즘 설명】
hook이 던진 궁금증을 해소할 때 반드시 "원리(인과 메커니즘)" 로 설명할 것.

  금지 ①(방향 예측): "이자가 오를 겁니다" / "환율이 내릴 것입니다"
                     → 채널 원칙(투자 예측 금지) 위반
  금지 ②(무방향):   "변화가 있을 수 있습니다" / "영향이 있을 수도 있습니다"
                     → 궁금증을 해소하지 못함

  필수(메커니즘): 왜·어떻게 영향이 전달되는지 인과 경로를 1~2단계로 설명
    예) "주가 상승 → 투자자 자금이 채권에서 주식으로 이동 → 채권 금리 상승 압력
         → 은행 예금 이자도 이 흐름의 영향을 받는 구조입니다."
    이 구조로 방향을 점치지 않으면서 시청자가 "이런 원리로 움직이는구나"를 이해하게 할 것.

  에버그린 원칙: 예측은 빗나가면 신뢰 훼손 / 원리는 6개월 뒤에도 유효
  투자 권유·시장 예측 완전 금지
"""

# ===== JA 단계: 시스템 프롬프트 =====
SYSTEM_PROMPT_JA = """\
あなたはJSONのみを出力するAIです。
出力は必ず { で始まり } で終わる純粋なJSONのみ。
```json などのマークダウン記号は絶対に使用禁止。
以下のキー以外は絶対に追加しないこと:
  title, hook, hook_korean, script, hashtags, korean_summary, emotion, image_prompt, short_title,
  backtranslate_hook, backtranslate_script
人名・企業名・役職名は正確に表記すること。略称・誤字・当て字は絶対禁止。
hashtagsは必ずJSON配列で出力すること。

【モチエンキャラクターシート】
一人称: モチエン。中性的で落ち着いた信頼感のある語り口（40〜60代向け）。
視聴者は「あなた」と呼ぶ。数値解説が口癖。生活翻訳役（統計→家計）。政治中立。
絶対に言わないこと: 投資推奨・政治家評価・断定的な未来予測・直接損益表現。
禁止語彙: やばい / オワコン / 爆益 / ガチで / マジで / めっちゃ
感情表現: 「!」は最大1回。強い感情表現禁止。断定的未来予測禁止。

【トーンガード規則】
禁止語彙: 衝撃 / 緊急 / 暴落 / 暴騰 / 危機的 / 警告
「必ず」「確実に」は断定的未来予測の文脈でのみ禁止（日常表現は許可）
  禁止例:「物価が必ず上がります」→ 許可例:「必ず確認してください」
断定的未来予測禁止:「〜するでしょう」→「〜する可能性があります」に換言
生活角度を維持すること: hookの数値・生活翻訳をJA変換後も保持し抽象化しない

【【hookのインパクト維持規則】
韓国語 hook のインパクト・궁금증（好奇心）を日本語に変換した後も完全に保持すること。
  禁止: 和らげる・抽象化する・結論を足す
  禁止例: "あなたの預金、今損しているかもしれません。" → ❌「最近の経済動向について解説します。」
  守る例: "あなたの預金、今損しているかもしれません。" → ✅「あなたの預金、今、損しているかもしれません。」
hookの最初の文は短く・インパクト重視で訳すこと。読者が「なぜ？どうして？」と思うよう仕上げること。
メカニズム説明文（因果経路）はJA変換後も具体性を保持し、「変化があるかもしれません」類の無方向表現に換言しないこと。
"""

# ===== JA 단계: 유저 프롬프트 본체 (KO 데이터는 별도 append) =====
USER_PROMPT_JA_BODY = """\
以下の韓国語ショーツ原稿を日本語に変換してください。

【変換ルール】
- title         : 30字以内の日本語タイトル（視聴者の損得・驚きに直結 / 数字・疑問形優先）
- hook          : 日本語フック文（視聴者の生活直結 / 数字・疑問含む）
- hook_korean   : 下記 hook_ko をそのまま転記（変更禁止）
- script        : 日本語スクリプト（モチエンキャラクター適用 / 冒頭挨拶禁止 / サインオフは含めないこと — コードが自動追加する）
- hashtags      : JSON配列 / 日本語・英語のみ（韓国語タグ絶対禁止）/ #Shorts必須
- korean_summary: 下記 korean_summary をそのまま転記（変更禁止）
- emotion       : 下記 emotion をそのまま転記（変更禁止）
- image_prompt  : 下記 image_prompt をそのまま転記（変更禁止）
- short_title   : 6〜10字の日本語核心キーワード
- backtranslate_hook   : 上記 hook の日本語を自然な韓国語に逆翻訳（검수용）
- backtranslate_script : 上記 script の日本語を自然な韓国語に逆翻訳（검수용）

誤読しやすい漢字にはふりがなを括弧で併記すること。
"""


# ─────────────────────────────────────────────────────────
# 사인오프 제거 헬퍼
# ─────────────────────────────────────────────────────────

def _strip_signoff(text: str) -> str:
    """텍스트 끝의 사인오프 패턴을 제거하고 공백을 정리."""
    return _SIGNOFF_RE.sub("", text).rstrip()


# ─────────────────────────────────────────────────────────
# 내부 GPT 호출
# ─────────────────────────────────────────────────────────

def _gpt_call(system: str, user: str) -> dict:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[오류] JSON 파싱 실패: {e}\n원본:\n{raw}")
        raise


# ─────────────────────────────────────────────────────────
# KO 단계
# ─────────────────────────────────────────────────────────

def stage_ko(title: str, article_body: str) -> dict:
    """한국어 초안 생성 → shorts_script_ko.json 저장 후 반환."""
    user = (
        USER_PROMPT_KO_BODY
        + f"\n뉴스 제목: {title}\n뉴스 본문: {article_body}\n"
    )
    data = _gpt_call(SYSTEM_PROMPT_KO, user)

    if data.get("emotion") not in VALID_EMOTIONS:
        data["emotion"] = "neutral"

    # 사인오프: GPT가 무시하고 넣었을 경우 제거 후 고정 문구 부착
    body = _strip_signoff(data.get("script_ko", ""))
    data["script_ko"] = body + " " + SIGNOFF_DEFAULT_KO

    with open(SHORTS_SCRIPT_KO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[KO] {SHORTS_SCRIPT_KO_FILE} 저장 완료")
    print(f"  hook_ko   : {data.get('hook_ko', '')[:80]}")
    print(f"  short_title: {data.get('short_title', '')}")
    return data


# ─────────────────────────────────────────────────────────
# JA 단계
# ─────────────────────────────────────────────────────────

def stage_ja(ko_data: dict) -> dict:
    """한국어 → 일본어 변환 + 역직역 생성.
    gpt_result.json + shorts_script_verify.json 저장 후 gpt_result dict 반환.
    """
    ko_block = (
        f"title_ko      : {ko_data.get('title_ko', '')}\n"
        f"hook_ko       : {ko_data.get('hook_ko', '')}\n"
        f"script_ko     : {ko_data.get('script_ko', '')}\n"
        f"korean_summary: {ko_data.get('korean_summary', '')}\n"
        f"image_prompt  : {ko_data.get('image_prompt', '')}\n"
        f"emotion       : {ko_data.get('emotion', 'neutral')}\n"
        f"short_title   : {ko_data.get('short_title', '')}\n"
    )
    user = USER_PROMPT_JA_BODY + "\n韓国語原稿:\n" + ko_block
    data = _gpt_call(SYSTEM_PROMPT_JA, user)

    # hashtags 정규화
    hashtags = data.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    data["hashtags"] = hashtags

    # emotion fallback
    if data.get("emotion") not in VALID_EMOTIONS:
        data["emotion"] = ko_data.get("emotion", "neutral")

    # ── 사인오프 처리 ──────────────────────────────────────
    # script: 본문만 남긴 뒤 활성 롱폼 여부에 따라 사인오프 부착
    script_body = _strip_signoff(data.get("script", ""))
    active = longform_link.get_active()
    if active:
        data["script"] = script_body + " " + SIGNOFF_FUNNEL_JA
        data["active_longform_url"]   = active.get("url", "")
        data["active_longform_title"] = active.get("title_ja", "")
    else:
        data["script"] = script_body + " " + SIGNOFF_DEFAULT_JA
        data["active_longform_url"]   = ""
        data["active_longform_title"] = ""

    # ── 역직역: 사인오프 제거 후 저장 (verify 대상 아님) ──
    verify = {
        "backtranslate_hook":   data.pop("backtranslate_hook", ""),
        "backtranslate_script": _strip_signoff(data.pop("backtranslate_script", "")),
    }
    with open(SHORTS_SCRIPT_VERIFY_FILE, "w", encoding="utf-8") as f:
        json.dump(verify, f, ensure_ascii=False, indent=2)

    with open(GPT_RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[JA] {GPT_RESULT_FILE} 저장 완료")
    print(f"  title: {data.get('title', '')}")
    print(f"  hook : {data.get('hook', '')[:80]}")
    active_url = data.get("active_longform_url", "")
    if active_url:
        print(f"  [깔때기] {data.get('active_longform_title', '')} — {active_url}")
    return data


# ─────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="쇼츠 대본 2단계 생성")
    parser.add_argument("--stage", choices=["ko", "ja"], default=None,
                        help="ko: 한국어 초안만 / ja: 일본어 변환만 / 없음: 자동 연속")
    args = parser.parse_args()

    with open(ARTICLE_FILE, encoding="utf-8") as f:
        article = json.load(f)
    title        = article["title"]
    article_body = article.get("article_body", "")

    if args.stage == "ko":
        stage_ko(title, article_body)

    elif args.stage == "ja":
        with open(SHORTS_SCRIPT_KO_FILE, encoding="utf-8") as f:
            ko = json.load(f)
        stage_ja(ko)

    else:
        ko = stage_ko(title, article_body)
        stage_ja(ko)


if __name__ == "__main__":
    main()
