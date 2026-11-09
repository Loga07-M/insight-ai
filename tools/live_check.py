"""Real API checks. Run on your PC:  python tools/live_check.py
1) Timbre v2.5 makes speech  2) Prisma v2.5 transcribes that same audio  3) LLM answers  4) RSS feeds load.
Prints PASS/FAIL honestly. Never prints your keys."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services import gnani_stt, gnani_tts, llm_provider, news_service


def step(name, fn):
    try:
        detail = fn()
        print(f"PASS  {name}: {detail}")
        return True
    except Exception as exc:
        print(f"FAIL  {name}: {config.redact(exc)}")
        return False


def main():
    results, audio = [], {}
    def tts():
        audio["wav"] = gnani_tts.synthesize("Hello. This is a test of INSIGHT AI.", "en-IN", "Kaveri")
        out = Path(config.BASE_DIR) / "data" / "live_check.wav"
        out.write_bytes(audio["wav"]); return f"{len(audio['wav'])} bytes saved to {out}"
    def stt():
        r = gnani_stt.transcribe(audio["wav"], "live_check.wav", "en-IN")
        return f"transcript = {r['transcript']!r} (model {r['model']})"
    def llm():
        return llm_provider.get_provider().chat([{"role": "user", "content": "Reply with the single word: ready"}], max_tokens=10)
    def rss():
        r = news_service.fetch_news(["Technology"], per_topic=3)
        if not r["articles"]:
            raise RuntimeError(f"0 articles retrieved; feed errors: {r['errors'][:2]}")
        return f"{len(r['articles'])} articles, {len(r['errors'])} feed errors"
    results.append(step("Gnani Timbre v2.5 (TTS)", tts))
    if "wav" in audio:
        results.append(step("Gnani Prisma v2.5 (STT)", stt))
    else:
        print("SKIP  Gnani Prisma v2.5 (STT): needs the TTS audio from the previous step"); results.append(False)
    results.append(step("LLM provider", llm))
    results.append(step("RSS news", rss))
    print("\nAll checks passed." if all(results) else "\nSome checks failed - read the messages above.")


if __name__ == "__main__":
    main()
