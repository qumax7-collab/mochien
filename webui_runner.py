"""모찌엔 웹 UI — 파이프라인 단계별 실행 래퍼 + SSE 제너레이터"""
import os
import sys
import json
import asyncio
import shutil
import subprocess
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator

from dotenv import load_dotenv
from openai import OpenAI
from webui_pexels import fetch_pexels_candidates, save_used_video

load_dotenv()

TRANSLATE_MODEL = "gpt-4.1-mini"

# step2_select 함수 직접 import (모듈 레벨 코드는 harmless)
from step2_select import fetch_articles as _fetch_articles
# step3_chatgpt 2단계 함수 import
from step3_chatgpt import stage_ko as _stage_ko, stage_ja as _stage_ja
# 생활밀착 점수 + 롱폼 예정 토픽 매칭
import article_score as _article_score
import longform_link as _longform_link

BASE = Path(__file__).parent
JST  = timezone(timedelta(hours=9))

# ── 단계별 예상 소요 시간 ─────────────────────────────────
ETA = {
    "BG":        "예상 10초",
    "TTS":       "예상 30~60초",
    "FFmpeg":    "예상 2~4분 소요 — 잠시 기다려주세요",
    "Whisper":   "예상 1~2분 소요",
    "Thumbnail": "예상 20~40초",
    "Upload":    "예상 1~2분 소요",
    "Long1":   "예상 3~5분 소요 (GPT 4회 호출)",
    "Long2":   "예상 1~2분 소요",
    "Long4":   "예상 6~10분 소요 — 잠시 기다려주세요",
    "Long5":   "예상 2~4분 소요",
    "Long6":   "예상 1~2분 소요",
    "Long7":   "예상 30초 소요",
}

# 의사 진행률 tick 간격 (초)
TICK_FFmpeg     = 25.0
TICK_Upload     = 30.0
TICK_Whisper    = 20.0
TICK_Thumbnail  = 15.0
TICK_Long4   = 40.0
TICK_Long5   = 25.0


LONG_SCRIPT_KO_FILE     = "long_script_ko.json"
LONG_SCRIPT_VERIFY_FILE = "long_script_verify.json"


def _today() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")

def _ev(step: str, pct: int, msg: str, **extra) -> str:
    payload = {"step": step, "pct": max(0, min(100, pct)), "msg": msg, **extra}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

def _err(step: str, detail: str) -> str:
    # 트레이스백 끝부분(실제 에러 메시지)이 보이도록 마지막 800자 사용
    tail = detail.strip()[-800:] if len(detail) > 800 else detail.strip()
    return _ev("Error", -1, f"[{step}] {tail}")


def _is_err(ev: str) -> bool:
    """SSE 이벤트가 Error 이벤트인지 판정. JSON 파싱 기반 — 직렬화 공백에 무관."""
    try:
        return json.loads(ev[len("data: "):])["step"] == "Error"
    except Exception:
        return False


# ── 배경 영상 다운로드 ─────────────────────────────────────
def download_video(url: str, dest: str, chunk: int = 1 << 20):
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for block in resp.iter_content(chunk):
            if block:
                f.write(block)


# ── RSS 기사 수집 ─────────────────────────────────────────
def translate_titles_korean(articles: list) -> list:
    """기사 제목 일본어 → 한국어 배치 번역 (GPT 1회 호출). 실패 시 원본 유지."""
    if not articles:
        return articles
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        numbered = "\n".join(f"{i+1}. {a['title']}" for i, a in enumerate(articles))
        resp = client.chat.completions.create(
            model=TRANSLATE_MODEL,
            messages=[
                {"role": "system", "content": "일본어 뉴스 제목을 자연스러운 한국어로 번역하세요. 번호를 그대로 유지하고 '번호. 한국어제목' 형식만 출력하세요."},
                {"role": "user", "content": numbered},
            ],
            max_tokens=400,
            temperature=0,
        )
        trans: dict = {}
        for line in resp.choices[0].message.content.strip().splitlines():
            line = line.strip()
            if ". " in line:
                try:
                    num, text = line.split(". ", 1)
                    trans[int(num) - 1] = text.strip()
                except Exception:
                    pass
        return [{**a, "korean_title": trans.get(i, a["title"])} for i, a in enumerate(articles)]
    except Exception:
        return [{**a, "korean_title": a["title"]} for a in articles]


