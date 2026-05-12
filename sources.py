"""Fetch press items from NewsAPI, Google News RSS, and YouTube."""
import hashlib
import re
from datetime import datetime, timezone, timedelta

import feedparser
import requests

# Sources classified by tier for PR purposes
_TIER_1_PATTERNS = [
    "guardian", "bbc", "variety", "deadline", "hollywoodreporter", "thr",
    "nytimes", "times", "telegraph", "independent", "sky news", "channel 4",
    "itv", "evening standard", "screen daily", "screendaily",
]
_TIER_2_PATTERNS = [
    "indiewire", "empire", "timeout", "total film", "little white lies",
    "sight and sound", "british vogue", "vogue", "elle", "harper",
    "radio times", "heat", "metro", "mirror", "express",
]


def _tier(source: str) -> str:
    s = source.lower()
    if any(p in s for p in _TIER_1_PATTERNS):
        return "Tier 1"
    if any(p in s for p in _TIER_2_PATTERNS):
        return "Tier 2"
    return "Tier 3"


def _classify_type(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["interview", "speaks", "talks to", "in conversation", "chats with", "q&a"]):
        return "Interview"
    if "review" in t:
        return "Review"
    if "profile" in t or "spotlight" in t:
        return "Profile"
    if any(w in t for w in ["bafta", "award", "wins", "winner", "nominated", "nomination", "prize"]):
        return "Award"
    return "Mention"


def _url_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def fetch_newsapi(query: str, api_key: str, days_back: int = 7) -> list[dict]:
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    resp = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": f'"{query}"',
            "from": from_date,
            "sortBy": "publishedAt",
            "pageSize": 100,
            "language": "en",
            "apiKey": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    items = []
    for a in resp.json().get("articles", []):
        if not a.get("url"):
            continue
        items.append({
            "id": _url_id(a["url"]),
            "title": (a.get("title") or "").strip(),
            "url": a["url"],
            "source": a.get("source", {}).get("name", ""),
            "date": (a.get("publishedAt") or "")[:10],
            "snippet": (a.get("description") or a.get("content") or "")[:1000],
            "platform": "Online",
            "type": _classify_type(a.get("title") or ""),
            "tier": _tier(a.get("source", {}).get("name", "")),
            "views": None,
            "likes": None,
            "full_text": "",
            "key_quotes": [],
        })
    return items


def fetch_google_news_rss(query: str, days_back: int = 7) -> list[dict]:
    encoded = query.replace(" ", "+")
    # Run two searches: UK and US editions for wider coverage
    feeds = [
        f"https://news.google.com/rss/search?q=%22{encoded}%22&hl=en-GB&gl=GB&ceid=GB:en",
        f"https://news.google.com/rss/search?q=%22{encoded}%22&hl=en-US&gl=US&ceid=US:en",
    ]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    seen: set[str] = set()
    items = []
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for e in feed.entries:
            link = getattr(e, "link", None)
            if not link or link in seen:
                continue
            seen.add(link)
            pub = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            if pub and pub < cutoff:
                continue
            raw_title = e.get("title", "")
            # Google News appends " - Source Name" — strip it for clean title
            title = re.sub(r"\s+-\s+[^-]+$", "", raw_title).strip()
            source_obj = e.get("source", {})
            source = source_obj.get("title", "") if isinstance(source_obj, dict) else str(source_obj)
            snippet = re.sub("<[^>]+>", "", e.get("summary", ""))[:1000]
            items.append({
                "id": _url_id(link),
                "title": title,
                "url": link,
                "source": source,
                "date": pub.strftime("%Y-%m-%d") if pub else "",
                "snippet": snippet,
                "platform": "Online",
                "type": _classify_type(title),
                "tier": _tier(source),
                "views": None,
                "likes": None,
                "full_text": "",
                "key_quotes": [],
            })
    return items


