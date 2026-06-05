# 모찌엔 변경 이력 (CHANGELOG)

현재 규칙·스펙은 CLAUDE.md를 참조하세요.
이 파일은 과거 세션 완료 기록입니다.

================================================================
## 완료 작업 이력
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

✅  세션 A 완료 (2026-05-22) — 롱폼 에버그린 전환 + 워드프레스 자동 발행
        - long1_script.py: 전면 재작성 (2단계 KO→JA 에버그린 방식)
          · 철학 전환: "오늘 뉴스 요약" → "뉴스=입구, 거시 원리=내용" (에버그린 컨셉)
          · 2단계 생성: --stage ko (한국어 초안 / 운영자 검토용) → --stage ja (일본어 변환)
          · Mode A/B 자동 판정: GPT가 2개 기사 공통 원리 판별 → A(통합) / B(단독 집중)
          · 할루시네이션 방지: 입력 데이터(raw_summary_jp + title + korean_summary) 외 사실 생성 금지
            출처 인용 필수 ([출처: 기사1] 형식)
          · 인물 페르소나: 교양 거시경제 해설가 / 뉴스를 입구 삼아 시대 흐름 해설
          · long_script_ko.json 신규 출력 (한국어 초안 검토용)
          · long_script_verify.json 신규 출력 (역직역 back-translation 확인용)
          · long_script.json에 _slug_keyword 필드 추가 (topic_id → WP slug)
        - topic_bank.json 신규 생성
          · 15개 거시 경제 토픽 (id / title_ja / principle / keywords_ja)
          · _readme 필드로 운영자용 토픽 추가 방법 안내 (Python 입문자 대상)
          · 토픽 ID 목록: real-wage / yen-rate / interest-rate / inflation-deflation /
            national-debt / trade-balance / aging-social-security / consumption-tax /
            gdp-growth / business-cycle / energy-dependency / central-bank /
            irregular-employment / declining-birthrate / cashless-society
        - topic_history.json 신규 생성 (런타임)
          · 최근 발행 토픽 이력 추적 / 21일 쿨다운 (같은 토픽 반복 방지)
          · 15개 골고루 소비되도록 최근 사용 토픽 후순위 배치
        - long7_wordpress.py 신규 생성
          · WordPress REST API + Application Password 인증
          · 썸네일: long_bg_main.mp4 첫 프레임 추출 → JPEG → /wp/v2/media 업로드
          · HTML 본문 자동 생성 (H2 섹션별 / YouTube embed 포함)
          · 예약 발행 21:00 JST (status: "future" / RFC3339)
          · WP slug: topic_id 순수 키워드형 (real-wage) / 재발행 시 -2/-3 suffix
          · get_unique_slug(): 기존 slug 충돌 시 자동 -N suffix 추가
          · 실패 시 tg_error() 알림 + sys.exit(0) (파이프라인 중단 없음)
          · 성공 시 텔레그램 블로그 URL 알림
        - long6_youtube.py: long_youtube_url.txt 저장 추가 (long7 연결용)
        - run_longform.py: PIPELINE에 long7_wordpress.py 추가
        - webui_runner.py:
          · LONG_SCRIPT_KO_FILE / LONG_SCRIPT_VERIFY_FILE 상수 추가
          · _run_sync_cmd() 신규 (generic cmd list runner / KBI-safe)
          · run_long1_ko(revise=None) / run_long1_ja() 신규
          · run_longform_stream() 에 Long7 SSE 스텝 추가
        - webui.py: 5개 신규 엔드포인트 추가
          · POST /api/longform/script/ko (KO 초안 생성)
          · POST /api/longform/script/ko/revise (KO 수정 재생성)
          · GET /api/longform/script/ko/read (KO 초안 조회)
          · POST /api/longform/script/ja (JA 변환)
          · GET /api/longform/script/verify/read (역직역 확인)
        - templates/longform.html: 4단계 위자드로 전면 재작성
          · 1단계: KO 초안 생성 + 수정 텍스트 입력 + "일본어로 변환" 버튼
          · 2단계: 일본어 확인 + 역직역 토글 표시
          · 3단계: 배경 영상 선택
          · 4단계: SSE 영상 생성 (Long7 블로그 발행 포함)
        - mochien_longform.yml / mochien_full.yml:
          · WP_URL / WP_USERNAME / WP_APP_PASSWORD Secret 주입 추가
          · workflow_dispatch 전용 유지 (cron 없음 — 주 2회 수동 운영 철학)
        - GitHub Secrets 신규 등록 필요: WP_URL / WP_USERNAME / WP_APP_PASSWORD
          로컬 .env에도 동일하게 등록 필요

