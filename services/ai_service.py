"""Grounded news explanations and the conversational assistant (reasoning via llm_provider)."""
import re

from database import db
from services import news_service
from services.llm_provider import get_provider

EXPLAIN_SYSTEM = """You are INSIGHT AI, a careful news explainer for ordinary readers and beginners.
You are given ONE article's retrieved content. Rules:
- Base everything on the provided content. Never invent facts, numbers, dates or quotations.
- If a detail is not in the content, say it is not stated. If the content is thin, say so plainly in the first section.
- Mark each bullet with [From article] for facts stated in the content, or [Interpretation] for your own reasoning.
- Use simple language. Short sentences. Explain jargon.
- Under WHAT COULD HAPPEN NEXT, give only clearly labelled possibilities ('could', 'might'), never predictions as fact.
Output exactly these markdown sections, in this order:
## What happened?
## Background
## Why it matters
## Impact on us
(Students, Businesses, Technology, Society - one bullet each where relevant)
## What could happen next?
"""

CHAT_SYSTEM = """You are INSIGHT AI, a friendly assistant that explains news, technology, AI, business, startups,
science and world affairs to ordinary people.
- When SOURCES are provided, ground news claims in them and cite with [1], [2] matching the numbers. Do not invent facts, statistics or quotes.
- If sources do not cover the question, say so, then give general background labelled as general knowledge, not as breaking news.
- For general knowledge questions without sources, answer clearly and say if you are unsure.
- Keep answers clear and beginner-friendly. Reply in the language the user wrote in."""


def explain_article(article: dict, force: bool = False) -> dict:
    """Returns {'text','limitation','cached'}. Raises LLMNotConfigured / LLMError."""
    url = article["link"]
    if not force:
        cached = db.get_cached_explanation(url)
        if cached:
            return {"text": cached, "limitation": "", "cached": True}
    body, status = news_service.fetch_article_text(url)
    basis = "full article text" if body else "RSS headline and summary only"
    content = body or article.get("summary", "")
    limitation = ""
    if not body:
        limitation = (f"{status}. This explanation uses only the headline and feed summary, "
                      "so details may be missing. Open the original article for full facts.")
    user = (f"Source: {article['source']}\nHeadline: {article['title']}\nPublished: {article['published']}\n"
            f"Content basis: {basis}\n\nCONTENT:\n{content or '(no content available)'}")
    text = get_provider().chat(
        [{"role": "system", "content": EXPLAIN_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=1400)
    if limitation:
        text = f"> ⚠️ **Limited information:** {limitation}\n\n{text}"
    text += f"\n\n---\n*Source: [{article['source']}]({url})*"
    db.cache_explanation(url, text)
    return {"text": text, "limitation": limitation, "cached": False}


_STOP = set("the a an and or of to in on for is are was were what why how who when about with this that it as at by be do does did can could would should tell me explain latest news".split())


def _kw(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 2}


def find_sources(question: str, feed_articles: list[dict], limit: int = 5) -> list[dict]:
    """Relevant articles: matches from the user's current feed + a live Google News search."""
    q = _kw(question)
    scored = []
    for a in feed_articles:
        overlap = len(q & _kw(a["title"] + " " + a.get("summary", "")))
        if overlap:
            scored.append((overlap, a))
    picks = [a for _, a in sorted(scored, key=lambda x: -x[0])[:3]]
    if q:
        picks = news_service.dedupe(picks + news_service.search_news(" ".join(sorted(q))[:80], limit=4))
    return picks[:limit]


def answer_question(question: str, feed_articles: list[dict], history: list[dict]) -> dict:
    """Returns {'answer','sources'}. Raises LLMNotConfigured / LLMError."""
    sources = find_sources(question, feed_articles)
    ctx = ""
    if sources:
        ctx = "SOURCES:\n" + "\n".join(
            f"[{i}] {s['title']} ({s['source']}, {s['published']}): {s.get('summary', '')[:400]}"
            for i, s in enumerate(sources, 1))
    interests = ", ".join(db.get_interests()) or "not set"
    msgs = [{"role": "system", "content": CHAT_SYSTEM + f"\nUser interests: {interests}."}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history[-8:]]
    msgs.append({"role": "user", "content": f"{question}\n\n{ctx}" if ctx else question})
    answer = get_provider().chat(msgs, max_tokens=1200)
    used = [s for i, s in enumerate(sources, 1) if f"[{i}]" in answer] or []
    return {"answer": answer, "sources": [{"title": s["title"], "source": s["source"], "link": s["link"]} for s in used]}
