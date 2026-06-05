# 모찌엔 레슨런 (누적)

기술 결정사항·금지선 → CLAUDE.md
프로젝트 전략·세션 기록 → mochien_master.md
변경 이력 → CHANGELOG.md

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
  ※ 실제 코드에 미반영 상태 — ElevenLabs 자체 처리 + pronunciation.json으로 충분히 대응
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
- step2_select.py --batch 모드: 선택 완료 시 09/13/18_gpt_result.json 동시 생성
  run_all.py가 shutil.copy()로 각 슬롯 파일을 gpt_result.json에 덮어쓰는 Approach B 채택
  step4~9는 gpt_result.json만 읽으므로 수정 없이 그대로 재사용 가능
- batch_poll(): allowed_updates: ["callback_query", "message"] 로 혼합 폴링
  callback_data 형식: "sel_{idx}" (선택 토글) / "pas_{idx}" (다음 기사 — 현재 미사용)
  "취소" 텍스트 메시지도 감지해 중단 가능 (대소문자 무관)
- run_all.py 슬롯 실패 처리: 해당 슬롯 건너뛰고 나머지 계속 진행 (파이프라인 전체 중단 금지)
  실패 시 TG 알림: "⚠️ 슬롯 {slot} 영상 생성 실패\n실패 단계: {script}\n나머지 슬롯은 계속 진행합니다."
  전체 슬롯 실패 시에만 sys.exit(1)
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
- WordPress REST API Application Password 인증:
  WP 관리자 → 사용자 → 프로필 → Application Passwords에서 발급
  Authorization: Basic base64(username:app_password) 헤더로 인증
  POST /wp/v2/posts 로 글 작성 / /wp/v2/media로 미디어 업로드
- WordPress 예약 발행: status: "future" + date: RFC3339 형식 (WP는 UTC로 저장, 표시는 블로그 시간대 기준)
  JST 21:00 → datetime.isoformat() 그대로 전송 (WP가 시간대 오프셋 포함된 RFC3339 인식)
- WordPress slug 충돌: GET /wp/v2/posts?slug=X 로 사전 확인 → 결과 비어있으면 사용 가능
  재사용 시 -2/-3... suffix 자동 추가 / 에버그린 URL은 날짜 prefix 없이 순수 키워드형
- long7_wordpress.py 실패 처리: sys.exit(0) — 파이프라인 중단 없음
  실패 원인(WP_URL 미설정·API 오류·파일 없음)을 tg_error()로 텔레그램 알림 후 조용히 종료
- topic_bank.json 운영 원칙: 15개는 시작 재고 / 계속 추가 예정
  새 토픽 추가: _readme 필드 안내대로 id/title_ja/title_ko/principle/keywords_ja/chart_type/fred_code 추가
  topic_history.json 쿨다운 21일: 동일 토픽 21일 이내 재발행 방지 / 자동 최신 우선순위 배제
- long1_script.py 2단계 생성 운영 방식:
  KO 단계(--stage ko): 한국어 초안 생성 → 웹 UI에서 검토 → 수정 텍스트로 재생성 가능
  JA 단계(--stage ja): KO 초안 기반 일본어 변환 + 역직역(back-translation) 확인용 출력
  인수 없이 실행: KO+JA 자동 연속 실행 (GitHub Actions 비대화형 환경용)
- 에버그린 컨셉 핵심: 뉴스는 입구(entry point) / 거시 원리가 실제 내용
  "실질 임금이 하락했다"(뉴스) → "실질 임금이란 무엇이고 생활에 어떤 영향을 주는가"(원리) 구조
  시청자가 6개월 후에 봐도 핵심 내용이 유효한 영상이 목표
- [출처: 기사1] 태그 제거 원칙: KO 단계 운영자 검수용 / JA 변환 후에도 GPT가 태그를 남길 수 있음
  TTS(long2_tts.py)와 블로그 본문(long7_wordpress.py) 양쪽 모두 re.sub으로 코드 레벨 제거 필수
  long_script_ko.json·long_script.json 원본에는 남겨둠 (검수·디버깅용)
- long_script_ko.json 백업: revise 재생성 전 shutil.copy2()로 .bak.json 자동 저장
  1세대만 유지 / revise 2회 연속 시 bak은 직전 버전만 보존 (그 이전은 덮어써짐)