def fetch_youtube(query: str, api_key: str, days_back: int = 60) -> list[dict]:
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    search_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "q": query,
            "part": "snippet",
            "type": "video",
            "publishedAfter": from_date,
            "maxResults": 50,
            "relevanceLanguage": "en",
            "key": api_key,
        },
        timeout=15,
    )
    search_resp.raise_for_status()
    video_ids = [i["id"]["videoId"] for i in search_resp.json().get("items", [])]
    if not video_ids:
        return []

    stats_resp = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "id": ",".join(video_ids),
            "part": "statistics,snippet",
            "key": api_key,
        },
        timeout=15,
    )
    stats_resp.raise_for_status()
    items = []
    for v in stats_resp.json().get("items", []):
        sn = v["snippet"]
        st = v.get("statistics", {})
        url = f"https://www.youtube.com/watch?v={v['id']}"
        items.append({
            "id": _url_id(url),
            "title": sn.get("title", "").strip(),
            "url": url,
            "source": sn.get("channelTitle", ""),
            "date": (sn.get("publishedAt") or "")[:10],
            "snippet": sn.get("description", "")[:500],
            "platform": "YouTube",
            "type": _classify_type(sn.get("title", "")),
            "tier": _tier(sn.get("channelTitle", "")),
            "views": int(st.get("viewCount", 0) or 0),
            "likes": int(st.get("likeCount", 0) or 0),
            "full_text": "",
            "key_quotes": [],
        })
    return items


