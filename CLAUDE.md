# 모찌엔 YouTube Shorts 자동화 프로젝트 — CLAUDE.md
최종 업데이트: 2026년 5월 20일 (웹 UI 개선 — 기사 재수집·Pexels 인물제외·KeyboardInterrupt 수정)

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
→ long1_script.py: gpt-4.1로 롱폼 스크립트 생성 (long_script.json) — 4회 순차 호출
   intro(1) → issue1(2) → issue2(3) → outro+메타(4)
   각 섹션이 직전 섹션의 summary를 컨텍스트로 수신해 섹션 간 연결성 유지
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
## 5. ChatGPT 프롬프트 (현재 버전) ← 10차 세션 수정 완료
================================================================
시스템 프롬프트:
  あなたはJSONのみを出力するAIです。
  出力は必ず { で始まり } で終わる純粋なJSONのみ。
  ```json などのマークダウン記号は絶対に使用禁止。
  以下のキー以外は絶対に追加しないこと:
    title, hook, hook_korean, script, hashtags, korean_summary, emotion, image_prompt, short_title
  人名・企業名・役職名は正確に表記すること。略称・誤字・当て字は絶対禁止。

유저 프롬프트 (USER_PROMPT 변수):
  【モチエンキャラクター設定】
  - 冒頭の挨拶は禁止。最初の一文は必ずhookの内容から始めること。
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
  - 必ず日本語で生成すること
  - 視聴者の生活・損得・驚きと直結させること
  - 数字・疑問形・「あなたの○○が変わる」形式を優先すること

  【hashtags ルール】
  - 日本語または英語のみ（韓国語タグは絶対に含めないこと）
  - 日本語検索ボリュームが高いタグを優先
  - #Shorts必須

  【その他】
  - 誤読しやすい漢字にはふりがなを括弧で併記すること
  - 人名・企業名・役職名は正確に表記すること
  - short_title：6〜10字の核心キーワード
  - image_prompt：Pexels検索用英語キーワード（例："japanese economy stock market"）

JSON 9필드 상세 (GPT 출력) + step2에서 3개 추가 = gpt_result.json 총 12필드:
  title          - 영상 제목 (30자 이내 / 시청자 손득·놀라움 직결)
  hook           - 첫 후킹 문장 (일본어 / 생활·손득·驚き 직결)
  hook_korean    - hook 일본어의 자연스러운 한국어 번역 (선택적 필드)
  script         - 본문 스크립트 (마무리 3줄 필수)
  hashtags       - 해시태그 배열 (일본어·영어만 / #Shorts 필수)
  korean_summary - 한국어 1줄 요약
  emotion        - 영어 감정값 (아래 목록 중 1개)
  image_prompt   - Pexels 검색 영어 키워드
  short_title    - 6~10자 핵심 키워드
  --- step2_select.py에서 추가 ---
  slot           - 슬롯 배정 ("09" / "18")
  article_url    - 기사 URL (당일 중복 방지용)
  raw_summary_jp - RSS entry.summary 일본어 원문 본문 (long1_script.py 심층 분석 입력용)

emotion 허용값:
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
입력 텍스트 : ChatGPT JSON의 script 필드
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
  ※ GITHUB_TOKEN은 자동 제공 — 별도 등록 불필요


================================================================
## 14. 파일 구조
================================================================
C:\mochien\
  ├── CLAUDE.md
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
  ├── step9_youtube.py
  ├── step10_gemini_review.py             ← Gemini+Claude 자막·발음 자동 검수 (--mode shorts|longform)
  ├── [ 롱폼 파이프라인 ]
  ├── run_longform.py                     ← 롱폼 전체 실행 (long1→6)
  ├── long1_script.py                     ← gpt-4.1 롱폼 스크립트 생성
  ├── long2_tts.py                        ← 4섹션 TTS + concat
  ├── long3_pexels.py                     ← 3개 배경 영상 다운로드
  ├── long4_ffmpeg.py                     ← 섹션별 클립 생성 + concat
  ├── long5_whisper.py                    ← Whisper 자막 합성
  ├── long6_youtube.py                    ← YouTube 업로드 + 텔레그램
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
## 17. 작업 순서 (현재 진행 단계)
================================================================
✅  1.  Python 가상환경 생성 및 라이브러리 설치
✅  2.  RSS 수집 + HTTP 크롤링 (step2_rss_crawler.py)
✅  3.  ChatGPT API 호출 + JSON 파싱 (step3_chatgpt.py) → step2_select에 통합됨
✅  4.  Pexels API 배경 영상 취득 (step4_pexels.py)
✅  5.  ElevenLabs TTS 호출 (step5_tts.py)
✅  6.  FFmpeg 영상 합성 (step6_ffmpeg.py)
✅  7.  Whisper API 자막 합성 (step7_whisper_subtitle.py)
✅  9.  YouTube 자동 업로드 + 텔레그램 완료 알림 (step9_youtube.py)
✅  9b. 텔레그램 기사 선택 + ChatGPT 통합 (step2_select.py)
✅  11. GitHub Actions 스케줄 설정 및 배포 완료
✅  12. 6차 세션 기능 추가 (2026-05-10)
        - cron 2시간 앞당기기 + keepalive 주간 자동 커밋
        - hook 강화 + 마무리 3줄 수정 (step2_select.py)
        - gpt_result JST 슬롯별 날짜 폴더 저장 (step2_select.py)
        - API 잔액 텔레그램 경고 (step2_select.py)
        - 무응답 10분 자동 진행 / ❌ 취소 명시적 구분 (step2_select.py)
        - 배경 쿨 블루 컬러 그레이딩 + 비네팅 (step6_ffmpeg.py)

✅  13. run_pipeline.py — 쇼츠 파이프라인 통합 실행 스크립트 (2026-05-10)

✅  16b. YouTube 채널 기본 세팅 완료 (2026-05-11)
        - 카테고리: 뉴스/정치
        - 키워드: 일본어 경제 키워드 15개 입력
        - 아동용: 아동용 아님 설정
        - 거주 국가: 일본 설정
        - 업로드 기본값 동영상 언어: 일본어 설정
        - 고급 기능 인증: 구독자 50명 때 진행 예정
        - 비즈니스 이메일: 나중에 추가 예정

✅  17. 9차 세션 기능 추가 (2026-05-12)
        - step9_youtube.py: 즉시 public → 예약 발행 (07:00/12:00/18:00 JST) / 자동 댓글 제거
        - long6_youtube.py: 예약 발행 21:00 JST / 자동 댓글 제거
        - run_pipeline.py: 쇼츠 3개 완료 시 run_longform.py 자동 호출
        - step2_select.py:
          · gpt_result.json에 slot / article_url / hook_korean 필드 추가
          · SYSTEM_PROMPT: 인명/기업명/직함 정확 표기 지시 추가
          · USER_PROMPT: 误読 한자 후리가나 병기 지시 추가
          · RSS 경제 키워드 필터링 (株/円/物価 등 10개) + fallback 전체 선택
          · 중복 기사 방지: 당일 사용 URL article_url로 추적, 재수집 시 제외
        - step7_whisper_subtitle.py: correct_proper_nouns() 추가
          Whisper 세그먼트 고유명사 오타 GPT 교정 (gpt_result.json 참조)
        - long4_ffmpeg.py: SD 해상도 배경 영상 crop 오류 수정
          scale=-2:H → scale=W:H:force_original_aspect_ratio=increase
        - step5_tts.py: TTS 전송 전 후리가나 괄호 제거 전처리 추가
          re.sub(r"[（(][^）)]*[）)]", "", script) — 全角/半角 모두 제거
        - long2_tts.py: 동일한 후리가나 괄호 제거 전처리 추가 (5섹션 전체 적용)
        - long1_script.py: 심층 분석 방식으로 전면 재작성
          · 입력: 쇼츠 full script 제거 → title + korean_summary만 사용
          · 3개 토픽의 공통 경제 트렌드·인과관계로 연결 (단순 요약 금지)
          · 각 이슈: 背景・現状→影響分析→視聴者へのメッセージ 3층 구조
          · 목표 분량: intro 400字(1분) / issues 800字×3(2분) / outro 400字(1분) = 3,200字/8분
          · 섹션명: "ショーツ①②③" → "トピック①②③"

✅  16a. 수동 트리거 전환 완료 (2026-05-11)
        - GitHub Actions cron 제거 (무료 플랜 1~4시간 지연으로 사용 불가 판단)
        - mochien.yml / mochien_longform.yml: workflow_dispatch 전용으로 전환
        - 트리거 방법: 핸드폰 GitHub 앱 → Actions → Run workflow
        - telegram_trigger.py: PC 로컬용 텔레그램 봇 (JST 알람 + 버튼 트리거)
        - step2_select.py: 슬롯 배정 시간 기준 → 당일 파일 순서 기준으로 변경

✅  15. 롱폼 파이프라인 구축 완료 (2026-05-10)
        - long1_script.py: gpt-4.1 롱폼 스크립트 생성 (5섹션 구조)
        - long2_tts.py: 섹션별 TTS + FFmpeg concat → long_voice.mp3
        - long3_pexels.py: 4개 배경 영상 다운로드
        - long4_ffmpeg.py: 섹션별 클립 생성 + concat → long_output_no_sub.mp4
        - long5_whisper.py: Whisper 자막 합성 → long_output.mp4
        - long6_youtube.py: YouTube 업로드 + 텔레그램 완료 알림
        - run_longform.py: 롱폼 파이프라인 통합 실행
        - mochien_longform.yml: GitHub Actions 롱폼 워크플로우
        - Artifact 누적 방식: 쇼츠→롱폼 gpt_result 파일 전달

✅  18. 10차 세션 버그 수정 (2026-05-12)
        - step2_select.py:
          · short_title 누락 시 title 앞 8자 fallback 추가 (GPT 미출력 대비)
          · 기사 소진·취소 시 sys.exit(0) → sys.exit(1) 변경 (파이프라인 중단 보장)
        - mochien.yml: dawidd6 artifact 다운로드 후 output/gpt-results/ 서브폴더 생성 시
          output/으로 자동 이동하는 보정 스텝 추가 (슬롯 중복 배정 버그 수정)
        - step9_youtube.py: 발행 시각 로직 — 목표 시각 초과 시 익일 동일 시각 예약 (원복)

✅  19. SRT 자막 YouTube 업로드 (2026-05-12)
        - step7_whisper_subtitle.py: Whisper 세그먼트로 subtitle.srt 생성 (추가 API 호출 없음)
        - step9_youtube.py: 영상 업로드 후 captions.insert로 subtitle.srt 전송 (ja / 日本語)
          subtitle.srt 없으면 자동 스킵 / private 예약 상태에서도 captions API 정상 작동

✅  20. 텔레그램 알림 개별 발송 전환 (2026-05-12)
        - step9_youtube.py: 숏폼 업로드 완료 시 즉시 개별 알림 (제목/예약시간/고정댓글)
        - long6_youtube.py: build_combined_notification() → build_notification() 단순화
          롱폼 단독 알림만 전송 (쇼츠 합산 제거)

✅  21. 12차 세션 품질 개선 (2026-05-13)
        - step5_tts.py / long2_tts.py: pykakasi 한자→히라가나 변환 추가
          kanji_to_hiragana() 함수 / re.sub(후리가나 제거) 다음 단계에 적용
          자막·JSON 원본은 건드리지 않음 — TTS 전송 텍스트에만 적용
        - step7_whisper_subtitle.py: correct_proper_nouns() 전면 강화
          SEP_TOKEN 배치 방식 폐기 → 세그먼트 1개씩 개별 GPT 교정으로 전환
          레퍼런스에 hook 필드 추가 / 교정 범위 확장 (고유명사 + 동음이자 + 음성인식 오류)
          개별 호출 실패 시 해당 세그먼트만 원본 유지 / 타이밍값 일절 건드리지 않음
        - step2_select.py:
          · SYSTEM_PROMPT에 hashtags JSON 배열 형식 명시
            ("hashtagsは必ずJSON配列で出力すること")
          · RSS_URL → RSS_URLS 3개 확장
            NHK cat6(경제) + NHK cat5(비즈니스) + Yahoo Japan 비즈니스
          · fetch_articles(): 소스별 순회 → URL 중복 제거(seen_urls) → 키워드 필터
            소스 실패 시 해당 소스만 건너뜀 (파이프라인 계속 진행)
        - step9_youtube.py: hashtags 문자열→배열 정규화 (.split()) 추가 (안전장치)
        - requirements.txt: pykakasi 추가

✅  22b. RSS pubDate 신선도 정렬 (2026-05-13, 13차 세션 추가 작업)
        - step2_select.py: fetch_articles() 정렬 단계 추가
          · FRESHNESS_HOURS=6 / fresh tier(최근 6시간 이내) → stale tier 순으로 텔레그램 후보 제시
          · tier 내부는 pubDate 최신순(내림차순)
          · pubDate 없는 기사는 stale 끝으로 (epoch 0 처리)
          · filtered / fallback 두 경로 모두 적용
          · 외부 API·신규 라이브러리 추가 없음 (feedparser pubDate + calendar.timegm만 활용)
        - import calendar 추가 / FRESHNESS_HOURS 상수 추가 / sort_by_freshness() 헬퍼 추가

✅  22. 13차 세션 — Whisper 자막 품질 개선 (2026-05-13)
        - step7_whisper_subtitle.py:
          · KNOWN_ASR_ERRORS에 부분 매칭 2개 추가
            ("公満事" → "コーマン事") / ("務省庁" → "務総長")
            세그먼트 분리로 전체 문자열 매칭 실패 시 대비
          · apply_glossary() 함수 추가 — 세그먼트 생성 직후 glossary.json 일괄 치환
          · transcribe(): gpt_result.json의 title+hook을 Whisper initial_prompt로 전달
            → 고유명사 인식률 향상 (公満事 오인식 사라짐 확인)
        - long5_whisper.py:
          · apply_glossary() 함수 추가 (동일 구조)
          · transcribe(): 동일하게 gpt_result.json initial_prompt 전달
        - glossary.json 신규 생성
          · 고유명사 오인식 패턴을 코드 밖 파일로 관리
          · 등록 기준: 3글자 이상 특수 패턴 위주 / 경제뉴스 일반 명사 등록 금지
          · 초기 등록: 公満事務省庁 / 公満事 / 務省庁 / 隠密に / 効果果
          · 영업→影響 / 公私→高市는 KNOWN_ASR_ERRORS에 안전장치 있으므로 glossary 제외

✅  23. 14차 세션 — Whisper 자막 오교정 방지 강화 (2026-05-14)
        - step7_whisper_subtitle.py / long5_whisper.py:
          · GPT 확장 방지: 교정 결과 길이 배수 * 3 → * 2
            (8자 세그먼트를 20자 문장으로 확장한 오교정 차단)
          · GPT 프롬프트 길이 제약 추가
            "文章を長くしたり補完したりしないこと / 増減は1〜3文字程度まで"
          · KNOWN_ASR_ERRORS 3개 추가 (step7 + long5 공통)
            ("市立" → "仕事") — 仕事の状況 오인식
            ("乱行政" → "ラン情勢") — イラン情勢 세그먼트 분리 후반부
            ("岸外務省" → "外務省") — 元外務省 오인식

✅  24. 15차 세션 기능 추가 (2026-05-14)
        - mochien_full.yml: 쇼츠 3편 + 롱폼 통합 GitHub Actions 워크플로우 신규 생성
          · workflow_dispatch 단일 트리거로 쇼츠 3슬롯 순차 처리 → 롱폼 자동 이어서 실행
          · timeout-minutes: 180 / 기존 mochien.yml · mochien_longform.yml은 개별 실행용으로 유지
        - run_all.py: 로컬 전체 파이프라인 일괄 실행 스크립트 신규 생성
          · 시작 시 오늘 슬롯 파일 3개 자동 초기화 (clean start / 재실행 시 중복 방지)
          · 각 슬롯 완료 후 all_slots_done() 체크 → True면 break (롱폼 중복 실행 방지)
        - run_all.bat: run_all.py 더블클릭 실행파일 신규 생성 (pause로 창 유지)
        - step2_select.py: gpt_result.json에 raw_summary_jp 필드 추가
          · 값: RSS entry.summary (일본어 원문 본문)
          · 총 12개 필드 (GPT 9 + step2 추가: slot / article_url / raw_summary_jp)
        - long1_script.py: raw_summary_jp를 롱폼 스크립트 생성 프롬프트에 포함
          · USER_PROMPT_TEMPLATE에 "日本語原文: {raw1/2/3}" 섹션 추가
          · 【深掘り分析の方針】에 원문 활용 3개 지시 추가
            "日本語原文を事実の根拠として活用" / "数値・引用・固有名詞は原文基準" / "因果関係・背景・今後の影響を抽出"
        - long2_tts.py: 5섹션 mp3 생성 후 long_chapters.json 자동 생성
          · ffprobe_duration()으로 각 섹션 mp3 길이 측정
          · 누적 시작 시각 계산 → 챕터 라벨 조립
            intro→"オープニング" / issue1~3→"①②③+short_title" / outro→"まとめ"
          · short_title은 오늘 날짜 09/13/18 gpt_result.json에서 읽음 (없으면 トピック①②③ fallback)
        - long6_youtube.py: long_chapters.json 읽어 description 상단에 챕터 타임라인 삽입
          · 형식: "MM:SS 라벨" (1시간 이상 시 H:MM:SS) / 파일 없으면 기존 description 유지

✅  25. 16차 세션 기능 추가 (2026-05-14)
        - step10_gemini_review.py 신규 생성
          · Gemini 2.5 Flash 1차 검수 (발음 오류 + 자막 오인식 후보 추출)
          · Claude Haiku 2차 검증 (approve/reject 판정 + 한국어 뜻/이유)
          · approve=true 항목 pronunciation.json / glossary.json 자동 반영
          · 전체 후보 suggested_*.json 누적 (count/first_seen/last_seen/approved/reason)
          · 텔레그램 한국어 알림 (한자 뜻 괄호 표시 / ✅ 자동 반영 / ⏸ 보류 구조)
          · --mode shorts / --mode longform CLI 분기
          · 실패 시 tg_error 전송 후 sys.exit(0) — 파이프라인 중단 금지
        - pronunciation.json 신규 생성 (TTS 전용 발음 교정 / 자막·JSON 원본 미적용)
        - long5_whisper.py: SRT 출력 추가 (long_subtitle.srt)
          · to_srt_time() + write_srt(segments, path) 함수 추가
          · apply_glossary/apply_rule_corrections 후 동일 교정 텍스트 적용
        - step5_tts.py / long2_tts.py: apply_pronunciation() 추가
          · pronunciation.json 읽어 TTS 전송 직전 치환 / 파일 없으면 원본 반환
        - run_pipeline.py / run_longform.py: step10 자동 호출 추가
          · step9/long6 완료 직후 실행 / 실패해도 파이프라인 계속 진행
        - mochien.yml: step10 --mode shorts 실행 스텝 추가 (continue-on-error: true)
        - mochien_full.yml: 슬롯1/2/3 step9 직후 shorts × 3 + long6 직후 longform 추가
        - mochien_longform.yml: GEMINI/ANTHROPIC 키 주입 추가 (run_longform이 step10 auto-call)
        - yml 3종: GEMINI_API_KEY / ANTHROPIC_API_KEY Secret 주입 추가
        - requirements.txt: anthropic 추가

✅  26. 17차 세션 — 발음 정확도 개선 (2026-05-15)
        - step5_tts.py / long2_tts.py: TTS 모델 eleven_flash_v2_5 → eleven_multilingual_v2 변경
          상수명 TTS_MODEL_ID로 통일 (NO MAGIC NUMBERS 원칙)
        - pronunciation.json: 초기 사전 71개 등록
          카테고리: 정치인·관료명(불규칙 독음) / 금융기관 / 기업명 / 경제용어 / 통화·시장 용어
          복합 키(三菱UFJ銀行)를 단순 키(三菱)보다 앞에 배치 → 부분 치환 오작동 방지
        - upload_pronunciation_dict.py 신규 생성
          pronunciation.json → ElevenLabs alias 규칙으로 변환 후 API 업로드
          결과 ID를 .env / GitHub Secrets에 등록하면 TTS 호출 시 자동 적용
        - step5_tts.py / long2_tts.py: ELEVENLABS_PD_ID / PD_VERSION_ID 환경변수 연동
          두 값 모두 있을 때만 pronunciation_dictionary_locators 파라미터 추가 (없으면 스킵)
        - step2_select.py: USER_PROMPT 후리가나 지시 강화
          인명·기업명·역직명·전문 경제용어 → 반드시 히라가나 괄호 병기
          _check_furigana(): 3자 이상 연속 한자 있고 후리가나 0개면 경고 로그 (파이프라인 유지)
        - step10_gemini_review.py: max_tokens 1024 → 2048 (JSONDecodeError 수정)

✅  27. 18차 세션 — 기사 일괄 선택 + 파이프라인 구조 변경 (2026-05-15)
        - step2_select.py: --batch 모드 추가 (전면 재작성)
          · single_main(): 기존 단독 선택 모드 (--batch 없이 실행 시)
            RSS 전체 실패 시 TG error 전송 + sys.exit(1)
          · batch_main(): 신규 일괄 선택 모드 (--batch 플래그)
            · fetch_articles() try/except → 실패 시 TG error + sys.exit(1)
            · ThreadPoolExecutor 병렬 GPT 호출 (5개 동시)
            · 후보 전체를 텔레그램에 카드형 메시지로 전송
            · sel_{idx}/pas_{idx} 버튼으로 3개 선택 완료 시 저장
            · 30분 타임아웃 / "취소" 텍스트 입력으로 중단
            · 선택 순서대로 09/13/18_gpt_result.json 저장
          · batch_poll(): 복수 메시지 ID + "취소" 텍스트 동시 폴링
            allowed_updates: ["callback_query", "message"]
        - run_all.py: 전면 재작성
          · step2_select.py --batch 1회 실행 → 슬롯 파일 3개 동시 생성
          · for slot in [09, 13, 18]:
              shutil.copy({slot}_gpt_result.json → gpt_result.json)
              step4~9 순차 실행
              슬롯 실패 시 TG 알림 "⚠️ 슬롯 {slot} 실패 / 나머지 계속" + 다음 슬롯 진행
              step10 --mode shorts (실패 무시)
          · 전체 슬롯 실패 시 롱폼 건너뜀 + sys.exit(1)
          · 롱폼: run_longform.py 호출 (step10 longform 포함)
        - mochien_full.yml: python run_all.py 단일 호출로 대폭 간소화
          · 기존: step2 × 3 + step4~9 × 3 + step10 × 3 + long1~6 + step10 longform
          · 변경: python run_all.py 1줄 → 전체 로직은 run_all.py에서 관리

✅  28. 19차 세션 — 롱폼 분량 확대 (2026-05-15)
        - long1_script.py: 1회 GPT 호출 → 5회 순차 호출로 전면 재작성
          · 호출 순서: intro → issue1(topic1 raw+intro요약) → issue2(+issue1요약)
            → issue3(+issue1·2요약) → outro+메타(전체 요약)
          · 각 섹션 content+summary 동시 출력 → 추가 API 호출 없이 컨텍스트 누적
          · 섹션별 필수 항목 수 강제:
            intro 3항목 / issue×3 6항목(각 3~4문) / outro 3항목
          · 목표 분량: intro 500자 + issue 1,000자×3 + outro 500자 = 약 4,000자 ≈ 7~8분
          · long_script.json 출력 포맷 기존 유지 → long2~6 수정 불필요
          · image_prompt: 각 슬롯 gpt_result.json에서 재사용 (추가 GPT 호출 없음)
          · emotion 필드 제거 (long2~6·step10 모두 미사용 확인)
          · 섹션별 글자수 + 총 토큰 합산 로깅 추가
        - 후속 수정 (issue 글자수 부족 + step10 JSONDecodeError):
          [A] issue prev_summaries 직전 1개만 전달 (전체 누적 시 GPT 요약 모드 전환 방지)
          [B] PROMPT_ISSUE에 "最低700字以上" 명시 + "titleは必ず日本語のみ（韓国語・英語禁止）" 추가
          [C] call_issue_retry() — 700자 미만 시 1회 재시도 (실패해도 파이프라인 계속)
          [D] step10_gemini_review.py max_tokens 2048 → 4096
          [E] PROMPT_ISSUE title 필드 일본어 강제 (챕터 한국어 제목 출력 버그 수정)
        - step10_gemini_review.py: call_claude() 발음·자막 2회 분할 호출로 재작성
          · 기존: 발음+자막 전체 1회 호출 → 후보 87건 시 max_tokens=4096도 초과
          · 변경: 발음 후보만 1차 호출 / 자막 후보만 2차 호출 → 결과 병합 반환
          · 외부 시그니처·반환값 구조 유지 → 하위 로직 변경 없음

✅  29. 20차 세션 — 롱폼 알림 개선 + run_all 임시파일 자동 정리 (2026-05-15)
        - long6_youtube.py: build_notification() 재작성
          · load_slot_short_titles(): output/{오늘날짜}/{09|13|18}_gpt_result.json에서 short_title 읽기
          · 고정댓글 문구: 「short_title1」「short_title2」「short_title3」の3つ 형식
            슬롯 일부 누락 시 있는 것만 나열 / 전부 없으면 "今日の経済ニュース" fallback
          · hook 150자 트리밍 로직 및 korean_summary 줄 제거
          · SLOTS 상수 추가
        - run_all.py: 임시파일 자동 정리 기능 추가
          · RETENTION_DAYS = 30 / TEMP_JSON_FILES 상수 추가 / import glob 추가
          · cleanup_temp_files(): *.mp4 / *.mp3 / 임시 JSON 8종 / 자막 파일 정리
          · cleanup_old_output_folders(retention_days): output/{YYYY-MM-DD}/ 30일 이전 삭제
          · main() 구조: cleanup_old_output_folders → clear_today_slots → try(파이프라인) → finally(cleanup_temp_files)
          · sys.exit() 포함 모든 종료 경로에서 finally 실행 보장

✅  30. 21차 세션 — 마무리 멘트 1줄화 + bow.gif 인사 오버레이 (2026-05-16)
        - step2_select.py: USER_PROMPT 스크립트 마무리 3줄 → 1줄로 변경
          · 변경 전: 「皆さんはどう思いますか？〜 / 以上、モチエンがお伝えしました！ / チャンネル登録お願いします！」
          · 변경 후: 「以上、モチエンがお伝えしました！」
        - step6_ffmpeg.py: bow.gif 인사 오버레이 기능 전면 구현
          · 상수 추가: BOW_GIF / BOW_DURATION(1.5s) / TEMP_MAIN_FILE / TEMP_BOW_FILE
          · get_bow_gif(): 로컬 파일 존재 시 사용 / 없으면 인사 애니메이션 스킵
          · detect_speech_end(): silencedetect -30dB으로 trailing silence 직전 발화 종료 시점 감지
            silenceremove 방식 폐기 (FFmpeg 8.1 filter_complex에서 입력 -t 옵션 미작동 확인)
            → 출력 옵션 -t로 Pass 1 정확히 자름
          · build_filter(): overlay에서 shortest=1 제거 → eof_action=repeat으로 마지막 프레임 고정
          · build_cmd_bow_clip(): bow.gif를 -ignore_loop 0으로 GIF 자체 1회 루프 설정 존중
          · build_cmd_concat(): Pass 1(본편) + Pass 2(bow 1.5s) → 3-pass concat
          · main() 3-pass 구조:
            Pass 1: voice.mp3 발화 종료 시점(-t 출력 옵션)에서 talk.gif 정확히 종료
            Pass 2: bow.gif 1.5s 단독 클립 생성 (anullsrc 무음)
            Pass 3: 두 클립 concat → output_no_sub.mp4
          · mochien_bow.gif 없으면 기존 1-pass 단순 합성으로 fallback (하위 호환)

✅  세션 5b 완료 (2026-05-18) — 로컬 웹 UI 구축 (FastAPI + SSE) → 상세: CLAUDE.md 섹션 20 참조

✅  웹 UI 버그 수정 + 롱폼 개선 (2026-05-19)
        - long4_ffmpeg.py: get_audio_duration() + -t 출력 옵션 추가 (step6와 동일 무한루프 방지)
          overlay filter shortest=1 제거 / -shortest 제거
        - step10_gemini_review.py: Gemini 오류 0건 시에도 "검수 완료" 텔레그램 발송
          기존: 0건이면 알림 없음 → step10 실행 여부 확인 불가 문제 수정
        - webui_pexels.py: save_used_video() ts(unix) → used_at(date str) 형식으로 전환
          _entry_is_recent() 추가로 기존 ts 항목 하위 호환 처리
          step4_pexels.py / long3_pexels.py도 동일 헬퍼로 webui 형식 항목 방어 처리
        - templates/longform.html: 4단계 → 3단계 (스크립트 확인 제거)
          페이지 로드 시 long_script.json 존재 확인 → "기존 스크립트 사용" 버튼 표시
        - templates/longform.html: 배경 선택 슬롯 3개 → 1개 (인트로·아웃트로만 수동 선택)
          이슈1·2 배경은 long3_pexels.py 자동 선택
        - webui_runner.py: long3 먼저 실행 후 사용자 선택(long_bg_main.mp4)으로 덮어쓰기
        - webui.py: /api/longform/pexels/{idx}에 page 파라미터 추가
                    /api/longform/script/exists 신규 (기존 스크립트 재사용용)

✅  세션 6 (Pexels 다양화) 완료 (2026-05-18) — per_page 10 / used_videos.json 30일 누적 / image_prompt 다양성 강화
        - step4_pexels.py / long3_pexels.py: per_page 1→10 / select_best_video() / load/save_used_video()
        - used_videos.json: 30일 누적 / repo 커밋으로 GitHub Actions 간 공유
        - step2_select.py: image_prompt 다양성 지시 강화 (장소·시간대·앵글·소재 명시)
        - long1_script.py: intro·outro image_prompt를 GPT 생성값으로 교체 (기존 r_list[0] 재사용 폐기)
        - yml 3종: permissions:contents:write + Commit used_videos.json 스텝 추가

✅  세션 6 완료 (2026-05-18) — 롱폼 영상 길이 조정 (10분 → 7.5분 목표)
        - long1_script.py: MIN_ISSUE_CHARS 1000 → 700
        - long1_script.py: PROMPT_ISSUE 분량·항목 축소
          · 「最低1000字以上」→「最低700字以上」
          · 필수 항목 8개 → 5개 (각 2~3문)
            제거: 今後の見通し（短期）/ 今後の見通し（中期）
            (캐릭터 시트 "단정 미래예측 금지"와 충돌, 분량 과다 원인)
            統合: 影響分析①②→単一項목 (影響分析)
          · 역산 근거: 실측 10:23 / TTS 약 300자/분
            현재 issue 1개당 ~1,150자 → 목표 725자
            총 3,200자 → 2,250자 → 7.5분

✅  세션 5 완료 (2026-05-18) — 30일 중복 기사 방지 + 한국어 요약 지시 추가
        - step2_select.py: RECENT_USED_URL_DAYS = 30 상수 추가
        - step2_select.py: load_recent_used_urls(days) 신규 함수
          · output/ 하위 YYYY-MM-DD 폴더를 스캔, days일 이내 폴더만 대상
          · 각 폴더의 *_gpt_result.json에서 article_url 수집 → set 반환
          · output 폴더 없거나 파일 없으면 빈 set (예외 없음)
        - step2_select.py: fetch_articles() 호출부 get_used_urls() → load_recent_used_urls(RECENT_USED_URL_DAYS) 교체
          · filtered/fallback 양쪽 모두 30일 제외 자동 적용 (all_articles 공유 구조 활용)
          · 기존 당일 중복 방지 → 30일 이력 방지로 확장
        - step2_select.py: USER_PROMPT 【その他】에 korean_summary 작성 지시 추가
          · 한국어 요약 비어있는 버그 원인: 캐릭터 시트 일본어화로 GPT가 한국어 출력 생략
          · "필ず韓国語（한국어）で1文" 명시로 해결

✅  세션 4 완료 (2026-05-18) — 영상 설명란 자동 삽입 + 캐릭터 인격 블록 추가
        - step9_youtube.py / long6_youtube.py: INFO_BLOCK 상수 추가
          · 내용: 【参考ソース】NHK / Yahoo Japan + 【このチャンネルについて】 면책 문구
          · 쇼츠(step9): INFO_BLOCK → hashtags → CHANNEL_FOOTER 순 (hashtags 위에 삽입)
          · 롱폼(long6): hashtags → 【本日の内容】 → INFO_BLOCK → CHANNEL_FOOTER 순
            (CHANNEL_FOOTER에 채널소개·구독호소 포함이므로 앞에 배치, 중복 방지)
        - step2_select.py / long1_script.py: SYSTEM_PROMPT에 신규 인격 고정 블록 삽입
          · 삽입 위치: JSON 출력 지시 뒤, 기존 【モチエンキャラクターシート】 앞
          · 【モチエンの人格】: 一人称「モチエン」/ 중성적 어조 / 「あなた」호칭 /
            수치 해설 습관 / 생활 번역 역할 / 정치 중립 / 마무리 고정 멘트
          · 【モチエンが繰り返し使うフレーズ】: 4개 고정 표현
          · 【モチエンが絶対に言わないこと】: 투자 추천·정치인 평가·간섭·직접 손익 표현 금지

✅  세션 3 완료 (2026-05-18) — 캐릭터 시트 강화
        - step2_select.py / long1_script.py: SYSTEM_PROMPT에 【モチエンキャラクターシート】 삽입
          · 인격·말투: 신뢰감 중심 뉴스캐스터 / 40~60대 / "あなた" 호칭
          · 배경: 일본 경제 20년 모찌모찌 해설 캐릭터
          · 감정 표현 규칙 6개:
            강한 감정표현 금지 / 「!」 최대 1회 / 「!!」 연속 금지 /
            중립 어미 우선 / 단정 미래예측 금지 / 과잉 동의 어미 최대 1회
          · 금지 어휘 13개:
            【지시 7개】 やばい / オワコン / 爆益 / 神回 / 草 / ガチで / マジで
            【재량 추가 6개】 ぶっちゃけ / めっちゃ / やっぱ / リアルに / ヤバすぎ / すごすぎ
        - long1_script.py: 기존 【モチエンキャラクター設定】 3행 → 풀 캐릭터 시트로 교체
          (4회 GPT 호출 전체에 일관 적용 / 【文章スタイル】 블록은 유지)

✅  세션 2 완료 (2026-05-17) — 발행 빈도 축소
        - 쇼츠 3슬롯 → 2슬롯 (07:00 + 18:00 JST, 12:00 제거)
          · 슬롯명 "09" / "18" 유지 (내부 식별자)
          · SELECTION_TARGET=2, SLOT_NAMES=["09","18"] 상수화
        - 롱폼 5섹션 → 4섹션 (intro / issue1 / issue2 / outro)
          · 약 7.5분 / issue 1,100자×2
          · PROMPT_ISSUE 필수 항목 6→8개, "最低1000字以上"
          · call_issue_retry 임계값 700→1000
        - 슬롯 1개만 성공한 날 롱폼 스킵 (run_all.py)
        - long3_pexels.py 배경 영상 4→3개
        - 변경 파일: step2_select.py, step9_youtube.py, run_all.py,
                    long1_script.py, long2_tts.py, long3_pexels.py,
                    long4_ffmpeg.py, long6_youtube.py

✅  세션 1 완료 (2026-05-17) — 투자 주제 전면 차단
        - step2_select.py:
          · BLOCKED_KEYWORDS 16개 상수 추가 (종목·추천 8 / 가상화폐 5 / 자산운용상품 5 / 부동산투자 5, 일부 중복)
          · BlockedArticleError 예외 클래스 신규
          · contains_blocked_keyword() 헬퍼 추가
          · fetch_articles() 차단 필터 (filtered·fallback 공통)
          · SYSTEM_PROMPT 「絶対に扱わないテーマ」 블록 삽입
          · call_chatgpt() __BLOCKED__ 감지 → BlockedArticleError raise
          · single_main() / batch_main().call_safe() 별도 캐치 처리
        - 거시 변수 단독 키워드(金利·為替·円安·円高) 차단어 미포함 (정책 뉴스 정상 통과용)

✅  웹 UI 개선 (2026-05-20)
        - step2_select.py: fetch_articles(limit=MAX_ARTICLES) 파라미터 추가
          · 기존 텔레그램/배치 호출 기본값 5 유지 / 웹 UI는 WEBUI_MAX_ARTICLES=10으로 호출
        - webui_runner.py:
          · WEBUI_MAX_ARTICLES = 10 상수 추가 → 웹 UI 기사 선택 최대 10개
          · _run_sync(): subprocess.run() → Popen 직접 관리로 전환
            KeyboardInterrupt 발생 시 child 프로세스 terminate/kill 후 returncode=1 반환
            → SSE 화면에 "재시도하세요" 에러 메시지 정상 표시 (기존: 비정상 스트림 종료)
        - webui_pexels.py: PEXELS_QUERY_SUFFIX = " no people b-roll" 상수 추가
          · 모든 Pexels 검색에 자동 append → 인물 클로즈업 영상 비중 감소
          · fallback 쿼리("japanese economy")에도 동일 적용
        - templates/select_article.html: "🔄 다시 불러오기" → location.reload() 제거
          · fetchArticles() 직접 호출로 변경 → 페이지 초기화 없이 바로 재수집

🔜  세션 7 — 워드프레스 자동 연재 (long7_wordpress.py)
⬜  세션 8 — E: AI 공시 + 정체성 명시
⬜  세션 9 — F: 댓글 반자동 응답 봇
⬜  세션 10 — B: 캐스터 3명 구도
⬜  세션 11 — C: 시리즈물 구조 (기획 단계)

🔜  32. 워드프레스 REST API 블로그 자동 발행
🔜  33. emotion 자동 매핑 복원 (블로그 자동발행 이후)
🔜  34. 롱폼 추가 개선 (챕터 밀도·섹션 구성 최적화)

실행 순서 (전체 — 권장):
  python run_all.py        ← 쇼츠 3편 + 롱폼 통합 실행 (run_all.bat 더블클릭도 가능)

실행 순서 (쇼츠 단독):
  python run_pipeline.py   ← 1편 실행. 3회 실행 후 롱폼 자동 트리거
  또는 단계별:
    python step2_select.py → step4_pexels.py → step5_tts.py
    → step6_ffmpeg.py → step7_whisper_subtitle.py → step9_youtube.py

실행 순서 (롱폼 단독):
  python run_longform.py   ← 통합 실행
  또는 단계별:
    python long1_script.py → long2_tts.py → long3_pexels.py
    → long4_ffmpeg.py → long5_whisper.py → long6_youtube.py


================================================================
## 18. 레슨런 (누적)
================================================================
- Pexels API Authorization 헤더: Bearer 없이 키만 입력
- OpenAI API 키는 platform.openai.com에서 발급 (ChatGPT Plus 구독과 완전히 별개)
- ElevenLabs 무료 플랜 API 키: 연결 저장은 되지만 런타임 실패 → 유료 크레딧 필요
- GitHub Raw URL CDN 캐시 이슈 → 파일 교체 후 브라우저에서 직접 확인 필요
- Python 3.12는 Windows 바이너리 설치 파일 미제공 → 3.13 이상 사용
- FFmpeg PATH 등록: C:\ffmpeg\bin 을 시스템 환경변수 Path에 추가
- NHK 사이트 Next.js 전환 → 정적 크롤링 불가 → RSS summary 사용
- .env 파일은 .gitignore 등록 필수 / API 키 노출 시 즉시 삭제 후 재발급
- Claude Code PowerShell 자동 승인: settings.json에 PowerShell(*) 추가
- Whisper API는 별도 키 불필요 / OPENAI_API_KEY 공용 사용
- YouTube OAuth 인증: 데스크톱 앱 유형으로 생성 / token.json 자동 갱신
- 텔레그램 봇 토큰 공개 노출 시 즉시 /revoke로 재발급
- GitHub Actions Secrets에 API 키 저장 → 코드에는 키 없음
- 저작권: RSS summary 수집 + ChatGPT 재작성 구조 → 원문 미사용으로 문제없음
- Google OAuth 앱 테스트→프로덕션 전환: Google Cloud Console → 대상 → 앱 게시 (무료)
  → 프로덕션 전환 후 refresh_token 무기한 유효 / GitHub Actions 장기 운용 가능
- GitHub Secrets는 repo별로 별도 등록 필요 (mochien-assets repo ≠ mochien repo)
- google-auth-oauthlib / python-dotenv requirements.txt에 명시 필요
  (로컬 venv에 설치돼 있어도 누락 시 GitHub Actions 실패)
- GitHub Actions 폰트: apt-get install -y fonts-noto-cjk 사용
  Linux 경로: /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
  step6/step7의 get_font()에 해당 경로를 Windows 경로보다 앞에 추가
- GitHub Actions Public repo: 실행 횟수 무제한 무료
- YouTube private 예약 영상은 commentThreads.insert API 차단
  → 승인 즉시 public 업로드로 전환하여 해결
- token.json 재발급 필요 시점: 새 API 스코프 추가 때만 (코드 수정과 무관)
- 쇼츠 조회수 수익 RPM: $0.01~$0.06 / 쇼츠는 구독자 모집 채널, 롱폼이 실질 수익 채널
- YouTube 고정댓글 pin: API 미지원 → YouTube Studio 수동 고정
  → 구독자 5,000명 이후부터 관리 시작해도 충분
- 텔레그램 승인 버튼 중복 탭 시 파이프라인 중복 실행 → 한 번만 탭할 것
- 롱폼 심층 분석은 gpt-4.1-mini 한계 → gpt-4.1 모델 사용 권장
- GitHub Actions cron: 무료 플랜 1~4시간 지연 / UTC 기준 (JST -9h) / 활동 없으면 트리거 건너뜀
  → 실사용 불가 판단 → workflow_dispatch 수동 트리거로 전환 / keepalive로 활성 유지
- 오후 시간대 업로드는 조회수 낮음 (일본 직장인 시청 패턴 고려)
  → 07:00/18:00 JST 예약 발행
- gpt_result.json 날짜/슬롯별 저장 → 롱폼 파이프라인에서 당일 2개 파일 읽어 활용
- .gitignore 작성 시 *.png / *.gif 와일드카드 금지
  mochien_*.png, mochien_talk.gif 캐릭터 에셋이 함께 무시됨 → 파일명 개별 지정
- Telegram getUpdates: flush_updates() 세션 시작 시 필수 (stale 콜백 재처리 방지)
- Ken Burns는 Pexels 모션 영상에 적용 시 어색함 → 비네팅+컬러그레이딩으로 대체
- FFmpeg colorbalance: rs/rm/rh (레드), bs/bm/bh (블루) / 범위: -1~1
- FFmpeg vignette: angle 파라미터 (0~PI/2) / 0.8이 자연스러운 수준
- step2 타임아웃과 취소 구분: CALLBACK_TIMEOUT (무응답→자동 진행) vs CALLBACK_CANCEL (❌ 버튼)
- ElevenLabs 잔액: GET /v1/user → subscription.character_limit - character_count = 잔여 캐릭터
- GITHUB_TOKEN은 별도 Secret 등록 불필요 — GitHub Actions가 모든 워크플로우에 자동 제공
- GitHub Artifacts: 같은 repo의 다른 워크플로우 간 파일 전달에 활용 가능
  actions/upload-artifact@v4로 업로드 / dawidd6/action-download-artifact@v6로 크로스 워크플로우 다운로드
- Artifact 누적 방식: 업로드 전에 기존 artifact를 먼저 다운로드해 병합해야 누적됨
  (overwrite:true만 하면 마지막 슬롯 파일만 남음)
- dawidd6/action-download-artifact: if_no_artifact_found: ignore 설정 시 첫 실행 오류 방지
- 롱폼 파이프라인: 4섹션 구조 (intro + issue1~2 + outro) / 각 섹션 TTS → 클립 → concat
- 롱폼 ASS 자막: \an2 (하단 중앙) / PlayResX:1920 PlayResY:1080 / 72px / 6단어/줄
- 롱폼 ChatGPT: gpt-4.1 사용 (심층 분석 품질 확보) / 쇼츠는 gpt-4.1-mini
- 쇼츠 슬롯 배정: 시간 기준(05~10시→09 등) 폐기 → 당일 output 폴더 파일 순서 기준(09→18)
  → 몇 시에 실행해도 그날 1번째=09, 2번째=18 / 하루 2개 완성 시 롱폼 가능
- telegram_trigger.py: PC 켜져 있을 때만 동작 / 핸드폰 트리거는 GitHub 앱 사용
- GH_PAT: GitHub PAT (workflow 스코프) → .env에 추가 / workflow_dispatch API 호출에 필요
- YouTube 예약 발행 API: privacyStatus를 "private"으로 설정 + publishAt(RFC 3339) 필드 추가
  즉시 public과 달리 댓글 API는 사용 가능 (단, 댓글은 YouTube Studio 수동으로 전환)
- Whisper 고유명사 교정: [SEP] 토큰으로 세그먼트 배치 처리 → GPT 1회 호출로 전체 교정
  세그먼트 수 불일치 시 원본 그대로 사용 (안전장치)
- ChatGPT 스크립트 후리가나 방식: 한자 제거 대신 誤読 한자에 괄호 병기
  ElevenLabs TTS가 괄호 내용을 읽을 수 있으므로 Whisper 교정으로 보완
- RSS 키워드 필터: 제목+본문 모두 체크 / 필터 후 0개면 전체 기사 fallback (종료 없음)
- 중복 기사 방지: article_url을 gpt_result.json에 저장 → 당일 슬롯 파일에서 읽어 제외
  당일 첫 실행은 슬롯 파일 없으므로 자동으로 중복 체크 없이 진행
- hook_korean: ChatGPT가 hook 일본어를 한국어로 번역해 출력 / REQUIRED_KEYS 제외
  (없거나 비어있어도 오류 없이 hook만 표시 — 선택적 필드)
- long4_ffmpeg.py SD 해상도 오류: scale=-2:H 후 crop W:H → 영상 너비 < W면 오류
  수정: scale=W:H:force_original_aspect_ratio=increase → crop W:H (항상 충분한 크기 확보)
- ElevenLabs TTS 후리가나 읽기 오류: 世界経済(せかいけいざい) → "(せかいけいざい)" 부분도 읽음
  step5_tts.py / long2_tts.py 모두 전송 전 re.sub(r"[（(][^）)]*[）)]", "", text)로 제거 / 全角・半角 모두 처리
- long1_script.py 심층 분석: 쇼츠 스크립트를 그대로 이어붙이면 단순 요약 반복 문제
  title+korean_summary만 입력 → GPT가 3개 토픽을 독립 분석하며 공통 트렌드 연결하게 유도
- dawidd6/action-download-artifact@v6: path: output/ 지정해도 내부적으로 output/gpt-results/ 서브폴더를 만들 수 있음
  → 다운로드 직후 output/gpt-results/ 존재 시 output/으로 복사하는 보정 스텝 필수
  → 이 버그로 2번째 실행이 항상 slot "09"를 재배정 → 발행 시각이 내일 07:00로 잘못 등록됨
- step9 발행 시각 로직: 목표 시각 초과 시 오늘 더 늦은 슬롯 시각 탐색 → 모두 지나면 익일 동일 시각
  낮 실행: 슬롯13(12시) 지남 → 슬롯18(18시) 남음 → 오늘 18:00 예약
  밤 11시 실행: 슬롯09/13/18 모두 지남 → 각각 익일 07:00/12:00/18:00 예약 (기존과 동일)
- GitHub Actions 쇼츠 워크플로우는 쇼츠 1개만 처리. 롱폼은 별도로 mochien_longform.yml 수동 트리거 필요
  → run_pipeline.py의 자동 롱폼 실행 로직은 로컬 전용 (GitHub Actions에서는 동작 안 함)
- 텔레그램 완료 알림: step9(숏폼) 개별 발송 + long6(롱폼) 개별 발송 — 총 4번
  숏폼은 업로드 즉시, 롱폼은 long6 완료 시 전송
- sys.exit(0)은 "성공" → run_pipeline.py가 다음 스텝 계속 진행
  sys.exit(1)은 "실패" → 파이프라인 즉시 중단. 기사 소진·취소 시 반드시 sys.exit(1) 사용
- 로컬 밤 11pm 실행 시 → 슬롯 목표 시각 모두 초과 → 익일 동일 시각으로 자동 예약
  → python run_pipeline.py 3회 실행으로 내일 07:00/12:00/18:00 JST 영상 3개 등록 가능
- YouTube captions.insert: commentThreads와 달리 private/예약 상태 영상에서도 정상 작동
  subtitle.srt를 영상 업로드 직후 바로 전송해도 무방
- SRT 생성: Whisper verbose_json 세그먼트를 재활용 → 추가 API 호출 없이 ASS와 동시 생성
- pykakasi: 한자→히라가나 변환 라이브러리 / item["hira"] 필드로 재조합
  ElevenLabs TTS 한자 오독 방지용 / 히라가나·알파벳·기호는 그대로 반환 / 자막·JSON에는 미적용
- Whisper 자막 교정 SEP_TOKEN 방식 한계: GPT가 SEP_TOKEN을 병합하여 세그먼트 수 불일치 빈발
  → 세그먼트 1개씩 개별 GPT 호출 방식으로 전환 / 횟수 40~60회지만 gpt-4.1-mini 기준 ~$0.015
- GPT JSON 배열 필드: SYSTEM_PROMPT에 형식 미명시 시 문자열로 반환
  hashtags 등 배열 필드는 반드시 "JSON配列で出力すること" 형태로 명시
  문자열로 저장된 경우 " ".join(string)이 글자 하나씩 조인되는 버그 발생
- BOJ RSS (www.boj.or.jp/rss/*.xml): 전 경로 404 — BOJ RSS 서비스 폐지된 것으로 확인
- NHK cat5 비즈니스 RSS: 정상 (82건) / Yahoo Japan 비즈니스 RSS: 정상 (8건)
- RSS 다소스 병합: URL 기준 seen_urls set으로 중복 제거 필수 (당일 사용 URL + 소스 간 중복)
- Whisper 세그먼트 분리 오인식: 긴 고유명사(コーマン事務総長)가 세그먼트 경계에서 잘리면
  KNOWN_ASR_ERRORS 전체 문자열 매칭 실패 → 전반부/후반부 부분 패턴을 각각 별도 등록 필요
- Whisper initial_prompt: gpt_result.json의 title+hook을 전달하면 고유명사 인식률 향상
  동일 스크립트에서 公満事 오인식이 사라지는 효과 확인 / gpt_result.json 없으면 자동 스킵
- feedparser published_parsed는 UTC struct_time → calendar.timegm()으로 UTC epoch 변환 후 time.time()과 비교
  datetime.utcnow()는 Python 3.12+에서 deprecated → time.time() + calendar.timegm() 조합 권장
- glossary.json 운영 규칙:
  · 고유명사·특수 오인식 패턴 위주로 등록 (코드 수정 없이 파일만 편집)
  · 키는 3글자 이상의 특수 패턴으로 — 경제뉴스에서 정상 쓰임 있는 단어(営業·公私 등) 등록 금지
  · 일반 명사 오인식은 KNOWN_ASR_ERRORS에 "correct in script" 안전장치와 함께 등록하는 게 올바른 위치
  · glossary는 맥락 무관 무조건 치환 → 짧은 키일수록 오발동 위험 증가
- GPT 자막 교정 확장 오류: correct_proper_nouns()의 * 3 배수는 너무 허용적
  8자 세그먼트가 20자 문장으로 확장되는 오교정 발생 → * 2로 변경 + 프롬프트에 길이 제약 명시
- Whisper セグメント 분리 패턴: イラン情勢 → 앞 세그먼트 끝에 "イ" 흡수 → 후반부가 "乱行政"으로 오인식
  부분 패턴 ("乱行政" → "ラン情勢")으로 대응 / 흡수된 "イ"는 교정 불가 (허용 범위)
- 元外務省 → 岸外務省 오인식: 발음 유사로 Whisper 오변환 / ("岸外務省" → "外務省")으로 대응
- YouTube 챕터 인식 조건: description에 "MM:SS 라벨" 형식 3개 이상 / 첫 챕터는 반드시 00:00
  → long2_tts.py가 long_chapters.json 생성 / long6_youtube.py가 description 상단에 삽입
- long_chapters.json: long2_tts.py → long6_youtube.py 단방향 파일 전달 / 없으면 챕터 없이 스킵
- ffprobe_duration(): ffprobe -show_entries format=duration -of csv=p=0 / 결과가 초(float)로 반환
- run_all.py 슬롯 초기화: 실행 시작 시 오늘 슬롯 파일 삭제 → 재실행 시 항상 09부터 clean start
  오늘 영상 이미 있어도 run_all.py 실행 시 초기화 후 새로 3편 생성 (의도적 설계)
- raw_summary_jp: RSS entry.summary 원문을 gpt_result.json에 저장
  long1_script.py 프롬프트에 포함 → GPT가 원문 근거로 수치·고유명사 정확히 반영하며 심층 분석
- google-generativeai는 일몰 예정 → google-genai (신규 SDK) 사용. `genai.Client(api_key=...)` 패턴
  response_mime_type="application/json" + response_schema로 구조화 JSON 출력 강제
- step7/long5의 KNOWN_ASR_ERRORS는 `if __name__ == "__main__":` 가드 + 모듈 레벨 상수
  → importlib.import_module()로 동적 import 가능 — 부수 작용 없이 상수만 읽을 수 있음
- mochien.yml / mochien_full.yml은 개별 step을 직접 호출 (run_pipeline.py 미사용)
  → step10 자동 실행 원하면 명시적 스텝 추가 필요 / continue-on-error: true 필수
- mochien_longform.yml은 run_longform.py 호출이므로 step10 env 주입만으로 충분
  (run_longform.py 내부에서 step10_gemini_review.py --mode longform 자동 호출)
- pronunciation.json: TTS 전송 텍스트에만 적용 / 자막·JSON 원본 미적용 (glossary.json과 동일 원칙)
- Claude 2차 검증: meaning_ko(한국어 뜻) + reason(한국어) 필드로 텔레그램 알림 한국어화
  SYSTEM_PROMPT를 한국어로 작성해야 meaning_ko/reason이 한국어로 출력됨
- step10 notify_telegram() 알림 조건: applied + rejected 합산 1건 이상이면 발송
  applied만 체크하면 rejected(보류) 건수가 있어도 알림이 생략되는 버그 발생
- step10 max_tokens=1024는 Gemini 오류 후보가 많을 때 Claude JSON 응답이 잘려 JSONDecodeError 발생
  → 2048→4096 상향해도 롱폼 87건 후보에서 여전히 잘림
  → 근본 해결: call_claude()를 발음/자막 각각 별도 호출로 분리 (max_tokens=4096×2)
  → 외부 시그니처·반환값 구조 유지하면 하위 로직 변경 없이 내부만 교체 가능
- long1_script.py PROMPT_ISSUE의 title 필드에 언어 지시 없으면 GPT가 한국어 제목 출력
  → 롱폼 챕터(YouTube description)에 한국어 그대로 노출되는 버그
  → "titleは必ず日本語のみで書くこと（韓国語・英語禁止）" + 포맷에 "日本語のみ・14字以内" 명시로 해결
- ElevenLabs Pronunciation Dictionary: 일본어는 phoneme 태그 미지원 → alias 태그만 사용 가능
  upload_pronunciation_dict.py로 한 번만 업로드 → ID를 .env에 저장 → TTS 호출마다 자동 참조
  pronunciation.json 자체 치환(apply_pronunciation)과 병용 → 이중 안전망
- pronunciation.json 키 순서 중요: 복합 키(三菱UFJ銀行)를 단순 키(三菱)보다 앞에 배치해야
  단순 키가 먼저 치환되어 복합 키가 매칭 실패하는 사고 방지 (json.load는 삽입 순서 보존)
- pykakasi는 CLAUDE.md 12차 세션에 추가 기록됐으나 실제 코드에 반영되지 않은 상태
  step5_tts.py / long2_tts.py 어디에도 kanji_to_hiragana() 없음 / requirements.txt에도 미등록
  ElevenLabs 자체 한자 처리 + pronunciation.json 치환 조합으로 충분히 대응 가능
- step2_select.py --batch 모드: 선택 완료 시 09/13/18_gpt_result.json 동시 생성
  run_all.py가 shutil.copy()로 각 슬롯 파일을 gpt_result.json에 덮어쓰는 Approach B 채택
  step4~9는 gpt_result.json만 읽으므로 수정 없이 그대로 재사용 가능
- batch_poll(): allowed_updates: ["callback_query", "message"] 로 혼합 폴링
  callback_data 형식: "sel_{idx}" (선택 토글) / "pas_{idx}" (다음 기사 — 현재 미사용)
  "취소" 텍스트 메시지도 감지해 중단 가능 (대소문자 무관)
- run_all.py 슬롯 실패 처리: 해당 슬롯 건너뛰고 나머지 계속 진행 (파이프라인 전체 중단 금지)
  실패 시 TG 알림: "⚠️ 슬롯 {slot} 영상 생성 실패\n실패 단계: {script}\n나머지 슬롯은 계속 진행합니다."
  전체 슬롯 실패 시에만 롱폼 건너뛰고 sys.exit(1)
- mochien_full.yml을 python run_all.py 단일 호출로 간소화하면
  GitHub Actions UI에서 개별 스텝 가시성은 줄지만 유지보수성 크게 향상
  로직 변경 시 yml 수정 불필요 — run_all.py만 수정하면 됨
- long1_script.py 4회 순차 호출 비용: gpt-4.1 기준 롱폼 1회 ~$0.08~0.16
  하루 1회 × 30일 = 월 ~$2~5 추가 → OpenAI 합계 ~$10~14/월
- 글자수 직접 지시(「約800字」)는 GPT가 잘 따르지 않음
  항목 수 필수 구조(8항목 × 각 3~4문)로 대체 → 항목 모두 채우면 1,000~1,200자 자동 확보
- long1 섹션별 summary 컨텍스트: content와 summary를 같은 응답에서 받아
  다음 호출에 summary만 전달 → 전체 스크립트를 메시지로 쌓지 않아 토큰 효율 유지
- long1 image_prompt: issue는 각 슬롯 gpt_result["image_prompt"] 재사용
  intro·outro는 r_list[0]["image_prompt"] 재사용 — 추가 GPT 호출 없음
- long6 고정댓글: hook 150자 트리밍 방식은 텔레그램에서 잘려 보임
  → 당일 슬롯 short_title 3개를 「」로 묶은 단문 고정 문구로 교체 (항상 전문 표시)
  load_slot_short_titles()로 output/{오늘날짜}/ 에서 읽음 / 누락 슬롯은 스킵
- run_all.py 임시파일 정리: 시작 시 정리는 GitHub Actions 병렬 실행 시 진행 중 파일 삭제 위험
  → 종료 시(finally)에만 정리 / 시작 시에는 슬롯 파일 초기화(clear_today_slots)만 수행
- Python try-finally: sys.exit()는 내부적으로 SystemExit 예외 → finally 블록 반드시 실행됨
  어떤 종료 경로(정상/오류/sys.exit)에서도 정리 코드를 보장하려면 try-finally 사용
- glob.glob("*.mp4"): 현재 디렉토리 루트만 스캔 → output/ 하위 파일은 비해당
  mp4·mp3 패턴은 png·gif·py·json과 겹치지 않아 별도 exclusion 불필요
- FFmpeg -t 입력 옵션 (input side)은 filter_complex + -shortest 조합에서 작동 안 함 (FFmpeg 8.1 확인)
  → 출력 옵션으로 사용해야 정확히 작동: cmd[-1:-1] = ["-t", str(t)] 로 출력 파일 직전 삽입
- GIF -ignore_loop 0: GIF 자체 loop count 존중 (loop=0이면 무한루프 / loop=N이면 N회)
  -ignore_loop 1 (기본값): GIF loop count 무시하고 항상 무한루프
  bow.gif(1회 루프용): -ignore_loop 0 / talk.gif(무한루프): -ignore_loop 0 + GIF loop=0(무한) 동일 결과
- overlay filter shortest=1: overlay 출력을 두 입력 중 짧은 쪽에서 종료
  bow.gif 오버레이에서 제거 시 eof_action=repeat(기본값)으로 마지막 프레임 고정 → -t로 클립 길이 제어
- silencedetect vs silenceremove: 정확한 trailing silence 위치는 silencedetect로 감지 후 -t 출력 옵션으로 자르는 것이 안전
  silenceremove stop_periods=-1은 예상보다 많은 구간을 제거하는 케이스 확인 (발화 2s 잘림)
- Telegram 409 Conflict: 같은 봇 토큰으로 getUpdates를 동시에 폴링하는 프로세스가 2개 이상이면 발생
  run_all.py 백그라운드 실행을 여러 번 시도하면 고아 프로세스가 남아 충돌 → 실행 전 python* 프로세스 전체 종료 필수
  Stop-Process -Name python* -Force 로 일괄 종료
- GPT korean_summary 빈값: SYSTEM_PROMPT 캐릭터 시트가 일본어 중심으로 강화되면 GPT가 한국어 출력(korean_summary)을 생략
  USER_PROMPT 【その他】에 "必ず韓国語（한국어）で1文" 명시로 해결 — 필드 설명이 없으면 GPT는 출력하지 않을 수 있음
- load_recent_used_urls(): output/ 하위 YYYY-MM-DD 폴더를 date() 비교로 스캔 (timedelta+datetime 비교 시 시각까지 비교되어 당일 경계 오차 발생 → .date() 비교 권장)
- long4_ffmpeg.py도 -stream_loop -1 + -shortest 조합 → step6_ffmpeg.py와 동일 FFmpeg 무한루프 위험
  ffprobe로 섹션 오디오 길이 측정 후 -t 출력 옵션 사용 / overlay shortest=1도 제거
- step10 Gemini 0건 감지 시 텔레그램 미발송 → 사용자가 step10 실행 여부를 알 수 없음
  0건이어도 "✅ 검수 완료 / 오류 없음" 텔레그램 발송으로 항상 실행 확인 가능하게 변경
- used_videos.json 혼합 형식: webui_pexels.py(ts/unix)와 step4/long3(used_at/date)가 같은 파일 공유
  → _entry_is_recent()로 양쪽 형식 처리. webui도 used_at으로 통일하면 충돌 없음
- 롱폼 배경 선택 UI: long3_pexels.py가 long_bg_main.mp4도 항상 다운로드
  → 사용자 선택을 long3 실행 후 덮어쓰는 순서로 구현해야 사용자 선택이 최종 반영됨
- webui _run_sync() KeyboardInterrupt: uvicorn Windows 시그널 핸들러가 executor 스레드에 KBI 주입
  subprocess.run() 사용 시 communicate() 내부 stdout_thread.join()에서 예외 발생 → SSE 비정상 종료
  → Popen 직접 관리로 전환, except KeyboardInterrupt 에서 terminate/kill 후 returncode=1 반환
  → _run_with_ticks가 returncode!=0 으로 에러 이벤트 yield → 웹 UI에 정상 에러 표시
- Pexels 인물 제외: API 자체 네거티브 필터 미지원 → 쿼리에 " no people b-roll" 접미사 추가
  완전 제거는 불가하나 인물 클로즈업 비중이 눈에 띄게 줄어듦 / 나머지는 페이지 넘기기로 대응
- fetch_articles limit 파라미터: 웹 UI는 더 많은 후보(10개)가 필요하나 텔레그램 모드는 5개 유지
  → 기본값 유지 함수 시그니처 변경으로 하위 호환 + 호출부에서 limit 지정하는 패턴 적용
- Windows asyncio + uvicorn: asyncio.create_subprocess_exec는 ProactorEventLoop 필요
  uvicorn이 SelectorEventLoop으로 실행 시 NotImplementedError 발생
  → subprocess.run (블로킹) + loop.run_in_executor(None, fn)으로 대체
  asyncio.wait({future}, timeout=tick_sec)으로 틱 진행률 구현 가능


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
