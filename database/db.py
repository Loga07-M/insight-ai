"""SQLite persistence: interests, saved items, chat history, settings, explanation cache."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config


@contextmanager
def _conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS interests(
                topic TEXT PRIMARY KEY, is_custom INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS saved_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,            -- 'article' or 'explanation'
                title TEXT NOT NULL, url TEXT, source TEXT, content TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(kind, url));
            CREATE TABLE IF NOT EXISTS chat_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL, content TEXT NOT NULL,
                sources TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS explanations(
                url TEXT PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL);
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- interests ----
def get_interests() -> list[str]:
    with _conn() as c:
        return [r["topic"] for r in c.execute("SELECT topic FROM interests ORDER BY rowid")]


def set_interests(topics: list[str], custom: list[str] | None = None) -> None:
    custom = [t.strip() for t in (custom or []) if t.strip()]
    clean = [t.strip() for t in topics if t.strip()]
    with _conn() as c:
        c.execute("DELETE FROM interests")
        seen = set()
        for t in clean + custom:
            if t.lower() in seen:
                continue
            seen.add(t.lower())
            c.execute("INSERT INTO interests(topic,is_custom) VALUES(?,?)",
                      (t, 0 if t in config.INTERESTS else 1))


# ---- saved items ----
def save_item(kind: str, title: str, url: str, source: str = "", content: str = "") -> bool:
    """Returns True if newly saved, False if it already existed."""
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO saved_items(kind,title,url,source,content,created_at) "
            "VALUES(?,?,?,?,?,?)", (kind, title, url, source, content, _now()))
        return cur.rowcount > 0


def list_saved(query: str = "") -> list[dict]:
    with _conn() as c:
        if query.strip():
            like = f"%{query.strip()}%"
            rows = c.execute(
                "SELECT * FROM saved_items WHERE title LIKE ? OR content LIKE ? OR source LIKE ? "
                "ORDER BY id DESC", (like, like, like))
        else:
            rows = c.execute("SELECT * FROM saved_items ORDER BY id DESC")
        return [dict(r) for r in rows]


def is_saved(kind: str, url: str) -> bool:
    with _conn() as c:
        return c.execute("SELECT 1 FROM saved_items WHERE kind=? AND url=?", (kind, url)).fetchone() is not None


def delete_saved(item_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM saved_items WHERE id=?", (item_id,))


# ---- chat ----
def add_chat(role: str, content: str, sources: list[dict] | None = None) -> None:
    with _conn() as c:
        c.execute("INSERT INTO chat_history(role,content,sources,created_at) VALUES(?,?,?,?)",
                  (role, content, json.dumps(sources or []), _now()))


def get_chat(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM (SELECT * FROM chat_history ORDER BY id DESC LIMIT ?) ORDER BY id",
                         (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d["sources"] or "[]")
        out.append(d)
    return out


def clear_chat() -> None:
    with _conn() as c:
        c.execute("DELETE FROM chat_history")


# ---- settings ----
def get_setting(key: str, default: str = "") -> str:
    with _conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# ---- explanation cache ----
def get_cached_explanation(url: str) -> str | None:
    with _conn() as c:
        r = c.execute("SELECT content FROM explanations WHERE url=?", (url,)).fetchone()
        return r["content"] if r else None


def cache_explanation(url: str, content: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO explanations(url,content,created_at) VALUES(?,?,?)",
                  (url, content, _now()))
