"""Podcast discovery: Apple's public iTunes Search API finds shows; each show's own RSS feed
supplies description and latest episodes. We only link to the original listening pages."""
import time
from datetime import datetime, timezone
from calendar import timegm

import requests

from services.news_service import HEADERS, clean_summary

SEARCH_TERMS = {
    "Artificial Intelligence": "artificial intelligence", "Technology": "technology news",
    "Business": "business news", "Startups": "startups founders", "Science": "science",
    "Space": "space astronomy", "Finance": "personal finance markets", "Education": "education learning",
    "Sports": "sports", "Environment": "environment climate", "World affairs": "world affairs geopolitics",
    "Health innovation": "health innovation medicine",
}


def search_shows(interest: str, limit: int = 4) -> list[dict]:
    term = SEARCH_TERMS.get(interest, interest)
    r = requests.get("https://itunes.apple.com/search",
                     params={"term": term, "media": "podcast", "entity": "podcast", "limit": limit},
                     headers=HEADERS, timeout=12)
    r.raise_for_status()
    return [x for x in r.json().get("results", []) if x.get("feedUrl")]


def latest_episode(feed_url: str) -> dict:
    import feedparser
    resp = requests.get(feed_url, headers=HEADERS, timeout=12)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    desc = clean_summary(feed.feed.get("subtitle") or feed.feed.get("summary") or "")[:400]
    ep = feed.entries[0] if feed.entries else None
    out = {"description": desc, "episode_title": "", "episode_date": "", "episode_link": ""}
    if ep:
        ts = ep.get("published_parsed")
        out.update(episode_title=clean_summary(ep.get("title", "")), episode_link=ep.get("link", ""),
                   episode_date=datetime.fromtimestamp(timegm(ts), timezone.utc).strftime("%d %b %Y") if ts else "")
    return out


def discover(interests: list[str], per_topic: int = 3) -> dict:
    shows, errors, seen = [], [], set()
    for topic in interests:
        try:
            found = search_shows(topic, limit=per_topic + 2)
        except Exception as exc:
            errors.append(f"{topic}: podcast directory unavailable ({type(exc).__name__})")
            continue
        added = 0
        for s in found:
            if s["feedUrl"] in seen or added >= per_topic:
                continue
            seen.add(s["feedUrl"])
            item = {"title": s.get("collectionName", ""), "publisher": s.get("artistName", ""),
                    "topic": topic, "show_link": s.get("collectionViewUrl", ""),
                    "description": "", "episode_title": "", "episode_date": "", "episode_link": ""}
            try:
                item.update(latest_episode(s["feedUrl"]))
            except Exception:
                item["description"] = "(Episode details unavailable - open the show page.)"
            item["listen_link"] = item["episode_link"] or item["show_link"]
            shows.append(item)
            added += 1
    return {"shows": shows, "errors": errors, "fetched_at": time.time()}
