"""쇼츠 전용 디자인 썸네일 자동 생성 (short_thumb.jpg)

처리 흐름:
  1. gpt_result.json → expression / direction / hook / short_title / image_prompt 읽기
  2. OpenAI Images API로 실사 배경 생성
  3. Pillow로 레이아웃 합성 → short_thumb.jpg 저장
  종료 코드 규칙:
    · 검증 게이트(thumb_headline 수치 불일치) → sys.exit(1) 파이프라인 중단
    · 이미지 생성 실패·파일 누락 등 미관 문제 → sys.exit(0) 중단 없음
"""
import base64
import io
import json
import os
import re
import sys

import requests
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 캔버스 =====
THUMB_W       = 1080
THUMB_H       = 1920
SAFE_BAND_TOP = 285    # (1920 - 1350) / 2 — 4:5 safe zone 상단 y
SAFE_BAND_BOT = 1635   # THUMB_H - SAFE_BAND_TOP

# ===== OpenAI 이미지 모델 =====
IMG_MODEL   = "gpt-image-1-mini"   # 업그레이드: "gpt-image-1.5" / "gpt-image-2"
IMG_SIZE    = "1024x1536"
IMG_QUALITY = "medium"

IMG_SAFETY_SUFFIX = (
    "No text, signs, watermarks, logos, or captions in the image. "
    "No specific real people, faces, or identifiable individuals. "
    "No specific company buildings, real landmarks, or event recreations. "
    "Generic scene representing the theme only. "
    "Photorealistic, clean, professional."
)

# ===== 방향 색 =====
COLOR_MODE    = "JP_DIRECTION"     # "ALL_RED"로 토글
ACCENT_RED    = (229,   0,   0)
COLOR_UP_JP   = (229,   0,   0)    # 상승 = 빨강
COLOR_DOWN_JP = ( 68, 153, 255)    # 하락 = 파랑

# ===== 타이포그래피 =====
HEADLINE_FONT_SIZE = 68
CHANNEL_FONT_SIZE  = 28
STROKE_WIDTH       = 5
LINE_SPACING       = 14
HEADLINE_PADDING_X = 60            # 헤드라인 좌우 여백

# ===== 상단 바 =====
TOP_BAR_H = 80
TOP_BAR_Y = SAFE_BAND_TOP          # 285

# ===== 채널 마크 =====
CHANNEL_BAR_H  = 60
CHANNEL_NAME   = "モチエンのひとこと経済ニュース"
CHANNEL_BAR_Y  = SAFE_BAND_BOT - CHANNEL_BAR_H   # 1575
CHANNEL_TEXT_X = 30

# ===== 캐릭터 =====
FACE_H_THUMB      = 380
FACE_MARGIN_X     = 30             # 우측 여백
FACE_MARGIN_Y_BOT = 50             # SAFE_BAND_BOT 기준 위로
FACE_BOTTOM_Y     = SAFE_BAND_BOT - FACE_MARGIN_Y_BOT   # 1585

# ===== 썸네일 헤드라인 =====
HEADLINE_FALLBACK_LEN = 14         # thumb_headline 없을 때 short_title 자름 기준
HEADLINE_BOX_PAD_X   = 24         # 박스 좌우 여백
HEADLINE_BOX_PAD_Y   = 14         # 박스 상하 여백
HEADLINE_BOX_ALPHA   = 210        # 박스 불투명도 (0=투명 / 255=불투명)

# ===== 표정 (9종 허용 / 직접 PNG 파일명 사용) =====
VALID_EXPRESSIONS = {
    "smile", "happy", "surprised", "shocked", "worried",
    "angry", "anxious", "sad", "base",
}
EXPRESSION_FALLBACK = "base"
ASSETS_BASE         = "https://raw.githubusercontent.com/qumax7-collab/mochien-assets/main"

# ===== OpenAI 조직/크레딧 오류 알림 =====
TG_IMG_API_ERROR = (
    "⚠️ OpenAI 이미지 생성 불가\n"
    "조직 인증 미완료 또는 크레딧 부족 확인 필요\n"
    "https://platform.openai.com/settings/organization/billing"
)