- ConoHa WAF PUT 차단: ConoHa Wing의 WAF가 HTTP PUT 메서드를 403 Forbidden으로 차단
  WP REST API 글 업데이트는 requests.put() 대신 requests.post(url_with_id, ...)로 호출해야 함
  POST /wp/v2/posts/{id} (URL에 ID 포함)은 WP가 내부적으로 업데이트로 처리 — PUT과 동일 동작
  WAF 설정은 보안상 끄지 않음 / POST 방식으로 우회하는 것이 정답
- WP REST API 예약 글 조회: 기본 GET /wp/v2/posts는 published 상태만 반환
  예약(future/scheduled) 글 포함 조회 시 params={"status": "any"} 필수
  find_post_by_slug()에 status=any 없으면 예약 글을 찾지 못해 항상 None 반환
- split_japanese() 구현: 일본어 句点 분리 시 「」 괄호 내부 。를 분리점으로 오인식하는 문제
  → 문자 단위 순회 + 괄호 깊이 카운터로 depth==0 일 때만 。를 분리점으로 처리
  OPEN_BRACKETS = set('「『（(') / CLOSE_BRACKETS = set('」』）)') 로 구분
- upload_media() 반환값 설계: featured 썸네일은 media_id만 필요 / 본문 삽입 이미지는 source_url 필요
  → (media_id, source_url) 튜플 반환으로 양쪽 용도 커버
  호출부: media_id, _ = upload_media(...) / _, src_url = upload_media(...)
- WP 본문 단락 분리: GPT 스크립트는 줄바꿈 없이 1개 장문 → split("\n") 로는 단락 1개만 생성
  → 句点(。) 기준 문장 분리 후 SENTENCES_PER_PARA 단위로 <p> 그룹화하는 방식이 정답
  마지막 그룹이 1문장이면 직전 그룹에 흡수 (고아 단락 방지)
- NHK cat2는 공식 분류명 "文化·エンタメ"이지만 실제 기사는 生活·社会政策 중심
  (실질임금·광열비·사회보험 등 39% 생활밀착) — 카테고리명이 아닌 실제 내용 기준으로 추가
- RSS 보강 시 cat6 주석 오류 주의: cat6=国際 (cat5가 経済) / 동작은 정상이나 주석 혼동 방지
- 쇼츠 아웃트로 signoff 설계: GPT가 매번 다른 마무리를 생성하면 일관성 없고 깔때기 문구 삽입 불가
  → GPT 프롬프트에서 마무리 지시 제거 → 코드(_strip_signoff + 고정 상수)가 항상 부착하는 구조
  _SIGNOFF_RE로 GPT 생성 변형도 제거 (레거시 텍스트 포함)
- get_active() vs get_upcoming() 구분:
  · get_active(): publish_at_jst <= now → 이미 공개된 롱폼. 아웃트로 깔때기에 사용.
  · get_upcoming(): publish_at_jst > now → 아직 미발행 예정 롱폼. 기사 선택 UI 정렬에 사용.
  · 토요일 제작 시 이번 주 일/목 롱폼은 미래 → get_active가 옛 토픽을 가리킴
    → 기사 선택 UI는 get_upcoming을 써야 "예정된" 롱폼 주제로 기사를 고를 수 있음
- article_score.py 소프트 정렬: is_active_match=True 먼저 → life_score 내림
  하드 필터(차단) 없음 — 점수 낮아도 선택 가능. UI는 정보 제공 목적.
  선택 자동화(is_active_match 기사 자동 채택 등)는 구현하지 않음 (운영자 판단 보존)
- _strip_signoff() 패턴 설계 원칙: 「以上、モチエンが...」패턴으로 작성하면 GPT가 「でした。」「でございます。」변형 출력 시 제거 실패
  → 「以上、モチエン」(が 제외)로 폭넓게 매칭해야 안전. GPT는 같은 의미를 다양한 조사로 표현할 수 있음
- GPT 프롬프트 내 사인오프 이중 지시 충돌: USER_PROMPT 필드 설명에 "마지막 줄은 OO로 끝낼 것" + 별도 지시에 "사인오프 포함하지 말 것"이 공존하면
  GPT가 랜덤하게 한쪽만 따름 → 코드에서 항상 부착/제거하는 방식으로 일원화하고 프롬프트에는 지시 1개만 남길 것
