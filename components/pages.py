"""Explore, Assistant, Briefing, Podcasts, Saved and Settings pages."""
import html
import os

import streamlit as st

import config
from components import audio_player, dashboard, data, news_cards
from database import db
from services import ai_service, briefing_service, gnani_stt, gnani_tts
from services.llm_provider import LLMError, LLMNotConfigured, llm_available


def _lang_voice(prefix: str) -> tuple[str, str]:
    c1, c2 = st.columns(2)
    default_lang = db.get_setting("language", "English")
    names = list(config.LANGUAGES)
    lang = c1.selectbox("Language", names, index=names.index(default_lang) if default_lang in names else 0,
                        key=f"{prefix}_lang")
    code = config.LANGUAGES[lang]
    voice = c2.selectbox("Voice (Gnani Timbre v2.5)", config.TTS_VOICES[code], key=f"{prefix}_voice_{code}")
    return code, voice


# ---------------- Explore ----------------
def explore() -> None:
    st.title("Explore Topics")
    interests = db.get_interests()
    st.caption("Edit what you follow, then browse each topic.")
    with st.expander("✏️ Edit my interests"):
        base, custom = dashboard.interest_picker("edit", interests)
        if st.button("Save interests", key="save_int"):
            if base or custom:
                db.set_interests(base, custom); data.refresh(); st.success("Interests updated."); st.rerun()
            else:
                st.warning("Select at least one interest.")
    if not interests:
        return
    res = data.load_news(tuple(interests))
    dashboard.render_news_status(res)
    news_cards.explanation_panel()
    tabs = st.tabs(interests)
    for tab, topic in zip(tabs, interests):
        with tab:
            items = [a for a in res["articles"] if a["topic"] == topic][:8]
            if not items:
                st.info("No stories found for this topic right now.")
            for i, a in enumerate(items):
                news_cards.card(a, f"x_{topic}_{i}")


# ---------------- Assistant ----------------
def _ask(question: str) -> None:
    db.add_chat("user", question)
    feed = data.load_news(tuple(db.get_interests()))["articles"]
    hist = db.get_chat()[:-1]
    try:
        res = ai_service.answer_question(question, feed, hist)
        db.add_chat("assistant", res["answer"], res["sources"])
    except LLMNotConfigured as exc:
        db.add_chat("assistant", f"⚠️ I can't answer yet. {exc}")
    except LLMError as exc:
        db.add_chat("assistant", f"⚠️ The AI provider returned an error: {exc}")
    except Exception as exc:
        db.add_chat("assistant", f"⚠️ Something went wrong ({type(exc).__name__}). Please try again.")


def _voice_input() -> None:
    with st.expander("🎙️ Ask with your voice (Gnani Prisma v2.5)"):
        lang = st.selectbox("Spoken language", list(config.LANGUAGES), key="stt_lang")
        code = config.LANGUAGES[lang]
        st.caption(f"Record up to {config.STT_MAX_SECONDS} seconds, or upload WAV/MP3/OGG/FLAC/AAC/M4A.")
        rec = st.audio_input("Record your question", key="stt_rec") if hasattr(st, "audio_input") else None
        up = st.file_uploader("…or upload audio", type=["wav", "mp3", "ogg", "flac", "aac", "m4a"], key="stt_up")
        src = rec or up
        if src is not None and st.button("Transcribe", key="stt_go"):
            with st.spinner("Transcribing with Gnani Prisma v2.5…"):
                try:
                    name = getattr(src, "name", "") or "recording.wav"
                    out = gnani_stt.transcribe(src.getvalue(), name, code)
                    st.session_state["stt_text"] = out["transcript"]
                    if not out["transcript"]:
                        st.warning("No speech was detected. Try speaking closer to the microphone.")
                except gnani_stt.STTError as exc:
                    st.error(f"Transcription failed: {exc}")
        if "stt_text" in st.session_state:
            edited = st.text_area("Recognised text (edit if needed)", st.session_state["stt_text"], key="stt_edit")
            if st.button("Send to INSIGHT AI", key="stt_send") and edited.strip():
                st.session_state["pending_question"] = edited.strip()
                st.session_state.pop("stt_text", None)
                st.rerun()


def assistant() -> None:
    st.title("Ask INSIGHT AI")
    if not llm_available():
        st.warning("LLM_API_KEY is not set in your .env file, so answers are disabled. Voice transcription still works.")
    top = st.columns([4, 1])
    if top[1].button("🗑 Clear chat", use_container_width=True):
        db.clear_chat(); st.rerun()
    _voice_input()

    q = st.session_state.pop("pending_question", None)
    typed = st.chat_input("Ask about news, AI, business, science…")
    q = q or typed
    if q:
        with st.spinner("Thinking…"):
            _ask(q)

    for i, m in enumerate(db.get_chat()):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["sources"]:
                st.caption("Sources: " + " · ".join(f"[{s['source']}: {s['title'][:60]}]({s['link']})" for s in m["sources"]))
            if m["role"] == "assistant" and not m["content"].startswith("⚠️"):
                if st.button("🔊 Listen", key=f"tts_{i}"):
                    code = config.LANGUAGES.get(db.get_setting("language", "English"), "en-IN")
                    try:
                        with st.spinner("Generating speech with Gnani Timbre v2.5…"):
                            st.session_state[f"aud_{i}"] = gnani_tts.synthesize(m["content"][:1500], code)
                    except gnani_tts.TTSError as exc:
                        st.error(f"Audio could not be generated: {exc}")
                audio_player.play(st.session_state.get(f"aud_{i}"))


