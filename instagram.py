"""
Instagram monitor — full coverage via instagrapi (Instagram private API).

Fetches three streams:
  1. Narges's own posts (@nargesrashidi)
  2. Posts that tag her (@nargesrashidi tagged-in)
  3. Hashtag posts: #nargesrashidi, #prisoner951, #nazaninzaghariratcliffe
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DB_PATH = Path(__file__).parent / "press_narges.db"
SESSION_FILE = Path(__file__).parent / ".instagrapi_session.json"

_HASHTAGS = ["nargesrashidi", "prisoner951", "nazaninzaghariratcliffe", "prisoner951bafta"]
_TARGET_USERNAME = "nargesrashidi"

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
    source_type  TEXT DEFAULT 'own_post',
    username     TEXT,
    hashtag      TEXT,
    notion_id    TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""

_ALTER_STMTS = [
    "ALTER TABLE instagram_posts ADD COLUMN source_type TEXT DEFAULT 'own_post'",
    "ALTER TABLE instagram_posts ADD COLUMN username TEXT",
    "ALTER TABLE instagram_posts ADD COLUMN hashtag TEXT",
]


def init_ig_table(conn: sqlite3.Connection) -> None:
    conn.executescript(_IG_SCHEMA)
    for stmt in _ALTER_STMTS:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    conn.commit()


def _get_client(login_user: str, login_pass: str):
    try:
        from instagrapi import Client
    except ImportError:
        print("  Instagram: pip install instagrapi")
        return None

    cl = Client()
    cl.delay_range = [1, 3]

    if SESSION_FILE.exists():
        try:
            cl.load_settings(str(SESSION_FILE))
            cl.login(login_user, login_pass)
            cl.dump_settings(str(SESSION_FILE))
            return cl
        except Exception:
            SESSION_FILE.unlink(missing_ok=True)

    try:
        cl.login(login_user, login_pass)
        cl.dump_settings(str(SESSION_FILE))
        return cl
    except Exception as e:
        print(f"  Instagram: login failed — {e}")
        return None


def _media_to_dict(media, source_type: str, hashtag: str = "") -> dict:
    shortcode = getattr(media, "code", None) or str(media.pk)
    url = f"https://www.instagram.com/p/{shortcode}/"
    taken = getattr(media, "taken_at", None)
    if taken and hasattr(taken, "strftime"):
        date_str = taken.strftime("%Y-%m-%d")
    else:
        date_str = ""
    caption = str(getattr(media, "caption_text", "") or "")[:1000]
    typename = str(getattr(media, "media_type", 1))
    type_map = {"1": "Image", "2": "Video", "8": "Sidecar"}
    media_type = type_map.get(typename, "Image")
    username = ""
    user = getattr(media, "user", None)
    if user:
        username = str(getattr(user, "username", ""))
    return {
        "id": shortcode,
        "url": url,
        "date": date_str,
        "caption": caption,
        "likes": int(getattr(media, "like_count", 0) or 0),
        "comments": int(getattr(media, "comment_count", 0) or 0),
        "media_type": media_type,
        "video_views": int(getattr(media, "view_count", 0) or 0) if media_type == "Video" else None,
        "source_type": source_type,
        "username": username,
        "hashtag": hashtag,
    }


def fetch_instagram_posts(username: str, days_back: int = 14,
                          login_user: str = "", login_pass: str = "") -> list[dict]:
    """
    Full Instagram coverage:
      - own posts from @{username}
      - posts tagging @{username}
      - recent posts for key hashtags
    """
    import os
    if not login_user:
        login_user = os.getenv("INSTAGRAM_LOGIN_USER", "")
    if not login_pass:
        login_pass = os.getenv("INSTAGRAM_LOGIN_PASS", "")

    # Fallback: public web API for own posts (no login needed)
    own_posts = _fetch_own_posts_web(username, days_back)

    if not login_user or not login_pass:
        return own_posts

    cl = _get_client(login_user, login_pass)
    if not cl:
        return own_posts

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    posts: dict[str, dict] = {p["id"]: p for p in own_posts}

    # Tagged posts
    try:
        user_info = cl.user_info_by_username(username)
        user_id = user_info.pk
        tagged = cl.usertag_medias(user_id, amount=50)
        for m in tagged:
            taken = getattr(m, "taken_at", None)
            if taken:
                ts = taken if taken.tzinfo else taken.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            d = _media_to_dict(m, "tagged")
            if d["id"] not in posts:
                posts[d["id"]] = d
        print(f"  Instagram tagged: {len(tagged)} posts")
    except Exception as e:
        print(f"  Instagram tagged error: {e}")

    # Hashtag posts
    for tag in _HASHTAGS:
        try:
            medias = cl.hashtag_medias_recent(tag, amount=30)
            added = 0
            for m in medias:
                taken = getattr(m, "taken_at", None)
                if taken:
                    ts = taken if taken.tzinfo else taken.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        continue
                d = _media_to_dict(m, "hashtag", hashtag=tag)
                if d["id"] not in posts:
                    posts[d["id"]] = d
                    added += 1
            print(f"  Instagram #{tag}: {added} new posts")
        except Exception as e:
            print(f"  Instagram #{tag} error: {e}")

    return list(posts.values())


def _fetch_own_posts_web(username: str, days_back: int) -> list[dict]:
    """Fallback: public web profile API for own posts (no login)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "x-ig-app-id": "936619743392459",
    }
    try:
        resp = requests.get(
            "https://www.instagram.com/api/v1/users/web_profile_info/",
            params={"username": username},
            headers=headers, timeout=20,
        )
        resp.raise_for_status()
        user = resp.json()["data"]["user"]
    except Exception as e:
        print(f"  Instagram web fallback error: {e}")
        return []

    posts = []
    for edge in user.get("edge_owner_to_timeline_media", {}).get("edges", []):
        node = edge.get("node", {})
        ts = node.get("taken_at_timestamp", 0)
        pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        if pub and pub < cutoff:
            continue
        shortcode = node.get("shortcode", "")
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        caption = (caption_edges[0]["node"]["text"] if caption_edges else "")[:1000]
        typename = node.get("__typename", "GraphImage")
        media_type = typename.replace("Graph", "")
        posts.append({
            "id": shortcode,
            "url": f"https://www.instagram.com/p/{shortcode}/",
            "date": pub.strftime("%Y-%m-%d") if pub else "",
            "caption": caption,
            "likes": node.get("edge_liked_by", {}).get("count", 0) or 0,
            "comments": node.get("edge_media_to_comment", {}).get("count", 0) or 0,
            "media_type": media_type,
            "video_views": node.get("video_view_count") if node.get("is_video") else None,
            "source_type": "own_post",
            "username": username,
            "hashtag": "",
        })
    return posts


