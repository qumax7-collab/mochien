"""롱폼 → 워드프레스 자동 발행

필요한 .env 변수:
  WP_URL           https://mochien.com
  WP_USERNAME      qumax7
  WP_APP_PASSWORD  (발급한 Application Password)
"""
import sys
import json
import os
import re
import datetime
import subprocess
import argparse
import requests

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ===== 상수 =====
LONG_SCRIPT_FILE      = "long_script.json"
LONG_YOUTUBE_URL_FILE = "long_youtube_url.txt"
LONG_BG_MAIN          = "long_bg_main.mp4"
LONG_THUMB_FILE       = "long_thumb.jpg"
WP_CATEGORY_ID        = 2         # 経済常識 (slug: economy)
LONGFORM_PUBLISH_HOUR = 21        # JST
JST                   = datetime.timezone(datetime.timedelta(hours=9))
RETRY_COUNT           = 2
THUMB_WIDTH           = 1280
THUMB_HEIGHT          = 720
META_DESC_MAX_CHARS   = 120

SENTENCES_PER_PARA = 3            # ① 한 <p>에 묶을 문장 수

AD_SLOT_1 = "<!-- AD_SLOT_1 -->"  # ② intro 첫 문단 직후
AD_SLOT_2 = "<!-- AD_SLOT_2 -->"  # ② issue1~2 사이
AD_SLOT_3 = "<!-- AD_SLOT_3 -->"  # ② まとめ 뒤

VIDEO_OUTRO_PAT = re.compile(      # ③ 영상 전용 멘트
    r'(以上、モチエンがお伝えしました[！!]|チャンネル登録お願いします[！!])\s*'
)
BLOG_OUTRO_TMPL   = (              # ③ 블로그용 마무리 (YouTube URL 있을 때)
    '<p>この内容は<a href="{url}">動画</a>でもご覧いただけます。'
    'チャンネル「モチエンの経済の話」もぜひご覧ください。</p>'
)
BLOG_OUTRO_NO_URL = (              # ③ 블로그용 마무리 (URL 없을 때)
    '<p>この内容は動画でもご覧いただけます。'
    'チャンネル「モチエンの経済の話」もぜひご覧ください。</p>'
)

ISSUE_BG_FILES    = {              # ④ issue 배경 영상 → 본문 이미지
    "issue1": "long_bg_issue1.mp4",
    "issue2": "long_bg_issue2.mp4",
}
ISSUE_THUMB_FILES = {
    "issue1": "long_thumb_issue1.jpg",
    "issue2": "long_thumb_issue2.jpg",
}

FURIGANA_PAT   = re.compile(r'[（(][^）)]*[）)]')  # ⑤ excerpt 후리가나 제거
OPEN_BRACKETS  = set('「『（(')                     # ① 句点 분할 시 내부 무시용
CLOSE_BRACKETS = set('」』）)')

WP_URL      = os.getenv("WP_URL", "").rstrip("/")
WP_USER     = os.getenv("WP_USERNAME", "")
WP_PASS     = os.getenv("WP_APP_PASSWORD", "")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


# ─────────────────────────────────────────
# 텔레그램 알림
# ─────────────────────────────────────────

