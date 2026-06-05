# 모찌엔 YouTube Shorts 자동화 프로젝트 — CLAUDE.md
최종 업데이트: 2026년 5월 29일 (business-cycle active 승격 + FRED 5개 재검증)

================================================================
## 0. 작업 규칙
================================================================

[ 소통 ]
- 모든 소통은 한국어로
- 에러 발생 시 원인 먼저 설명 후 수정
- Make.com, Creatomate는 이 프로젝트에서 사용하지 않음. Python + FFmpeg으로 직접 구현

[ 구현 전 필수 ]
- 구현 전 반드시 [Plan] 먼저 제시. 어떤 파일을 만들고 수정하는지 설명 후 승인받고 진행
- 기존 파일이 있는지 먼저 확인하고, 없을 때만 새로 만든다 (중복 생성 금지)
- 한 번 요청에 여러 기능 동시 구현 금지. 단계별로 나눠 확인

[ 코딩 원칙 ]
- 수치를 코드에 직접 쓰지 않음 (NO MAGIC NUMBERS). 파일 상단에 상수로 정의
- 스크립트 하나에 역할 하나 (SRP). 기능이 다르면 파일 분리
- 기존 파일 수정 시 관련 없는 코드 절대 건드리지 않음
- 파일 500줄 초과 시 분리 제안
- 오버엔지니어링 금지. 지금 당장 필요하지 않은 것은 만들지 않음 (YAGNI)
- 최소한의 코드로 동작하게

[ 진행 방식 ]
- 단계별로 하나씩 진행. 테스트 1종 후 나머지 처리 방식 선호하지 않음. 한 번에 전체 처리 선호
- 개발자가 Python 입문 단계임을 감안해 왜 이렇게 짜는지 이유를 항상 함께 설명


================================================================
## 1. 프로젝트 개요
================================================================
목적      : 일본 경제 뉴스를 자동 수집 → 모찌엔 캐릭터가 일본어로 요약하는
            YouTube Shorts 영상을 자동 생성·업로드
타겟      : 일본 YouTube 이용자 (40~60대 직장인, 은퇴 준비층)
부가 수신 : 한국어 요약본을 파이프라인 종료 후 텔레그램 봇으로 수신 (Mochien_Notify_bot)
개발자    : 게임 원화 8년차 강사 / 코딩 비전공 / Python 입문 단계
목표      : 포트폴리오 + 패시브 인컴 사이드 비즈니스


================================================================
## 2. 전체 자동화 플로우
================================================================
[ step2_select.py — 기사 선택 ]
RSS (NHK cat6/cat5 + Yahoo Japan 비즈니스) 최대 5개 수집
→ 기사별 ChatGPT API (gpt-4.1-mini) 병렬 호출 → 한국어 요약 생성
→ 단독 모드 (기본): 텔레그램 기사 선택 1건 (✅ 진행 / 🔄 다음 / ❌ 취소) → gpt_result.json 저장
→ 일괄 모드 (--batch): 후보 전체 메시지 전송 → 텔레그램에서 2건 선택 → 09/18_gpt_result.json 동시 생성
→ 슬롯 파일을 output/{날짜}/{슬롯}_gpt_result.json에 저장 (롱폼 연결용)

[ step4~step7 — 영상 생성 ]
→ Pexels API 배경 영상 취득
→ ElevenLabs TTS (Eleven Multilingual v2) + 발음 사전 (pronunciation.json) → 일본어 음성 생성
→ FFmpeg 영상 합성 (1080x1920) + 쿨 블루 컬러그레이딩 + 비네팅
→ Whisper API 일본어 자막 합성

[ step9 — 업로드 + 알림 ]
→ YouTube Data API v3 예약 발행 (privacyStatus: private + publishAt RFC 3339)
→ SRT 자막 captions.insert로 YouTube 업로드 (자동번역 활성화용)
→ 텔레그램 완료 알림 개별 전송 (제목 / 예약시간 / 고정댓글 hook 포함)
→ output/{날짜}/{슬롯}_gpt_result.json을 GitHub Artifact로 업로드

[ 롱폼 파이프라인 (mochien_longform.yml) — JST 21:00 ]
→ GitHub Artifact에서 당일 gpt_result 2개 파일 복원
→ long1_script.py: gpt-4.1 롱폼 스크립트 2단계 생성 (KO→JA)
   KO 단계 5회 순차 호출: mode_judge(토픽+분리축 결정) → intro → issue1 → issue2 → outro
     분리축(issue1_angle/issue2_angle)을 mode_judge에서 1회 사전 결정 → 각 이슈는 각도 하나만 깊게
     (--topic 직접 지정 시 call_angle_judge로 분리축만 결정 — 기사 불필요)
   JA 단계: 한국어 초안 → 모찌엔 일본어 변환 + 역직역 확인
   → long_script_ko.json (KO 검토) / long_script.json (JA 완성) / long_script_verify.json
→ long2_tts.py: 4섹션 TTS → long_voice.mp3 + long_chapters.json 생성 (ffprobe 길이 측정)
→ long3_pexels.py: 3개 배경 영상 다운로드
→ long4_ffmpeg.py: 섹션별 클립 생성 → concat → long_output_no_sub.mp4
→ long5_whisper.py: Whisper 자막 합성 → long_output.mp4
→ long6_youtube.py: YouTube 업로드 + 텔레그램 롱폼 완료 알림 개별 전송


================================================================
## 3. 기술 스택
================================================================
언어            : Python 3.14
영상 합성        : FFmpeg (Creatomate 대체)
자동화 실행      : GitHub Actions (Make.com 대체) - 공개 repo 무료 무제한
스케줄          : 09:00 / 18:00 JST (하루 2회)
                  ※ GitHub Actions cron 제거 → GitHub 앱에서 workflow_dispatch 수동 트리거
로컬 개발 환경   : Windows / C:\mochien 프로젝트 폴더

Make.com 대체 이유   : Python으로 모든 API 직접 호출 가능. $9/월 절감
Creatomate 대체 이유 : FFmpeg으로 동일 기능 구현 가능. $45/월 절감
ZapCap 대체 이유     : Whisper API로 동일 기능 구현 가능. ~$8/월 추가 절감
전환 후 월 비용      : ~$4.48 (기존 ~$67 대비 $62.52 절감)


