"""모찌엔 로컬 웹 UI — FastAPI 진입점"""
import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from webui_runner import (
    run_fetch_articles, run_call_gpt, save_slot_gpt_result,
    run_shorts_stream, run_long1_script, run_longform_stream,
)
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
    "09": {"is_running": False, "articles": [], "selected": None, "gpt": None, "bg_url": None, "bg_thumb": None},
    "18": {"is_running": False, "articles": [], "selected": None, "gpt": None, "bg_url": None, "bg_thumb": None},
}
LONGFORM_STATE: dict = {
    "is_running": False,
    "script": None,
    "bg_urls": {},   # {0: url, 1: url, 2: url}
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
        "longform_ready": all(status.values()),
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
    gpt = SLOT_STATE[slot].get("gpt")
    if not gpt:
        return templates.TemplateResponse(request, "select_article.html", {
            "slot": slot, "error": "먼저 기사를 선택해주세요.",
        })
    return templates.TemplateResponse(request, "confirm_script.html", {"slot": slot, "gpt": gpt})

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
        "longform_ready": all(slot_done(s) for s in ["09", "18"]),
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
    validate_slot(slot)
    body    = await request.json()
    article = body.get("article")
    if not article:
        raise HTTPException(400, "article 필드 필요")
    SLOT_STATE[slot]["selected"] = article
    result = await asyncio.to_thread(run_call_gpt, article["title"], article["article_body"])
    SLOT_STATE[slot]["gpt"] = result
    return result

@app.post("/api/shorts/{slot}/regenerate")
async def api_regenerate(slot: str):
    validate_slot(slot)
    article = SLOT_STATE[slot].get("selected")
    if not article:
        raise HTTPException(400, "선택된 기사 없음 — 기사 먼저 선택")
    result = await asyncio.to_thread(run_call_gpt, article["title"], article["article_body"])
    SLOT_STATE[slot]["gpt"] = result
    return result

@app.post("/api/shorts/{slot}/save-gpt")
async def api_save_gpt(slot: str):
    validate_slot(slot)
    gpt = SLOT_STATE[slot].get("gpt")
    if not gpt:
        raise HTTPException(400, "GPT 결과 없음")
    selected = SLOT_STATE[slot].get("selected", {})
    save_slot_gpt_result(slot, gpt, selected)
    return {"ok": True, "slot": slot}


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

@app.get("/api/longform/stream")
async def api_longform_stream():
    if LONGFORM_STATE["is_running"]:
        async def _busy():
            yield 'data: {"step":"Error","pct":-1,"msg":"롱폼 이미 실행 중입니다."}\n\n'
        return StreamingResponse(_busy(), media_type="text/event-stream")

    bg_urls = LONGFORM_STATE.get("bg_urls", {})
    LONGFORM_STATE["is_running"] = True

    async def _gen():
        try:
            async for ev in run_longform_stream(bg_urls):
                yield ev
                await asyncio.sleep(0)
        finally:
            LONGFORM_STATE["is_running"] = False

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