# ===== 파일 경로 =====
GPT_RESULT_PATH = "gpt_result.json"
OUTPUT_FILE     = "short_thumb.jpg"
FONT_PATH       = "fonts/NotoSansJP-Bold.ttf"

# ===== thumb_headline 수치 검증 =====
THUMB_NUM_RE = re.compile(r'\d+(?:\.\d+)?%?')  # 숫자 토큰 추출 (소수점·% 포함)
FULLWIDTH_TABLE = str.maketrans('０１２３４５６７８９．％', '0123456789.%')


# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────

def tg_notify(text: str):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Pillow용 NotoSansJP-Bold 폰트 (시스템 폰트 fallback)."""
    candidates = [
        FONT_PATH,
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/NotoSansJP-Bold.ttf",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    print("  [경고] 일본어 폰트 없음 → 기본 폰트 사용")
    return ImageFont.load_default(size=size)


def fill_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """이미지를 w×h에 채워 크롭 (비율 유지, 중앙 크롭)."""
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw = int(iw * scale + 0.5)
    nh = int(ih * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top  = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def make_gradient_overlay(width: int, height: int, max_alpha: int = 160) -> Image.Image:
    """투명→어두운 수직 그라데이션 (상단 투명, 하단 max_alpha). 1px 컬럼 → 리사이즈."""
    col = Image.new("RGBA", (1, height))
    for y in range(height):
        alpha = int(max_alpha * y / max(height - 1, 1))
        col.putpixel((0, y), (0, 0, 0, alpha))
    return col.resize((width, height), Image.NEAREST)


def wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
              max_width: int) -> list[str]:
    """텍스트를 max_width 이하로 글자 단위 줄 분할 (일본어 공백 없음 대응)."""
    lines = []
    current = ""
    for char in text:
        test = current + char
        try:
            w = draw.textlength(test, font=font)
        except Exception:
            w = len(test) * HEADLINE_FONT_SIZE * 0.7
        if w > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def draw_stroked(draw: ImageDraw.Draw, xy: tuple, text: str,
                 font: ImageFont.FreeTypeFont, fill: tuple,
                 stroke_fill: tuple = (0, 0, 0, 220),
                 stroke_width: int = STROKE_WIDTH,
                 anchor: str = "mm"):
    """외곽선 포함 텍스트 렌더링."""
    draw.text(xy, text, font=font, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill,
              anchor=anchor)


def get_direction_color(direction: str) -> tuple:
    if COLOR_MODE == "ALL_RED":
        return ACCENT_RED
    if direction == "up":
        return COLOR_UP_JP
    if direction == "down":
        return COLOR_DOWN_JP
    return ACCENT_RED


# ─────────────────────────────────────────────────────────────
# thumb_headline 수치 검증 게이트
# ─────────────────────────────────────────────────────────────

def _normalize_num_token(tok: str) -> str:
    return tok.translate(FULLWIDTH_TABLE)


def extract_num_tokens(text: str) -> set:
    return {_normalize_num_token(t) for t in THUMB_NUM_RE.findall(text)}


def validate_thumb_numerics(gpt: dict):
    """thumb_headline 수치 ↔ script+hook 수치 정합성 검증. 불일치 시 sys.exit(1)."""
    thumb = gpt.get("thumb_headline", "")
    thumb_nums = extract_num_tokens(thumb)
    if not thumb_nums:
        return  # 워드형(숫자 없음) → 검증 불필요

    ref_text = gpt.get("script", "") + " " + gpt.get("hook", "")
    ref_nums  = extract_num_tokens(ref_text)
    bad = thumb_nums - ref_nums
    if not bad:
        return  # 전체 일치 → 통과

    title = gpt.get("title", "")
    msg = (
        f"⛔ [step8] thumb_headline 수치 불일치 — 파이프라인 중단\n"
        f"영상: {title}\n"
        f"thumb_headline: {thumb}\n"
        f"불일치 수치: {sorted(bad)}\n"
        f"script+hook 수치 집합: {sorted(ref_nums)}"
    )
    tg_notify(msg)
    print(f"[오류] {msg}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# AI 배경 생성
# ─────────────────────────────────────────────────────────────

def generate_ai_bg(image_prompt: str) -> Image.Image | None:
    """OpenAI Images API로 배경 이미지 생성. 실패 시 None."""
    prompt = f"{image_prompt}. {IMG_SAFETY_SUFFIX}"
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    try:
        resp = client.images.generate(
            model=IMG_MODEL,
            prompt=prompt,
            size=IMG_SIZE,
            quality=IMG_QUALITY,
            n=1,
        )
        item = resp.data[0]
        b64  = getattr(item, "b64_json", None)
        if b64:
            img_bytes = base64.b64decode(b64)
        else:
            url = getattr(item, "url", None)
            if not url:
                raise ValueError("이미지 응답에 데이터 없음")
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            img_bytes = r.content
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    except Exception as e:
        err_str = str(e).lower()
        if any(k in err_str for k in ("insufficient_quota", "organization", "billing", "quota")):
            tg_notify(TG_IMG_API_ERROR)
        print(f"[이미지 생성 오류] {e}")
        return None


def make_fallback_bg() -> Image.Image:
    """AI 이미지 생성 실패 시 단색 다크 배경."""
    return Image.new("RGBA", (THUMB_W, THUMB_H), (27, 42, 74, 255))


# ─────────────────────────────────────────────────────────────
# 캐릭터 에셋
# ─────────────────────────────────────────────────────────────

def get_face_asset(expression: str) -> Image.Image | None:
    """표정 PNG 로드 (로컬 → 원격 다운로드 → base fallback). RGBA 반환."""
    for expr in (expression, EXPRESSION_FALLBACK):
        filename = f"mochien_{expr}.png"
        if os.path.exists(filename):
            return Image.open(filename).convert("RGBA")
        url = f"{ASSETS_BASE}/{filename}"
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            img_bytes = r.content
            with open(filename, "wb") as f:
                f.write(img_bytes)
            print(f"  캐릭터 다운로드: {filename}")
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except Exception as e:
            print(f"  [{filename}] 로드 실패: {e}")
    return None


# ─────────────────────────────────────────────────────────────
# 합성
# ─────────────────────────────────────────────────────────────

def composite_thumbnail(bg: Image.Image, gpt: dict) -> Image.Image:
    """배경 위에 레이어를 순서대로 합성해 RGBA 캔버스 반환."""
    canvas = fill_crop(bg, THUMB_W, THUMB_H).convert("RGBA")

    # ── 그라데이션 오버레이 ──────────────────────────────────
    grad_h = int(THUMB_H * 0.6)
    canvas.alpha_composite(make_gradient_overlay(THUMB_W, grad_h), (0, THUMB_H - grad_h))

    draw          = ImageDraw.Draw(canvas)
    font_hl       = get_font(HEADLINE_FONT_SIZE)
    font_ch       = get_font(CHANNEL_FONT_SIZE)

    expression     = gpt.get("expression", EXPRESSION_FALLBACK)
    if expression not in VALID_EXPRESSIONS:
        expression = EXPRESSION_FALLBACK
    direction      = gpt.get("direction", "none")
    thumb_headline = (gpt.get("thumb_headline")
                      or gpt.get("short_title", "")[:HEADLINE_FALLBACK_LEN])
    short_title    = gpt.get("short_title") or gpt.get("title", "")[:10]
    dir_color      = get_direction_color(direction)

    # ── 상단 바: short_title ────────────────────────────────
    bar_y1 = TOP_BAR_Y
    bar_y2 = TOP_BAR_Y + TOP_BAR_H
    draw.rectangle([(0, bar_y1), (THUMB_W, bar_y2)], fill=(*ACCENT_RED, 230))
    draw_stroked(draw, (THUMB_W // 2, (bar_y1 + bar_y2) // 2), short_title,
                 font_hl, (255, 255, 255, 255),
                 stroke_fill=(0, 0, 0, 200), stroke_width=3, anchor="mm")

    # 방향 화살표 (up/down 일 때 상단 바 우측)
    if direction in ("up", "down"):
        arrow = "↑" if direction == "up" else "↓"
        font_arrow = get_font(HEADLINE_FONT_SIZE + 10)
        draw_stroked(draw, (THUMB_W - 48, (bar_y1 + bar_y2) // 2), arrow,
                     font_arrow, (*dir_color, 255),
                     stroke_fill=(0, 0, 0, 200), stroke_width=3, anchor="mm")

    # ── 헤드라인: thumb_headline (최대 3줄) ──────────────────
    max_text_w  = THUMB_W - HEADLINE_PADDING_X * 2
    lines       = wrap_text(draw, thumb_headline, font_hl, max_text_w)[:3]
    line_h      = HEADLINE_FONT_SIZE + LINE_SPACING

    # 헤드라인 블록 y: top bar 하단~캐릭터 상단 사이 중앙 정렬
    headline_area_top    = bar_y2 + 40
    headline_area_bottom = FACE_BOTTOM_Y - FACE_H_THUMB - 20
    block_h              = len(lines) * line_h
    headline_y0 = max(headline_area_top,
                      (headline_area_top + headline_area_bottom - block_h) // 2)

    # ── 헤드라인 배경 박스 ─────────────────────────────────
    max_line_w = max(
        (draw.textlength(line, font=font_hl) for line in lines),
        default=0,
    )
    box_left = int(THUMB_W // 2 - max_line_w // 2 - HEADLINE_BOX_PAD_X)
    box_right = int(THUMB_W // 2 + max_line_w // 2 + HEADLINE_BOX_PAD_X)
    box_top   = headline_y0 - HEADLINE_BOX_PAD_Y
    box_bot   = headline_y0 + block_h + HEADLINE_BOX_PAD_Y
    draw.rounded_rectangle(
        [(box_left, box_top), (box_right, box_bot)],
        radius=8,
        fill=(0, 0, 0, HEADLINE_BOX_ALPHA),
    )

    for i, line in enumerate(lines):
        draw_stroked(draw, (THUMB_W // 2, headline_y0 + i * line_h),
                     line, font_hl, (255, 255, 255, 255),
                     stroke_width=STROKE_WIDTH, anchor="mt")

    # ── 채널 바 배경 ────────────────────────────────────────
    ch_overlay = Image.new("RGBA", (THUMB_W, CHANNEL_BAR_H), (27, 42, 74, 200))
    canvas.alpha_composite(ch_overlay, (0, CHANNEL_BAR_Y))

    # 채널명 텍스트 (좌측 정렬 — 캐릭터와 수평 분리)
    draw.text((CHANNEL_TEXT_X, CHANNEL_BAR_Y + CHANNEL_BAR_H // 2),
              CHANNEL_NAME, font=font_ch, fill=(255, 255, 255, 230), anchor="lm")

    # ── 캐릭터 (우하단, 채널 바와 수평 분리) ──────────────
    face = get_face_asset(expression)
    if face:
        fw, fh = face.size
        face_w = int(fw * FACE_H_THUMB / fh)
        face   = face.resize((face_w, FACE_H_THUMB), Image.LANCZOS)
        face_x = THUMB_W - face_w - FACE_MARGIN_X
        face_y = FACE_BOTTOM_Y - FACE_H_THUMB
        canvas.alpha_composite(face, (face_x, face_y))

    return canvas


# ─────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(GPT_RESULT_PATH):
        print(f"[오류] {GPT_RESULT_PATH} 없음 → 썸네일 생성 건너뜀")
        sys.exit(0)

    with open(GPT_RESULT_PATH, encoding="utf-8") as f:
        gpt = json.load(f)

    image_prompt = gpt.get("image_prompt", "japanese economy news abstract background")
    print("썸네일 생성 시작")
    print(f"  image_prompt   : {image_prompt[:60]}")
    print(f"  thumb_headline : {gpt.get('thumb_headline', '[없음 → short_title fallback]')}")
    print(f"  expression     : {gpt.get('expression', 'N/A')}")
    print(f"  direction      : {gpt.get('direction', 'N/A')}")

    validate_thumb_numerics(gpt)

    bg = generate_ai_bg(image_prompt)
    if bg is None:
        print("  AI 이미지 실패 → 단색 배경 fallback")
        bg = make_fallback_bg()

    canvas = composite_thumbnail(bg, gpt)
    canvas.convert("RGB").save(OUTPUT_FILE, "JPEG", quality=92)
    print(f"  저장: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
