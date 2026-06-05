"""모찌엔 로컬 웹 UI — FastAPI 진입점"""
import json
import shutil
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from webui_runner import (
    run_fetch_articles, run_call_gpt_ko, run_translate_ja, save_slot_gpt_result,
    run_shorts_stream, run_long1_script, run_longform_stream,
    run_long1_ko, run_long1_ja,
    LONG_SCRIPT_KO_FILE, LONG_SCRIPT_VERIFY_FILE,
)

LONG_SCRIPT_KO_BAK_FILE = "long_script_ko.bak.json"
from webui_pexels import fetch_pexels_candidates, save_used_video

BASE = Path(__file__).parent
JST  = timezone(timedelta(hours=9))

app = FastAPI(title="모찌엔 웹 UI", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

# Python 3.14 호환: 캐시를 0으로 설정한 Jinja2 환경 직접 생성
_jinja_env = Environment(
    loader=FileSystemLoader(str(BASE / "templates")),
    auto_reload=True,
    cache_size=0,
)
templates = Jinja2Templates(env=_jinja_env)

# ── 슬롯별 인메모리 상태 ─────────────────────────────────
SLOT_STATE: dict = {
    "09": {"is_running": False, "articles": [], "selected": None, "gpt_ko": None, "gpt": None, "bg_url": None, "bg_thumb": None},
    "18": {"is_running": False, "articles": [], "selected": None, "gpt_ko": None, "gpt": None, "bg_url": None, "bg_thumb": None},
}
LONGFORM_STATE: dict = {
    "is_running": False,
    "script": None,
    "bg_urls": {},   # {0: url, 1: url, 2: url}
}

# 표정 허용값 (자동 풀 9종 + 수동 전용 3종)
VALID_ALL_EXPRESSIONS = {
    "smile", "happy", "surprised", "shocked", "worried",
    "angry", "anxious", "sad", "base",
    "shy", "embarrassed", "sleepy",
}


# ── 유틸 ─────────────────────────────────────────────────
def today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")

def slot_file(slot: str) -> Path:
    return BASE / "output" / today_jst() / f"{slot}_gpt_result.json"

def slot_done(slot: str) -> bool:
    return slot_file(slot).exists()

def validate_slot(slot: str):
    if slot not in ("09", "18"):
        raise HTTPException(400, "슬롯은 09 또는 18")

def get_today_used_urls() -> set:
    used: set = set()
    today_dir = BASE / "output" / today_jst()
    if not today_dir.exists():
        return used
    for f in today_dir.glob("*_gpt_result.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            url = data.get("article_url", "")
            if url:
                used.add(url)
        except Exception:
            pass
    return used


# ── 페이지 라우트 ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    status = {s: slot_done(s) for s in ["09", "18"]}
    return templates.TemplateResponse(request, "index.html", {
        "status":         status,
        "today":          today_jst(),
        "slot_state":     {s: {"is_running": SLOT_STATE[s]["is_running"]} for s in ["09", "18"]},
    })

@app.get("/shorts/{slot}/select", response_class=HTMLResponse)
async def page_select(request: Request, slot: str):
    validate_slot(slot)
    return templates.TemplateResponse(request, "select_article.html", {"slot": slot})

@app.get("/shorts/{slot}/script", response_class=HTMLResponse)
async def page_script(request: Request, slot: str):
    validate_slot(slot)
    gpt_ko = SLOT_STATE[slot].get("gpt_ko")
    gpt    = SLOT_STATE[slot].get("gpt")
    if not gpt_ko and not gpt:
        return templates.TemplateResponse(request, "select_article.html", {
            "slot": slot, "error": "먼저 기사를 선택해주세요.",
        })
    return templates.TemplateResponse(request, "confirm_script.html", {
        "slot": slot, "gpt_ko": gpt_ko, "gpt": gpt,
    })

@app.get("/shorts/{slot}/background", response_class=HTMLResponse)
async def page_background(request: Request, slot: str):
    validate_slot(slot)
    gpt = SLOT_STATE[slot].get("gpt")
    if not gpt:
        return templates.TemplateResponse(request, "select_article.html", {
            "slot": slot, "error": "먼저 기사를 선택해주세요.",
        })
    return templates.TemplateResponse(request, "select_background.html", {
        "slot": slot, "image_prompt": gpt.get("image_prompt", "japanese economy"),
    })

@app.get("/shorts/{slot}/generate", response_class=HTMLResponse)
async def page_generate(request: Request, slot: str):
    validate_slot(slot)
    state = SLOT_STATE[slot]
    if not state.get("gpt") or not state.get("bg_url"):
        return templates.TemplateResponse(request, "select_article.html", {
            "slot": slot, "error": "기사와 배경 영상을 모두 선택해주세요.",
        })
    return templates.TemplateResponse(request, "generate.html", {
        "slot":     slot,
        "gpt":      state["gpt"],
        "bg_thumb": state.get("bg_thumb", ""),
    })

@app.get("/longform", response_class=HTMLResponse)
async def page_longform(request: Request):
    both_done = all(slot_done(s) for s in ["09", "18"])
    return templates.TemplateResponse(request, "longform.html", {
        "today":      today_jst(),
        "both_done":  both_done,
        "script":     LONGFORM_STATE.get("script"),
        "is_running": LONGFORM_STATE["is_running"],
    })


# ── API: 슬롯 상태 ────────────────────────────────────────
@app.get("/api/slot-status")
async def api_slot_status():
    return {
        "09":             slot_done("09"),
        "18":             slot_done("18"),
        "today":          today_jst(),
    }


# ── API: 기사 수집 / GPT ──────────────────────────────────
@app.post("/api/shorts/{slot}/articles")
async def api_fetch_articles(slot: str):
    validate_slot(slot)
    articles = await asyncio.to_thread(run_fetch_articles)
    used = get_today_used_urls()
    articles = [a for a in articles if a.get("url", "") not in used]
    SLOT_STATE[slot]["articles"] = articles
    return {"articles": articles, "count": len(articles)}

@app.post("/api/shorts/{slot}/gpt")
async def api_call_gpt(slot: str, request: Request):
    """KO 단계: 기사 선택 → 한국어 초안 생성."""
    validate_slot(slot)
    body    = await request.json()
    article = body.get("article")
    if not article:
        raise HTTPException(400, "article 필드 필요")
    SLOT_STATE[slot]["selected"] = article
    SLOT_STATE[slot]["gpt"]      = None   # 기존 JA 결과 초기화
    result = await asyncio.to_thread(run_call_gpt_ko, article["title"], article["article_body"])
    SLOT_STATE[slot]["gpt_ko"] = result
    return result

@app.post("/api/shorts/{slot}/regenerate")
async def api_regenerate(slot: str):
    """KO 재생성 — gpt_ko 업데이트, gpt(JA) 초기화."""
    validate_slot(slot)
    article = SLOT_STATE[slot].get("selected")
    if not article:
        raise HTTPException(400, "선택된 기사 없음 — 기사 먼저 선택")
    SLOT_STATE[slot]["gpt"] = None
    result = await asyncio.to_thread(run_call_gpt_ko, article["title"], article["article_body"])
    SLOT_STATE[slot]["gpt_ko"] = result
    return result

@app.post("/api/shorts/{slot}/translate-ja")
async def api_translate_ja(slot: str):
    """JA 단계: KO 초안 → 일본어 변환 + 역직역 반환."""
    validate_slot(slot)
    gpt_ko = SLOT_STATE[slot].get("gpt_ko")
    if not gpt_ko:
        raise HTTPException(400, "KO 초안이 없습니다. 먼저 대본을 생성하세요.")
    result = await asyncio.to_thread(run_translate_ja, gpt_ko)
    SLOT_STATE[slot]["gpt"] = result["gpt"]
    return result

@app.post("/api/shorts/{slot}/save-gpt")
async def api_save_gpt(slot: str):
    validate_slot(slot)
    gpt = SLOT_STATE[slot].get("gpt")
    if not gpt:
        raise HTTPException(400, "일본어 변환이 완료되지 않았습니다. [일본어로 변환]을 먼저 실행하세요.")
    selected = SLOT_STATE[slot].get("selected", {})
    save_slot_gpt_result(slot, gpt, selected)
    return {"ok": True, "slot": slot}

@app.post("/api/shorts/{slot}/set-expression")
async def api_set_expression(slot: str, request: Request):
    """표정 수동 선택 — SLOT_STATE 및 gpt_result.json 즉시 반영."""
    validate_slot(slot)
    body = await request.json()
    expr = body.get("expression", "")
    if expr not in VALID_ALL_EXPRESSIONS:
        raise HTTPException(400, f"허용되지 않는 표정값: {expr}")
    gpt = SLOT_STATE[slot].get("gpt")
    if not gpt:
        raise HTTPException(400, "GPT 대본이 없습니다. 일본어 변환을 먼저 실행하세요.")
    if "expression_auto" not in gpt:
        gpt["expression_auto"] = gpt.get("expression", "base")
    gpt["expression"] = expr
    gpt["expression_final"] = expr
    SLOT_STATE[slot]["gpt"] = gpt
    with open("gpt_result.json", "w", encoding="utf-8") as f:
        json.dump(gpt, f, ensure_ascii=False, indent=2)
    return {"ok": True, "expression": expr}


# ── API: 배경 영상 ────────────────────────────────────────
@app.get("/api/shorts/{slot}/pexels")
async def api_pexels(slot: str, page: int = Query(default=1, ge=1)):
    validate_slot(slot)
    gpt   = SLOT_STATE[slot].get("gpt") or {}
    query = gpt.get("image_prompt", "japanese economy news")
    candidates = await asyncio.to_thread(fetch_pexels_candidates, query, 6, page)
    return {"candidates": candidates, "query": query, "page": page}

@app.post("/api/shorts/{slot}/select-bg")
async def api_select_bg(slot: str, request: Request):
    validate_slot(slot)
    body  = await request.json()
    url   = body.get("url", "")
    thumb = body.get("thumb", "")
    if not url:
        raise HTTPException(400, "url 필드 필요")
    SLOT_STATE[slot]["bg_url"]   = url
    SLOT_STATE[slot]["bg_thumb"] = thumb
    save_used_video(url, thumb)
    return {"ok": True}


# ── API: 쇼츠 영상 생성 SSE ──────────────────────────────
@app.get("/api/shorts/{slot}/stream")
async def api_shorts_stream(slot: str):
    validate_slot(slot)
    s = SLOT_STATE[slot]

    if s["is_running"]:
        async def _busy():
            yield 'data: {"step":"Error","pct":-1,"msg":"이미 실행 중입니다."}\n\n'
        return StreamingResponse(_busy(), media_type="text/event-stream")

    if not s.get("gpt") or not s.get("bg_url"):
        async def _missing():
            yield 'data: {"step":"Error","pct":-1,"msg":"GPT 대본 또는 배경 영상이 없습니다."}\n\n'
        return StreamingResponse(_missing(), media_type="text/event-stream")

    s["is_running"] = True

    async def _gen():
        try:
            async for ev in run_shorts_stream(slot, s["gpt"], s["bg_url"]):
                yield ev
                await asyncio.sleep(0)
        finally:
            s["is_running"] = False

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── API: 롱폼 ─────────────────────────────────────────────
@app.get("/api/longform/script/exists")
async def api_longform_script_exists():
    """long_script.json 존재 여부 확인 (기존 스크립트 재사용용)."""
    path = BASE / "long_script.json"
    if not path.exists():
        return {"exists": False}
    try:
        script = json.loads(path.read_text(encoding="utf-8"))
        LONGFORM_STATE["script"] = script
        return {"exists": True, "title": script.get("title", "")}
    except Exception:
        return {"exists": False}

@app.post("/api/longform/script")
async def api_longform_script():
    script = await asyncio.to_thread(run_long1_script)
    LONGFORM_STATE["script"] = script
    return script

@app.get("/api/longform/pexels/{idx}")
async def api_longform_pexels(idx: int, page: int = Query(default=1, ge=1)):
    script   = LONGFORM_STATE.get("script") or {}
    fallback = "japanese economy news"
    if idx == 0:
        query = script.get("intro", {}).get("image_prompt", fallback)
    else:
        issues = script.get("issues", [])
        query  = issues[idx - 1].get("image_prompt", fallback) if idx - 1 < len(issues) else fallback
    candidates = await asyncio.to_thread(fetch_pexels_candidates, query, 6, page)
    return {"candidates": candidates, "idx": idx}

@app.post("/api/longform/select-bg")
async def api_longform_select_bg(request: Request):
    body  = await request.json()
    idx   = body.get("idx")
    url   = body.get("url", "")
    thumb = body.get("thumb", "")
    if idx is None or not url:
        raise HTTPException(400, "idx·url 필드 필요")
    LONGFORM_STATE["bg_urls"][idx] = {"url": url, "thumb": thumb}
    save_used_video(url, thumb)
    return {"ok": True, "idx": idx}

@app.get("/api/longform/topics")
async def api_longform_topics():
    """topic_bank.json에서 status=active 토픽 목록 반환.
    topic_history.json 조회 → made(JA 완료 여부) / made_date 필드 추가.
    미제작(made=False) 토픽을 앞으로 정렬.
    """
    bank_path    = BASE / "topic_bank.json"
    history_path = BASE / "topic_history.json"
    try:
        bank    = json.loads(bank_path.read_text(encoding="utf-8"))
        history: dict = {}
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        topics = [
            {
                "id":        t["id"],
                "title_ja":  t.get("title_ja", ""),
                "title_ko":  t.get("title_ko", ""),
                "principle": t.get("principle", ""),
                "made":      t["id"] in history,
                "made_date": history.get(t["id"]),
            }
            for t in bank.get("topics", [])
            if t.get("status") == "active"
        ]
        topics.sort(key=lambda t: t["made"])   # False(미제작) → True(제작됨)
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(500, f"topic_bank 로드 실패: {e}")


@app.post("/api/longform/script/ko")
async def api_longform_ko(request: Request):
    """KO 단계: 한국어 거시 원리형 초안 생성 → long_script_ko.json.
    body: { topic_id?: string }  — 없거나 빈 문자열이면 기사 기반 경로.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    topic_id = (body.get("topic_id") or "").strip() or None
    ko = await asyncio.to_thread(run_long1_ko, None, topic_id)
    return ko

@app.post("/api/longform/script/ko/revise")
async def api_longform_ko_revise(request: Request):
    """수정 요청 텍스트로 KO 초안 재생성."""
    body   = await request.json()
    revise = body.get("revise", "").strip()
    if not revise:
        raise HTTPException(400, "revise 필드 필요")
    ko = await asyncio.to_thread(run_long1_ko, revise)
    return ko

@app.get("/api/longform/script/ko/read")
async def api_longform_ko_read():
    """long_script_ko.json 내용 반환 (웹 UI 표시용)."""
    path = BASE / LONG_SCRIPT_KO_FILE
    if not path.exists():
        return {"exists": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"exists": True, **data}
    except Exception:
        return {"exists": False}

@app.post("/api/longform/script/ko/save")
async def api_longform_ko_save(request: Request):
    """한국어 대본 직접 편집 저장 — script_ko 4개 필드 덮어쓰기."""
    path = BASE / LONG_SCRIPT_KO_FILE
    if not path.exists():
        raise HTTPException(400, "long_script_ko.json 없음 — 먼저 초안을 생성하세요.")
    try:
        ko = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"파일 읽기 실패: {e}")

    body = await request.json()

    shutil.copy2(str(path), str(BASE / LONG_SCRIPT_KO_BAK_FILE))

    if "intro_ko" in body:
        ko["intro"]["script_ko"] = body["intro_ko"]
    if "issue1_ko" in body:
        ko["issues"][0]["script_ko"] = body["issue1_ko"]
    if "issue2_ko" in body:
        ko["issues"][1]["script_ko"] = body["issue2_ko"]
    if "outro_ko" in body:
        ko["outro"]["script_ko"] = body["outro_ko"]

    path.write_text(json.dumps(ko, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@app.post("/api/longform/script/ja")
async def api_longform_ja():
    """JA 단계: 일본어 변환 → long_script.json + long_script_verify.json."""
    ja = await asyncio.to_thread(run_long1_ja)
    LONGFORM_STATE["script"] = ja
    return ja

@app.get("/api/longform/script/verify/read")
async def api_longform_verify_read():
    """long_script_verify.json 반환 (역직역 확인용)."""
    path = BASE / LONG_SCRIPT_VERIFY_FILE
    if not path.exists():
        return {"exists": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"exists": True, **data}
    except Exception:
        return {"exists": False}

@app.get("/api/longform/stream")
async def api_longform_stream(slot: str = Query(default="sun")):
    if slot not in ("sun", "thu"):
        slot = "sun"

    if LONGFORM_STATE["is_running"]:
        async def _busy():
            yield 'data: {"step":"Error","pct":-1,"msg":"롱폼 이미 실행 중입니다."}\n\n'
        return StreamingResponse(_busy(), media_type="text/event-stream")

    bg_urls = LONGFORM_STATE.get("bg_urls", {})
    LONGFORM_STATE["is_running"] = True

    async def _gen():
        try:
            async for ev in run_longform_stream(bg_urls, slot=slot):
                yield ev
                await asyncio.sleep(0)
        finally:
            LONGFORM_STATE["is_running"] = False

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
