import unittest

from services import news_service as ns
from services.briefing_service import select_stories


def art(title, link, topic="AI", ts=1):
    return {"title": title, "link": link, "topic": topic, "source": "S", "summary": "", "published_ts": ts, "published": "x"}


class NewsTests(unittest.TestCase):
    def test_dedupe_url_title_and_near_duplicates(self):
        items = [
            art("OpenAI launches new model today", "http://a"),
            art("OpenAI launches new model today", "http://b"),       # same title
            art("OpenAI launches new model today!", "http://c"),      # punctuation only
            art("OpenAI launches a new model today", "http://d"),     # near duplicate
            art("Totally different story about rockets", "http://a"), # same URL
            art("ISRO plans lunar sample mission", "http://e"),
            art("", "http://f"),                                      # no title dropped
            art("No link", ""),                                       # no link dropped (must have source link)
        ]
        out = ns.dedupe(items)
        self.assertEqual([a["link"] for a in out], ["http://a", "http://e"])

    def test_google_title_split(self):
        self.assertEqual(ns._split_source("Big news here - Reuters", "Google News"), ("Big news here", "Reuters"))
        self.assertEqual(ns._split_source("No publisher", "Feed"), ("No publisher", "Feed"))

    def test_google_url_encoding(self):
        self.assertIn("q=Artificial+Intelligence+when%3A3d", ns.google_news_url("Artificial Intelligence"))

    def test_html_text_extraction(self):
        page = "<html><nav><p>menu menu menu menu menu menu menu menu menu menu menu</p></nav><script>var x=1</script>" \
               "<p>" + "Real article paragraph with enough words to count. " + "</p></html>"
        text = ns.html_to_text(page)
        self.assertIn("Real article paragraph", text)
        self.assertNotIn("menu", text)
        self.assertNotIn("var x", text)

    def test_briefing_round_robin(self):
        arts = [art(f"A{i}", f"a{i}", "AI") for i in range(3)] + [art(f"S{i}", f"s{i}", "Space") for i in range(3)]
        picks = select_stories(arts, ["AI", "Space"], max_items=4)
        self.assertEqual([p["title"] for p in picks], ["A0", "S0", "A1", "S1"])


if __name__ == "__main__":
    unittest.main()
