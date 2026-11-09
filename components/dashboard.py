import re
from collections import Counter

import streamlit as st

import config
from components import data, news_cards
from database import db
from services.llm_provider import llm_available


def interest_picker(key: str, preset: list[str]) -> tuple[list[str], list[str]]:
    base = st.multiselect("Choose your interests", config.INTERESTS,
                          default=[t for t in preset if t in config.INTERESTS], key=f"{key}_base")
    existing_custom = ", ".join(t for t in preset if t not in config.INTERESTS)
    raw = st.text_input("Add custom topics (comma separated)", value=existing_custom, key=f"{key}_custom",
                        placeholder="e.g. Quantum computing, Cricket, EV batteries")
    return base, [t for t in raw.split(",") if t.strip()]


def onboarding() -> None:
    st.markdown('<div class="hero"><h1>Welcome to INSIGHT AI ✦</h1>'
                '<p>Pick what you care about. We will explain the news that matters to you, in simple words.</p></div>',
                unsafe_allow_html=True)
    base, custom = interest_picker("onb", [])
    if st.button("Start my feed", type="primary"):
        if not base and not custom:
            st.warning("Pick at least one interest to continue.")
        else:
            db.set_interests(base, custom)
            st.rerun()


def _trending(articles: list[dict], n: int = 8) -> list[str]:
    stop = set("this that with from after about their have will says said over into more than what when"
               " amid new year news live india world could would first".split())
    words = Counter(w for a in articles for w in set(re.findall(r"[A-Za-z][A-Za-z\-]{3,}", a["title"].lower()))
                    if w not in stop)
    return [w for w, c in words.most_common(n) if c > 1]


def render_news_status(res: dict) -> None:
    if res["errors"]:
        with st.expander(f"⚠️ {len(res['errors'])} feed(s) were unavailable"):
            for e in res["errors"]:
                st.write("•", e)
    if not res["articles"]:
        st.error("No articles could be retrieved. Check your internet connection and press Refresh.")


def render() -> None:
    interests = db.get_interests()
    display_name = st.session_state.get("insight_display_name", "Explorer")
    st.markdown(
        f'<div class="hero"><h1>Hello, {display_name}! ✨</h1>'
        f'<p>Make today an insightful day. “Curiosity turns information into inspiration.”</p>'
        f'<p style="margin-top:.65rem"><b>YOUR DAILY DISCOVERY SPACE</b> &nbsp;·&nbsp; Personalised for: {", ".join(interests)}</p></div>',
        unsafe_allow_html=True)
    top = st.columns([4, 1])
    if top[1].button("🔄 Refresh", use_container_width=True):
        data.refresh(); st.rerun()
    with st.spinner("Collecting the latest stories…"):
        res = data.load_news(tuple(interests))
    arts = res["articles"]
    render_news_status(res)
    if not arts:
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("Fresh stories", len(arts), "Across your interests")
    m2.metric("Topics you follow", len(interests), "Your personal mix")
    m3.metric("Your AI space", "Ready", "Ask, explore and listen")
    news_cards.explanation_panel()

    st.subheader("✦ Today's highlights")
    for i, a in enumerate(arts[:3]):
        news_cards.card(a, f"top{i}")

    trend = _trending(arts)
    if trend:
        st.subheader("🔥 Trending topics")
        st.markdown("".join(f'<span class="chip">{t}</span>' for t in trend), unsafe_allow_html=True)

    st.subheader("💡 More stories worth your time")
    st.caption("Tap 💡 Explain on any story for what happened, why, impact and what could come next.")
    for i, a in enumerate(arts[3:9]):
        news_cards.card(a, f"feed{i}")

    st.subheader("🤖 Your AI companion")
    q = st.text_input("Ask anything about today's news or any topic", key="dash_q")
    if st.button("Ask", key="dash_ask") and q.strip():
        st.session_state["pending_question"] = q.strip()
        st.session_state["nav_to"] = "AI Assistant"
        st.rerun()

    st.subheader("🎧 Your daily audio moment")
    if st.button("🎧 Open Daily Briefing"):
        st.session_state["nav_to"] = "Daily Briefing"; st.rerun()
    if not llm_available():
        st.info("Add LLM_API_KEY to your .env to enable AI explanations, chat and briefings.")
