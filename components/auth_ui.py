"""Frontend-only welcome/login screen. No credentials are sent to or checked by a backend."""
import streamlit as st


def render() -> None:
    st.markdown(
        """
        <div class="login-shell">
          <div class="login-art">
            <div class="login-brand">✦ INSIGHT AI</div>
            <div class="login-orbit orbit-one"></div>
            <div class="login-orbit orbit-two"></div>
            <div class="login-art-copy">
              <span class="eyebrow">YOUR PERSONAL KNOWLEDGE SPACE</span>
              <h1>See the world<br>with fresh eyes.</h1>
              <p>Stay curious. Stay informed. Make every insight count.</p>
              <div class="login-art-pills"><span>✦ Discover</span><span>◉ Understand</span><span>♫ Listen</span></div>
            </div>
            <div class="login-spark">✧</div>
          </div>
          <div class="login-form-panel">
            <div class="login-welcome-tag">A LITTLE MORE INSIGHT, EVERY DAY</div>
            <h2>Welcome back <span>👋</span></h2>
            <p class="login-subtitle">Sign in to continue your journey of discovery.</p>
        """,
        unsafe_allow_html=True,
    )
    with st.form("frontend_login", clear_on_submit=False):
        name = st.text_input("Your name", placeholder="How should we greet you?")
        email = st.text_input("Email address", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Let's explore  →", use_container_width=True)
    if submitted:
        if not name.strip() or not email.strip() or not password:
            st.warning("Please fill in all three fields to continue.")
        elif "@" not in email or "." not in email.split("@")[-1]:
            st.warning("Please enter a valid email address.")
        else:
            # Frontend-only demo gate: no authentication or credential verification occurs.
            st.session_state["insight_frontend_logged_in"] = True
            st.session_state["insight_display_name"] = name.strip().split()[0]
            st.rerun()
    st.markdown(
        '<div class="login-footnote">✦ Your next insight is just around the corner.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