✅  세션 A 후속 버그 수정 (2026-05-22)
        - long2_tts.py: get_section_script()에 출처 태그 제거 추가
          · re.sub으로 [출처: ...] (한국어) / [出典: ...] (일본어) 패턴 제거
          · TTS 전송 텍스트에서만 제거 / long_script.json 원본 미변경
          · 이유: JA 단계 GPT 지시만으로는 태그 완전 제거 보장 불가
        - long7_wordpress.py: build_html_body()에 동일 출처 태그 제거 추가
          · strip_citations() 헬퍼 신규 / to_paragraphs() 내부에서 자동 적용
          · 블로그 본문 전체(인트로·이슈1·이슈2·아웃트로) 적용
        - long1_script.py: KO 초안 덮어쓰기 전 자동 백업 추가
          · LONG_SCRIPT_KO_BAK_FILE = "long_script_ko.bak.json" 상수 추가
          · stage_ko() 저장 직전 기존 파일 있으면 shutil.copy2()로 bak 복사
          · --revise 재생성 시 이전 버전 자동 보존 (1세대)
          · import shutil 추가

✅  세션 B 완료 (2026-05-22) — 롱폼 대본 분량 정상화 + 블로그 서식 정비 + 기존 글 재발행
        - long1_script.py: issue2 retry 블록 추가 (edit ⑩)
          · call_issue_retry()를 issue2에도 적용 (issue1과 동일 구조)
          · ISSUE_RETRY_MIN_CHARS=450 기준 / 미달 시 1회 재시도
        - long2_tts.py: SECTION_LABEL_PAT 상수 추가 + get_section_script()에 적용
          · 섹션 레이블 ([issue1], intro: 등) TTS 텍스트 오출력 방어
          · 한국어·일본어·영어 레이블 패턴 일괄 제거 (re.IGNORECASE | re.MULTILINE)
        - long7_wordpress.py: 블로그 서식 5건 정비 (전면 재작성)
          ① 문단 분리: split_japanese()로 句点(。) 기준 분리 + SENTENCES_PER_PARA=3 그룹화
             괄호 깊이 추적으로 「」『』（） 내부 句点 오분리 방지
          ② 광고 슬롯: AD_SLOT_1/2/3 HTML 주석 마커 (섹션 첫 문단 후 자동 삽입)
          ③ 영상 멘트 제거: VIDEO_OUTRO_PAT로 「以上、モチエンが…」 제거 + 블로그 전용 마무리 삽입
             BLOG_OUTRO_TMPL: YouTube URL을 "動画" 텍스트에 하이퍼링크
          ④ 이슈 이미지: extract_frame()으로 long_bg_issue1/2.mp4 첫 프레임 → JPEG
             upload_media() 반환값을 (media_id, source_url) 튜플로 변경
             이슈 H2 직후 <img> 태그로 본문 내 이미지 삽입
          ⑤ SEO: get_or_create_tag()로 hashtags → WP 태그 자동 생성·연결
             Yoast SEO 메타: _yoast_wpseo_metadesc + _yoast_wpseo_focuskw meta 필드
             excerpt: 후리가나 제거 후 intro 첫 120자
        - long7_wordpress.py: --update 모드 추가 (argparse)
          · find_post_by_slug(slug): GET /wp/v2/posts?slug=X&status=any 로 예약 글 포함 검색
          · update_post(post_id, ...): POST /wp/v2/posts/{id} 로 내용·태그·메타만 업데이트
            slug·status·date·featured_media는 보존 (예약 상태 유지)
          · slug 없으면 tg_error 후 sys.exit(0) (신규 발행 폴백 없음)
        - 신규 런타임 파일: long_thumb_issue1.jpg / long_thumb_issue2.jpg

