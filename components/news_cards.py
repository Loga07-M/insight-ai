import html

import streamlit as st

from database import db
from services import ai_service
from services.llm_provider import LLMError, LLMNotConfigured


def card(a: dict, key: str, explain: bool = True) -> None:
    esc = html.escape
    st.markdown(
        f'<div class="card"><span class="chip">{esc(a["topic"])}</span>'
        f'<h4><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["title"])}</a></h4>'
        f'<div class="meta">{esc(a["source"])} · {esc(a["published"])}</div>'
        f'<p class="meta" style="margin-top:.5rem">{esc(a.get("summary", "")[:220])}</p></div>',
        unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 3])
    saved = db.is_saved("article", a["link"])
    if c1.button("★ Saved" if saved else "☆ Save", key=f"sv_{key}", disabled=saved):
        db.save_item("article", a["title"], a["link"], a["source"], a.get("summary", ""))
        st.rerun()
    if explain and c2.button("💡 Explain", key=f"ex_{key}"):
        st.session_state["explain_target"] = a
    c3.markdown(f'<a href="{html.escape(a["link"])}" target="_blank" rel="noopener">Read original ↗</a>', unsafe_allow_html=True)


def explanation_panel() -> None:
    a = st.session_state.get("explain_target")
    if not a:
        return
    with st.container(border=True):
        st.markdown(f"### 💡 Why it matters: {a['title']}")
        try:
            with st.spinner("Reading the article and writing a simple explanation…"):
                res = ai_service.explain_article(a)
            st.markdown(res["text"])
            c1, c2, c3 = st.columns(3)
            if c1.button("Save explanation", key="save_expl"):
                db.save_item("explanation", f"Explained: {a['title']}", a["link"], a["source"], res["text"])
                st.success("Saved to Saved Insights.")
            if c2.button("Regenerate", key="regen_expl"):
                ai_service.explain_article(a, force=True)
                st.rerun()
            if c3.button("Close", key="close_expl"):
                st.session_state.pop("explain_target"); st.rerun()
        except LLMNotConfigured as exc:
            st.warning(f"AI explanations need an LLM key. {exc}")
        except LLMError as exc:
            st.error(f"The AI provider returned an error: {exc}")
        except Exception as exc:
            st.error(f"Something went wrong while explaining this article: {type(exc).__name__}")
