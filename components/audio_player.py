import streamlit as st


def play(audio: bytes | None, error: str = "", label: str = "") -> None:
    """Show a player only when real audio bytes exist; otherwise show the real error."""
    if audio:
        if label:
            st.caption(label)
        st.audio(audio, format="audio/wav")
        st.download_button("⬇ Download audio", audio, file_name="insight_ai.wav", mime="audio/wav",
                           key=f"dl_{hash(audio[:2000]) & 0xffffff}")
    elif error:
        st.error(f"Audio could not be generated: {error}")
