import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from database import db
from services import ai_service, llm_provider


class FakeProvider:
    def __init__(self, reply): self.reply, self.calls = reply, []
    def chat(self, messages, **kw): self.calls.append(messages); return self.reply


class AITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config.DB_PATH = Path(self.tmp.name) / "t.db"; db.init_db()

    def tearDown(self): self.tmp.cleanup()

    def test_missing_llm_key_is_reported_not_simulated(self):
        with patch.dict("os.environ", {"LLM_API_KEY": ""}):
            with self.assertRaises(llm_provider.LLMNotConfigured):
                llm_provider.get_provider()

    def test_explanation_flags_thin_content_and_cites_source(self):
        art = {"title": "T", "link": "http://x", "source": "BBC", "published": "today", "summary": "short"}
        fake = FakeProvider("## What happened?\n- [From article] x")
        with patch("services.ai_service.get_provider", return_value=fake), \
             patch("services.news_service.fetch_article_text", return_value=("", "Page text unavailable")):
            res = ai_service.explain_article(art)
        self.assertIn("Limited information", res["text"])
        self.assertIn("http://x", res["text"])
        self.assertIn("RSS headline and summary only", fake.calls[0][1]["content"])
        self.assertTrue(ai_service.explain_article(art)["cached"])            # served from SQLite cache

    def test_answer_returns_only_sources_the_model_cited(self):
        feed = [{"title": "Chip export rules tighten", "link": "http://c", "source": "Reuters", "published": "d",
                 "summary": "chip export", "topic": "Technology", "published_ts": 1}]
        fake = FakeProvider("Rules tightened [1].")
        with patch("services.ai_service.get_provider", return_value=fake), \
             patch("services.news_service.search_news", return_value=[]):
            out = ai_service.answer_question("chip export rules?", feed, [])
        self.assertEqual(out["sources"][0]["link"], "http://c")

    def test_provider_error_redacts_key(self):
        import requests
        with patch.dict("os.environ", {"LLM_API_KEY": "LLMSECRET", "LLM_PROVIDER": "openai_compatible"}):
            r = type("R", (), {"status_code": 401, "text": "bad key LLMSECRET", "json": lambda s: {}})()
            with patch.object(requests, "post", return_value=r):
                with self.assertRaises(llm_provider.LLMError) as cm:
                    llm_provider.get_provider().chat([{"role": "user", "content": "x"}])
        self.assertNotIn("LLMSECRET", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