# ---------------- Briefing ----------------
def briefing() -> None:
    st.title("Your Daily Briefing")
    interests = db.get_interests()
    st.caption("A short, spoken news summary built from today's stories on your interests.")
    code, voice = _lang_voice("brief")
    if not llm_available():
        st.warning("LLM_API_KEY is missing, so the briefing script cannot be written.")
    if st.button("🎧 Generate / regenerate briefing", type="primary", disabled=not llm_available()):
        with st.spinner("Choosing stories, writing the script and recording audio…"):
            try:
                arts = data.load_news(tuple(interests))["articles"]
                st.session_state["briefing"] = briefing_service.make_briefing(arts, interests, code, voice)
            except ValueError as exc:
                st.error(str(exc))
            except LLMError as exc:
                st.error(f"The AI provider returned an error: {exc}")
            except Exception as exc:
                st.error(f"Could not build the briefing ({type(exc).__name__}).")
    b = st.session_state.get("briefing")
    if b:
        audio_player.play(b["audio"], b["audio_error"], "Narrated by Gnani Timbre v2.5")
        st.markdown("### Script")
        st.write(b["script"])
        st.markdown("### Stories covered")
        for s in b["stories"]:
            st.markdown(f"- [{s['title']}]({s['link']}) — {s['source']}")


# ---------------- Podcasts ----------------
def podcasts() -> None:
    st.title("Podcast Discovery")
    interests = db.get_interests()
    st.caption("Shows matched to your interests. We only link to the original listening pages.")
    with st.spinner("Finding podcasts…"):
        res = data.load_podcasts(tuple(interests))
    for e in res["errors"]:
        st.warning(e)
    if not res["shows"]:
        st.info("No podcasts found right now. Try Refresh in the Dashboard, or check your connection.")
    esc = html.escape
    for p in res["shows"]:
        st.markdown(
            f'<div class="card"><span class="chip">{esc(p["topic"])}</span><h4>{esc(p["title"])}</h4>'
            f'<div class="meta">by {esc(p["publisher"])}</div><p class="meta">{esc(p["description"])}</p>'
            f'<div class="meta">Latest: <b>{esc(p["episode_title"] or "n/a")}</b> {esc(p["episode_date"])}</div></div>',
            unsafe_allow_html=True)
        if p["listen_link"]:
            st.markdown(f"[Listen on original page ↗]({p['listen_link']})")


# ---------------- Saved ----------------
def saved() -> None:
    st.title("Saved Insights")
    q = st.text_input("🔍 Search saved items", key="saved_q")
    items = db.list_saved(q)
    if not items:
        st.info("Nothing saved yet. Use ☆ Save on a story or 'Save explanation'.")
    for it in items:
        with st.container(border=True):
            st.markdown(f"**{it['title']}**  \n<span class='meta'>{it['kind']} · {it['source'] or ''} · {it['created_at'][:10]}</span>",
                        unsafe_allow_html=True)
            if it["kind"] == "explanation":
                with st.expander("Read explanation"):
                    st.markdown(it["content"])
            elif it["content"]:
                st.caption(it["content"][:240])
            c1, c2 = st.columns([1, 1])
            if it["url"]:
                c1.markdown(f"[Open original ↗]({it['url']})")
            if c2.button("Remove", key=f"rm_{it['id']}"):
                db.delete_saved(it["id"]); st.rerun()


# ---------------- Settings ----------------
def settings() -> None:
    st.title("Settings")
    names = list(config.LANGUAGES)
    cur = db.get_setting("language", "English")
    lang = st.selectbox("Default audio language", names, index=names.index(cur) if cur in names else 0)
    if st.button("Save language"):
        db.set_setting("language", lang); st.success("Saved.")
    st.subheader("Connection status")
    st.write("Gnani (speech):", "✅ key found" if config.gnani_key() else "❌ GNANI_API_KEY missing")
    s = config.llm_settings()
    st.write("LLM (reasoning):", f"✅ key found · {s['provider']} · {s['model']}" if s["api_key"] else "❌ LLM_API_KEY missing")
    st.caption("Keys are read from your local .env file and never shown here.")
    if st.button("Clear news cache"):
        data.refresh(); st.success("Cache cleared.")
