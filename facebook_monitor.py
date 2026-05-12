"""
Facebook monitor — finds public Facebook posts via Google News RSS (site:facebook.com search).
No API key or login required. Optionally enhances with Graph API if FB_ACCESS_TOKEN is set.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone

import feedparser
import requests

_TIER_1_PAGES = {
    "bbcnews", "bbc", "itv", "itvnews", "channel4news", "skynews",
    "theguardian", "telegraph", "theindependent", "eveningstandard",
    "bafta", "screendaily",
}


def _url_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _source_from_url(url: str) -> str:
    """Extract a readable source name from a facebook.com URL."""
    m = re.search(r"facebook\.com/([^/?#]+)", url)
    if m:
        slug = m.group(1).strip("/")
        if slug not in ("permalink", "photo", "video", "posts", "watch"):
            return slug
    return "Facebook"


def _tier_for_source(source: str) -> str:
    return "Tier 1" if source.lower() in _TIER_1_PAGES else "Tier 2"


def fetch_facebook_pages(query: str, days_back: int = 7,
                         fb_access_token: str = "") -> list[dict]:
    """
    Search Google News RSS for site:facebook.com mentions of the query.
    Falls back to Facebook Graph API for specific pages if fb_access_token provided.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    query_lower = query.lower()
    encoded = query.replace(" ", "+")
    items = []
    seen: set[str] = set()

    # Google News RSS — site:facebook.com scoped, UK + US editions
    feeds = [
        f"https://news.google.com/rss/search?q=%22{encoded}%22+site:facebook.com&hl=en-GB&gl=GB&ceid=GB:en",
        f"https://news.google.com/rss/search?q=%22{encoded}%22+site:facebook.com&hl=en-US&gl=US&ceid=US:en",
    ]
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        for e in feed.entries:
            link = getattr(e, "link", None) or ""
            if link in seen:
                continue
            raw_title = e.get("title", "")
            title = re.sub(r"\s+-\s+[^-]+$", "", raw_title).strip()
            summary = re.sub("<[^>]+>", "", e.get("summary", ""))
            combined = (title + " " + summary).lower()
            if query_lower not in combined:
                continue
            pub = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            if pub and pub < cutoff:
                continue
            seen.add(link)
            source = _source_from_url(link)
            items.append({
                "id": _url_id(link),
                "title": title,
                "url": link,
                "source": source,
                "date": pub.strftime("%Y-%m-%d") if pub else "",
                "snippet": summary[:500],
                "platform": "Facebook",
                "type": "Mention",
                "tier": _tier_for_source(source),
                "views": None,
                "likes": None,
                "full_text": summary,
                "key_quotes": [],
            })

    # Optional: Graph API for real-time page posts (needs User Access Token)
    if fb_access_token:
        _GRAPH_PAGES = [
            ("bbcnews", "BBC News", "Tier 1"),
            ("itvnews", "ITV News", "Tier 1"),
            ("Channel4News", "Channel 4 News", "Tier 1"),
            ("skynews", "Sky News", "Tier 1"),
            ("theguardian", "The Guardian", "Tier 1"),
            ("BAFTA", "BAFTA", "Tier 1"),
        ]
        since = int(cutoff.timestamp())
        for slug, source_name, tier in _GRAPH_PAGES:
            try:
                resp = requests.get(
                    f"https://graph.facebook.com/v19.0/{slug}/posts",
                    params={
                        "fields": "message,story,permalink_url,created_time",
                        "since": since, "limit": 50,
                        "access_token": fb_access_token,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                for post in resp.json().get("data", []):
                    text = (post.get("message") or post.get("story") or "")
                    if query_lower not in text.lower():
                        continue
                    url = post.get("permalink_url", "")
                    if url in seen:
                        continue
                    seen.add(url)
                    created = post.get("created_time", "")
                    try:
                        pub = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    except Exception:
                        pub = None
                    items.append({
                        "id": _url_id(url or text[:80]),
                        "title": text[:200],
                        "url": url,
                        "source": source_name,
                        "date": pub.strftime("%Y-%m-%d") if pub else "",
                        "snippet": text[:500],
                        "platform": "Facebook",
                        "type": "Mention",
                        "tier": tier,
                        "views": None,
                        "likes": None,
                        "full_text": text,
                        "key_quotes": [],
                    })
            except Exception:
                continue

    return items
