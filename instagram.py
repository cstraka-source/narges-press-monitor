"""
Instagram profile monitor for Narges Rashidi.

Uses Instagram's public web profile API (no login required for public accounts).
Fetches her recent posts: captions, engagement, post type.
"""
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DB_PATH = Path(__file__).parent / "press_narges.db"

_IG_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "x-ig-app-id": "936619743392459",
    "Accept": "*/*",
    "Accept-Language": "en-GB,en;q=0.9",
}

_IG_SCHEMA = """
CREATE TABLE IF NOT EXISTS instagram_posts (
    id           TEXT PRIMARY KEY,
    url          TEXT UNIQUE,
    date         TEXT,
    caption      TEXT,
    likes        INTEGER,
    comments     INTEGER,
    media_type   TEXT,
    video_views  INTEGER,
    notion_id    TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""


def init_ig_table(conn: sqlite3.Connection) -> None:
    conn.executescript(_IG_SCHEMA)
    conn.commit()


def fetch_instagram_posts(username: str, days_back: int = 14) -> list[dict]:
    """Fetch recent posts from a public Instagram profile via web API."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    try:
        resp = requests.get(
            "https://www.instagram.com/api/v1/users/web_profile_info/",
            params={"username": username},
            headers=_IG_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        user = resp.json()["data"]["user"]
    except Exception as e:
        print(f"  Instagram: could not load profile @{username} — {e}")
        return []

    edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
    posts = []
    for edge in edges:
        node = edge.get("node", {})
        ts = node.get("taken_at_timestamp", 0)
        pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        if pub and pub < cutoff:
            continue
        shortcode = node.get("shortcode", "")
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        caption = (caption_edges[0]["node"]["text"] if caption_edges else "")[:1000]
        typename = node.get("__typename", "GraphImage")
        media_type = typename.replace("Graph", "")  # Image / Video / Sidecar
        posts.append({
            "id": shortcode,
            "url": f"https://www.instagram.com/p/{shortcode}/",
            "date": pub.strftime("%Y-%m-%d") if pub else "",
            "caption": caption,
            "likes": node.get("edge_liked_by", {}).get("count", 0) or 0,
            "comments": node.get("edge_media_to_comment", {}).get("count", 0) or 0,
            "media_type": media_type,
            "video_views": node.get("video_view_count") if node.get("is_video") else None,
        })
    return posts


def upsert_ig_post(conn: sqlite3.Connection, post: dict) -> bool:
    cur = conn.execute("SELECT id FROM instagram_posts WHERE id = ?", (post["id"],))
    is_new = cur.fetchone() is None
    conn.execute("""
        INSERT INTO instagram_posts (id, url, date, caption, likes, comments, media_type, video_views)
        VALUES (:id, :url, :date, :caption, :likes, :comments, :media_type, :video_views)
        ON CONFLICT(id) DO UPDATE SET
            likes       = excluded.likes,
            comments    = excluded.comments,
            video_views = COALESCE(excluded.video_views, video_views)
    """, post)
    conn.commit()
    return is_new


def push_ig_posts_to_notion(
    conn: sqlite3.Connection,
    token: str,
    database_id: str,
) -> None:
    """Push new Instagram posts as rows into the press Notion database."""
    cur = conn.execute("SELECT * FROM instagram_posts WHERE notion_id IS NULL")
    cols = [d[0] for d in cur.description]
    unpushed = [dict(zip(cols, row)) for row in cur.fetchall()]
    if not unpushed:
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    pushed = errors = 0
    for post in unpushed:
        caption_preview = (post.get("caption") or "")[:100]
        title = f"[Instagram] {caption_preview or post['date']}"
        props = {
            "Title": {"title": [{"text": {"content": title[:2000]}}]},
            "Source": {"rich_text": [{"text": {"content": "Instagram @nargesrashidi"}}]},
            "Platform": {"select": {"name": "Online"}},
            "Type": {"select": {"name": "Mention"}},
            "Tier": {"select": {"name": "Tier 1"}},
            "URL": {"url": post["url"]},
            "Snippet": {"rich_text": [{"text": {"content": (post.get("caption") or "")[:2000]}}]},
        }
        if post.get("date"):
            props["Date"] = {"date": {"start": post["date"]}}
        if post.get("likes") is not None:
            props["Likes"] = {"number": post["likes"]}
        if post.get("comments") is not None:
            props["Views"] = {"number": post["comments"]}

        try:
            resp = requests.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json={"parent": {"database_id": database_id}, "properties": props},
                timeout=15,
            )
            resp.raise_for_status()
            notion_id = resp.json()["id"]
            conn.execute(
                "UPDATE instagram_posts SET notion_id = ? WHERE id = ?",
                (notion_id, post["id"]),
            )
            conn.commit()
            pushed += 1
        except Exception as e:
            print(f"    ! Instagram Notion push error: {e}")
            errors += 1

    print(f"  Instagram → Notion: {pushed} pushed, {errors} errors")