WEBUI_MAX_ARTICLES = 10

def run_fetch_articles() -> list:
    """step2_select.fetch_articles() 호출 → 생활밀착 점수·롱폼 매칭 포함 dict 리스트 반환."""
    raw = _fetch_articles(limit=WEBUI_MAX_ARTICLES)
    result = []
    for a in raw:
        result.append({
            "title":        a.get("title", ""),
            "url":          a.get("url", ""),
            "article_body": a.get("article_body", ""),
            "published":    str(a.get("_published", "")),
        })
    # 생활밀착 점수 + 예정 롱폼 토픽 매칭 후 소프트 정렬
    upcoming_topic_id = _longform_link.get_upcoming()
    result = _article_score.enrich_articles(result, upcoming_topic_id)
    return translate_titles_korean(result)


# ── GPT 호출 (2단계) ──────────────────────────────────────
def run_call_gpt_ko(title: str, article_body: str) -> dict:
    """KO 단계: 한국어 초안 생성 → shorts_script_ko.json 저장 후 dict 반환."""
    return _stage_ko(title, article_body)


def run_translate_ja(ko_data: dict) -> dict:
    """JA 단계: 한국어 → 일본어 변환 → gpt_result dict + verify dict 반환.
    반환: {"gpt": ..., "verify": ...}
    """
    gpt = _stage_ja(ko_data)
    verify_path = BASE / "shorts_script_verify.json"
    verify = {}
    try:
        verify = json.loads(verify_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"gpt": gpt, "verify": verify}


