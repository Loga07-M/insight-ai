import streamlit as st

from database import db

PAGES = ["Dashboard", "Explore Topics", "AI Assistant", "Daily Briefing", "Podcasts", "Saved Insights", "Settings"]


def render() -> str:
    with st.sidebar:
        st.markdown("## ✦ INSIGHT AI")
        st.caption("Understand the world, faster.")
        st.markdown(f"### Hey, {st.session_state.get('insight_display_name', 'Explorer')} ✨")
        page = st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
        st.divider()
        interests = db.get_interests()
        st.caption("YOUR INTERESTS")
        st.markdown("".join(f'<span class="chip on">{t}</span>' for t in interests) or "_None selected_",
                    unsafe_allow_html=True)
        st.divider()
        if st.button("↩ Log out", use_container_width=True):
            st.session_state["insight_frontend_logged_in"] = False
            st.session_state.pop("insight_display_name", None)
            st.rerun()
    return page
