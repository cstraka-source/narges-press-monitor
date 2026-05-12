"""SQLite store — local source of truth, deduplication layer."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "press_narges.db"

def score_sentiment(text: str) -> str:
    """Return 'positive', 'negative', or 'neutral'."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        score = SentimentIntensityAnalyzer().polarity_scores(text)["compound"]
        if score >= 0.05:
            return "positive"
        if score <= -0.05:
            return "negative"
        return "neutral"
    except Exception:
        return "neutral"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS press (
    id           TEXT PRIMARY KEY,
    title        TEXT,
    url          TEXT UNIQUE,
    source       TEXT,
    date         TEXT,
    snippet      TEXT,
    full_text    TEXT,
    key_quotes   TEXT,          -- JSON array of strings
    platform     TEXT,
    type         TEXT,
    tier         TEXT,
    views        INTEGER,
    likes        INTEGER,
    sentiment    TEXT,          -- positive / neutral / negative
    notion_id    TEXT,          -- set once pushed to Notion
    created_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_press_date ON press(date DESC);
CREATE INDEX IF NOT EXISTS idx_press_tier ON press(tier);
"""


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def upsert_item(conn: sqlite3.Connection, item: dict) -> bool:
    """Insert or update a press item. Returns True if it was a new row."""
    cur = conn.execute("SELECT id FROM press WHERE id = ?", (item["id"],))
    is_new = cur.fetchone() is None
    sentiment = item.get("sentiment") or score_sentiment(
        (item.get("title") or "") + " " + (item.get("snippet") or "")
    )
    conn.execute(
        """
        INSERT INTO press
            (id, title, url, source, date, snippet, full_text, key_quotes,
             platform, type, tier, views, likes, sentiment)
        VALUES
            (:id, :title, :url, :source, :date, :snippet, :full_text, :key_quotes,
             :platform, :type, :tier, :views, :likes, :sentiment)
        ON CONFLICT(id) DO UPDATE SET
            views      = COALESCE(excluded.views, views),
            likes      = COALESCE(excluded.likes, likes),
            snippet    = COALESCE(NULLIF(excluded.snippet, ''), snippet),
            full_text  = COALESCE(NULLIF(excluded.full_text, ''), full_text),
            key_quotes = COALESCE(NULLIF(excluded.key_quotes, '[]'), key_quotes),
            sentiment  = COALESCE(excluded.sentiment, sentiment)
        """,
        {
            **item,
            "full_text": item.get("full_text") or "",
            "key_quotes": json.dumps(item.get("key_quotes") or []),
            "sentiment": sentiment,
        },
    )
    conn.commit()
    return is_new


def set_notion_id(conn: sqlite3.Connection, item_id: str, notion_id: str) -> None:
    conn.execute("UPDATE press SET notion_id = ? WHERE id = ?", (notion_id, item_id))
    conn.commit()


def get_unpushed(conn: sqlite3.Connection) -> list[dict]:
    """Return all rows that haven't been pushed to Notion yet."""
    cur = conn.execute("SELECT * FROM press WHERE notion_id IS NULL ORDER BY date DESC")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def export_parquet(conn: sqlite3.Connection, out_dir: Path = None) -> None:
    """Export press + instagram tables to Parquet files for the cloud dashboard."""
    import pandas as pd
    out_dir = out_dir or (Path(__file__).parent / "data")
    out_dir.mkdir(exist_ok=True)
    df = pd.read_sql_query("SELECT * FROM press ORDER BY date DESC", conn)
    df.to_parquet(out_dir / "press.parquet", index=False)
    try:
        ig = pd.read_sql_query("SELECT * FROM instagram_posts ORDER BY date DESC", conn)
        ig.to_parquet(out_dir / "instagram.parquet", index=False)
    except Exception:
        pass


def export_csv(conn: sqlite3.Connection, path: str) -> None:
    import csv
    cur = conn.execute(
        "SELECT date, source, tier, type, platform, title, url, views, likes, snippet "
        "FROM press ORDER BY date DESC"
    )
    cols = [d[0] for d in cur.description]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(dict(zip(cols, row)) for row in cur.fetchall())