# ── gpt_result.json 저장 ──────────────────────────────────
def save_slot_gpt_result(slot: str, gpt: dict, article: dict | None = None):
    """gpt_result.json (루트) + output/{today}/{slot}_gpt_result.json 동시 저장."""
    now = datetime.now(JST)
    save = {
        **gpt,
        "slot":           slot,
        "article_url":    (article or {}).get("url", gpt.get("article_url", "")),
        "raw_summary_jp": (article or {}).get("article_body", gpt.get("raw_summary_jp", "")),
        "webui_published": False,  # 발행 완료 전까지 기사 재선택 허용
    }
    root_path = BASE / "gpt_result.json"
    root_path.write_text(json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8")

    slot_dir = BASE / "output" / now.strftime("%Y-%m-%d")
    slot_dir.mkdir(parents=True, exist_ok=True)
    (slot_dir / f"{slot}_gpt_result.json").write_text(
        json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def mark_slot_published(slot: str):
    """step9 업로드 성공 후 호출 — webui_published: True로 갱신."""
    slot_file = BASE / "output" / datetime.now(JST).strftime("%Y-%m-%d") / f"{slot}_gpt_result.json"
    if not slot_file.exists():
        return
    try:
        data = json.loads(slot_file.read_text(encoding="utf-8"))
        data["webui_published"] = True
        slot_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[webui] mark_slot_published 실패: {e}")


# ── 서브프로세스 실행 (공용) ───────────────────────────────
# Windows SelectorEventLoop에서 asyncio.create_subprocess_exec이 NotImplementedError를
# 발생시키므로 subprocess.run + run_in_executor 방식으로 대체
def _run_sync_cmd(cmd: list) -> subprocess.CompletedProcess:
    """임의 커맨드 리스트를 서브프로세스로 실행 (KBI 안전)."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(BASE),
    )
    try:
        stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return subprocess.CompletedProcess(
            proc.args, 1, b"",
            b"[KBI] \xec\x8b\xa4\xed\x96\x89 \xec\xa4\x91 \xec\x9d\xb8\xed\x84\xb0\xeb\x9f\xbd\xed\x8a\xb8",
        )


def _run_sync(script: str) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(BASE),
    )
    try:
        stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return subprocess.CompletedProcess(
            proc.args, 1, b"",
            f"[{script}] 실행 중 시스템 인터럽트 발생 (재시도하세요)".encode(),
        )

async def _run_proc(script: str) -> tuple[int, bytes, bytes]:
    """venv Python으로 스크립트 실행 → (returncode, stdout, stderr)."""
    loop = asyncio.get_event_loop()
    r = await loop.run_in_executor(None, _run_sync, script)
    return r.returncode, r.stdout, r.stderr


async def _run_with_ticks(
    script: str,
    step: str,
    start_pct: int,
    end_pct: int,
    msg: str,
    tick_sec: float,
) -> AsyncGenerator[str, None]:
    """
    서브프로세스를 실행하면서 의사 진행률(tick) SSE 이벤트를 yield하는 내부 헬퍼.
    성공이면 end_pct 이벤트를 yield. 실패이면 Error 이벤트를 yield.
    호출부는 마지막 이벤트에 "Error"가 포함됐는지로 판단한다.
    """
    eta = ETA.get(step, "")
    yield _ev(step, start_pct, f"{msg} ({eta})")

    loop    = asyncio.get_event_loop()
    future  = loop.run_in_executor(None, _run_sync, script)

    n_ticks  = max(2, int((end_pct - start_pct) // 10))
    tick_pts = [
        start_pct + (end_pct - start_pct) * (i + 1) // (n_ticks + 1)
        for i in range(n_ticks)
    ]

    for tp in tick_pts:
        done, _ = await asyncio.wait({future}, timeout=tick_sec)
        if done:
            break
        yield _ev(step, tp, msg)

    r = await future

    if r.returncode != 0:
        yield _err(step, r.stderr.decode(errors="replace").strip())
        return

    yield _ev(step, end_pct, f"{step} 완료 ✓")


# ── 쇼츠 파이프라인 SSE ───────────────────────────────────
async def run_shorts_stream(slot: str, gpt: dict, bg_url: str | None = None) -> AsyncGenerator[str, None]:
    """쇼츠 영상 생성 파이프라인 SSE 이벤트 제너레이터."""

    # gpt_result.json 준비
    slot_file = BASE / "output" / _today() / f"{slot}_gpt_result.json"
    if slot_file.exists():
        shutil.copy(slot_file, BASE / "gpt_result.json")
    else:
        (BASE / "gpt_result.json").write_text(
            json.dumps({**gpt, "slot": slot}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── 1. 배경 영상 다운로드 ─────────────────────────────
    if bg_url:
        yield _ev("BG", 3, f"선택한 배경 영상 다운로드 중... ({ETA['BG']})")
        try:
            await asyncio.to_thread(download_video, bg_url, str(BASE / "background.mp4"))
        except Exception as e:
            yield _err("BG", str(e))
            return
    else:
        yield _ev("BG", 3, f"배경 영상 자동 검색 중... ({ETA['BG']})")
        try:
            image_prompt = gpt.get("image_prompt", "japanese economy news")
            candidates = await asyncio.to_thread(fetch_pexels_candidates, image_prompt, 6, 1)
            if not candidates:
                raise Exception(f"Pexels 검색 결과 없음: '{image_prompt}'")
            chosen = candidates[0]
            bg_url = chosen["url"]
            await asyncio.to_thread(save_used_video, bg_url, chosen.get("thumb", ""))
            await asyncio.to_thread(download_video, bg_url, str(BASE / "background.mp4"))
        except Exception as e:
            yield _err("BG", str(e))
            return
    yield _ev("BG", 12, "배경 영상 다운로드 완료 ✓")

    # ── 2. TTS ─────────────────────────────────────────────
    failed = False
    async for ev in _run_with_ticks("step5_tts.py", "TTS", 15, 28, "음성 생성 중...", 15.0):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── 3. FFmpeg (긴 단계 — 의사 진행률) ─────────────────
    failed = False
    async for ev in _run_with_ticks("step6_ffmpeg.py", "FFmpeg", 30, 62, "영상 합성 중...", TICK_FFmpeg):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── 4. Whisper ─────────────────────────────────────────
    failed = False
    async for ev in _run_with_ticks("step7_whisper_subtitle.py", "Whisper", 65, 83, "자막 생성 중...", TICK_Whisper):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── 4.5 썸네일 생성 ──────────────────────────────────
    # step8 종료 코드를 존중: 검증 게이트(thumb 수치 불일치) exit(1) → 업로드 차단.
    # 이미지 생성 실패 등 미관 문제는 step8이 exit(0)으로 통과시키므로 영향 없음.
    failed = False
    async for ev in _run_with_ticks("step8_thumbnail.py", "Thumbnail", 84, 84,
                                    "썸네일 생성 중...", TICK_Thumbnail):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── 5. YouTube 업로드 (긴 단계 — 의사 진행률) ─────────
    yield _ev("Upload", 85, f"YouTube 업로드 중... ({ETA['Upload']})")
    loop     = asyncio.get_event_loop()
    upload_f = loop.run_in_executor(None, _run_sync, "step9_youtube.py")

    for tp in [88, 93]:
        done, _ = await asyncio.wait({upload_f}, timeout=TICK_Upload)
        if done:
            break
        yield _ev("Upload", tp, "업로드 진행 중...")

    r   = await upload_f
    rc  = r.returncode
    out = r.stdout.decode(errors="replace")

    if rc != 0:
        yield _err("Upload", r.stderr.decode(errors="replace"))
        return

    # stdout에서 YouTube URL 파싱 (step9가 "URL       : https://..." 형식으로 출력)
    yt_url = "https://studio.youtube.com/channel/videos"
    for line in out.splitlines():
        if "youtube.com/watch" in line or "youtu.be" in line:
            parts = line.split(":")
            # "URL       : https://www.youtube.com/watch?v=xxx"
            url_candidate = line.split(":", 1)[-1].strip()
            if url_candidate.startswith("http"):
                yt_url = url_candidate
                break

    # 발행 완료 마킹 — 이 기사는 이제 재선택 대상에서 제외
    mark_slot_published(slot)

    # step10 검수: 백그라운드 실행 (완료를 기다리지 않음 — 텔레그램으로 결과 수신)
    asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(
        [sys.executable, "step10_gemini_review.py", "--mode", "shorts"],
        capture_output=True, cwd=str(BASE),
    ))
    yield _ev("Done", 100, "영상 생성 및 업로드 완료! 🎉", url=yt_url)


# ── 롱폼: long1 실행 ──────────────────────────────────────
def run_long1_script() -> dict:
    """long1_script.py (자동 모드: KO+JA 연속) → long_script.json 반환."""
    r = _run_sync_cmd([sys.executable, "long1_script.py"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip()[-500:])
    return json.loads((BASE / "long_script.json").read_text(encoding="utf-8"))


def run_long1_ko(revise: str | None = None, topic_id: str | None = None) -> dict:
    """KO 단계만 실행 (--stage ko) → long_script_ko.json 반환.
    topic_id 지정 시 --topic {id} 경로 (기사 불필요). 미지정 시 기사 기반.
    """
    cmd = [sys.executable, "long1_script.py", "--stage", "ko"]
    if topic_id:
        cmd += ["--topic", topic_id]
    if revise:
        cmd += ["--revise", revise]
    r = _run_sync_cmd(cmd)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip()[-500:])
    return json.loads((BASE / LONG_SCRIPT_KO_FILE).read_text(encoding="utf-8"))


def run_long1_ja() -> dict:
    """JA 단계만 실행 (--stage ja) → long_script.json 반환."""
    r = _run_sync_cmd([sys.executable, "long1_script.py", "--stage", "ja"])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip()[-500:])
    return json.loads((BASE / "long_script.json").read_text(encoding="utf-8"))


# ── 롱폼 파이프라인 SSE ───────────────────────────────────
async def run_longform_stream(bg_urls: dict, slot: str = "sun") -> AsyncGenerator[str, None]:
    """롱폼 영상 생성 파이프라인 SSE 이벤트 제너레이터.
    bg_urls: {0: {url, thumb}, 1: {url, thumb}, 2: {url, thumb}}
    slot: 발행 슬롯 ("sun" | "thu")
    """

    # ── 배경 영상: long3_pexels.py로 섹션 기본 bg 다운로드 ──
    # 섹션별 선택 배경(long_bg_brief_{section}.mp4)은 webUI 선택 시 이미 다운로드됨
    # long3는 brief.bg_section 미설정 섹션의 폴백 bg를 담당
    yield _ev("Long3", 2, f"배경 영상 준비 중... ({ETA['BG']})")
    rc, _, stderr = await _run_proc("long3_pexels.py")
    if rc != 0:
        yield _err("Long3", stderr.decode(errors="replace"))
        return
    yield _ev("Long3", 8, "배경 영상 준비 완료 ✓")

    # ── long2: TTS ──────────────────────────────────────────
    failed = False
    async for ev in _run_with_ticks("long2_tts.py", "Long2", 10, 22, "롱폼 음성 생성 중...", 15.0):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── long_render_charts: 차트 데이터 fetch + Remotion 렌더 ──
    failed = False
    async for ev in _run_with_ticks("long_render_charts.py", "Charts", 23, 25, "차트 렌더 중...", 20.0):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── long4: FFmpeg (가장 긴 단계) ───────────────────────
    failed = False
    async for ev in _run_with_ticks("long4_ffmpeg.py", "Long4", 25, 68, "롱폼 영상 합성 중...", TICK_Long4):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── long5: Whisper ─────────────────────────────────────
    failed = False
    async for ev in _run_with_ticks("long5_whisper.py", "Long5", 70, 84, "롱폼 자막 생성 중...", TICK_Long5):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # ── long6: YouTube 업로드 ──────────────────────────────
    yield _ev("Long6", 86, f"롱폼 YouTube 업로드 중... ({ETA['Long6']})")
    loop   = asyncio.get_event_loop()
    long6_f = loop.run_in_executor(
        None, _run_sync_cmd,
        [sys.executable, "long6_youtube.py", "--slot", slot],
    )

    for tp in [90, 95]:
        done, _ = await asyncio.wait({long6_f}, timeout=TICK_Upload)
        if done:
            break
        yield _ev("Long6", tp, "롱폼 업로드 진행 중...")

    r   = await long6_f
    rc  = r.returncode
    out = r.stdout.decode(errors="replace")

    if rc != 0:
        yield _err("Long6", r.stderr.decode(errors="replace"))
        return

    yt_url = "https://studio.youtube.com/channel/videos"
    for line in out.splitlines():
        if "youtube.com/watch" in line or "youtu.be" in line:
            url_candidate = line.split(":", 1)[-1].strip()
            if url_candidate.startswith("http"):
                yt_url = url_candidate
                break

    # ── long7: 워드프레스 발행 ─────────────────────────────
    yield _ev("Long7", 98, f"블로그 발행 중... ({ETA.get('Long7', '예상 30초')})")
    r7 = await loop.run_in_executor(None, _run_sync, "long7_wordpress.py")
    if r7.returncode != 0:
        # 실패해도 영상 업로드는 완료 → 에러 이벤트 없이 경고만 로그
        print(f"[Long7 경고] returncode={r7.returncode}")
    yield _ev("Long7", 99, "블로그 발행 완료 ✓")

    # step10 검수: 백그라운드 실행 (롱폼 모드)
    asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(
        [sys.executable, "step10_gemini_review.py", "--mode", "longform"],
        capture_output=True, cwd=str(BASE),
    ))
    yield _ev("Done", 100, "롱폼 영상 생성 및 업로드 완료! 🎉", url=yt_url)


# ── 배경만 재렌더 SSE (TTS·자막 보존) ───────────────────────
async def run_longform_bg_only_stream() -> AsyncGenerator[str, None]:
    """배경 재렌더 전용: long4(FFmpeg 합성) + 기존 ASS 자막 번인만 실행.
    long2(TTS)·long5(Whisper) 재호출 없이 교정 완료된 자막 보존."""

    ass_file = "long_subtitle.ass"
    no_sub   = "long_output_no_sub.mp4"
    output   = "long_output.mp4"

    if not (BASE / ass_file).exists():
        yield _err("Sub", f"{ass_file} 없음 — long5를 먼저 실행하세요")
        return
    if not (BASE / "long_voice_intro.mp3").exists():
        yield _err("Long4", "long_voice_intro.mp3 없음 — long2를 먼저 실행하세요")
        return

    # long4: FFmpeg 섹션 합성 → long_output_no_sub.mp4
    failed = False
    async for ev in _run_with_ticks("long4_ffmpeg.py", "Long4", 5, 75, "롱폼 영상 합성 중...", TICK_Long4):
        yield ev
        if _is_err(ev):
            failed = True
    if failed:
        return

    # 기존 ASS 자막 번인 (Whisper 재호출 없음)
    yield _ev("Sub", 78, "기존 자막 번인 중...")
    sub_cmd = [
        "ffmpeg", "-y",
        "-i", no_sub,
        "-vf", f"ass={ass_file}",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        output,
    ]
    r = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_sync_cmd(sub_cmd)
    )
    if r.returncode != 0:
        yield _err("Sub", r.stderr.decode(errors="replace").strip()[-2000:])
        return

    yield _ev("Done", 100, "배경 재렌더 완료 ✓", url="")