✅  세션 C (2026-05-23) — RSS 보강 + 쇼츠 프롬프트 3차 개편
        - step2_select.py: RSS_URLS 3개 → 5개 확장
          · NHK cat2.xml (生活·社会政策) 신규 추가
          · Yahoo Japan domestic.xml 신규 추가 (Yahoo 経済 이외 국내 생활밀착 기사 공급)
          · cat6 주석 수정: "경제" → "国際" (실제 카테고리 반영)
        - step3_chatgpt.py (쇼츠 2단계 KO→JA): 프롬프트 3차 개편
          · 1차 개편: 후크 간결·임팩트·궁금증 강화 — 30자 이내 / 질문형·수치형·뒤집기형
            숫자는 반드시 포함 / 「あなたの○○」型 / 네거티브 앵커 + 반전 구조
          · 2차 개편: 후크 추가 강화 — 익숙한 생활 현상으로 시작 / 경제용어 금지 /
            첫 문장=의문 제기, 둘째=긴장 확장, 셋째=해결 예고 3-beat 구조
          · 3차 개편: script 궁금증 해소 — 메커니즘 설명 의무
            "어떻게 연결되는가"의 인과 경로 서술 (방향 예측 금지 / 방향 중립 표현 필수)
          · 톤 가드 (감정 과잉 방지): 「！」최대 1회 / 연속 「！！」금지 /
            단정 미래예측 맥락에서만 「確かに/必ず」금지

✅  세션 D (2026-05-23) — 롱폼 발행 슬롯 + active_longform.json + 쇼츠 아웃트로
        - longform_link.py 신규 생성 (SRP)
          · next_publish_jst(slot): sun(일) / thu(목) 18:00 JST RFC3339 계산
          · append_active(entry): active_longform.json에 항목 추가, MAX_ACTIVE=6 trim
          · get_active(): publish_at_jst <= now 중 최신 1개 반환 (아웃트로 깔때기용)
          · get_upcoming(): publish_at_jst > now 중 가장 가까운 topic_id 반환 (기사 선택 UI용)
        - long6_youtube.py: 21:00 고정 → sun/thu 18:00 슬롯 방식으로 전환
          · longform_link.next_publish_jst(args.slot) 사용
          · 업로드 후 append_active() 호출 (topic_id / topic_ja / title_ja / url / publish_at_jst)
          · long_youtube_url.txt 저장 (long7 연결용)
        - run_longform.py: --slot 인수 추가 → long6에 전달
        - mochien_longform.yml: workflow_dispatch input "slot" (sun/thu, default: sun) 추가
        - mochien_full.yml: Commit 스텝에 active_longform.json 추가
        - webui.py: /api/longform/stream?slot= 쿼리 파라미터 추가
        - templates/longform.html: 슬롯 드롭다운 (일요일/목요일 18:00 JST)
        - step3_chatgpt.py: 쇼츠 아웃트로 signoff 아키텍처 구현
          · SIGNOFF_DEFAULT_KO / SIGNOFF_DEFAULT_JA / SIGNOFF_FUNNEL_JA 상수
          · _SIGNOFF_RE 정규식 — KO/JA 기본/깔때기/레거시 변형 모두 캐치
          · _strip_signoff(): GPT 출력에서 아웃트로 제거 (stage_ko/stage_ja 양쪽 적용)
          · stage_ko(): 한국어 기본 아웃트로 코드에서 부착
          · stage_ja(): get_active() 확인 → 공개 롱폼 있으면 깔때기 멘트 부착,
            없으면 기본 아웃트로. active_longform_url / active_longform_title gpt 결과에 저장
          · backtranslate_script에도 _strip_signoff 적용 (역직역 대상에서 제외)
        - step9_youtube.py: build_notification()에 롱폼 링크 줄 추가
          · active_longform_url 있으면 "▼今週の解説：「{title}」\n{url}" 고정댓글에 포함

✅  세션 E (2026-05-23) — 기사 선택 UI — 생활밀착 점수 + 토픽뱅크 매치
        - life_keywords.json 신규 생성
          · 생활밀착 키워드 37개, 가중치 2~3 (给料·物価·年金·光熱費 등)
          · 코드 수정 없이 이 파일만 편집하면 가중치 조정 가능
        - article_score.py 신규 생성 (SRP)
          · life_score(article): 제목+본문 생활밀착 키워드 가중치 합산
          · match_topic(article): topic_bank.json keywords_ja 중복 최다 토픽 반환 (0이면 None)
          · enrich_articles(articles, active_topic_id): life_score/match_topic_id/match_topic_ja/
            is_active_match 필드 추가 + 소프트 정렬 (is_active_match=True 먼저 → life_score 내림)
        - longform_link.py: get_upcoming() 추가 (세션 D에 포함)
        - webui_runner.py: run_fetch_articles()에 enrich_articles 적용
          · get_upcoming()으로 예정 롱폼 topic_id 취득 → enrich_articles(result, upcoming)
          · 결과 리스트에 life_score / match_topic_id / match_topic_ja / is_active_match 포함
        - templates/select_article.html: 점수 배지 + 롱폼 매칭 하이라이트
          · 📊 생활밀착 N 배지 (초록색), 📌 토픽명 배지 (파란색)
          · 🔗 롱폼 연결 칩 (빨간색) + article-card--match 빨간 테두리
        - static/style.css: score-badge / topic-badge / match-chip / article-card--match 추가
        - step2_select.py: 텔레그램 메시지에 점수 줄 추가 (선택 순서·로직 변경 없음)
          · build_preview() / batch_main() 후보 텍스트: "📊 생활밀착 N · 토픽:제목" 줄 삽입
          · import article_score as _article_score 추가

