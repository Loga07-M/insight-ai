import tempfile
import unittest
from pathlib import Path

import config
from database import db


class DBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config.DB_PATH = Path(self.tmp.name) / "t.db"
        db.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_interests_persist_and_custom(self):
        db.set_interests(["Space", "Science"], ["Quantum computing", "space"])
        self.assertEqual(db.get_interests(), ["Space", "Science", "Quantum computing"])  # case-insensitive dedupe
        db.init_db()  # simulates restart
        self.assertEqual(len(db.get_interests()), 3)

    def test_saved_items_crud_search(self):
        self.assertTrue(db.save_item("article", "Chip news", "http://a", "BBC", "semiconductor"))
        self.assertFalse(db.save_item("article", "Chip news", "http://a"))   # no duplicates
        db.save_item("explanation", "Explained: Chip news", "http://a", "BBC", "because supply")
        self.assertEqual(len(db.list_saved()), 2)
        self.assertEqual(len(db.list_saved("semiconductor")), 1)
        db.delete_saved(db.list_saved()[0]["id"])
        self.assertEqual(len(db.list_saved()), 1)

    def test_chat_and_settings(self):
        db.add_chat("user", "hi"); db.add_chat("assistant", "hello", [{"title": "t", "source": "s", "link": "l"}])
        chat = db.get_chat()
        self.assertEqual([m["role"] for m in chat], ["user", "assistant"])
        self.assertEqual(chat[1]["sources"][0]["link"], "l")
        db.clear_chat(); self.assertEqual(db.get_chat(), [])
        db.set_setting("language", "Tamil"); db.set_setting("language", "Hindi")
        self.assertEqual(db.get_setting("language"), "Hindi")

    def test_explanation_cache(self):
        self.assertIsNone(db.get_cached_explanation("u"))
        db.cache_explanation("u", "text"); self.assertEqual(db.get_cached_explanation("u"), "text")


if __name__ == "__main__":
    unittest.main()
