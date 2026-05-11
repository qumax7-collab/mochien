# 모찌엔 YouTube Shorts 자동화 프로젝트 — CLAUDE.md
최종 업데이트: 2026년 5월 11일 (8차 세션)

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
→ gpt_result.json을 output/{날짜}/{시간}_gpt_result.json 에도 복사 (롱폼 연결용)

[ step4~step7 — 영상 생성 ]
→ Pexels API 배경 영상 취득
→ ElevenLabs TTS (Eleven Flash v2.5) → 일본어 음성 생성
→ FFmpeg 영상 합성 (1080x1920) + Ken Burns 효과
→ Whisper API 일본어 자막 합성

[ step9 — 업로드 + 알림 ]
→ 텔레그램 승인 버튼 (10분 무응답 시 자동 진행)
→ YouTube Data API v3 즉시 public 업로드
→ hook 일본어 자동 댓글 등록
→ 텔레그램 완료 알림 (Mochien_Notify_bot)
→ output/{날짜}/{슬롯}_gpt_result.json을 GitHub Artifact로 업로드

[ 롱폼 파이프라인 (mochien_longform.yml) — JST 21:00 ]
→ GitHub Artifact에서 당일 gpt_result 3개 파일 복원
→ long1_script.py: gpt-4.1로 롱폼 스크립트 생성 (long_script.json)
→ long2_tts.py: 5섹션 TTS → long_voice.mp3
→ long3_pexels.py: 4개 배경 영상 다운로드
→ long4_ffmpeg.py: 섹션별 클립 생성 → concat → long_output_no_sub.mp4
→ long5_whisper.py: Whisper 자막 합성 → long_output.mp4
→ long6_youtube.py: YouTube 업로드 + 댓글 + 텔레그램 "[롱폼] 완료" 알림


================================================================
## 3. 기술 스택
================================================================
언어            : Python 3.14
영상 합성        : FFmpeg (Creatomate 대체)
자동화 실행      : GitHub Actions (Make.com 대체) - 공개 repo 무료 무제한
스케줄          : 09:00 / 13:00 / 18:00 JST (하루 3회)
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