✅  세션 F (2026-05-24) — 사인오프 이중 버그 수정 + CHANNEL_FOOTER 발행 시각 수정
        - step3_chatgpt.py: _SIGNOFF_PATTERNS 정규식 수정
          · 변경 전: r"以上、モチエンが[^。！]*[。！]"  ← 「が」필수로 매칭 실패
          · 변경 후: r"以上、モチエン[^。！]*[。！]"   ← 「でした。」「がお伝えしました。」모든 변형 대응
          · 이유: GPT가 「以上、モチエンでした。」변형을 출력했을 때 기존 패턴이 캐치 못해 이중 사인오프 발생
        - step3_chatgpt.py: USER_PROMPT_KO_BODY 79번째 줄 사인오프 지시 충돌 제거
          · 변경 전: script_ko 필드 설명에 "마지막 문장은 반드시 '이상, 모찌엔이었습니다!'" 포함
          · 변경 후: 해당 지시 제거 (126번째 줄 "사인오프 포함하지 말 것" 지시와 충돌 방지)
        - long6_youtube.py: CHANNEL_FOOTER 발행 시각 수정 (41번째 줄)
          · 변경 전: 「毎日2回のショーツ＋毎晩21時に深掘り解説！」
          · 변경 후: 「毎日2回のショーツ＋毎週日・木18時に深掘り解説！」
          · 이유: 롱폼 예약 슬롯이 21:00 고정 → 일/목 18:00으로 변경된 것과 불일치

✅  세션 G (2026-05-28) — 썸네일 자동 생성 + expression/direction 전환 + 웹UI 표정 그리드
        - step8_thumbnail.py 신규 생성
          · gpt-image-1-mini로 AI 배경 이미지 생성 (1024×1024 → 1080×1920 crop)
          · Pillow composite: 상단 네이비바 + 빨간선 + short_title / 반투명 검정 박스 + thumb_headline
          · 캐릭터 PNG(expression 기반) + 채널 하단바 + 방향 화살표(up=빨강/down=파랑/none 없음)
          · safe zone: SAFE_BAND_TOP=285 / SAFE_BAND_BOT=1635 (YouTube 4:5 안전영역)
          · HEADLINE_BOX_ALPHA=210 반투명 박스 → 밝은 배경에서도 헤드라인 0.5초 가독성
          · step9_youtube.py에서 thumbnails.set으로 YouTube 업로드
        - step2_select.py: emotion 필드 → expression + direction + thumb_headline 전환
          · expression: 9종 자동 선택 풀 (shy/embarrassed/sleepy는 수동 전용)
          · direction: "up"(빨강/호재) / "down"(파랑/악재) / "none"(중립)
          · thumb_headline: 14자 이내 썸네일 전용 헤드라인 (수치형/워드형 자동 분기)
          · expression 3단계 사고 프롬프트 (chain-of-thought / 양면 기사 처리 규칙 포함)
        - step3_chatgpt.py: KO/JA 단계 모두 expression + direction + thumb_headline 반영
          · KO 단계: expression 3단계 프롬프트 + thumb_headline_ko 필드
          · JA 단계: expression "転記（変更禁止）" + thumb_headline 일본어 변환
        - webui.py: POST /api/shorts/{slot}/set-expression 엔드포인트 신규
          · VALID_ALL_EXPRESSIONS 상수 12종 (9 자동 + 3 수동 전용)
          · expression_auto(원본 AI 추천값) 보존 + expression_final(최종 선택) 기록
        - templates/confirm_script.html: 표정 선택 그리드 12종
          · 9종 자동 + 3종 수동(dashed 테두리 구분) / 선택 시 setExpression() API 호출
          · 메타 표시: "표정 (자동 추천)" id=ja-expr-auto

