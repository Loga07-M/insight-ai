"""Cached data loaders shared by pages (15-minute cache; manual refresh clears it)."""
import streamlit as st

from services import news_service, podcast_service


@st.cache_data(ttl=900, show_spinner=False)
def load_news(interests: tuple[str, ...]) -> dict:
    return news_service.fetch_news(list(interests))


@st.cache_data(ttl=3600, show_spinner=False)
def load_podcasts(interests: tuple[str, ...]) -> dict:
    return podcast_service.discover(list(interests))


def refresh() -> None:
    st.cache_data.clear()
