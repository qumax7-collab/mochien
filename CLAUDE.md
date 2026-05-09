# 모찌엔 YouTube Shorts 자동화 프로젝트 — CLAUDE.md
최종 업데이트: 2026년 5월 9일 (GitHub Actions 배포 완료)

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
RSS (NHK cat6) 최대 5개 수집
→ 기사별 ChatGPT API (gpt-4.1-mini) → 한국어 요약 생성
→ 텔레그램 기사 선택 (✅ 진행 / 🔄 다음 / ❌ 취소)
→ article.json + gpt_result.json 저장

[ step4~step7 — 영상 생성 ]
→ Pexels API 배경 영상 취득
→ ElevenLabs TTS (Eleven Flash v2.5) → 일본어 음성 생성
→ FFmpeg 영상 합성 (1080x1920)
→ Whisper API 일본어 자막 합성

[ step9 — 업로드 + 알림 ]
→ YouTube Data API v3 자동 업로드 (예약)
→ 텔레그램 완료 알림 (Mochien_Notify_bot)


================================================================
## 3. 기술 스택
================================================================
언어            : Python 3.14
영상 합성        : FFmpeg (Creatomate 대체)
자동화 실행      : GitHub Actions (Make.com 대체) - 공개 repo 무료 무제한
스케줄          : 08:00 / 12:00 / 18:00 JST (하루 3회)
로컬 개발 환경   : Windows / C:\mochien 프로젝트 폴더
중간 저장        : Google Drive (검수 후 YouTube 업로드)

Make.com 대체 이유   : Python으로 모든 API 직접 호출 가능. $9/월 절감
Creatomate 대체 이유 : FFmpeg으로 동일 기능 구현 가능. $45/월 절감
ZapCap 대체 이유     : Whisper API로 동일 기능 구현 가능. ~$8/월 추가 절감
전환 후 월 비용      : ~$6 (기존 ~$67 대비 $61 절감)


================================================================
## 4. Python 라이브러리 목록
================================================================
feedparser                - RSS 수집
requests                  - HTTP 크롤링, Pexels API 호출
openai                    - ChatGPT API 호출 + Whisper API 자막 생성
ffmpeg-python             - FFmpeg 영상 합성
google-auth               - Google Drive 업로드 인증
google-auth-oauthlib      - YouTube OAuth2 인증
google-api-python-client  - YouTube Data API v3 / Google Drive API
Pillow                    - 이미지 처리 (캐릭터 PNG 오버레이)
python-dotenv             - .env 파일 로드