def fetch_guardian_api(query: str, api_key: str, days_back: int = 7) -> list[dict]:
    """Guardian Content API — free tier, returns full article text."""
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    resp = requests.get(
        "https://content.guardianapis.com/search",
        params={
            "q": f'"{query}"',
            "from-date": from_date,
            "show-fields": "bodyText,trailText",
            "page-size": 50,
            "api-key": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    items = []
    for a in resp.json().get("response", {}).get("results", []):
        fields = a.get("fields", {})
        full_text = fields.get("bodyText", "")
        snippet = fields.get("trailText", "") or full_text[:500]
        items.append({
            "id": _url_id(a["webUrl"]),
            "title": a.get("webTitle", "").strip(),
            "url": a["webUrl"],
            "source": "The Guardian",
            "date": (a.get("webPublicationDate") or "")[:10],
            "snippet": snippet[:1000],
            "platform": "Online",
            "type": _classify_type(a.get("webTitle", "")),
            "tier": "Tier 1",
            "views": None,
            "likes": None,
            "full_text": full_text,
            "key_quotes": [],
        })
    return items


# UK print & magazine RSS feeds — filtered for query mentions
_PRINT_RSS_FEEDS = [
    ("Heat",             "https://www.heatworld.com/rss/",                    "Tier 2"),
    ("Grazia",           "https://graziadaily.co.uk/feed/",                   "Tier 2"),
    ("Radio Times",      "https://www.radiotimes.com/rss/",                   "Tier 2"),
    ("Empire",           "https://www.empireonline.com/movies/news/feed/",    "Tier 2"),
    ("Little White Lies","https://lwlies.com/feed/",                          "Tier 2"),
    ("Sight & Sound",    "https://www.bfi.org.uk/rss",                       "Tier 1"),
    ("Total Film",       "https://www.gamesradar.com/film/rss/",             "Tier 2"),
    ("Stylist",          "https://www.stylist.co.uk/rss",                    "Tier 2"),
    ("Evening Standard", "https://www.standard.co.uk/news/rss",               "Tier 1"),
    ("The Guardian Arts","https://www.theguardian.com/culture/rss",           "Tier 1"),
    ("Independent Arts", "https://www.independent.co.uk/arts-entertainment/rss","Tier 1"),
    ("Screen Daily",     "https://www.screendaily.com/rss/news",             "Tier 1"),
    ("IndieWire",        "https://www.indiewire.com/feed/",                  "Tier 2"),
]


def _bluesky_token(identifier: str, password: str):
    try:
        resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": identifier, "password": password},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["accessJwt"]
    except Exception:
        return None


def fetch_bluesky(query: str, days_back: int = 7,
                  identifier: str = "", password: str = "") -> list[dict]:
    """Search Bluesky posts via the AT Protocol API (requires auth for search)."""
    token = _bluesky_token(identifier, password) if identifier else None
    if not token:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    headers = {"Authorization": f"Bearer {token}"}
    items = []
    seen: set[str] = set()
    cursor = None

    for _ in range(5):
        params: dict = {"q": query, "limit": 100, "sort": "latest"}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(
                "https://bsky.social/xrpc/app.bsky.feed.searchPosts",
                headers=headers, params=params, timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            break

        for post in data.get("posts", []):
            uri = post.get("uri", "")
            if uri in seen:
                continue
            seen.add(uri)
            record = post.get("record", {})
            text = record.get("text", "")
            created = record.get("createdAt", "")
            try:
                pub = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                pub = None
            if pub and pub < cutoff:
                continue
            author = post.get("author", {})
            handle = author.get("handle", "")
            rkey = uri.split("/")[-1]
            url = f"https://bsky.app/profile/{handle}/post/{rkey}"
            items.append({
                "id": _url_id(url),
                "title": text[:200],
                "url": url,
                "source": f"{handle}",
                "date": pub.strftime("%Y-%m-%d") if pub else "",
                "snippet": text[:500],
                "platform": "Bluesky",
                "type": "Mention",
                "tier": "Tier 2" if post.get("author", {}).get("followersCount", 0) or 0 > 10000 else "Tier 3",
                "views": post.get("likeCount", 0),
                "likes": post.get("likeCount", 0),
                "full_text": text,
                "key_quotes": [],
            })

        cursor = data.get("cursor")
        if not cursor:
            break

    return items


def fetch_reddit(query: str, days_back: int = 7) -> list[dict]:
    """Search Reddit for mentions via the public JSON API."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    try:
        resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": f'"{query}"', "sort": "new", "limit": 100, "type": "link"},
            headers={"User-Agent": "press-monitor/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception:
        return []

    items = []
    for child in resp.json().get("data", {}).get("children", []):
        d = child.get("data", {})
        ts = d.get("created_utc", 0)
        pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        if pub and pub < cutoff:
            continue
        url = f"https://reddit.com{d.get('permalink', '')}"
        title = d.get("title", "")
        if query.lower() not in title.lower() and query.lower() not in (d.get("selftext") or "").lower():
            continue
        items.append({
            "id": _url_id(url),
            "title": title,
            "url": url,
            "source": f"r/{d.get('subreddit', 'reddit')}",
            "date": pub.strftime("%Y-%m-%d") if pub else "",
            "snippet": (d.get("selftext") or "")[:500] or title,
            "platform": "Online",
            "type": "Mention",
            "tier": "Tier 3",
            "views": d.get("score", 0),
            "likes": d.get("score", 0),
            "full_text": d.get("selftext") or "",
            "key_quotes": [],
        })
    return items


def fetch_print_rss(query: str, days_back: int = 7) -> list[dict]:
    """Scan UK print/magazine RSS feeds for items mentioning the query."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    query_lower = query.lower()
    query_words = [w.lower() for w in query.split() if len(w) > 3]
    items = []
    seen: set[str] = set()

    for source_name, feed_url, tier in _PRINT_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue
        for e in feed.entries:
            link = getattr(e, "link", None)
            if not link or link in seen:
                continue
            title = e.get("title", "")
            summary = re.sub("<[^>]+>", "", e.get("summary", ""))
            combined = (title + " " + summary).lower()
            if not (query_lower in combined or all(w in combined for w in query_words)):
                continue
            seen.add(link)
            pub = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            if pub and pub < cutoff:
                continue
            items.append({
                "id": _url_id(link),
                "title": title.strip(),
                "url": link,
                "source": source_name,
                "date": pub.strftime("%Y-%m-%d") if pub else "",
                "snippet": summary[:1000],
                "platform": "Print",
                "type": _classify_type(title),
                "tier": tier,
                "views": None,
                "likes": None,
                "full_text": "",
                "key_quotes": [],
            })
    return items
