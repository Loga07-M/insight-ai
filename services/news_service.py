"""Real RSS news collection (Google News RSS + publisher feeds), dedup, article text fetch."""
import html
import re
import time
from calendar import timegm
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote_plus

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsightAI/1.0; +personal-news-assistant)"}
FEED_TIMEOUT = 12

# Publisher RSS feeds by topic. Any feed that is down is skipped with a warning.
PUBLISHER_FEEDS = {
    "Artificial Intelligence": ["https://www.technologyreview.com/feed/", "https://techcrunch.com/category/artificial-intelligence/feed/"],
    "Technology": ["http://feeds.bbci.co.uk/news/technology/rss.xml", "https://feeds.arstechnica.com/arstechnica/index",
                   "https://www.thehindu.com/sci-tech/technology/feeder/default.rss"],
    "Business": ["http://feeds.bbci.co.uk/news/business/rss.xml", "https://www.thehindu.com/business/feeder/default.rss"],
    "Startups": ["https://techcrunch.com/category/startups/feed/"],
    "Science": ["https://www.sciencedaily.com/rss/all.xml", "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"],
    "Space": ["https://www.nasa.gov/feed/", "https://www.space.com/feeds/all"],
    "Finance": ["https://www.thehindu.com/business/Economy/feeder/default.rss"],
    "Education": ["http://feeds.bbci.co.uk/news/education/rss.xml", "https://www.thehindu.com/education/feeder/default.rss"],
    "Sports": ["http://feeds.bbci.co.uk/sport/rss.xml", "https://www.thehindu.com/sport/feeder/default.rss"],
    "Environment": ["https://www.theguardian.com/environment/rss", "https://news.mongabay.com/feed/"],
    "World affairs": ["http://feeds.bbci.co.uk/news/world/rss.xml", "https://www.thehindu.com/news/international/feeder/default.rss"],
    "Health innovation": ["http://feeds.bbci.co.uk/news/health/rss.xml"],
}


def google_news_url(query: str, region: str = "IN") -> str:
    return (f"https://news.google.com/rss/search?q={quote_plus(query + ' when:3d')}"
            f"&hl=en-{region}&gl={region}&ceid={region}:en")


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip, self._in_p = [], 0, False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag == "p":
            self._in_p = True

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag == "p":
            self._in_p = False
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_p and not self._skip and data.strip():
            self.parts.append(data.strip() + " ")


def html_to_text(raw_html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(raw_html)
    except Exception:
        pass
    paras = [x.strip() for x in "".join(p.parts).split("\n") if len(x.strip()) > 40]
    return "\n".join(paras)


def clean_summary(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _split_source(title: str, fallback: str) -> tuple[str, str]:
    """Google News titles look like 'Headline - Publisher'."""
    if " - " in title:
        head, _, pub = title.rpartition(" - ")
        if head and 0 < len(pub) < 60:
            return head.strip(), pub.strip()
    return title.strip(), fallback


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def _tokens(t: str) -> set[str]:
    return {w for w in _norm_title(t).split() if len(w) > 3}


def dedupe(articles: list[dict]) -> list[dict]:
    """Drop duplicates by URL, exact normalised title, and near-identical titles (Jaccard >= 0.7)."""
    seen_urls, seen_titles, kept, kept_tokens = set(), set(), [], []
    for a in articles:
        url, nt = a.get("link", ""), _norm_title(a.get("title", ""))
        if not url or not nt or url in seen_urls or nt in seen_titles:
            continue
        tk = _tokens(a["title"])
        if tk and any(len(tk & o) / len(tk | o) >= 0.7 for o in kept_tokens):
            continue
        seen_urls.add(url); seen_titles.add(nt); kept.append(a); kept_tokens.append(tk)
    return kept


def parse_feed(url: str, topic: str, limit: int = 12) -> list[dict]:
    """Fetch one feed. Raises on network/parse failure so callers can report it."""
    import feedparser  # imported lazily so unit tests of other helpers don't need it

    resp = requests.get(url, headers=HEADERS, timeout=FEED_TIMEOUT)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError("feed could not be parsed")
    feed_name = clean_summary(feed.feed.get("title", "")) or url.split("/")[2]
    out = []
    for e in feed.entries[:limit]:
        title, source = _split_source(clean_summary(e.get("title", "")), feed_name)
        if "source" in e and e.source.get("title"):
            source = e.source["title"]
        ts = e.get("published_parsed") or e.get("updated_parsed")
        out.append({
            "title": title, "link": e.get("link", ""), "source": source, "topic": topic,
            "summary": clean_summary(e.get("summary", ""))[:600],
            "published_ts": timegm(ts) if ts else 0,
            "published": datetime.fromtimestamp(timegm(ts), timezone.utc).strftime("%d %b %Y, %H:%M UTC") if ts else "Date unavailable",
        })
    return out


def fetch_news(interests: list[str], per_topic: int = 8) -> dict:
    """Returns {'articles': [...], 'errors': [...]}. Never fabricates items."""
    articles, errors = [], []
    for topic in interests:
        urls = [google_news_url(topic)] + PUBLISHER_FEEDS.get(topic, [])
        for url in urls:
            try:
                articles += parse_feed(url, topic, limit=per_topic)
            except Exception as exc:  # unavailable feed: record, keep going
                host = url.split("/")[2]
                errors.append(f"{topic}: {host} unavailable ({type(exc).__name__})")
    articles = dedupe(sorted(articles, key=lambda a: a["published_ts"], reverse=True))
    return {"articles": articles, "errors": errors, "fetched_at": time.time()}


def search_news(query: str, limit: int = 6) -> list[dict]:
    """Ad-hoc Google News search used by the assistant."""
    try:
        return dedupe(parse_feed(google_news_url(query), "search", limit=limit))[:limit]
    except Exception:
        return []


def fetch_article_text(url: str, max_chars: int = 6000) -> tuple[str, str]:
    """Best-effort full text. Returns (text, status). Google News redirect links often
    cannot be resolved without JavaScript, in which case text is empty."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=FEED_TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        if "html" not in r.headers.get("Content-Type", "html"):
            return "", "Not an HTML page"
        text = html_to_text(r.text)
        if len(text) < 300:
            return "", "Page text unavailable (paywall, JavaScript page or redirect)"
        return text[:max_chars], "Full article text retrieved"
    except Exception as exc:
        return "", f"Could not fetch article ({type(exc).__name__})"