================================================================
## 5. ChatGPT 프롬프트 (현재 버전)
================================================================
시스템 프롬프트:
  あなたはJSONのみを出力するAIです。
  出力は必ず { で始まり } で終わる純粋なJSONのみ。
  ```json などのマークダウン記号は絶対に使用禁止。
  以下のキー以外は絶対に追加しないこと:
    title, hook, script, hashtags, korean_summary, emotion, image_prompt, short_title

유저 프롬프트:
  【モチエンキャラクター設定】
  - 落ち着いていて信頼感がある話し方（40〜60代向け）
  - 難しい経済用語はやさしい言葉に言い換える
  - 視聴者を「あなた」と呼ぶ
  - スクリプト末尾は必ず「以上、モチエンがお伝えしました！」で締める

  short_title : 6〜10字の核心キーワード
                例:「日越首脳会談」「原油急騰の影響」
  image_prompt: Pexels 검색용 영어 키워드
                예: "japanese economy stock market"

  뉴스 제목: {title}
  뉴스 본문: {article_body}

JSON 8필드 상세:
  title          - 영상 제목 (30자 이내, 숫자 포함)
  hook           - 첫 후킹 문장
  script         - 본문 스크립트 (마무리: 「以上、モチエンがお伝えしました！」)
  hashtags       - 해시태그 배열
  korean_summary - 한국어 1줄 요약
  emotion        - 영어 감정값 (아래 목록 중 1개)
  image_prompt   - Pexels 검색 영어 키워드
  short_title    - 6~10자 핵심 키워드

emotion 허용값:
  smile / happy / surprised / shocked / worried /
  angry / anxious / sad / neutral / shy / embarrassed / sleepy


================================================================
## 6. FFmpeg 영상 합성 레이아웃 스펙
================================================================
해상도      : 1080x1920 (YouTube Shorts 세로형)
폰트        : Noto Sans JP
배경        : Pexels 스톡 영상 (전체 화면)
프레임레이트 : 30fps

레이어 구성 (아래에서 위 순서):
  1. background  - Pexels 영상 / 전체 화면 1080x1920
  2. top_bar     - 상단 레터박스 / 네이비(#1B2A4A) / 상단 고정 / 높이 약 10%
  3. red_line    - 가로선 #E50000 / 두께 4~6px / top_bar 하단 경계
  4. short_title - top_bar 위 텍스트 / 흰색 / Noto Sans JP Bold / 중앙 정렬
  5. face        - 모찌엔 캐릭터 PNG / 우하단 고정 / 흰 외곽선 10px 포함된 PNG
  6. mouth_gif   - mochien_talk.gif 무한루프 / face 레이어 입 위치에 오버레이
  7. subtitle    - 화면 중앙 (Y:50%) / 흰 텍스트 + 검정 스트로크 3~5px
                   ※ Whisper API 처리 후 자막 오버레이
  8. audio       - ElevenLabs 생성 mp3

하단 레터박스: 없음 (v13에서 제거 확정)
자막 최종 처리: Whisper API (음성 → SRT 변환 → FFmpeg burn-in)


================================================================
## 7. Pexels API 설정
================================================================
URL         : https://api.pexels.com/videos/search
Method      : GET
Header      : Authorization: {PEXELS_API_KEY}  ※ Bearer 없이 키만
Query params: query={image_prompt 키워드}, per_page=1
응답 경로   : response["videos"][0]["video_files"][0]["link"]
무료 플랜   : 월 200 요청 / 하루 3편x30일=90 요청으로 여유 있음
상업적 사용 : 가능 (크레딧 표기 권장)


================================================================
## 8. ElevenLabs TTS 설정
================================================================
모델        : Eleven Flash v2.5
보이스      : 차분한 일본어 여성 뉴스 앵커 보이스
              (ElevenLabs Voice Library → Japanese 필터 → calm/professional/mature)
API 키명    : Mozzi
출력 형식   : mp3_44100_128
연동 방식   : Python requests로 직접 API 호출
입력 텍스트 : ChatGPT JSON의 script 필드


================================================================
## 9. Whisper API 자막 설정
================================================================
용도        : ElevenLabs 생성 음성(mp3)을 텍스트로 변환 → SRT 자막 생성 → FFmpeg burn-in
선택 이유   : ZapCap 대비 월 ~$8 절감 / OpenAI API 키 하나로 통합 관리 가능
모델        : whisper-1
언어        : ja (Japanese)
출력 형식   : srt (타임스탬프 포함 자막 파일)
가격        : $0.006/분 → 하루 3편 x 1분 x 30일 = 90분 → 월 ~$0.54
파이프라인  :
  ElevenLabs mp3 생성
  → Whisper API에 mp3 전송 → SRT 수신
  → FFmpeg로 SRT 자막 burn-in
  → Google Drive 저장 → YouTube 업로드


================================================================
## 10. 모찌엔 캐릭터 에셋
================================================================
GitHub      : https://github.com/qumax7-collab/mochien-assets
Raw URL     : https://raw.githubusercontent.com/qumax7-collab/mochien-assets/main/mochien_{emotion}.png
외곽선      : 흰색 10px / 알파채널 유지 / 포토샵 액션 배치 처리
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
## 11. YouTube 업로드 설정
================================================================
API         : YouTube Data API v3 videos.insert
설명란 구성 : korean_summary + hashtags + 채널 고정 문구
업로드 시간 : 08:00 / 12:00 / 18:00 JST (하루 3회)
카테고리    : 뉴스 (News & Politics)
언어        : 일본어


================================================================
## 12. 텔레그램 알림 설정
================================================================
봇 이름     : Mochien_Notify_bot
역할 1      : 기사 선택 (step2_select.py)
              - 기사별 일본어 제목 + 한국어 요약 전송
              - 인라인 버튼: ✅ 이 기사로 진행 / 🔄 다음 기사 / ❌ 취소
              - 선택 후 "⏳ 영상 생성 시작..." 상태 표시
역할 2      : 업로드 완료 알림 (step9_youtube.py)
              - 영상 제목, 예약 시간, 한국어 요약, YouTube URL 전송
연동 방식   : Python requests → Telegram Bot API (sendMessage, editMessageText, answerCallbackQuery)
주의        : 세션 시작 전 flush_updates() 필수 (오래된 콜백 재처리 방지)


================================================================
## 13. Google Drive 설정
================================================================
용도        : YouTube 업로드 전 영상 검수용 중간 저장소
연동 방식   : google-api-python-client
검수 흐름   : Whisper 자막 합성 완료 영상 → Google Drive 저장 → 확인 후 YouTube 업로드


================================================================
## 14. GitHub Actions 스케줄 설정
================================================================
용도        : 스케줄 자동 실행 (내 PC 꺼져 있어도 동작)
트리거      : cron
              - "0 23 * * *"  (KST 08:00 = UTC 23:00 전날)
              - "0 3 * * *"   (KST 12:00 = UTC 03:00)
              - "0 9 * * *"   (KST 18:00 = UTC 09:00)
실행 환경   : ubuntu-latest
비용        : 공개 repo 무료 무제한

워크플로우 파일 : .github/workflows/mochien.yml
repo URL        : https://github.com/qumax7-collab/mochien.git

GitHub Secrets 등록 필요:
  OPENAI_API_KEY
  ELEVENLABS_API_KEY
  ELEVENLABS_VOICE_ID
  PEXELS_API_KEY
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  YOUTUBE_CREDENTIALS   ← token.json 전체 내용
  CLIENT_SECRETS        ← client_secrets.json 전체 내용


================================================================
## 15. 월 예상 비용
================================================================
서비스          플랜                    월 비용
--------------  ----------------------  -----------
Make            미사용 (Python 대체)    $0
Creatomate      미사용 (FFmpeg 대체)    $0
ZapCap          미사용 (Whisper 대체)   $0
OpenAI API      gpt-4.1-mini + Whisper  ~$4.54
ElevenLabs      종량제                  ~$0.30
Pexels API      무료 플랜               $0
GitHub Actions  공개 repo 무료          $0
YouTube API     무료                    $0
Telegram Bot    무료                    $0
--------------  ----------------------  -----------
합계                                    ~$6/월
기존 비용                               ~$67/월
절감액                                  ~$61/월 (한화 약 8만 5천원)


================================================================
## 16. AI 구독 정리
================================================================
Claude        유지   - 프로젝트 설계, 디버깅, 프롬프트 최적화 핵심
ChatGPT Plus  선택   - API만으로 대체 가능
Gemini        해지   - 현재 파이프라인 활용 구간 없음


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
✅  8.  Google Drive 업로드 (미구현, 현재 생략)
✅  9.  YouTube 자동 업로드 + 텔레그램 완료 알림 (step9_youtube.py)
✅  9b. 텔레그램 기사 선택 + ChatGPT 통합 (step2_select.py)
✅  10. 전체 파이프라인 통합 테스트 (step2~9 순차 실행 완료)
✅  11. GitHub Actions 스케줄 설정 및 배포 완료

실행 순서 (현재):
  python step2_select.py   ← 텔레그램에서 기사 선택 (ChatGPT 포함)
  python step4_pexels.py
  python step5_tts.py
  python step6_ffmpeg.py
  python step7_whisper_subtitle.py
  python step9_youtube.py  ← 자동 업로드 후 완료 알림


================================================================
## 18. 레슨런 (누적)
================================================================
- Pexels API Authorization 헤더: Bearer 없이 키만 입력
- OpenAI API 키는 platform.openai.com에서 발급 (ChatGPT Plus 구독과 완전히 별개)
- Make OpenAI Connection에 저장된 키는 암호화되어 직접 확인 불가
- Creatomate Stroke/Shadow는 알파채널 인식 불가 → PNG에 직접 외곽선 추가 필요
- ElevenLabs 무료 플랜 API 키: 연결 저장은 되지만 런타임 실패 → 유료 크레딧 필요
- Google Drive 공유 URL은 Creatomate와 호환 안 됨 (현재는 미사용)
- GitHub Raw URL CDN 캐시 이슈 → 파일 교체 후 브라우저에서 직접 확인 필요
- Pexels API 무료 월 200 요청 한도: 하루 3편x30일=90 요청으로 여유
- Creatomate 트랜스크립션: 일본어 띄어쓰기 미인식 → 단어별 자막 불가
- ZapCap: 월 $9 종량제 → Whisper API로 대체 ($0.54/월). OpenAI 키로 통합 가능
- Whisper API: 입력은 mp3, 출력 형식 srt 지정 시 타임스탬프 포함 자막 파일 반환
- Python 3.12는 Windows 바이너리 설치 파일 미제공 → 3.13 이상 사용
- FFmpeg PATH 등록: C:\ffmpeg\bin 을 시스템 환경변수 Path에 추가
- GitHub Actions는 공개 repo에서 무료 무제한 (비디오 렌더링도 CPU로 충분)
- Telegram Bot API: sendMessage 엔드포인트, chat_id + text 파라미터로 간단 연동
- Telegram getUpdates offset 미공유 버그: wait_for_callback을 매번 offset=None으로 시작하면
  이전 세션의 stale 콜백이 재처리됨 → 세션 시작 시 flush_updates()로 큐 비우기 필수
- step2_select 설계: 기사 선택 전 ChatGPT를 먼저 호출해 한국어 요약을 Telegram에 표시.
  거절된 기사는 ChatGPT 비용만 소모 (TTS·FFmpeg·Whisper 등 고비용 단계는 선택 후 1회만 실행)
- GitHub Actions 폰트: apt-get install fonts-noto-cjk 사용.
  Linux 설치 경로는 /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
  step6/step7의 get_font()에 해당 경로를 Windows 경로보다 앞에 추가해야 함
- .gitignore 작성 시 *.png / *.gif 와일드카드 금지.
  mochien_*.png, mochien_talk.gif 캐릭터 에셋이 함께 무시됨 → 파일명 개별 지정
- requirements.txt에 python-dotenv, google-auth-oauthlib 누락 주의.
  로컬 venv에 설치돼 있어도 requirements.txt에 없으면 GitHub Actions에서 실패함
- token.json에 client_id / client_secret이 포함되어 있어 민감 정보.
  .gitignore에 반드시 포함. GitHub Actions에서는 YOUTUBE_CREDENTIALS Secret으로 복원
- client_secrets.json도 민감 정보. CLIENT_SECRETS Secret으로 관리하고 .gitignore에 추가


================================================================
## 19. 2단계 예고 (파이프라인 안정화 이후 검토)
================================================================
- emotion 자동 매핑 복원 (ChatGPT emotion 필드 → 캐릭터 PNG URL 자동 선택)
- 씬별 배경 영상 전환 (4씬 구조 재설계)
- 워드프레스 REST API 블로그 자동 발행
- 퀀트 트레이딩 Python 파이프라인 구축
- Project Flint (Unity 2D) C# 개발 시작
- Claude Code 전환 완료 후 Make 의존도 완전 제거

================================================================
