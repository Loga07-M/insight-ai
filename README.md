# INSIGHT AI

Personalised AI news explainer: RSS news -> grounded AI explanations -> chat (text + voice) -> spoken daily briefing.
Speech: **Gnani Prisma v2.5** (STT) and **Timbre v2.5** (TTS). Reasoning: **any LLM** you configure (separate key).

## 1. One-time setup (Windows 11, VS Code terminal, inside the INSIGHT_AI folder)

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again.

## 2. Keys (.env)
Your existing `.env` is untouched by this project. Make sure it contains (no quotes, no spaces around `=`):
```
GNANI_API_KEY=your_gnani_key
LLM_API_KEY=your_llm_key
```
Optional: `LLM_PROVIDER` (`openai_compatible` or `anthropic`), `LLM_BASE_URL`, `LLM_MODEL`.
The Gnani key only powers speech. **Chat, explanations and briefings also need `LLM_API_KEY`** - without it the app
says so and does not fake answers. Examples:
- OpenAI: defaults work. Set `LLM_MODEL` to a model your account can use.
- Groq: `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=<a Groq model>`
- Anthropic: `LLM_PROVIDER=anthropic`, `LLM_MODEL=<a Claude model>`

## 3. Run
```powershell
streamlit run app.py
```
Opens at http://localhost:8501. First launch asks for your interests.

## 4. Test everything
```powershell
python -m unittest discover -s tests -v     # 26 offline tests (database, news, Gnani requests, AI logic)
python tools/live_check.py                  # REAL calls: TTS -> STT round trip, LLM, RSS
```
`live_check.py` generates speech with Timbre, sends that same audio to Prisma, and prints what was transcribed.

Manual UI tests:
- **STT:** AI Assistant -> "Ask with your voice" -> record (max 30 s) or upload -> Transcribe -> edit text -> Send.
- **TTS:** AI Assistant -> press 🔊 Listen under an answer; or Daily Briefing -> pick language/voice -> Generate.
- **AI answers:** ask "What is happening in AI today?"; answers cite sources as numbered links.
- **Daily briefing:** Daily Briefing -> Generate; you get a script, an audio player, and the stories used.

## 5. Notes and limits
- STT: 30 s max per clip (official REST limit); WAV/MP3/OGG/FLAC/AAC/M4A. Your Gnani account may allow only
  1 request at a time - the app retries once on a 429.
- TTS: each Timbre v2.5 voice has one preferred language; the voice list follows the language you choose.
  Long scripts are split into sentences, synthesised in pieces and joined into one WAV.
- Google News links redirect through Google, so full article text often cannot be fetched. In that case the
  explanation is built from the headline + feed summary and is clearly labelled "Limited information".
  Publisher feeds (BBC, The Hindu, TechCrunch, etc.) link directly and give fuller text.
- Publisher feed URLs can change; a dead feed is skipped and listed under "feeds unavailable".
- Podcasts use Apple's public search API for discovery and each show's own RSS feed for details. No audio is copied.

## 6. Deployment
**Streamlit Community Cloud (free):** push to a private GitHub repo (`.env` is git-ignored), create the app on
share.streamlit.io, and paste `GNANI_API_KEY` / `LLM_API_KEY` into the app's *Secrets* as `KEY = "value"`.
Note: SQLite on that host resets on redeploy; use a VM/Docker with a mounted `data/` folder for permanent storage.
**Docker/VM:** `pip install -r requirements.txt`, set the two env vars, run `streamlit run app.py --server.port 8501`.

## Structure
app.py, config.py | services/ (news, llm_provider, ai, gnani_stt, gnani_tts, briefing, podcast) |
database/db.py | components/ (sidebar, dashboard, pages, news_cards, audio_player, data) | assets/style.css |
tests/ | tools/live_check.py


LIVE LINK 

https://insight-aigit-34kquguabvzkae7guzky7j.streamlit.app/