================================================================
## 4. Python 라이브러리 목록
================================================================
feedparser                - RSS 수집
requests                  - HTTP 크롤링, Pexels API 호출
openai                    - ChatGPT API 호출 + Whisper API 자막 생성
ffmpeg-python             - FFmpeg 영상 합성
google-auth               - Google 인증
google-auth-oauthlib      - YouTube OAuth2 인증 (필수 — requirements.txt에 명시)
google-api-python-client  - YouTube Data API v3
Pillow                    - 이미지 처리 (캐릭터 PNG 오버레이)
python-dotenv             - .env 파일 로드 (필수 — requirements.txt에 명시)
python-telegram-bot       - 텔레그램 봇 연동
beautifulsoup4            - HTML 파싱
google-genai              - Gemini API (신규 SDK / step10 1차 검수)
anthropic                 - Claude API (step10 2차 검증)


================================================================
## 5. ChatGPT 프롬프트 (현재 버전)
================================================================
시스템 프롬프트:
  あなたはJSONのみを出力するAIです。
  出力は必ず { で始まり } で終わる純粋なJSONのみ。
  ```json などのマークダウン記号は絶対に使用禁止。
  以下のキー以外は絶対に追加しないこと:
    title, hook, hook_korean, script, hashtags, korean_summary, expression, direction, image_prompt, short_title, thumb_headline
  人名・企業名・役職名は正確に表記すること。略称・誤字・当て字は絶対禁止。

유저 프롬프트 (USER_PROMPT 변수):
  【モチエンキャラクター設定】
  - 冒頭の挨拶は禁止。
  - 落ち着いていて信頼感がある話し方（40〜60代向け）
  - 難しい経済用語はやさしい言葉に言い換える
  - 視聴者を「あなた」と呼ぶ
  - スクリプト末尾は必ず下記で締めること:
    「皆さんはどう思いますか？コメントで教えてください！
     以上、モチエンがお伝えしました！
     チャンネル登録お願いします！」

  【title ルール】
  - 30字以内
  - 事実の羅列ではなく視聴者の損得・驚き・生活への影響に直結すること
  - 数字・疑問形・「あなたの〇〇」形式を優先
  - 例：✗「アゼルバイジャン産原油到着」→ ✅「ガソリン代安くなる？アゼルバイジャン産原油の力」

  【hook ルール】
  - 必ず日本語で生成すること / 2文構成（事実文。+疑問・共感文？）
  - 視聴者の生活・損得・驚きと直結させること
  - 数字・疑問形・「あなたの○○が変わる」形式を優先すること

  【script ルール】
  - scriptの冒頭はhookの内容を繰り返さないこと。hookの次の情報・詳細から始めること。

  【hashtags ルール】
  - 日本語または英語のみ（韓国語タグは絶対に含めないこと）
  - 日本語検索ボリュームが高いタグを優先
  - #Shorts必須

  【direction / expression / thumb_headline ルール】
  - direction："up"(상승·호재) / "down"(하락·악재) / "none"(방향 판별 불가·고착·복합)
    수치가 있어도 방향이 애매하면 none이 맞음 (예: 170円 고착→none)
    상승·하락이 명확하면 up/down을 적극 선택
  - expression：캐릭터 표정 (아래 허용값 참조)
  - thumb_headline：썸네일 전용 14자 이내 / 수치 우선 규칙 적용
    기사에 수치(%, 금액, 배수 등)가 있으면 반드시 수치 포함
    좋은 예: 「家賃+12%」「170円の壁」 / 나쁜 예: 「最高」(수치 누락)·본문 토막

  【その他】
  - 誤読しやすい漢字にはふりがなを括弧で併記すること
  - 人名・企業名・役職名は正確に表記すること
  - short_title：6〜10字の核心キーワード
  - image_prompt：Pexels検索用英語キーワード（例："japanese economy stock market"）

gpt_result.json 필드 (GPT 출력 11개 + step2 추가 3개 = 총 14개):
  title          - 영상 제목 (30자 이내 / 시청자 손득·놀라움 직결)
  hook           - 첫 후킹 2문장 (일본어 / 도입부 음성으로 TTS 맨 앞에 추가됨)
  hook_korean    - hook 일본어의 자연스러운 한국어 번역 (선택적 필드)
  script         - 본문 스크립트 / hook 반복 없이 이어지는 상세 내용
  hashtags       - 해시태그 배열 (일본어·영어만 / #Shorts 필수)
  korean_summary - 한국어 1줄 요약
  expression     - 캐릭터 표정 (아래 허용값 중 1개)
  direction      - 방향성 "up"/"down"/"none"
  image_prompt   - Pexels 검색 영어 키워드
  short_title    - 6~10자 핵심 키워드
  thumb_headline - 썸네일 전용 헤드라인 (14자 이내 / 수치 우선)
  --- step2_select.py에서 추가 ---
  slot           - 슬롯 배정 ("09" / "18")
  article_url    - 기사 URL (당일 중복 방지용)
  raw_summary_jp - RSS entry.summary 일본어 원문 본문 (long1_script.py 심층 분석 입력용)

expression 허용값:
  smile / happy / surprised / shocked / worried /
  angry / anxious / sad / neutral / shy / embarrassed / sleepy


================================================================
## 6. FFmpeg 영상 합성 레이아웃 스펙
================================================================
[ 쇼츠 (step6_ffmpeg.py) ]
해상도      : 1080x1920 (YouTube Shorts 세로형)
폰트        : Noto Sans JP
배경        : Pexels 스톡 영상 (전체 화면) + 쿨 블루 컬러 그레이딩 + 비네팅
프레임레이트 : 30fps

레이어 구성 (아래에서 위 순서):
  1. background  - Pexels 영상 / 전체 화면 1080x1920
                   → colorbalance (rs-0.10/bs+0.08 등) + vignette(angle=0.8)
  2. top_bar     - 상단 레터박스 / 네이비(#1B2A4A) / 상단 고정 / 높이 약 10%
  3. red_line    - 가로선 #E50000 / 두께 4~6px / top_bar 하단 경계
  4. short_title - top_bar 위 텍스트 / 흰색 / Noto Sans JP Bold / 105px
  5. face        - 모찌엔 캐릭터 PNG / 우하단 고정 / 흰 외곽선 10px 포함된 PNG
  6. mouth_gif   - mochien_talk.gif 무한루프 / face 레이어 입 위치에 오버레이
  7. subtitle    - 화면 하단 고정 / 흰 텍스트 + 검정 스트로크 / 132px
                   ※ Whisper API 처리 후 자막 오버레이 (\an5 화면 중앙)
  8. audio       - ElevenLabs 생성 mp3

[ 롱폼 (long4_ffmpeg.py) ]
해상도      : 1920x1080 (YouTube 가로형)
폰트        : Noto Sans JP Bold / 제목 80px
배경        : Pexels 스톡 영상 + 동일 컬러 그레이딩 + 비네팅
섹션 구성   : intro / issue1 / issue2 / outro (4섹션 FFmpeg concat)
상단 바     : 높이 108px / 네이비 + 빨간 구분선 / 섹션별 라벨 표시
              intro·outro → short_title / issueN → "①② + 이슈 제목 14자"
캐릭터      : 우하단 고정 / FACE_H=300px / mochien_talk.gif 오버레이
자막        : Whisper ASS \an2 (하단 중앙) / 72px / 6단어/줄


================================================================
## 7. Pexels API 설정
================================================================
URL         : https://api.pexels.com/videos/search
Method      : GET
Header      : Authorization: {PEXELS_API_KEY}  ※ Bearer 없이 키만
Query params: query={image_prompt 키워드}, per_page=1
응답 경로   : response["videos"][0]["video_files"][0]["link"]
무료 플랜   : 월 200 요청 / 하루 2편×쇼츠+3개×롱폼=5req×30일=150 요청으로 여유 있음
상업적 사용 : 가능 (크레딧 표기 권장)


================================================================
## 8. ElevenLabs TTS 설정
================================================================
모델        : Eleven Multilingual v2 (eleven_multilingual_v2) ← 17차 세션 변경
보이스      : Harune (일본어 여성 / 차분한 뉴스 앵커 스타일)
API 키명    : Mozzi
출력 형식   : mp3_44100_128
연동 방식   : Python requests로 직접 API 호출
입력 텍스트 : hook + script 합산 (step5_tts.py / hook 없으면 script만)
              hook이 영상 도입부 음성으로 맨 앞에 추가됨 → 첫 3초 후킹 강화
발음 사전   : ElevenLabs Pronunciation Dictionary API (alias 규칙 / 일본어 phoneme 미지원)
              upload_pronunciation_dict.py 실행 → ELEVENLABS_PD_ID / ELEVENLABS_PD_VERSION_ID 취득
              .env / GitHub Secrets 등록 후 TTS 호출 시 자동 적용
              미등록 시 자동 스킵 (하위 호환 유지)


================================================================
## 9. Whisper API 자막 설정
================================================================
용도        : ElevenLabs 생성 음성(mp3)을 텍스트로 변환 → ASS 자막 생성 → FFmpeg burn-in
모델        : whisper-1
언어        : ja (Japanese)
출력 형식   : ASS (FFmpeg burn-in용) + SRT (YouTube captions.insert용)
가격        : $0.006/분 → 하루 3편 x 1분 x 30일 = 월 ~$0.18
별도 키     : 불필요 / OPENAI_API_KEY 공용 사용


================================================================
## 10. 모찌엔 캐릭터 에셋
================================================================
GitHub      : https://github.com/qumax7-collab/mochien-assets
Raw URL     : https://raw.githubusercontent.com/qumax7-collab/mochien-assets/main/mochien_{emotion}.png
외곽선      : 흰색 10px / 알파채널 유지
배치        : 우하단 고정
현재 고정값 : neutral (emotion 자동 매핑은 2단계에서 구현)

emotion 값        파일명                    사용 상황
----------------  ------------------------  ------------------
smile             mochien_smile.png         긍정적 뉴스
happy             mochien_happy.png         호재
surprised         mochien_surprised.png     충격적 수치
shocked           mochien_shocked.png       속보/브레이킹
worried           mochien_worried.png       불안 지표
angry             mochien_angry.png         급등/급락
anxious           mochien_anxious.png       불확실 전망
sad               mochien_sad.png           악재/하락
neutral           mochien_neutral.png       중립 뉴스 (현재 고정)
shy               mochien_shy.png           소소한 긍정
embarrassed       mochien_embarrassed.png   아이러니
sleepy            mochien_sleepy.png        변동 없음


================================================================
## 11. YouTube 업로드 설정 ← 9차 세션 업데이트
================================================================
API         : YouTube Data API v3 videos.insert
채널명      : モチエンのひとこと経済ニュース
설명란 구성 : 일본어 채널 소개 + hashtags (한국어 제거)
업로드 방식 : 예약 발행 (privacyStatus: private + publishAt RFC 3339)
              ※ YouTube가 지정 시각에 자동 public 전환
쇼츠 예약   : 슬롯 09 → 07:00 JST / 슬롯 18 → 18:00 JST
롱폼 예약   : 21:00 JST 고정
승인 방식   : 텔레그램 봇 기사 선택 후 파이프라인 자동 실행
              ※ 10분 무응답 시 자동 진행
자동 댓글   : 미구현 (YouTube Studio 수동)
              ※ 고정댓글 내용은 영상 업로드 완료 시 텔레그램 개별 알림으로 수신
              ※ YouTube Studio에서 직접 달 것 (수동)


================================================================
## 12. 텔레그램 알림 설정
================================================================
봇 이름     : Mochien_Notify_bot
역할 1      : 기사 선택 (step2_select.py)
              - 기사별 일본어 제목 + 한국어 요약 전송
              - 인라인 버튼: ✅ 이 기사로 진행 / 🔄 다음 기사 / ❌ 취소
              - 선택 후 "⏳ 영상 생성 시작..." 상태 표시
              - 경제 키워드 없는 날 → "⚠️ 경제 키워드 기사 없어 전체에서 선택" 알림
역할 2      : 영상 업로드 완료 시 개별 알림
              - 숏폼: step9_youtube.py → 업로드 완료 시 즉시 전송
                제목 / 예약 시간 / 고정댓글 (hook 일본어 + hook_korean 한국어) 포함
              - 롱폼: long6_youtube.py → 업로드 완료 시 전송
                제목 / 예약 시간 / 고정댓글 (당일 슬롯 short_title 3개 기반 일본어 문구) 포함
역할 3      : API 잔액 경고
              - OpenAI $3 이하 / ElevenLabs $2 이하 시 경고 전송
              - 경고만 보내고 파이프라인은 계속 실행
연동 방식   : Python requests → Telegram Bot API
주의        : 세션 시작 전 flush_updates() 필수 (오래된 콜백 재처리 방지)


================================================================
## 13. GitHub Actions / 보안 설정 ← 7차 세션 업데이트
================================================================
repo        : https://github.com/qumax7-collab/mochien (Public)
워크플로우  : .github/workflows/mochien.yml          (쇼츠 / 하루 2회 — 개별 실행용)
              .github/workflows/mochien_longform.yml  (롱폼 / 하루 1회 — 개별 실행용)
              .github/workflows/mochien_full.yml       (쇼츠 2편+롱폼 통합 / 하루 1회)
              .github/workflows/keepalive.yml          (repo 활성 유지 / 주 1회)
실행 환경   : ubuntu-latest / 공개 repo 무료 무제한

트리거 방식 (8차 세션 변경):
  cron 스케줄 전면 제거 — GitHub Actions 무료 플랜 지연(1~4시간)으로 사용 불가 판단
  → GitHub 앱(핸드폰) 또는 PC에서 workflow_dispatch 수동 트리거로 전환

  수동 트리거 방법:
    핸드폰: GitHub 앱 → mochien repo → Actions → 워크플로우 선택 → Run workflow
    PC: telegram_trigger.py 실행 후 텔레그램 /메뉴 → 버튼 탭 (로컬 상시 실행 필요)

  keepalive:
  "0 0 * * 1"   → 매주 월요일 UTC 00:00 / .github/keepalive.txt 타임스탬프 커밋

쇼츠→롱폼 gpt_result 파일 전달 방식 (Artifact):
  1. 쇼츠 워크플로우 시작 시: 기존 gpt-results artifact 다운로드 (이전 슬롯 복원)
  2. 파이프라인 실행: step2가 output/{날짜}/{슬롯}_gpt_result.json 저장
     ※ 슬롯명은 시간 기준이 아닌 당일 파일 순서 기준 (09→13→18)
     → 같은 날 몇 시에 실행해도 09/18 순서로 채워짐
  3. step9 이후: output/ 전체를 gpt-results artifact로 업로드 (overwrite)
  → 하루 2회 실행 후 artifact에 09/18 파일 누적됨
  4. 롱폼 워크플로우: dawidd6/action-download-artifact로 gpt-results 수신
  ※ GITHUB_TOKEN은 별도 등록 불필요 — GitHub Actions가 자동 제공

GitHub Actions 지연 특성:
  - 무료 플랜: 30분~4시간 지연 발생 가능 (정상 동작)
  - repo 최근 활동 없으면 트리거 자체가 건너뛰어짐
  - 대응: keepalive.yml이 매주 월요일 자동 커밋으로 활성 상태 유지

OAuth 설정:
  Google Cloud Console → OAuth 앱 프로덕션 전환 완료
  → token.json refresh_token 무기한 유효 (재인증 불필요)
  ※ 새 API 스코프 추가 시에만 token.json 재발급 필요

보안 구조:
  로컬 → .env 파일에 키 보관 / .gitignore로 GitHub 업로드 차단
  GitHub → Secrets에 암호화 저장 / Actions 실행 시 자동 주입

GitHub Secrets 등록 목록:
  OPENAI_API_KEY / ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID /
  PEXELS_API_KEY / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID /
  YOUTUBE_CREDENTIALS / CLIENT_SECRETS /
  GEMINI_API_KEY / ANTHROPIC_API_KEY   ← 16차 세션 추가
  WP_URL / WP_USERNAME / WP_APP_PASSWORD  ← 세션 A 추가 (워드프레스 REST API)
  ※ GITHUB_TOKEN은 자동 제공 — 별도 등록 불필요


================================================================
## 14. 파일 구조
================================================================
C:\mochien\
  ├── CLAUDE.md
  ├── CHANGELOG.md                        ← 완료 세션 이력 (CLAUDE.md에서 분리)
  ├── glossary.json                       ← Whisper 오인식 패턴 사전 (코드 밖에서 관리)
  ├── .env
  ├── .gitignore
  ├── requirements.txt
  ├── client_secrets.json
  ├── token.json
  ├── pronunciation.json                  ← TTS 발음 교정 사전 (코드 밖에서 관리 / 자막·JSON 미적용)
  ├── suggested_pronunciation.json        ← Gemini+Claude 검수 발음 후보 누적 (런타임 생성)
  ├── suggested_glossary.json             ← Gemini+Claude 검수 자막 후보 누적 (런타임 생성)
  ├── .github/
  │     └── workflows/
  │           ├── mochien.yml             ← 쇼츠 파이프라인 (하루 2회 — 개별 실행용)
  │           ├── mochien_longform.yml    ← 롱폼 파이프라인 (하루 1회 — 개별 실행용)
  │           ├── mochien_full.yml        ← 쇼츠 2편+롱폼 통합 워크플로우 (하루 1회)
  │           └── keepalive.yml           ← repo 활성 유지 (주 1회)
  ├── venv\
  ├── [ 데이터 파이프라인 — 작업 2 ]
  ├── data/
  │     ├── fred_fetch.py    ← FRED API fetch (시계열 / 환경변수: FRED_API_KEY)
  │     │                      CLI: python -m data.fred_fetch DEXJPUS
  │     │                      504/503/ReadTimeout → 메시지 출력 후 sys.exit (수동 재실행)
  │     ├── boj_fetch.py     ← BOJ API fetch (시계열 / 인증 불필요)
  │     │                      CLI: python -m data.boj_fetch --meta FM08 / FM08 FXERD05
  │     │                      高頻度アクセス 금지 — 503/504 시 30초 대기 후 1회 재시도
  │     ├── estat_fetch.py   ← e-Stat API fetch (시계열 / 환경변수: ESTAT_APP_ID)
  │     │                      CLI: python -m data.estat_fetch --search 실질賃金
  │     │                           python -m data.estat_fetch --meta 0002070001
  │     │                           python -m data.estat_fetch 0002070001 --cat01 059 --cat02 03 --area 00000
  │     └── cache/           ← 월 1회 캐시 자동 저장 (.gitignore 등록 / 런타임 생성)
  ├── [ 쇼츠 파이프라인 ]
  ├── telegram_trigger.py                 ← 텔레그램 수동 트리거 봇 (PC 로컬 실행용)
  ├── start_bot.bat                       ← telegram_trigger.py 실행 배치파일
  ├── run_all.py                          ← 전체 파이프라인 일괄 실행 (쇼츠 3편+롱폼)
  ├── run_all.bat                         ← run_all.py 더블클릭 실행파일
  ├── run_pipeline.py                     ← 쇼츠 1편 실행 (step2→4→5→6→7→9 / 3회 실행 후 롱폼 자동)
  ├── step2_rss_crawler.py
  ├── step2_select.py                     ← RSS + ChatGPT + 텔레그램 선택
  ├── step3_chatgpt.py                    ← step2_select에 통합됨
  ├── step4_pexels.py
  ├── step5_tts.py
  ├── step6_ffmpeg.py
  ├── step7_whisper_subtitle.py
  ├── step8_thumbnail.py              ← 쇼츠 전용 디자인 썸네일 자동 생성 + YouTube thumbnails.set
  ├── step9_youtube.py
  ├── step10_gemini_review.py             ← Gemini+Claude 자막·발음 자동 검수 (--mode shorts|longform)
  ├── [ 롱폼 파이프라인 ]
  ├── run_longform.py                     ← 롱폼 전체 실행 (long1→7)
  ├── long1_script.py                     ← gpt-4.1 롱폼 스크립트 생성 (2단계 KO→JA / 에버그린)
  ├── long2_tts.py                        ← 4섹션 TTS + concat
  ├── long3_pexels.py                     ← 3개 배경 영상 다운로드
  ├── long4_ffmpeg.py                     ← 섹션별 클립 생성 + concat
  ├── long5_whisper.py                    ← Whisper 자막 합성
  ├── long6_youtube.py                    ← YouTube 업로드 + 텔레그램
  ├── long7_wordpress.py                  ← WordPress REST API 블로그 발행 (세션 A 신규)
  ├── [ 런타임 생성 파일 ]
  ├── article.json
  ├── gpt_result.json
  ├── pexels_result.json
  ├── background.mp4
  ├── voice.mp3
  ├── output_video.mp4
  ├── output_video_subtitled.mp4
  ├── long_script.json
  ├── long_voice.mp3 / long_voice_intro.mp3 … long_voice_outro.mp3
  ├── long_bg_main.mp4 / long_bg_issue1~3.mp4
  ├── long_clip_intro.mp4 … long_clip_outro.mp4
  ├── long_output_no_sub.mp4
  ├── long_output.mp4
  ├── long_subtitle.srt                   ← long5_whisper.py가 생성 / 롱폼 SRT (참조용)
  ├── long_chapters.json                  ← long2_tts.py가 생성 / long6_youtube.py가 소비
  ├── long_youtube_url.txt                ← long6_youtube.py가 생성 / long7_wordpress.py가 소비
  ├── long_script_ko.json                 ← long1 KO 단계 출력 (한국어 초안 / 웹 UI 검토용)
  ├── long_script_verify.json             ← long1 JA 단계 역직역 확인용 (일→한 back-translation)
  ├── long_thumb.jpg                      ← long7이 생성하는 썸네일 (long_bg_main.mp4 첫 프레임)
  ├── topic_bank.json                     ← 거시 경제 토픽 15개 (에버그린 컨셉 / 세션 A 신규)
  ├── topic_history.json                  ← 최근 발행 토픽 이력 (21일 쿨다운 / 런타임 생성)
  └── output/                             ← 날짜별 gpt_result (롱폼 연결용)
        └── 2026-05-10/
              ├── 09_gpt_result.json
              ├── 13_gpt_result.json
              └── 18_gpt_result.json


================================================================
## 15. 월 예상 비용
================================================================
서비스          플랜                    월 비용
--------------  ----------------------  -----------
Make            미사용 (Python 대체)    $0
Creatomate      미사용 (FFmpeg 대체)    $0
ZapCap          미사용 (Whisper 대체)   $0
OpenAI API      gpt-4.1-mini+Whisper(쇼츠) + gpt-4.1×5(롱폼)  ~$10~14
ElevenLabs      종량제                  ~$0.30
Pexels API      무료 플랜               $0
GitHub Actions  공개 repo 무료          $0
YouTube API     무료                    $0
Telegram Bot    무료                    $0
Conoha Wing     정액제 (예정)           ~$5
--------------  ----------------------  -----------
현재 합계                               ~$10~14/월
롱폼 5회 호출 포함 / 블로그 추가 후     ~$15~20/월 (예상)


================================================================
## 16. AI 구독 정리
================================================================
Claude        유지   - 프로젝트 설계, 디버깅, 프롬프트 최적화 핵심 + step10 2차 검증
ChatGPT Plus  선택   - API만으로 대체 가능
Gemini        활용   - step10 1차 검수 (Gemini 2.5 Flash API / google-genai SDK)


================================================================
## 17. 남은 작업 + 실행 순서
================================================================
완료 이력 → CHANGELOG.md

⬜  세션 8 — E: AI 공시 + 정체성 명시
⬜  세션 9 — F: 댓글 반자동 응답 봇
⬜  세션 10 — B: 캐스터 3명 구도
⬜  세션 11 — C: 시리즈물 구조 (기획 단계)

✅  작업 2-1 FRED fetch 모듈 (data/fred_fetch.py) — 2026-05-29
        검증 시리즈: DEXJPUS (USD/JPY daily) / 캐시 월 1회 / 504 시 메시지+수동 재실행
        ※ 구현 당일 api.stlouisfed.org 504 장애로 검수 표 미출력 — 모듈 자체는 완성
✅  작업 2-2 BOJ fetch 모듈 (data/boj_fetch.py) — 2026-05-29
        검증 시리즈: FM08/FXERD05 (도쿄시장 USD/JPY 중심시세 daily)
        검수 표 통과: 최신값 159.3엔, 1,237개 observation
✅  작업 2-3 e-Stat fetch 모듈 (data/estat_fetch.py) — 2026-05-29
        검증 시리즈: 0002070001 家計調査 消費支出 全国 二人以上世帯
        검수 표 통과: 최신값 334,701엔 (2026-03), 59개 observation
        매월근로통계조사(00450071) API DB 2016 정지 확인 — 실질임금은 작업 2-4에서 보류 처리
✅  작업 2-4 토픽뱅크 데이터 코드 정비 — 2026-05-29
        topic_bank.json 스키마 확장: fred_code 단일 → data_sources 배열(fred/boj/estat 다중 소스)
        각 소스 호출 매핑: fred→fred_fetch.fetch_series(code) / boj→boj_fetch.fetch_series(db,code)
                          estat→estat_fetch.fetch_series(stats_data_id, filters)
        active 14개 매핑 확정 — FRED ×5, BOJ ×6(FM08·FM01·FM02·BP01·MD01), e-Stat ×8
          주요 확정: yen-rate(BOJ FM08 primary) / interest-rate(FRED 10년물 primary)
                    inflation-deflation(e-Stat 0003427113 CPI 前年同月比)
                    trade-balance(BOJ BP01 무역수지/경상수지) / central-bank(BOJ MD01 마네타리베이스)
                    irregular-employment(e-Stat 0003006361 非正規 분기) / aging(e-Stat 0003443838 65歳以上)
                    declining-birthrate(e-Stat 0003411721 出生数 연간) / energy(FRED POILDUBUSDM 두바이유)
                    business-cycle(e-Stat 0003446461 CI一致指数) ← 2026-05-29 보류 해제
        각색 2건 확정:
          real-wage — principle 갱신: 소비지출 대리 접근으로 재프레임 (실질임금 직접 시리즈 없음)
          energy-dependency — title_ja/title_ko/principle 갱신: 수입의존도→가격압력·질문형 중립 표현
        보류 1건 (data_sources 비움·사유 기록):
          cashless-society: 전체가구 캐시리스 결제 월별 직접 통계 없음 (e-Stat은 無職世帯 한정·2019)
        ※ business-cycle 보류 해제 — 별도 세션에서 e-Stat 0003446461 CI一致 셀(tab=100/cat01=110) 확정
✅  작업 2 마무리 — FRED 5개 fetch 재검증 + business-cycle active 승격 (2026-05-29)
        FRED 재검증: 작업 2 당시 504 장애로 미확인이던 검수 표 5개 전부 통과
          DEXJPUS(159.2엔) / IRLTLT01JPM156N(2.515%) / GGGDTAJPA188N(239.97%)
          JPNRGDPEXP(593,693억엔) / POILDUBUSDM(126.71USD)
        ※ national-debt(GGGDTAJPA188N): 연간 IMF 시리즈 / months=60 기준 3건
          → 차트 구현 단계(작업 5)에서 기간 확장(months 늘리기) 처리 예정
✅  작업 3 완료 (2026-05-30) — 롱폼 KO 대본 재설계 + JA 변환 검증
        KO: issue1_angle/issue2_angle 사전 결정(mode_judge/call_angle_judge) /
          단일 각도 깊게 파고드는 구조 / SYSTEM_KO 9→5개 슬림화 / GPT 모델 유지 확정
        JA: SYSTEM_JA 사인오프 「チャンネル登録お願いします！」 추가
        KO 검증: yen-rate·inflation-deflation·business-cycle 3토픽 통과
        JA 검증: business-cycle·yen-rate KO→JA→backcheck 3단 비교 통과
          (수치·기준시점·일본인 시점·사인오프 2줄 모두 보존)
        미해결: backcheck JSONDecodeError 간헐 발생(영상 무영향, temperature 조정 별도) /
          일별 data_block 날짜 월단위 변환(B안 확정, 코드 처리 별도)
✅  작업 4 완료 (2026-05-30) — real-wage 1편차 + webui 롱폼 개선
        [real-wage 1편차 완주]
          · long1_script.py --topic real-wage --stage ko/ja → KO·JA 검수 통과
          · 영상화(Pexels 배경) → 예약발행 완료
        [webui 롱폼 위자드 개선]
          · 토픽 직접 지정 경로: GET /api/longform/topics + 드롭다운
            run_long1_ko(topic_id) — --topic 플래그를 웹에서 지정 가능
          · both_done / longform_ready 게이트 완전 제거 → 언제든 롱폼 진입
          · KO 전문 표시 autoResize 버그 수정: display:block 후 scrollHeight 측정
            + input 이벤트 연결(편집 시 실시간 높이 추적)
          · 제작 마커: topic_history.json 기반 ⬜/✅ + 미제작 우선 정렬 + 제작일 표시
          · index.html 문구: 일·목 18:00 JST / 토픽 또는 당일 쇼츠 기반
        [코드 추가 수정]
          · long1_script.py: BACKCHECK_TEMP=0.3 + call_backcheck() (실패 시 경고 후 계속)
          · run_longform.py: --skip-long1 플래그 (KO/JA 완료 후 영상화만 재실행용)
        [★ 작업 순서 변경 — 선제작 중단, 차트 먼저]
          · 발견: 루트 단일 경로 무버전 저장 → 다음 영상 제작 시 비축분 중간 파일 덮어쓰기
            "렌더링 겹 소급 가능" 전제가 비축 간격이 생기면 실질적으로 불성립
          · 결정: 선제작(4) 추가 비축 중단 → 작업 5(차트) 완성 후 선제작 재개
            Remotion 도입 검토 (데이터 차트 mp4 생성 도구)
✅  작업 5-0 완료 (2026-06-01) — Remotion 환경 셋업
        Node.js v24.16.0 / npm 11.13.0 확인 / remotion-best-practices 스킬 설치
        C:\mochien\remotion\ 프로젝트 생성 / out/sample.mp4 렌더 성공으로 환경 확인
✅  작업 5-1 완료 (2026-06-03) — 롱폼 이슈 섹션 화면 템플릿 PoC + 톤·서사 확정
        컴포넌트: NumberCard(게이지 링 아크) + LineChart(cubic bezier + 그라데이션 면적)
        톤(확정): navy_dark 팔레트 — 배경 #1B2A4A 어두운 네이비 / 숫자·주요 텍스트 흰색
          차트 선·마커 레드 #E50000 / 면적 다크레드 그라데이션
          Noto Sans JP Bold 위계 4단계 / 여백 70% 이상 유지
          ※ "밝은 인포그래픽" 톤(poc_issue.mp4) 폐기 → navy_dark.mp4 최종
        서사 구조(확정): poc_d_story 3비트
          비트①(0~1.5초) 제목+방향 신호 / 비트②(1.5~3초) 대형 수치 포스터(화면 80%, 카운트업 ease-out)
          비트③(3~5.8초) 풀 차트 전개(카드 패널→꺾은선 좌→우 자라남, ease-out)
          컨셉: "숫자가 주인공인 미니멀 모션그래픽. 설명보다 수치 자체로 충격. ①주제+방향 → ②수치 폭탄 → ③맥락 차트"
        레이아웃 4종 탐색: poc_a_split / poc_b_fullchart / poc_c_cards / poc_d_story
✅  작업 5-2(A) 완료 (2026-06-03) — BOJ fetch → yen-rate 차트 실연결
          data/make_chart_json.py 신규 / NavyDark.tsx props 동적 수용 / yen_rate_real.mp4 렌더 성공
🔜  작업 5-2(B) — 대본 검수 중 구분자(===차트===) 분기 마킹 통합
          TTS 전송 전 구분자 제거 + 사전 검증 이중 안전망
🔜  작업 5-3 — 음성·자막 동기화 + long4 합성 = 첫 완성본 / 운영자 검수 게이트 지점
🔜  작업 5-4 — 템플릿 N종 확장 + GitHub Actions Node 셋업
🔜  선제작 (작업 4 재개) — 작업 5 완성 후 토픽뱅크 상위 토픽 점진 비축
🔜  34. 롱폼 추가 개선 (챕터 밀도·섹션 구성 최적화)

실행 순서 (전체 — 권장):
  python run_all.py        ← 쇼츠 3편 + 롱폼 통합 실행 (run_all.bat 더블클릭도 가능)

실행 순서 (쇼츠 단독):
  python run_pipeline.py   ← 1편 실행. 3회 실행 후 롱폼 자동 트리거
  또는 단계별:
    python step2_select.py → step4_pexels.py → step5_tts.py
    → step6_ffmpeg.py → step7_whisper_subtitle.py → step9_youtube.py

실행 순서 (롱폼 단독):
  python run_longform.py                 ← 통합 실행 (long1~7)
  python run_longform.py --skip-long1   ← KO/JA 완료 후 영상화만 (long2~7)
  또는 단계별:
    python long1_script.py --topic {id} --stage ko  → --stage ja
    → long2_tts.py → long3_pexels.py
    → long4_ffmpeg.py → long5_whisper.py → long6_youtube.py


================================================================
## 18. 레슨런
================================================================
상세 레슨런 전체 → lessons.md 참조
(기술 트릭·API 함정·FFmpeg 패턴·버그 원인 등 누적 기록)

================================================================
## 20. 로컬 웹 UI (세션 7 추가 — 2026-05-18)
================================================================
목적       : GitHub Actions + 텔레그램 자동 모드와 별개로, PC에서 수동 운영하는 웹 인터페이스
실행       : webui.bat 더블클릭 → http://localhost:8000 접속
기술 스택  : FastAPI + Jinja2 + Vanilla JS + SSE / 다크모드 고정

신규 파일 목록:
  webui.py           ← FastAPI 진입점 (모든 라우트)
  webui_runner.py    ← 파이프라인 래퍼 + SSE 제너레이터
  webui_pexels.py    ← Pexels 후보 6개 + used_videos.json 관리
  used_videos.json   ← 런타임 생성 / 최근 30일 사용 영상 URL 누적
  templates/index.html          ← 대시보드 (슬롯 상태 + 진입 버튼)
  templates/select_article.html ← 기사 선택 카드
  templates/confirm_script.html ← GPT 대본 확인 + 재생성
  templates/select_background.html ← Pexels 후보 선택 (hover 미리보기)
  templates/generate.html       ← SSE 진행상황 + YouTube URL 표시
  templates/longform.html       ← 롱폼 단일 페이지 위자드
  static/style.css   ← 다크모드 / 모찌엔 컬러 (#1a1a2e 배경, #1B2A4A 네이비, #E50000 포인트)
  static/app.js      ← SSE 공용 헬퍼, 진행바 업데이트 유틸
  webui.bat          ← uvicorn webui:app --reload --port 8000 실행 배치

쇼츠 화면 흐름 (슬롯별):
  / → /shorts/{slot}/select → /shorts/{slot}/script → /shorts/{slot}/background → /shorts/{slot}/generate
  각 단계 중간 결과는 서버 인메모리 (SLOT_STATE) + 파일 동시 보존
  [다시 생성] 무제한 / 기사·배경 선택 언제든 재진행 가능

롱폼 화면 흐름 (단일 페이지 위자드):
  /longform → ① 스크립트 생성 → ② 확인 → ③ 배경 3슬롯 선택 → ④ 생성 SSE

SSE 진행률 설계:
  - 단계 시작 시: {step, pct, msg, eta} 이벤트
  - 긴 단계(FFmpeg·Upload·Long4 등): TICK_INTERVAL(25~40초)마다 의사 진행률 tick
  - 완료: {step:"Done", pct:100, url:"https://..."} / 오류: {step:"Error", pct:-1, msg:"..."}
  - FFmpeg 내부 진행률: step6_ffmpeg.py가 stderr을 capture_output=True로 내부 처리하므로
    외부 파싱 불가 → 25초 tick 의사 진행률로 대응

핵심 설계 원칙:
  - 기존 step2~9 / long1~6 코드 무변경 — webui_runner가 subprocess로 호출
  - step4_pexels.py 대체: webui UI에서 선택 → webui_runner.download_video()로 직접 다운로드
  - 동시 실행 방지: SLOT_STATE[slot]["is_running"] 플래그
  - 자동 모드(GitHub Actions)와 완전 독립 — 진입점 분리

requirements.txt 추가 항목: fastapi / uvicorn[standard] / jinja2 / sse-starlette

================================================================
## 19. 2단계 예고 (파이프라인 안정화 이후 검토)
================================================================
- output 폴더 날짜별 자동 생성 + 30일 이전 자동 삭제
- 주간 경제 정리 영상 (매주 일요일 JST 20~21시)
  → 당주 gpt_result 7일치를 주간 요약으로 재편집
  → 주간 데이터 보관 구조 별도 설계 필요 (artifact는 하루 만에 삭제됨)
  → repo data 브랜치 또는 output/ 매일 자동 커밋 방식 검토
- 씬별 배경 영상 전환 (4씬 구조 재설계)
- 워드프레스 REST API 블로그 자동 발행
- Streamlit 웹 UI 구축 (파이프라인 실행 버튼 + 결과 미리보기)
- 퀀트 트레이딩 Python 파이프라인 구축
- Project Flint (Unity 2D) C# 개발 시작
- 한국 채널 파이프라인 구축 (쇼츠 안정화 이후)

================================================================


================================================================
## 20. 펀넬·신뢰성·리텐션 재설계 — 구현 지침 (2026-05-29 회의)
================================================================
전략 서사·근거는 mochien_master.md 9장 참조. 여기엔 Claude Code가 상속할
결정사항·금지선만 기록. 충돌 시 본 절(최신) 우선.

### 작업 순서 (의존관계 기준, 작업량 기준 아님)
1. 펀넬 구조 → 2. 데이터 연결(FRED/e-Stat/BOJ) → 3. 대본 재설계
→ 4. 선제작(점진) → 5. 화면 재설계(차트·키네틱·타입라이터·토픽비주얼).
- 콘텐츠 겹(대본+음성)=소급 불가 → 선제작 전 완성. 렌더링 겹(화면)=ffmpeg
  재렌더로 소급 가능 → 뒤로 가도 손해 0. 이 구분이 순서의 근거.
- 차트(구 세션 B)는 5번으로 재배치(폐기 아님).
- "작업량 많으니 나중에/별도 세션" 식 미룸 금지. 작업량은 세션 분할 여부에만 관여.

### 펀넬 구조 (작업 1 — 회의 직후 착수)
- 원칙: 쇼츠는 '오늘 만든 롱폼'이 아니라 '같은 topic_id로 이미 발행된 롱폼'으로 링크.
- 생산 분리: run_all/run_pipeline의 "쇼츠 2편 성공→롱폼" 묶음 해제, 롱폼 독립 실행.
  (GitHub Actions는 mochien_longform.yml로 이미 분리 — 로컬 경로만 정합)
- 토픽 브리지: 쇼츠 기사 선택 시 가장 가까운 topic_id 자동 태깅(article_score의
  match_topic을 UI 정렬 힌트→펀넬 연결 키로 승격).
- 펀넬 타겟: 쇼츠 링크/아웃트로가 같은 topic_id의 '발행된' 롱폼을 가리킴.
  폴백: 매칭 롱폼 없음→최신 롱폼→그것도 없음→일반 구독 CTA.
- 링크 자동화: 펀넬 링크를 쇼츠 '설명란 첫 줄'에 API로 자동 삽입(핀 불필요).
  고정댓글 핀은 보너스로 강등(수동 핀 의존 탈피).
- 검증 지표: YouTube 분석 롱폼 트래픽 소스에 'Shorts' 노출 여부 = 펀넬 작동 증거.

### 롱폼 신뢰성 (작업 2~3) — 금지선
- 대본 근거를 '당일 뉴스 요약+GPT 기억'에서 '공공 1차 데이터+교과서 원리'로 전환.
- 수치 출처: FRED + e-Stat + 일본은행(BOJ) + 총무성 통계국. GPT가 데이터 밖
  새 주장·예측 생성 금지(기존 할루시네이션 가드 강화).
- [금지] 닛케이/이코노미스트 등 공인 저널 기사 크롤링·인용 금지(저작권+유료차단).
  원천 공공 데이터만 사용.
- 데이터 수치 차트 = 리텐션 ② 차트와 동일 산출물(작업 맞물림).

### 리텐션 패키지 (작업 3 대본 / 작업 5 화면)
- ① 질문형 대본(화자1이 시청자 속마음 대신 질문) — 대본 프롬프트.
- ② 키네틱 숫자/차트(발화 순간 수치 화면 표시) — 렌더링.
- ③ 섹션 비트 화면표시 + 첫 15초 콜드오픈 — 대본+렌더링.
- 에스컬레이션: ①②③ →[리텐션 데이터 확인]→ ④ 오프스크린 질문 보이스
  (얼굴·표정·캐릭터시트 없는 질문 전용 TTS 1트랙) →[데이터]→ 풀 2인 대담(최후수단).
- [금지] 풀 2인 대담·캐스터/전문가 캐릭터를 지금 구현하지 말 것(보류). 실존 인물
  모방 금지. 롱폼 표정 사용은 세션3 결정(neutral 고정) 번복이므로 임의 도입 금지.
- [금지] 매 장면 AI 이미지 생성(master 5-8 폐기). 토픽별 고정 비주얼 세트를
  미리 만들어 키워드 규칙 전환으로 대체. 썸네일 AI 이미지(세션 G)는 예외 유지.

### 선제작 (작업 4)
- 토픽뱅크 상위 10토픽 롱폼 선발행으로 펀넬 매칭 구멍 메움.
- 방식: 1편 검수 → 점진 제작(주2 기준에서 내키면 주3·4편 비축 가속). 한 번에 몰지 않음.
- 비축은 한시적. 라이브러리 차면 주2편 정상 복귀(정상 빈도 상향 아님).
- 제작은 집중 가능, 공개(발행)는 일/목 슬롯 예약 분산(몰아 올리면 양산 신호).

※ 작업 1 구현 상세 기록 → mochien_master.md 8절 참조.
