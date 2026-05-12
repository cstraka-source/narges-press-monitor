"""
TikTok monitor — searches via hashtags and username profile.
Uses TikTokApi (Playwright-based). No login required for public content.
Monitors: #nargesrashidi #prisoner951 #narges_rashidi
"""
import asyncio
import hashlib
import sys
from datetime import datetime, timedelta, timezone


def _url_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


async def _fetch(days_back: int) -> list[dict]:
    try:
        from TikTokApi import TikTokApi
    except ImportError:
        print("  TikTok: pip install TikTokApi", file=sys.stderr)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    hashtags = ["nargesrashidi", "prisoner951", "nargesrashidi951", "narges_rashidi"]
    items = []
    seen: set[str] = set()

    try:
        async with TikTokApi() as api:
            await api.create_sessions(num_sessions=1, sleep_after=5,
                                      headless=True, browser="webkit")

            for tag in hashtags:
                try:
                    async for video in api.hashtag(name=tag).videos(count=30):
                        try:
                            d = video.as_dict
                            vid_id = d.get("id", "")
                            if vid_id in seen:
                                continue
                            seen.add(vid_id)
                            ts = d.get("createTime", 0)
                            pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
                            if pub and pub < cutoff:
                                continue
                            author = d.get("author", {})
                            username = author.get("uniqueId", "")
                            url = f"https://www.tiktok.com/@{username}/video/{vid_id}"
                            stats = d.get("stats", {})
                            desc = d.get("desc", "")
                            items.append({
                                "id": _url_id(url),
                                "title": (desc[:200] or f"TikTok #{tag} by @{username}"),
                                "url": url,
                                "source": f"@{username}",
                                "date": pub.strftime("%Y-%m-%d") if pub else "",
                                "snippet": desc[:500],
                                "platform": "TikTok",
                                "type": "Mention",
                                "tier": "Tier 2" if (stats.get("playCount", 0) or 0) > 50000 else "Tier 3",
                                "views": stats.get("playCount", 0) or 0,
                                "likes": stats.get("diggCount", 0) or 0,
                                "full_text": desc,
                                "key_quotes": [],
                            })
                        except Exception:
                            continue
                except Exception as e:
                    print(f"  TikTok #{tag}: {e}", file=sys.stderr)
                    continue

    except Exception as e:
        print(f"  TikTok session error: {e}", file=sys.stderr)

    return items


def fetch_tiktok(days_back: int = 30) -> list[dict]:
    try:
        return asyncio.run(_fetch(days_back))
    except Exception as e:
        print(f"  TikTok error: {e}", file=sys.stderr)
        return []