✅  세션 H (2026-05-28) — CLAUDE.md 분리 + hook TTS 추가 + thumb_headline/direction 개선
        - CLAUDE.md 분리: 완료 세션 이력을 CHANGELOG.md로 분리
          · 판단 기준: "내일 새 작업 시 Claude Code가 알아야 할 규칙" → CLAUDE.md
            "X월에 무엇을 했다는 기록" → CHANGELOG.md
          · CLAUDE.md 약 1,450줄 → 약 850줄로 축소 (컨텍스트 로딩 속도 개선)
        - step5_tts.py: hook + script 합산 TTS (도입부 후킹 강화)
          · 기존: gpt["script"]만 ElevenLabs에 전송
          · 변경: hook + "　" + script 합산 후 전송 (전각 스페이스로 자연스러운 호흡)
          · hook 없는 구버전 gpt_result 하위 호환 유지
          · hook은 기존에 생성되지만 TTS 음성에 미포함 상태였음 — 이번에 최초 연결
        - step2_select.py: thumb_headline 숫자 우선 규칙 + direction none 판정 개선
          · thumb_headline: 수치(%, 금액, 배수) 있으면 반드시 수치 포함 의무화
            良い例: 「家賃+12%」「170円の壁」/ 나쁜 예: 「最高」(수치 누락)·본문 토막 명시
          · direction: "none"의 기준을 "数字なし" → "방향 판별 불가·고착·복합"으로 수정
            수치 있어도 방향이 애매하면 none 정당 / 명확하면 up/down 적극 선택
          · script 첫 문장 hook 반복 금지 지시 추가 ("scriptの冒頭はhookの内容を繰り返さないこと")
        - step3_chatgpt.py: 동일 규칙 한국어 프롬프트 버전 반영
          · thumb_headline_ko 숫자 의무 강화
          · direction none 설명 수정 ("숫자없음" → "방향 판별 불가·고착·복합")
          · script 한국어 hook 반복 금지 지시 추가

✅  세션 I (2026-05-29) — 작업 2 데이터 파이프라인 fetch 모듈 3개 완성
        [작업 2-1] data/fred_fetch.py 신규 생성
          · FRED API V1 / api_key 쿼리 파라미터 방식
          · fetch_series(series_id, months=60) → 시계열 dict 반환
          · 캐시: data/cache/{series_id}_{YYYY-MM}.json (월 1회)
          · 예외 분리: 504/503/ReadTimeout/ConnectionError → _FredTransientError + 안내 메시지 출력
            400/401/403/404 → 즉시 sys.exit(1) (키·코드 문제)
          · 검증 시리즈: DEXJPUS (USD/JPY daily)
          · ※ 구현 당일 api.stlouisfed.org 504 장애 — 모듈 완성, 검수 표는 장애 복구 후 확인
        [작업 2-2] data/boj_fetch.py 신규 생성
          · BOJ 時系列統計検索サイト API / 인증 불필요
          · fetch_series(db, code, months=60) + fetch_metadata(db) → --meta / CLI
          · 캐시: data/cache/boj_{db}_{code_safe}_{YYYY-MM}.json
          · 高頻度アクセス 금지: 503/504 시 30초 대기 후 1회 재시도
          · 검증 시리즈: FM08/FXERD05 (도쿄시장 ドル・円 中心相場 daily)
          · 검수 표 통과: 최신값 159.3엔 (2026-05-27), 총 1,237개 observation
        [작업 2-3] data/estat_fetch.py 신규 생성
          · e-Stat API 3.0 / 환경변수 ESTAT_APP_ID
          · fetch_series(stats_data_id, filters, months=60) + fetch_metadata + search_stats_list
          · CLI: --search "키워드" [--code 통계코드] / --meta statsDataId / statsDataId --catNN --area
          · 캐시: data/cache/estat_{id}_{filter_hash}_{YYYY-MM}.json
          · time 코드 dual-format: 가계조사(YYYY00MMNN) / 매월근로통계류(YYYYMM0000) 자동 판정
          · frequency: 정규화된 날짜 길이로 추론 (raw time 코드 직접 파싱 오판 방지)
          · --area CLI 인자 추가 (cdArea 필터)
          · 검증 시리즈: 0002070001 家計調査 / 消費支出(cat01=059) / 二人以上世帯(cat02=03) / 全国(area=00000)
          · 검수 표 통과: 최신값 334,701엔 (2026-03), 총 59개 observation
          · 매월근로통계조사(00450071) API DB 2016-03-31 정지 확인 — 실질임금 토픽 작업 2-4로 이월
        [공통]
          · 출력 스키마 통일: series_id / title / frequency / unit / observations[{date,value}]
                              latest_date / latest_value / fetched_at
          · 작업 2-4(토픽뱅크 정비) / 작업 2-5(long1 연결) 시 통합 처리 가능 구조
          · .gitignore에 data/cache/ 등록