================================================================
## 5. ChatGPT 프롬프트 (현재 버전) ← 6차 세션 수정 완료
================================================================
시스템 프롬프트:
  あなたはJSONのみを出力するAIです。
  出力は必ず { で始まり } で終わる純粋なJSONのみ。
  ```json などのマークダウン記号は絶対に使用禁止。
  以下のキー以外は絶対に追加しないこと:
    title, hook, script, hashtags, korean_summary, emotion, image_prompt, short_title

유저 프롬프트:
  【モチエンキャラクター設定】
  - 冒頭の挨拶は禁止。最初の一文は必ずhookの内容から始めること。
  - hookは必ず日本語で生成すること。数字・疑問形・驚きの表現を含めること。
  - hashtagsには必ず#Shortsを含めること。
  - 落ち着いていて信頼感がある話し方（40〜60代向け）
  - 難しい経済用語はやさしい言葉に言い換える
  - 視聴者を「あなた」と呼ぶ
  - スクリプト末尾は必ず下記で締めること:
    「皆さんはどう思いますか？コメントで教えてください！
     以上、モチエンがお伝えしました！
     チャンネル登録お願いします！」

  short_title : 6〜10字の核心キーワード
  image_prompt: Pexels 검색용 영어 키워드 (예: "japanese economy stock market")

  뉴스 제목: {title}
  뉴스 본문: {article_body}

JSON 8필드 상세:
  title          - 영상 제목 (30자 이내, 숫자 포함)
  hook           - 첫 후킹 문장 (일본어 / 숫자·의문형·충격 표현 포함)
  script         - 본문 스크립트 (마무리 3줄 필수)
  hashtags       - 해시태그 배열 (#Shorts 필수 포함)
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
섹션 구성   : intro / issue1 / issue2 / issue3 / outro (5섹션 FFmpeg concat)
상단 바     : 높이 108px / 네이비 + 빨간 구분선 / 섹션별 라벨 표시
              intro·outro → short_title / issueN → "①②③ + 이슈 제목 14자"
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
무료 플랜   : 월 200 요청 / 하루 3편x30일=90 요청으로 여유 있음
상업적 사용 : 가능 (크레딧 표기 권장)


================================================================
## 8. ElevenLabs TTS 설정
================================================================
모델        : Eleven Flash v2.5
보이스      : Harune (일본어 여성 / 차분한 뉴스 앵커 스타일)
API 키명    : Mozzi
출력 형식   : mp3_44100_128
연동 방식   : Python requests로 직접 API 호출
입력 텍스트 : ChatGPT JSON의 script 필드


================================================================
## 9. Whisper API 자막 설정
================================================================
용도        : ElevenLabs 생성 음성(mp3)을 텍스트로 변환 → ASS 자막 생성 → FFmpeg burn-in
모델        : whisper-1
언어        : ja (Japanese)
출력 형식   : ASS (타임스탬프 포함 자막 파일)
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
## 11. YouTube 업로드 설정 ← 6차 세션 업데이트
================================================================
API         : YouTube Data API v3 videos.insert
채널명      : モチエンのひとこと経済ニュース
설명란 구성 : 일본어 채널 소개 + hashtags (한국어 제거)
업로드 방식 : 승인 즉시 public 공개 (예약 공개 제거)
              ※ private 예약 시 댓글 API 차단 → 즉시 공개로 전환
업로드 시간 : 09:00 / 13:00 / 18:00 JST
승인 방식   : 텔레그램 봇 승인 버튼 탭 후 즉시 업로드
              ※ 10분 무응답 시 자동 업로드 진행
자동 댓글   : 업로드 직후 hook 필드 (일본어) 자동 댓글 등록
              ※ 고정댓글: YouTube API 미지원 → YouTube Studio 수동 고정
              ※ 구독자 5,000명 이후부터 관리 시작해도 충분


================================================================
## 12. 텔레그램 알림 설정
================================================================
봇 이름     : Mochien_Notify_bot
역할 1      : 기사 선택 (step2_select.py)
              - 기사별 일본어 제목 + 한국어 요약 전송
              - 인라인 버튼: ✅ 이 기사로 진행 / 🔄 다음 기사 / ❌ 취소
              - 선택 후 "⏳ 영상 생성 시작..." 상태 표시
역할 2      : 업로드 완료 알림
              - 영상 제목, YouTube URL 전송
역할 4      : API 잔액 경고
              - OpenAI $3 이하 / ElevenLabs $2 이하 시 경고 전송
              - 경고만 보내고 파이프라인은 계속 실행
연동 방식   : Python requests → Telegram Bot API
주의        : 세션 시작 전 flush_updates() 필수 (오래된 콜백 재처리 방지)


================================================================
## 13. GitHub Actions / 보안 설정 ← 7차 세션 업데이트
================================================================
repo        : https://github.com/qumax7-collab/mochien (Public)
워크플로우  : .github/workflows/mochien.yml          (쇼츠 / 하루 3회)
              .github/workflows/mochien_longform.yml  (롱폼 / 하루 1회)
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
     → 같은 날 몇 시에 실행해도 09/13/18 순서로 채워짐
  3. step9 이후: output/ 전체를 gpt-results artifact로 업로드 (overwrite)
  → 하루 3회 실행 후 artifact에 09/13/18 파일 누적됨
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
  YOUTUBE_CREDENTIALS / CLIENT_SECRETS
  ※ GITHUB_TOKEN은 자동 제공 — 별도 등록 불필요


================================================================
## 14. 파일 구조
================================================================
C:\mochien\
  ├── CLAUDE.md
  ├── .env
  ├── .gitignore
  ├── requirements.txt
  ├── client_secrets.json
  ├── token.json
  ├── .github/
  │     └── workflows/
  │           ├── mochien.yml             ← 쇼츠 파이프라인 (하루 3회)
  │           ├── mochien_longform.yml    ← 롱폼 파이프라인 (하루 1회)
  │           └── keepalive.yml           ← repo 활성 유지 (주 1회)
  ├── venv\
  ├── [ 쇼츠 파이프라인 ]
  ├── telegram_trigger.py                 ← 텔레그램 수동 트리거 봇 (PC 로컬 실행용)
  ├── start_bot.bat                       ← telegram_trigger.py 실행 배치파일
  ├── run_pipeline.py                     ← 쇼츠 전체 실행 (step2→4→5→6→7→9)
  ├── step2_rss_crawler.py
  ├── step2_select.py                     ← RSS + ChatGPT + 텔레그램 선택
  ├── step3_chatgpt.py                    ← step2_select에 통합됨
  ├── step4_pexels.py
  ├── step5_tts.py
  ├── step6_ffmpeg.py
  ├── step7_whisper_subtitle.py
  ├── step9_youtube.py
  ├── [ 롱폼 파이프라인 ]
  ├── run_longform.py                     ← 롱폼 전체 실행 (long1→6)
  ├── long1_script.py                     ← gpt-4.1 롱폼 스크립트 생성
  ├── long2_tts.py                        ← 5섹션 TTS + concat
  ├── long3_pexels.py                     ← 4개 배경 영상 다운로드
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
OpenAI API      gpt-4.1-mini + Whisper  ~$4.18
ElevenLabs      종량제                  ~$0.30
Pexels API      무료 플랜               $0
GitHub Actions  공개 repo 무료          $0
YouTube API     무료                    $0
Telegram Bot    무료                    $0
Conoha Wing     정액제 (예정)           ~$5
--------------  ----------------------  -----------
현재 합계                               ~$4.48/월
롱폼+블로그 추가 후                     ~$10~12/월 (예상)


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

🔜  16. 롱폼 파이프라인 실제 실행 테스트 (GitHub Actions)
🔜  17. 워드프레스 REST API 블로그 자동 발행
🔜  18. emotion 자동 매핑 복원 (블로그 자동발행 이후)

실행 순서 (쇼츠):
  python run_pipeline.py   ← 통합 실행
  또는 단계별:
    python step2_select.py → step4_pexels.py → step5_tts.py
    → step6_ffmpeg.py → step7_whisper_subtitle.py → step9_youtube.py

실행 순서 (롱폼):
  python run_longform.py   ← 통합 실행
  또는 단계별:
    python long1_script.py → long2_tts.py → long3_pexels.py
    → long4_ffmpeg.py → long5_whisper.py → long6_youtube.py


================================================================
## 18. 레슨런 (누적)
================================================================
- Pexels API Authorization 헤더: Bearer 없이 키만 입력
- OpenAI API 키는 platform.openai.com에서 발급 (ChatGPT Plus 구독과 완전히 별개)
- Creatomate Stroke/Shadow는 알파채널 인식 불가 → PNG에 직접 외곽선 추가 필요
- ElevenLabs 무료 플랜 API 키: 연결 저장은 되지만 런타임 실패 → 유료 크레딧 필요
- GitHub Raw URL CDN 캐시 이슈 → 파일 교체 후 브라우저에서 직접 확인 필요
- Creatomate 트랜스크립션: 일본어 띄어쓰기 미인식 → ZapCap 대체
- Python 3.12는 Windows 바이너리 설치 파일 미제공 → 3.13 이상 사용
- FFmpeg PATH 등록: C:\ffmpeg\bin 을 시스템 환경변수 Path에 추가
- NHK 사이트 Next.js 전환 → 정적 크롤링 불가 → RSS summary 사용
- .env 파일은 .gitignore 등록 필수 / API 키 노출 시 즉시 삭제 후 재발급
- Claude Code PowerShell 자동 승인: settings.json에 PowerShell(*) 추가
- ZapCap API 불안정 + 처리 시간 5~10분 → Whisper API로 대체
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
- GitHub Actions cron: 무료 플랜에서 1~4시간 지연 발생 가능 (정상 동작)
  → repo 최근 활동 없으면 스케줄 트리거 자체가 건너뛰어짐
  → 더미 커밋 자동화로 repo 활성 유지 필요
  → 트리거 시간을 목표 시간보다 2시간 앞당겨서 지연 보정
- GitHub Actions cron은 무조건 UTC 기준 (JST/KST 직접 입력 불가)
  KST = UTC+9이므로 원하는 시간에서 9시간 빼서 입력
- 오후 시간대 업로드는 조회수 낮음 (일본 직장인 시청 패턴 고려)
  → 09시/13시/18시 JST 업로드 목표로 트리거 시간 앞당겨 운용
- gpt_result.json 날짜/시간별 저장 → 롱폼 파이프라인에서 당일 3개 파일 읽어 활용
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
- 롱폼 파이프라인: 5섹션 구조 (intro + issue1~3 + outro) / 각 섹션 TTS → 클립 → concat
- 롱폼 ASS 자막: \an2 (하단 중앙) / PlayResX:1920 PlayResY:1080 / 72px / 6단어/줄
- 롱폼 ChatGPT: gpt-4.1 사용 (심층 분석 품질 확보) / 쇼츠는 gpt-4.1-mini
- GitHub Actions cron 무료 플랜에서 실사용 불가 수준 지연 → workflow_dispatch 수동 트리거로 전환
- 쇼츠 슬롯 배정: 시간 기준(05~10시→09 등) 폐기 → 당일 output 폴더 파일 순서 기준(09→13→18)
  → 몇 시에 실행해도 그날 1번째=09, 2번째=13, 3번째=18 / 하루 3개 완성 시 롱폼 가능
- telegram_trigger.py: PC 켜져 있을 때만 동작 / 핸드폰 트리거는 GitHub 앱 사용
- GH_PAT: GitHub PAT (workflow 스코프) → .env에 추가 / workflow_dispatch API 호출에 필요


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