- gpt-image-1-mini response_format 파라미터: 이 모델은 response_format 미지원 (400 Bad Request 발생)
  → 파라미터 완전 제거 / API 기본 반환이 URL 형식이므로 resp.data[0].url로 접근하면 됨
- PIL draw.rounded_rectangle(): Pillow 8.2+ 지원 / radius 파라미터로 둥근 모서리
  fill 인자에 RGBA 튜플(0,0,0,210)로 반투명 박스 가능 — alpha_composite 이후 레이어 순서 주의
- expression/direction 필드 설계: emotion(단일 감정 문자열)을 두 필드로 분리
  expression = 캐릭터 표정(9종 자동 / 3종 수동 전용) / direction = 색상 방향성(up/down/none)
  expression으로 PNG 파일명 결정 / direction으로 화살표 색상 결정 (up=빨강/down=파랑/none=없음)
- thumb_headline 필드: hook은 음성 스크립트용 / thumb_headline은 썸네일 전용 14자 이내
  기사에 수치가 있으면 "수치형"(例:170円の壁) / 없으면 "워드형"(例:円安、止まらない)
  fallback: gpt.get("thumb_headline") or gpt.get("short_title","")[:14]
- expression_auto / expression_final 분리 로깅: AI가 자동 추천한 값과 운영자가 최종 선택한 값 모두 기록
  expression_auto는 최초 1회만 기록 (if "expression_auto" not in gpt 가드로 중복 덮어쓰기 방지)
- expression 3단계 사고 프롬프트: 단순 라벨 나열 대신 ステップ1(감정 톤 언어화) → ステップ2(매핑) →
  ステップ3(hook/thumb_headline 프레임 일치 확인)으로 GPT가 순서대로 판단하게 유도
  양면 기사 처리 규칙 필수: "補助金あり+全体トーン安定 → smile/happy 選択" 명시하지 않으면
  보조금 있어도 가격 언급만으로 worried를 선택하는 오분류 발생
- 썸네일 safe zone 설계: YouTube 4:5 미리보기 기준 SAFE_BAND_TOP=285 / SAFE_BAND_BOT=1635
  상단 바 하단=365 / 캐릭터 상단=1205 / 채널 하단바 상단=1575 와 겹치지 않아야 함
  헤드라인 박스 최대 범위: top_min=391(>365 ✓) / bot_max=1199(<1205 ✓)
- hook 필드는 생성되지만 TTS에 미포함 상태였음 (step5가 script만 읽었음)
  → step5_tts.py를 hook+script 합산으로 변경 / hook이 도입부 후킹으로 음성 맨 앞에 추가됨
  hook 없는 구버전 gpt_result는 하위 호환 (script만 전송)
- thumb_headline 숫자 우선 규칙: 기사에 수치(%, 금액, 배수)가 있으면 반드시 수치 포함
  GPT가 "最高" 같은 수치 누락형으로 빠지는 사례 방지 → step2/step3 프롬프트에 명시
  나쁜 예: 「最高」(수치 누락)·「費用の負担」(수치 누락)·본문 토막 / 좋은 예: 「家賃+12%」「170円の壁」
- direction "none" 판정 기준: "数字なし"가 아니라 "방향 판별 불가·고착·복합"
  수치가 있어도 방향이 애매하면 none이 맞음 (예: 170円 가격 고착→none)
  상승·하락이 명확하면 up/down 적극 선택 (예: 가賃+12%急上昇→up)
- hook은 항상 2문장 구성: "사실文。+ 의문·공감文？" 패턴
  (예: "家賃が過去最高を記録しました。なぜ急に上がったのでしょうか？")
  hook+script 합산 TTS에서 script는 hook 반복 없이 상세 내용부터 시작하도록 프롬프트 지시 추가