def tg_error(msg: str):
    """long7 실패 시 텔레그램 에러 알림."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": f"⚠️ long7_wordpress 실패\n{msg}",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception:
        pass


# ─────────────────────────────────────────
# 썸네일 추출 (featured_media 전용 — 기존 유지)
# ─────────────────────────────────────────

def extract_thumbnail() -> bool:
    """long_bg_main.mp4 첫 프레임 → long_thumb.jpg. 실패 시 False."""
    if not os.path.exists(LONG_BG_MAIN):
        print(f"  [경고] {LONG_BG_MAIN} 없음 — 썸네일 없이 발행")
        return False
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", LONG_BG_MAIN,
                "-frames:v", "1",
                "-vf", f"scale={THUMB_WIDTH}:{THUMB_HEIGHT}:force_original_aspect_ratio=increase,"
                       f"crop={THUMB_WIDTH}:{THUMB_HEIGHT}",
                "-q:v", "3",
                LONG_THUMB_FILE,
            ],
            capture_output=True, check=True,
        )
        print(f"  썸네일 추출 완료: {LONG_THUMB_FILE}")
        return True
    except Exception as e:
        print(f"  [경고] 썸네일 추출 실패: {e}")
        return False


def extract_frame(src: str, dest: str) -> bool:
    """범용 MP4 첫 프레임 → JPG 추출 (issue 본문 이미지용). 실패 시 False."""
    if not os.path.exists(src):
        return False
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", src,
                "-frames:v", "1",
                "-vf", f"scale={THUMB_WIDTH}:{THUMB_HEIGHT}:force_original_aspect_ratio=increase,"
                       f"crop={THUMB_WIDTH}:{THUMB_HEIGHT}",
                "-q:v", "3",
                dest,
            ],
            capture_output=True, check=True,
        )
        print(f"  프레임 추출 완료: {dest}")
        return True
    except Exception as e:
        print(f"  [경고] 프레임 추출 실패 ({src}): {e}")
        return False


# ─────────────────────────────────────────
# WP 미디어 업로드
# ─────────────────────────────────────────

def upload_media(slug: str, filepath: str = LONG_THUMB_FILE) -> tuple:
    """이미지 파일을 WP 미디어에 업로드 → (media_id, source_url). 실패 시 (None, "")."""
    if not os.path.exists(filepath):
        return None, ""
    try:
        with open(filepath, "rb") as f:
            img_data = f.read()
        resp = requests.post(
            f"{WP_URL}/wp-json/wp/v2/media",
            auth=(WP_USER, WP_PASS),
            headers={
                "Content-Disposition": f'attachment; filename="{slug}.jpg"',
                "Content-Type": "image/jpeg",
            },
            data=img_data,
            timeout=30,
        )
        resp.raise_for_status()
        rdata      = resp.json()
        media_id   = rdata["id"]
        source_url = rdata.get("source_url", "")
        print(f"  미디어 업로드 완료: ID={media_id}")
        return media_id, source_url
    except Exception as e:
        print(f"  [경고] 미디어 업로드 실패 ({filepath}): {e}")
        return None, ""


# ─────────────────────────────────────────
# WP 태그
# ─────────────────────────────────────────

def get_or_create_tag(name: str):
    """WP 태그 ID 취득. 없으면 신규 생성. 실패 시 None."""
    try:
        resp = requests.get(
            f"{WP_URL}/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 5},
            auth=(WP_USER, WP_PASS),
            timeout=10,
        )
        if resp.ok:
            for tag in resp.json():
                if tag.get("name") == name:
                    return tag["id"]
        # 없으면 신규 생성
        resp2 = requests.post(
            f"{WP_URL}/wp-json/wp/v2/tags",
            auth=(WP_USER, WP_PASS),
            json={"name": name},
            timeout=10,
        )
        if resp2.ok:
            return resp2.json().get("id")
    except Exception as e:
        print(f"  [경고] 태그 취득/생성 실패 ({name}): {e}")
    return None


# ─────────────────────────────────────────
# 본문 HTML 생성
# ─────────────────────────────────────────

def split_japanese(text: str) -> list:
    """일본어 句点(。)으로 문장 분할. 「」『』（）() 안의 。는 분할하지 않음."""
    sentences = []
    buf = []
    depth = 0
    for ch in text:
        if ch in OPEN_BRACKETS:
            depth += 1
        elif ch in CLOSE_BRACKETS:
            depth = max(0, depth - 1)
        buf.append(ch)
        if ch == '。' and depth == 0:   # 。= U+3002
            s = ''.join(buf).strip()
            if s:
                sentences.append(s)
            buf = []
    remainder = ''.join(buf).strip()
    if remainder:
        sentences.append(remainder)
    return sentences


def strip_citations(text: str) -> str:
    """운영자 검수용 출처 태그 제거."""
    text = re.sub(r'\[출처[^\]]*\]', '', text)
    text = re.sub(r'\[出典[^\]]*\]', '', text)
    return text.strip()


def strip_video_phrases(text: str) -> str:
    """영상 전용 멘트 제거 (블로그 본문에 부적합한 문구)."""
    return VIDEO_OUTRO_PAT.sub('', text).strip()


def insert_ad_after_first_para(html_block: str, marker: str) -> str:
    """HTML 블록의 첫 </p> 직후에 광고 마커 삽입."""
    idx = html_block.find("</p>")
    if idx == -1:
        return html_block + "\n" + marker
    return html_block[:idx + 4] + "\n" + marker + html_block[idx + 4:]


def to_paragraphs(text: str) -> str:
    """출처·영상 멘트 제거 → 句点 분할 → SENTENCES_PER_PARA 문장씩 <p>로 묶음."""
    text = strip_citations(text)
    text = strip_video_phrases(text)
    sentences = split_japanese(text)
    if not sentences:
        return ''
    groups = [sentences[i:i + SENTENCES_PER_PARA]
              for i in range(0, len(sentences), SENTENCES_PER_PARA)]
    # 마지막 그룹이 1문장이면 직전 그룹에 흡수
    if len(groups) >= 2 and len(groups[-1]) == 1:
        groups[-2].extend(groups.pop())
    paras = [''.join(g) for g in groups]
    return '\n'.join(f'<p>{p}</p>' for p in paras)


def build_html_body(data: dict, yt_url, issue_img_urls: dict = None) -> str:
    """
    블로그 본문 HTML 생성.
    issue_img_urls: {"issue1": "https://...", "issue2": "https://..."} — 없으면 {}
    """
    if issue_img_urls is None:
        issue_img_urls = {}

    intro_script = data["intro"]["script"]
    issue1       = data["issues"][0]
    issue2       = data["issues"][1]
    outro_script = data["outro"]["script"]

    # YouTube embed 블록
    if yt_url and "watch?v=" in yt_url:
        vid_id = yt_url.split("watch?v=")[-1].split("&")[0]
        embed_block = (
            f'<figure class="wp-block-embed is-type-video">'
            f'<div class="wp-block-embed__wrapper">'
            f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{vid_id}" '
            f'frameborder="0" allowfullscreen></iframe>'
            f'</div></figure>'
        )
    else:
        embed_block = "<!-- YouTube URL未設定 -->"

    # ① intro: 첫 문단 직후에 AD_SLOT_1 삽입
    intro_html = to_paragraphs(intro_script)
    intro_html = insert_ad_after_first_para(intro_html, AD_SLOT_1)

    # ④ issue 이미지 블록 (URL 없으면 빈 문자열)
    def img_block(key: str, title: str) -> str:
        url = issue_img_urls.get(key, "")
        if not url:
            return ""
        return (f'<figure class="wp-block-image">'
                f'<img src="{url}" alt="{title}"/>'
                f'</figure>\n')

    # ③ 블로그용 마무리 문구
    blog_outro = (
        BLOG_OUTRO_TMPL.format(url=yt_url) if yt_url else BLOG_OUTRO_NO_URL
    )

    html = (
        f"<h2>今日のニュース</h2>\n"
        f"{intro_html}\n\n"
        f"{embed_block}\n\n"
        f"<h2>{issue1['title']}</h2>\n"
        f"{img_block('issue1', issue1['title'])}"
        f"{to_paragraphs(issue1['script'])}\n\n"
        f"{AD_SLOT_2}\n\n"
        f"<h2>{issue2['title']}</h2>\n"
        f"{img_block('issue2', issue2['title'])}"
        f"{to_paragraphs(issue2['script'])}\n\n"
        f"<h2>まとめ</h2>\n"
        f"{to_paragraphs(outro_script)}\n"
        f"{blog_outro}\n"
        f"{AD_SLOT_3}\n"
    )
    return html


# ─────────────────────────────────────────
# 발행 시각
# ─────────────────────────────────────────

def get_publish_at() -> str:
    """당일 21:00 JST. 이미 지난 경우 익일로."""
    now = datetime.datetime.now(JST)
    target = now.replace(hour=LONGFORM_PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return target.isoformat()


# ─────────────────────────────────────────
# slug 유니크 처리
# ─────────────────────────────────────────

def get_unique_slug(base_slug: str) -> str:
    """slug 충돌 시 -2/-3... 을 붙여 유일하게 만든다."""
    try:
        resp = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            params={"slug": base_slug, "per_page": 1},
            auth=(WP_USER, WP_PASS),
            timeout=10,
        )
        if resp.ok and resp.json():
            for n in range(2, 20):
                candidate = f"{base_slug}-{n}"
                r2 = requests.get(
                    f"{WP_URL}/wp-json/wp/v2/posts",
                    params={"slug": candidate, "per_page": 1},
                    auth=(WP_USER, WP_PASS),
                    timeout=10,
                )
                if r2.ok and not r2.json():
                    return candidate
    except Exception as e:
        print(f"  [경고] slug 확인 실패: {e}")
    return base_slug


# ─────────────────────────────────────────
# WP 글 발행
# ─────────────────────────────────────────

def publish_post(title: str, content: str, slug: str, media_id,
                 meta_desc: str, publish_at: str,
                 tag_ids: list = None, focus_kw: str = ""):
    """WP REST API로 예약 발행. 반환: 포스트 URL (실패 시 None)."""
    post_body: dict = {
        "title":      title,
        "content":    content,
        "slug":       slug,
        "status":     "future",
        "date":       publish_at,
        "categories": [WP_CATEGORY_ID],
        "excerpt":    meta_desc,
        "meta": {
            "_yoast_wpseo_metadesc": meta_desc,
            "_yoast_wpseo_focuskw":  focus_kw,
        },
    }
    if media_id:
        post_body["featured_media"] = media_id
    if tag_ids:
        post_body["tags"] = tag_ids

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts",
                auth=(WP_USER, WP_PASS),
                json=post_body,
                timeout=30,
            )
            resp.raise_for_status()
            post_url = resp.json().get("link", "")
            print(f"  WP 발행 완료: {post_url}")
            return post_url
        except Exception as e:
            print(f"  [오류] WP 발행 시도 {attempt}/{RETRY_COUNT} 실패: {e}")
            if attempt == RETRY_COUNT:
                return None
    return None


# ─────────────────────────────────────────
# --update 모드: 기존 글 조회·갱신
# ─────────────────────────────────────────

def find_post_by_slug(slug: str):
    """slug로 WP 포스트 ID 조회 (예약 포함). 없거나 실패 시 None.
    status=any 로 future(예약) 글도 검색 대상에 포함."""
    try:
        resp = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            params={"slug": slug, "status": "any", "per_page": 1},
            auth=(WP_USER, WP_PASS),
            timeout=10,
        )
        if resp.ok and resp.json():
            return resp.json()[0]["id"]
    except Exception as e:
        print(f"  [경고] slug 조회 실패: {e}")
    return None


def update_post(post_id: int, content: str, excerpt: str,
                tag_ids: list, meta: dict):
    """기존 포스트 PUT 업데이트.
    slug / status / date / featured_media 는 body 미포함 → WP가 기존값 보존."""
    post_body = {
        "content": content,
        "excerpt": excerpt,
        "meta":    meta,
    }
    if tag_ids:
        post_body["tags"] = tag_ids

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.post(
                f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
                auth=(WP_USER, WP_PASS),
                json=post_body,
                timeout=30,
            )
            resp.raise_for_status()
            post_url = resp.json().get("link", "")
            print(f"  WP 업데이트 완료: {post_url}")
            return post_url
        except Exception as e:
            print(f"  [오류] WP 업데이트 시도 {attempt}/{RETRY_COUNT} 실패: {e}")
            if attempt == RETRY_COUNT:
                return None
    return None


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="롱폼 워드프레스 발행")
    parser.add_argument("--update", action="store_true",
                        help="slug로 기존 글 조회 후 PUT 업데이트 (신규 발행 아님)")
    args = parser.parse_args()

    if not WP_URL or not WP_USER or not WP_PASS:
        msg = ".env에 WP_URL / WP_USERNAME / WP_APP_PASSWORD를 입력하세요."
        print(f"[오류] {msg}")
        tg_error(msg)
        sys.exit(0)

    if not os.path.exists(LONG_SCRIPT_FILE):
        msg = f"{LONG_SCRIPT_FILE} 없음. long6가 완료된 후 실행하세요."
        print(f"[오류] {msg}")
        tg_error(msg)
        sys.exit(0)

    with open(LONG_SCRIPT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # YouTube URL
    yt_url = None
    if os.path.exists(LONG_YOUTUBE_URL_FILE):
        yt_url = open(LONG_YOUTUBE_URL_FILE, encoding="utf-8").read().strip()
        print(f"  YouTube URL: {yt_url}")
    else:
        print(f"  [경고] {LONG_YOUTUBE_URL_FILE} 없음 — embed 없이 발행")

    title     = data.get("title", "モチエン経済解説")
    base_slug = data.get("_slug_keyword", "economy")

    # ⑤ excerpt: 후리가나 제거 후 120자
    intro_text = data.get("intro", {}).get("script", "")
    meta_desc  = FURIGANA_PAT.sub('', intro_text)[:META_DESC_MAX_CHARS].rstrip()

    print(f"\n제목: {title}")
    print(f"slug 기반: {base_slug}")

    # ── --update 모드 ─────────────────────────────────────────
    if args.update:
        post_id = find_post_by_slug(base_slug)
        if post_id is None:
            msg = f"--update: '{base_slug}' 글을 WP에서 찾을 수 없음 (slug 확인 또는 신규 발행 사용)"
            print(f"[오류] {msg}")
            tg_error(msg)
            sys.exit(0)
        print(f"  업데이트 대상: post_id={post_id}")

        # issue 이미지 (featured_media 재추출 없음)
        issue_img_urls = {}
        for key in ("issue1", "issue2"):
            src_mp4  = ISSUE_BG_FILES[key]
            dest_jpg = ISSUE_THUMB_FILES[key]
            if extract_frame(src_mp4, dest_jpg):
                _, src_url = upload_media(f"{base_slug}-{key}", dest_jpg)
                if src_url:
                    issue_img_urls[key] = src_url
        print(f"  본문 이미지: {list(issue_img_urls.keys())}")

        # 태그
        hashtags = data.get("hashtags", [])
        if isinstance(hashtags, str):
            hashtags = hashtags.split()
        tag_names = [h.lstrip('#') for h in hashtags if h.strip('#')]
        tag_ids   = [tid for name in tag_names
                     if (tid := get_or_create_tag(name)) is not None]
        print(f"  태그: {tag_names} → IDs {tag_ids}")

        # HTML 본문
        html_content = build_html_body(data, yt_url, issue_img_urls)

        # PUT 업데이트
        meta = {
            "_yoast_wpseo_metadesc": meta_desc,
            "_yoast_wpseo_focuskw":  base_slug,
        }
        post_url = update_post(post_id, html_content, meta_desc, tag_ids, meta)

        if post_url:
            print(f"\n✅ 블로그 업데이트 완료: {post_url}")
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": TELEGRAM_CHAT_ID,
                            "text": f"📝 블로그 업데이트 완료\n제목: {title}\nURL: {post_url}",
                            "parse_mode": "HTML",
                        },
                        timeout=10,
                    )
                except Exception:
                    pass
        else:
            msg = f"WP 업데이트 최종 실패 (재시도 {RETRY_COUNT}회)\n제목: {title}"
            print(f"\n[오류] {msg}")
            tg_error(msg)
            sys.exit(0)
        return   # 신규 발행 로직 진입 방지

    # ── 기존 신규 발행 로직 (변경 없음) ──────────────────────
    # featured_media 썸네일 (기존 처리 유지)
    has_thumb = extract_thumbnail()

    # slug 유니크 처리
    slug = get_unique_slug(base_slug)
    if slug != base_slug:
        print(f"  slug 충돌 → {slug}")

    # featured_media 업로드
    media_id, _ = upload_media(slug) if has_thumb else (None, "")

    # ④ issue 본문 이미지: 배경 영상 첫 프레임 추출 → 업로드
    issue_img_urls = {}
    for key in ("issue1", "issue2"):
        src_mp4  = ISSUE_BG_FILES[key]
        dest_jpg = ISSUE_THUMB_FILES[key]
        if extract_frame(src_mp4, dest_jpg):
            _, src_url = upload_media(f"{slug}-{key}", dest_jpg)
            if src_url:
                issue_img_urls[key] = src_url
    print(f"  본문 이미지: {list(issue_img_urls.keys())}")

    # ⑤ 태그: hashtags 필드에서 # 제거 → WP 태그 ID 취득/생성
    hashtags = data.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    tag_names = [h.lstrip('#') for h in hashtags if h.strip('#')]
    tag_ids   = [tid for name in tag_names
                 if (tid := get_or_create_tag(name)) is not None]
    print(f"  태그: {tag_names} → IDs {tag_ids}")

    # HTML 본문 생성
    html_content = build_html_body(data, yt_url, issue_img_urls)

    # 예약 시각
    publish_at = get_publish_at()
    print(f"  예약: {publish_at}")

    # 발행
    post_url = publish_post(
        title, html_content, slug, media_id, meta_desc, publish_at,
        tag_ids=tag_ids, focus_kw=base_slug,
    )

    if post_url:
        print(f"\n✅ 블로그 발행 완료: {post_url}")
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": TELEGRAM_CHAT_ID,
                        "text": f"📝 블로그 예약 완료\n제목: {title}\nURL: {post_url}\n예약: {publish_at[:16]} JST",
                        "parse_mode": "HTML",
                    },
                    timeout=10,
                )
            except Exception:
                pass
    else:
        msg = f"WP 발행 최종 실패 (재시도 {RETRY_COUNT}회)\n제목: {title}"
        print(f"\n[오류] {msg}")
        tg_error(msg)
        sys.exit(0)


if __name__ == "__main__":
    main()