def upsert_ig_post(conn: sqlite3.Connection, post: dict) -> bool:
    cur = conn.execute("SELECT id FROM instagram_posts WHERE id = ?", (post["id"],))
    is_new = cur.fetchone() is None
    conn.execute("""
        INSERT INTO instagram_posts
            (id, url, date, caption, likes, comments, media_type, video_views,
             source_type, username, hashtag)
        VALUES
            (:id, :url, :date, :caption, :likes, :comments, :media_type, :video_views,
             :source_type, :username, :hashtag)
        ON CONFLICT(id) DO UPDATE SET
            likes       = excluded.likes,
            comments    = excluded.comments,
            video_views = COALESCE(excluded.video_views, video_views)
    """, post)
    conn.commit()
    return is_new


def push_ig_posts_to_notion(conn: sqlite3.Connection, token: str, database_id: str) -> None:
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
        src_type = post.get("source_type", "own_post")
        username = post.get("username", "nargesrashidi")
        hashtag  = post.get("hashtag", "")

        if src_type == "hashtag":
            label = f"[IG #{hashtag}] @{username}"
        elif src_type == "tagged":
            label = f"[IG tagged] @{username}"
        else:
            label = "[Instagram] @nargesrashidi"

        caption_preview = (post.get("caption") or "")[:100]
        title = f"{label} — {caption_preview or post['date']}"

        props = {
            "Title":    {"title":     [{"text": {"content": title[:2000]}}]},
            "Source":   {"rich_text": [{"text": {"content": label}}]},
            "Platform": {"select":    {"name": "Online"}},
            "Type":     {"select":    {"name": "Mention"}},
            "Tier":     {"select":    {"name": "Tier 1"}},
            "URL":      {"url":       post["url"]},
            "Snippet":  {"rich_text": [{"text": {"content": (post.get("caption") or "")[:2000]}}]},
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
            conn.execute("UPDATE instagram_posts SET notion_id = ? WHERE id = ?",
                         (notion_id, post["id"]))
            conn.commit()
            pushed += 1
        except Exception as e:
            print(f"    ! Instagram Notion push error: {e}")
            errors += 1

    print(f"  Instagram → Notion: {pushed} pushed, {errors} errors")
