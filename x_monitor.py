"""
X.com (Twitter) mention monitor using twscrape.
Requires Python 3.12 — called as a subprocess from run.py.

Searches for mentions of the query and outputs JSON to stdout.
Run directly: python3.12 x_monitor.py "Narges Rashidi" --days 7
"""
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ACCOUNTS_DB = Path(__file__).parent / "twscrape_accounts.db"


def _url_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


async def _search(query: str, email: str, username: str, password: str, days_back: int) -> list[dict]:
    from twscrape import API, gather
    from twscrape.logger import set_log_level
    set_log_level("ERROR")

    api = API(str(ACCOUNTS_DB))

    # Add account if not already there
    existing = await api.pool.get_all()
    if not any(a.username.lower() == username.lower() for a in existing):
        await api.pool.add_account(
            username=username,
            password=password,
            email=email,
            email_password=password,
        )
        await api.pool.login_all()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    search_query = f'"{query}" lang:en -is:retweet'

    items = []
    try:
        async for tweet in api.search(search_query, limit=100):
            if tweet.date < cutoff:
                continue
            url = f"https://x.com/{tweet.user.username}/status/{tweet.id}"
            items.append({
                "id": _url_id(url),
                "title": tweet.rawContent[:200],
                "url": url,
                "source": f"@{tweet.user.username}",
                "date": tweet.date.strftime("%Y-%m-%d"),
                "snippet": tweet.rawContent[:500],
                "platform": "X",
                "type": "Mention",
                "tier": "Tier 2" if tweet.user.followersCount > 10000 else "Tier 3",
                "views": tweet.viewCount or 0,
                "likes": tweet.likeCount or 0,
                "full_text": tweet.rawContent,
                "key_quotes": [],
            })
    except Exception as e:
        print(f"[x_monitor] search error: {e}", file=sys.stderr)

    return items


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--email", default=os.getenv("X_EMAIL", ""))
    parser.add_argument("--username", default=os.getenv("X_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("X_PASSWORD", ""))
    args = parser.parse_args()

    if not args.email or not args.password:
        print("[]")
        return

    items = asyncio.run(_search(args.query, args.email, args.username, args.password, args.days))
    print(json.dumps(items))


if __name__ == "__main__":
    main()
