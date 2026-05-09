import sys
import feedparser
import json

sys.stdout.reconfigure(encoding="utf-8")

RSS_URL = "https://www3.nhk.or.jp/rss/news/cat6.xml"
OUTPUT_FILE = "article.json"


def fetch_rss():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        raise Exception("RSS 피드에서 기사를 가져오지 못했습니다.")
    entry = feed.entries[0]
    title = entry.title
    url = entry.link
    # NHK RSS의 summary 필드가 기사 본문 요약을 포함
    body = entry.get("summary", "") or entry.get("description", "")
    return title, url, body


def main():
    print("=== NHK cat6 RSS 수집 ===")
    title, url, body = fetch_rss()
    print(f"제목 : {title}")
    print(f"URL  : {url}")
    print(f"본문 ({len(body)}자):\n{body}")

    result = {
        "title": title,
        "url": url,
        "article_body": body
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{OUTPUT_FILE} 저장 완료")
    return result


if __name__ == "__main__":
    main()
