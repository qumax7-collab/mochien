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
    run_shorts_stream, run_long1_script, run_longform_stream, run_longform_bg_only_stream,
    run_long1_ko, run_long1_ja,
    LONG_SCRIPT_KO_FILE, LONG_SCRIPT_VERIFY_FILE,
    download_video as _download_video,
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
    "bg_urls": {},        # 레거시 (문단별 선택 — 현재 미사용)
    "section_bgs": {},    # 섹션별 배경 선택 결과 {intro/issue1/issue2/outro: {url,thumb,path}}
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
    """오늘 이미 사용 확정된 기사 URL 세트.
    webui_published 키가 있으면 True일 때만 제외 (발행 전은 재선택 가능).
    키가 없으면 자동화 파이프라인 생성 파일로 보고 항상 제외.
    """
    used: set = set()
    today_dir = BASE / "output" / today_jst()
    if not today_dir.exists():
        return used
    for f in today_dir.glob("*_gpt_result.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            url = data.get("article_url", "")
            if not url:
                continue
            published = data.get("webui_published")
            # webui_published 키 없음 = 자동화 파이프라인 → 항상 제외
            # webui_published=True  = webui에서 발행 완료 → 제외
            # webui_published=False = webui에서 미발행 → 제외 안 함 (재사용 가능)
            if published is None or published is True:
                used.add(url)
        except Exception:
            pass
    return used


def _try_restore_gpt(slot: str) -> dict | None:
    """SLOT_STATE가 비어있을 때 오늘 슬롯 파일에서 gpt 데이터 복원."""
    slot_file = BASE / "output" / today_jst() / f"{slot}_gpt_result.json"
    if not slot_file.exists():
        return None
    try:
        data = json.loads(slot_file.read_text(encoding="utf-8"))
        # webui 생성 파일만 복원 (webui_published 키 존재 여부로 판단)
        if "webui_published" in data:
            return data
    except Exception:
        pass
    return None


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
        gpt = _try_restore_gpt(slot)
        if gpt:
            SLOT_STATE[slot]["gpt"] = gpt
        else:
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
        gpt = _try_restore_gpt(slot)
        if gpt:
            SLOT_STATE[slot]["gpt"] = gpt
        else:
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
    if not state.get("gpt"):
        return templates.TemplateResponse(request, "select_article.html", {
            "slot": slot, "error": "먼저 기사를 선택해주세요.",
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
async def api_pexels(slot: str, page: int = Query(default=1, ge=1), q: str = Query(default="")):
    validate_slot(slot)
    gpt   = SLOT_STATE[slot].get("gpt") or {}
    query = q.strip() if q.strip() else gpt.get("image_prompt", "japanese economy news")
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

    if not s.get("gpt"):
        async def _missing():
            yield 'data: {"step":"Error","pct":-1,"msg":"GPT 대본이 없습니다."}\n\n'
        return StreamingResponse(_missing(), media_type="text/event-stream")

    s["is_running"] = True

    async def _gen():
        try:
            async for ev in run_shorts_stream(slot, s["gpt"], bg_url=s.get("bg_url")):
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

@app.get("/api/longform/paragraphs")
async def api_longform_paragraphs():
    """long_script.json에서 섹션별 나레이션 문단 목록 반환 (배경 슬롯 동적 생성용)."""
    import re
    script_path = BASE / "long_script.json"
    if not script_path.exists():
        raise HTTPException(404, "long_script.json 없음")
    try:
        script = json.loads(script_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"스크립트 파싱 실패: {e}")

    def extract_paras(text: str) -> list:
        clean = re.sub(r'===차트\[[^\]]*\]===.*?===차트끝===', '', text, flags=re.DOTALL)
        paras = [p.strip() for p in clean.split('\n') if p.strip()]
        return [{"idx": i, "preview": p[:60]} for i, p in enumerate(paras)]

    issues = script.get("issues", [])
    return {
        "intro":  [{"idx": 0, "preview": (script.get("intro", {}).get("script", "") or "")[:60]}],
        "issue1": extract_paras(issues[0].get("script", "") if issues else ""),
        "issue2": extract_paras(issues[1].get("script", "") if len(issues) > 1 else ""),
    }

@app.get("/api/longform/pexels/para/{section_key}/{para_idx}")
async def api_longform_pexels_para(section_key: str, para_idx: int, page: int = Query(default=1, ge=1)):
    """섹션·문단 지정 Pexels 후보 조회 (문단별 배경 선택용)."""
    script   = LONGFORM_STATE.get("script") or {}
    fallback = "japan economy news"
    if section_key == "intro":
        query = script.get("intro", {}).get("image_prompt", fallback)
    elif section_key == "issue1":
        issues = script.get("issues", [])
        query  = issues[0].get("image_prompt", fallback) if issues else fallback
    elif section_key == "issue2":
        issues = script.get("issues", [])
        query  = issues[1].get("image_prompt", fallback) if len(issues) > 1 else fallback
    else:
        query = fallback
    if "japan" not in query.lower():
        query = "japan " + query
    candidates = await asyncio.to_thread(fetch_pexels_candidates, query, 6, page)
    return {"candidates": candidates, "section_key": section_key, "para_idx": para_idx}

@app.post("/api/longform/select-bg")
async def api_longform_select_bg(request: Request):
    body  = await request.json()
    key   = body.get("key")   # e.g. "intro", "issue1_p0", "issue2_p1"
    url   = body.get("url", "")
    thumb = body.get("thumb", "")
    if key is None or not url:
        raise HTTPException(400, "key·url 필드 필요")
    LONGFORM_STATE["bg_urls"][key] = {"url": url, "thumb": thumb}
    save_used_video(url, thumb)
    return {"ok": True, "key": key}

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

_SECTION_KEYS = ("intro", "issue1", "issue2", "outro")
_SECTION_LABELS = {"intro": "イントロ / アウトロ", "issue1": "イシュー①", "issue2": "イシュー②", "outro": "アウトロ"}


@app.get("/api/longform/section-bg/search")
async def api_section_bg_search(
    section: str = Query(...),
    q: str       = Query(default=""),
    page: int    = Query(default=1, ge=1),
):
    """섹션 배경 Pexels 검색 (section: intro/issue1/issue2/outro)."""
    if section not in _SECTION_KEYS:
        raise HTTPException(400, "section은 intro/issue1/issue2/outro")

    if not q.strip():
        script = LONGFORM_STATE.get("script") or {}
        issues = script.get("issues", [])
        if section in ("intro", "outro"):
            q = script.get("image_prompt", "") or script.get("intro", {}).get("image_prompt", "japan economy")
        elif section == "issue1":
            q = (issues[0].get("image_prompt", "") if issues else "") or "japan economy"
        elif section == "issue2":
            q = (issues[1].get("image_prompt", "") if len(issues) > 1 else "") or "japan energy"

    if "japan" not in q.lower():
        q = "japan " + q.strip()

    candidates = await asyncio.to_thread(fetch_pexels_candidates, q, 6, page)
    return {"candidates": candidates, "section": section, "page": page, "query": q}


@app.post("/api/longform/section-bg/select")
async def api_section_bg_select(request: Request):
    """섹션 배경 선택 → 다운로드 + brief.bg_section 갱신."""
    body    = await request.json()
    section = body.get("section", "")
    url     = body.get("url", "")
    thumb   = body.get("thumb", "")

    if section not in _SECTION_KEYS:
        raise HTTPException(400, "section 값 오류")
    if not url:
        raise HTTPException(400, "url 필드 필요")

    dest_filename = f"long_bg_brief_{section}.mp4"
    dest_path     = str(BASE / dest_filename)

    try:
        await asyncio.to_thread(_download_video, url, dest_path)
    except Exception as e:
        raise HTTPException(500, f"다운로드 실패: {e}")

    # brief.bg_section 갱신
    try:
        script_path = BASE / "long_script.json"
        if script_path.exists():
            script = json.loads(script_path.read_text(encoding="utf-8"))
            slug   = script.get("_slug_keyword", "").replace("-", "_")
            if slug:
                brief_path = BASE / f"brief_{slug}.json"
                if brief_path.exists():
                    brief = json.loads(brief_path.read_text(encoding="utf-8"))
                    if section in brief and isinstance(brief[section], dict):
                        brief[section]["bg_section"] = dest_filename
                        brief_path.write_text(
                            json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
    except Exception as e:
        print(f"[경고] brief.bg_section 갱신 실패: {e}")

    save_used_video(url, thumb)
    LONGFORM_STATE["section_bgs"][section] = {"url": url, "thumb": thumb, "path": dest_filename}
    return {"ok": True, "section": section, "path": dest_filename}


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


@app.get("/api/longform/render-bg-only")
async def api_longform_render_bg_only():
    """배경만 재렌더: long4(FFmpeg) + 기존 ASS 번인. TTS·Whisper 재호출 없음."""
    if LONGFORM_STATE["is_running"]:
        async def _busy():
            yield 'data: {"step":"Error","pct":-1,"msg":"롱폼 이미 실행 중입니다."}\n\n'
        return StreamingResponse(_busy(), media_type="text/event-stream")

    LONGFORM_STATE["is_running"] = True

    async def _gen():
        try:
            async for ev in run_longform_bg_only_stream():
                yield ev
                await asyncio.sleep(0)
        finally:
            LONGFORM_STATE["is_running"] = False

    return StreamingResponse(
        _gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