✅  작업 3 완료 (2026-05-30) — 롱폼 KO 대본 재설계 + JA 변환 검증
        수정 파일: long1_script.py (KO 구조 / JA 사인오프)
        [KO 구조 변경]
          · call_mode_judge: JSON 출력에 issue1_angle/issue2_angle 추가 → 분리축 사전 결정
          · call_angle_judge 신규 함수: --topic 직접 지정 경로 전용 (기사 불필요)
          · stage_ko(): topic_override·기사 양쪽 경로 모두 분리축 추출 → ko_data에 저장
          · SYSTEM_KO 규칙 9→5개 슬림화 (시청자 전제 블록 유지)
          · issue1/2 프롬프트: 「이슈 분리 원칙」블록 삭제 → 각도 고정 지시 / 흔한 오해 강제 삭제
        [JA 수정]
          · SYSTEM_JA 사인오프 종료 지시 1줄 → 2줄 확장
            「以上、モチエンがお伝えしました！」→ +「チャンネル登録お願いします！」
        [KO 검증 통과]
          · yen-rate·inflation-deflation·business-cycle 3토픽
            분리축 두 각도 다름 ✓ / 이슈1·2 각 450자+ ✓ / 시점·금지선·에버그린 유지 ✓
        [JA 검증 통과 — KO→JA→backcheck 3단 비교]
          · business-cycle: 116.4/2026年3月時点/+0.6 수치 완전 보존 ✓
          · yen-rate: 159.3엔/2026年5月27日現在/159만엔 환산 완전 보존 ✓
          · 일본인 시점 유지(한국 시점 없음) ✓ / 사인오프 2줄 보존 ✓ / 이슈1 수치 없음 ✓
        [미해결 — 다음 처리]
          · backcheck 역직역 간헐적 JSONDecodeError (영상 결과 무영향 / temperature 조정 또는 실패 처리)
          · 일별 데이터(yen-rate 등) data_block 날짜 특정 일자 박힘 → 월 단위 변환 필요(B안 확정)

✅  작업 2 마무리 (2026-05-29) — business-cycle 셀 확정·active 승격 + FRED 5개 재검증
        [business-cycle 보류 해제]
          · e-Stat 0003446461 --meta 조회로 [tab](CI/DI) × [cat01](先行/一致/遅行) 축 구조 확인
          · CI指数(tab=100) × 一致指数(cat01=110) 셀 fetch: 최신값 116.4 (2020年=100, 2026-03), 59건
          · topic_bank.json: business-cycle data_sources에 estat 소스(cdTab=100/cdCat01=110) 추가
            status: hold → active / status_reason: null / chart_type: null → "line"
          · active 토픽 수 13 → 14 / 보류 잔여: cashless-society 1건
        [FRED 5개 재검증]
          · 작업 2-1 당시 api.stlouisfed.org 504 장애로 미확인이던 검수 표 5개 전부 통과
            DEXJPUS(159.2엔/79건) · IRLTLT01JPM156N(2.515%/60건) · GGGDTAJPA188N(239.97%/3건)
            JPNRGDPEXP(593,693억엔/20건) · POILDUBUSDM(126.71USD/59건)
          · ※ national-debt(GGGDTAJPA188N): 연간 IMF 시리즈 → months=60 기준 3건
            차트 구현 단계(작업 5)에서 기간 확장(months 늘리기) 처리 예정

✅  작업 4 완료 (2026-05-30) — real-wage 1편차 영상화 + 웹 UI 롱폼 위자드 개선
        [real-wage 1편차 완주]
          · long1_script.py --topic real-wage --stage ko → KO 검수 통과
          · long1_script.py --topic real-wage --stage ja → JA 검수 통과
          · 영상화(Pexels 배경·TTS·FFmpeg·Whisper) → 예약발행 완료
        [웹 UI 롱폼 위자드 개선]
          · GET /api/longform/topics 신규 + 드롭다운 토픽 직접 지정 경로
            run_long1_ko(topic_id) — --topic 플래그를 웹에서 지정 가능
          · both_done / longform_ready 게이트 완전 제거 → 언제든 롱폼 진입
          · KO 전문 표시 autoResize 버그 수정 (display:block → scrollHeight 순서 보장)
            + input 이벤트 연결 (편집 시 실시간 높이 추적)
          · 제작 마커: topic_history.json 기반 ⬜/✅ + 미제작 우선 정렬 + 제작일 표시
          · index.html 문구: "일·목 18:00 JST / 토픽 또는 당일 쇼츠 기반"
        [코드 추가 수정]
          · long1_script.py: BACKCHECK_TEMP=0.3 / call_backcheck() — 실패 시 경고 후 계속
          · run_longform.py: --skip-long1 플래그 (KO/JA 완료 후 영상화만 재실행용)
        [★ 작업 순서 변경 결정]
          · 원인: 루트 단일 경로 무버전 저장 → 다음 제작 시 비축분 중간파일 덮어쓰기
            "렌더링 겹 소급 가능" 전제가 비축 간격이 생기면 실질 불성립
          · 결정: 선제작 추가 비축 중단 → 작업 5(차트·Remotion) 완성 후 재개

