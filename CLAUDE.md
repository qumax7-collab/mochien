# 모찌엔 YouTube Shorts 자동화 프로젝트 — CLAUDE.md
최종 업데이트: 2026년 5월 14일 (14차 세션)

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
→ FFmpeg 영상 합성 (1080x1920) + 쿨 블루 컬러그레이딩 + 비네팅
→ Whisper API 일본어 자막 합성

[ step9 — 업로드 + 알림 ]
→ YouTube Data API v3 예약 발행 (privacyStatus: private + publishAt RFC 3339)
→ SRT 자막 captions.insert로 YouTube 업로드 (자동번역 활성화용)
→ 텔레그램 완료 알림 개별 전송 (제목 / 예약시간 / 고정댓글 hook 포함)
→ output/{날짜}/{슬롯}_gpt_result.json을 GitHub Artifact로 업로드

[ 롱폼 파이프라인 (mochien_longform.yml) — JST 21:00 ]
→ GitHub Artifact에서 당일 gpt_result 3개 파일 복원
→ long1_script.py: gpt-4.1로 롱폼 스크립트 생성 (long_script.json)
→ long2_tts.py: 5섹션 TTS → long_voice.mp3
→ long3_pexels.py: 4개 배경 영상 다운로드
→ long4_ffmpeg.py: 섹션별 클립 생성 → concat → long_output_no_sub.mp4
→ long5_whisper.py: Whisper 자막 합성 → long_output.mp4
→ long6_youtube.py: YouTube 업로드 + 텔레그램 롱폼 완료 알림 개별 전송


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

JSON 9필드 상세:
  title          - 영상 제목 (30자 이내 / 시청자 손득·놀라움 직결)
  hook           - 첫 후킹 문장 (일본어 / 생활·손득·驚き 직결)
  hook_korean    - hook 일본어의 자연스러운 한국어 번역 (선택적 필드)
  script         - 본문 스크립트 (마무리 3줄 필수)
  hashtags       - 해시태그 배열 (일본어·영어만 / #Shorts 필수)
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
쇼츠 예약   : 슬롯 09 → 07:00 JST / 슬롯 13 → 12:00 JST / 슬롯 18 → 18:00 JST
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
                제목 / 예약 시간 / 고정댓글 (intro 앞 150자 + korean_summary) 포함
역할 3      : API 잔액 경고
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
  ├── glossary.json                       ← Whisper 오인식 패턴 사전 (코드 밖에서 관리)
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

🔜  24. 워드프레스 REST API 블로그 자동 발행
🔜  25. emotion 자동 매핑 복원 (블로그 자동발행 이후)
🔜  26. 롱폼 분량 확대 (현재 ~5분 → 목표 7분, long1_script.py 문자수 목표 상향)

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
  → 07:00/12:00/18:00 JST 예약 발행
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
- 쇼츠 슬롯 배정: 시간 기준(05~10시→09 등) 폐기 → 당일 output 폴더 파일 순서 기준(09→13→18)
  → 몇 시에 실행해도 그날 1번째=09, 2번째=13, 3번째=18 / 하루 3개 완성 시 롱폼 가능
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