- 펀넬 구조:
  · 생산 분리: run_pipeline.py / run_all.py의 "쇼츠 N편 → 롱폼 자동 트리거" 제거. 롱폼은 run_longform.py 단독 실행.
  · 토픽 브리지: step3_chatgpt.py stage_ja()에서 article.json → article_score.match_topic() 호출 → matched_topic_id를 gpt_result.json에 저장
  · 펀넬 타겟: longform_link.get_active_for_topic(topic_id) 신규 함수 — 동일 topic_id 발행 롱폼 우선, 없으면 최신 발행 롱폼 폴백
    None이면 active_longform_url = "" → SIGNOFF_DEFAULT_JA + 설명란 링크 미삽입으로 자연 폴백
  · 링크 자동화: step9_youtube.py build_description()에 gpt 인자 추가. active_longform_url 있으면 설명란 첫 줄에 「▼ くわしい経済解説はこちら→ {url}」 prepend
  · 설명란 링크 문구: 「今週」금지(에버그린 정체성·사실 일치). 「くわしい経済解説はこちら→」 고정
  · 텔레그램 알림: 「▼今週の解説：」→「▼くわしい解説：」/ lf_url 있을 때만 핀 선택 안내 줄 추가
  · 검증 지표: YouTube 분석 롱폼 트래픽 소스에 'Shorts' 노출 여부 = 펀넬 작동 증거
- 토픽 매칭 정확도:
  · 기존 키워드 교집합 카운트 → GPT(gpt-4.1-mini) 인과·방향 판정으로 교체
  · 키워드 사전필터 없음. 토픽뱅크 전체(15개)를 GPT에 넘겨 정확도 우선
  · enrich_articles: GPT 1회 배치 호출로 N건 판정 (UI 응답속도 최적화)
  · match_topic (단건): _gpt_judge_topic() 1회 호출 — step3_chatgpt 등 단건 경로용
  · 확신 없으면 None → 폴백(최신 롱폼 → 일반 구독 CTA). 오매칭보다 무링크가 안전.
  · topic_bank.json에 title_ko 추가 (운영자 한국어로 매칭 검증 가능)
  · match_reason 필드: 반환 dict에 포함. 웹 UI 배지 아래 · 텔레그램 topic_line에 표시
  · 비용: 단건 ~$0.0004, 배치 10건 ~$0.001 — 무시 가능 수준
- e-Stat time 코드 위치가 통계마다 다름. 가계조사는 s[6:8]에 월 코드(YYYY00MMNN), 매월근로통계 류는 s[4:6]에 월 코드(YYYYMM0000). 둘 다 fallback 처리하는 로직 필수. _normalize_time() 참조.
- FRED API 504 진단법: api.stlouisfed.org가 504인데 fred.stlouisfed.org 사이트가 200이면 API 인프라 일시 장애.
  curl로 두 호스트 분리 진단 가능. 공식 status page 없음. 코드·키 문제가 아니므로 즉시 재시도는 무의미.
  모찌엔 방식: 504 발생 시 안내 메시지 출력 + sys.exit(1) → 운영자가 잠시 후 수동 재실행.
- FRED V1(api.stlouisfed.org/fred/)과 V2(api.stlouisfed.org/v2/)는 별도 용도로 공식 병존 유지.
  V1=단건 시리즈 조회 / V2=릴리스 단위 대량 조회. V1 단종 아님. data/fred_fetch.py는 V1 사용.
- BOJ 時系列統計検索サイト API: 2026-02-18 신규 출시. 등록·키 불필요. 高頻度アクセス 금지 명시(매뉴얼 Ⅰ.2).
  응답 구조: RESULTSET 최상위 키 (STATISTICAL_DATA 아님). SURVEY_DATES는 정수(int) 배열.
- e-Stat 통계마다 API DB 갱신 상태가 천차만별. 매월근로통계조사(00450071)는 파일은 정상 갱신 중이나
  API DB는 2016-03-31 정지. 운영자가 자주 쓸 통계는 --search로 UPDATED_DATE 사전 확인 필수.
  갱신 확인된 통계: 家計調査(2026-05), 労働力調査(2026-05), 消費者物価指数(2026-05).
- 실질임금 토픽은 e-Stat API로 최신 월별 데이터 취득 불가(매월근로통계 API DB 2016 정지).
  FRED+BOJ 합성으로 추정하는 방식은 신뢰도 문제로 채택 안 함.
  작업 2-4에서 家計調査 소비지출 기반 변형 또는 real-wage 토픽 보류 여부 결정 예정.