✅  작업 5-0 완료 (2026-06-01) — Remotion 환경 셋업
        - 전제 확인: Node.js v24.16.0 / npm 11.13.0 로컬 설치·PATH 정상
        - npx skills add remotion-dev/skills
          → remotion-best-practices 스킬 설치 (.agents/skills/remotion-best-practices/)
        - npx create-video@latest --yes --blank --no-tailwind remotion
          → C:\mochien\remotion\ 생성 (기존 Python 구조와 분리)
        - npm install (307 packages, 25s)
        - npx remotion render MyComp out/sample.mp4
          → 60프레임 렌더 성공 (88.6 kB) — 환경 정상 확인

✅  작업 5-1 완료 (2026-06-02) — 롱폼 이슈 섹션 화면 템플릿 PoC
        [컴포넌트 구성]
          · src/mochien/fonts.ts       — Noto Sans JP Bold/Regular Google Fonts 로드
          · src/mochien/NumberCard.tsx — 원형 게이지 링 (카운트업 동기화 아크 + 레드 마커 닷)
          · src/mochien/LineChart.tsx  — Catmull-Rom cubic bezier 곡선 + 클립패스 진행 애니메이션
                                         그라데이션 면적 채움 / 데이터 포인트 마커 / 파선 기준선 / 뱃지 레이블
          · src/mochien/MochienIssue.tsx — BG #EFF2F8, 75프레임 NumberCard + 108프레임 LineChart
        [npm 추가]
          · @remotion/google-fonts@4.0.470 (Noto Sans JP 지원 확인)
        [톤 탐색 이력]
          · 1차: 네이비 #1B2A4A 금융단말기 톤 → "차갑고 딱딱함" 피드백
          · 2차: 동일 톤에서 곡선·그라데이션·마커 고급화
          · 3차: 밝은 인포그래픽 톤 (#EFF2F8 배경 / #2B7DE9 블루) 전면 전환
          · 4차(최종): 게이지 링 + 블루 카드 패널 구조 채택 — PoC OK
        [출력]
          · C:\mochien\remotion\out\poc_issue.mp4 (183프레임 / 6.1초 / 1920×1080)
        [주의 사항 (5-2 전 확인 필요)]
          · 밝은 배경 위에 흰 자막·캐릭터 흰 외곽선 가독성 문제
            → A안: 자막 영역 반투명 어두운 바 / B안: 자막 색 다크(#1A2742)로 변경

✅  작업 5-1 탐색 완료 (2026-06-02) — 레이아웃 4종 비교 샘플 생성
        [공통 유틸]
          · src/mochien/chartUtils.ts  — 데이터·색상·toX/toY/buildLinePath/buildAreaPath 공유
        [샘플 4종 — 구조가 근본적으로 다른 레이아웃]
          · SampleA (poc_a_split.mp4, 150f/5s)
            좌우 분할: 게이지 링(좌) + 꺾은선 차트(우) 동시 애니메이션
          · SampleB (poc_b_fullchart.mp4, 120f/4s)
            풀스크린 차트 + 좌상단 수치 오버레이 카드 (파선 기준선 + 뱃지)
          · SampleC (poc_c_cards.mp4, 165f/5.5s)
            상단 3카드(現在値/期間変化/観測期間) 순차 슬라이드인 → 하단 컴팩트 차트
          · SampleD (poc_d_story.mp4, 175f/5.8s)
            3비트 서사: ① 상승화살표 아이콘+타이틀 → ② 포스터 대형 수치 → ③ 풀 차트
        [다음 단계]
          · 레이아웃 방향 결정 → 작업 5-2 (데이터 fetch 실연결)로 진행

✅  작업 5-2(A) 완료 (2026-06-03) — BOJ fetch → yen-rate 차트 실연결
        [data/make_chart_json.py 신규]
          · CLI: python data/make_chart_json.py yen-rate [--months N] [--step N]
          · topic_bank.json primary source 자동 읽기 → BOJ FM08/FXERD05 fetch (months=36)
          · 월말 마지막 거래일 리샘플 → 3개월 간격 서브샘플 → 13포인트
          · Y_MIN/Y_MAX 자동 계산 (±5 마진 + 10단위 내림/올림) + Y틱 자동 생성
          · CHART_TITLE_JA / CHART_UNIT_LABEL 오버라이드 맵 (BOJ "￥／＄" → "円")
          · 저장: remotion/public/chart_data/yen_rate.json (Remotion --props 형식)
          · fetch 실패 시 에러 출력 + sys.exit(1) (더미값 대체 금지)
        [NavyDark.tsx 수정]
          · ChartData 타입 + NavyDarkProps 추가 (chartData?: ChartData)
          · props 있으면 실데이터 / 없으면 chartUtils 정적 데이터 fallback (기존 PoC 동작 보존)
          · 모듈 레벨 pts/lp/ap → 컴포넌트 내부 동적 계산 (toXDyn/toYDyn 로컬 헬퍼)
          · yTicks / sourceLabel / unitLabel / titleJa props 기반 동적 표시
        [Root.tsx 소폭 수정]
          · NavyDarkProps import + Composition defaultProps={{}} 추가
        [검증]
          · 실데이터: '23/6=144.88 ~ '26/5=159.3円 / Y범위 135~170 / Y틱 [140,150,160,170]
          · out/yen_rate_real.mp4 렌더 성공 (446 kB / 150프레임)
          · out/navy_dark.mp4 (PoC 더미 fallback) 동작 보존 확인

✅  롱폼 깊이 개선 세션 완료 (2026-06-05) — food-prices 1편 프롬프트 체계 확립
        [Work 1] 데이터 fetch 확장
          · food-prices 토픽 신규: CPI 6종(食料/総合/生鮮食品/エネルギー/コアコア/穀類)
            data_months=120(10년치) / 비교 스냅샷·1·3·5년 비교·12개월 추이 출력
          · estat_fetch.py CLI --tab 인수 추가
          · build_data_block: 다중 소스 풍부 포맷 (단일 소스는 기존 유지)
        [Work 2] 프롬프트 경계 재설정 + food-prices 활성화
          · SYSTEM_KO: [절대 금지] / [허용·권장] / [principle 사용 규칙] 분리 명시
            허용·권장: 이미 일어난 일의 분해·연결·인과 해석 (예측 ≠ 메커니즘 설명)
          · food-prices: status active / title_ja 확정 / principle 계단 구조 확정
          · 출처 표기 자동화: long6_youtube.py · long7_wordpress.py에 _source_line() 추가
            topic data_sources 기반 자동 표기 (food-prices→e-Stat / yen-rate→BOJ·FRED / 폴백 NHK)
        [Work 3] 섹션 역할 분리 + 영구 규칙 2개
          · 인트로=콜드오픈(반직관 미끼, 답 금지) / 이슈1=원리 / 이슈2=데이터 역할 분리
          · [영구 규칙] 자국민 시점: "일본의 경우"·「日本では」 금지 → SYSTEM_KO·JA 양쪽
          · 차트 태그 초판 ===차트=== / ===차트끝=== + long2_tts.py TTS 제거 안전망
        [Work 5 + 보정] 이슈 역할 재조정 + 차트 태그 B안
          · 이슈1=원리+대표 수치 1~2개+차트1 / 이슈2=세분화+의미 반전+차트 다수
          · principle 계단 구조 개정: "큰 대비 → 세분화 → 숨은 사실 반전"
          · [영구 규칙] 차트 태그 B안: ===차트[항목명, 시점]=== 음성문장 ===차트끝===
            raw 수치 금지 / 항목은 data_block 실존 항목만 / TTS 전 전체 제거 / JA 변환 시 보존
        [검증] food-prices KO 대본이 real-wage 교정본(4:21) 대비
          분해·반전(穀類 27.4%→1.2%)·인과·자국민 시점 개선 확인
        [미해결] 이슈1 대표 수치 시점 통일 미완 (프롬프트 덧대기 2회 실패)
          → 다음 세션: data_block에서 최신월 고정 코드 구조적 해결로 전환
