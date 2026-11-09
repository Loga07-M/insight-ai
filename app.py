"""INSIGHT AI - run with: streamlit run app.py"""
from pathlib import Path
import streamlit as st
import config
from components import auth_ui, dashboard, pages, sidebar
from database import db

st.set_page_config(page_title="INSIGHT AI", page_icon="✦", layout="wide", initial_sidebar_state="auto")
db.init_db()
st.markdown(f"<style>{(Path(config.BASE_DIR) / 'assets' / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# Frontend-only welcome gate. No credentials are verified or sent to a backend.
if not st.session_state.get("insight_frontend_logged_in", False):
    auth_ui.render()
    st.stop()

if not db.get_interests():
    dashboard.onboarding()
    st.stop()

ROUTES = {
    "Dashboard": dashboard.render, "Explore Topics": pages.explore, "AI Assistant": pages.assistant,
    "Daily Briefing": pages.briefing, "Podcasts": pages.podcasts, "Saved Insights": pages.saved,
    "Settings": pages.settings,
}
if "nav_to" in st.session_state:
    st.session_state["page"] = st.session_state.pop("nav_to")
ROUTES[sidebar.render()]()
