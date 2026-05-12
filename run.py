"""
Main orchestrator — run manually or via cron.

Usage:
    python run.py              # fetch last 7 days, push new items to Notion
    python run.py --days 30    # wider lookback
    python run.py --csv        # also export press_narges.csv after run
    python run.py --no-notion  # store in SQLite only (useful while setting up)
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY", "")
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "nargesrashidi")
X_EMAIL = os.getenv("X_EMAIL", "")
X_USERNAME = os.getenv("X_USERNAME", "")
X_PASSWORD = os.getenv("X_PASSWORD", "")
BLUESKY_IDENTIFIER = os.getenv("BLUESKY_IDENTIFIER", "")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD", "")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN", "")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
QUERY = os.getenv("SEARCH_QUERY", "Narges Rashidi")

_PLACEHOLDER_PREFIXES = ("your_", "secret_your_")


def _is_set(val: str) -> bool:
    return bool(val) and not any(val.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--no-notion", action="store_true")
    args = parser.parse_args()

    from enrich import extract_full_text
    from notion_push import push_page
    from sources import fetch_bluesky, fetch_google_news_rss, fetch_guardian_api, fetch_newsapi, fetch_print_rss, fetch_reddit, fetch_youtube
    from store import export_csv, get_unpushed, init_db, set_notion_id, upsert_item
    from instagram import fetch_instagram_posts, init_ig_table, push_ig_posts_to_notion, upsert_ig_post
    from facebook_monitor import fetch_facebook_pages

    conn = init_db()
    init_ig_table(conn)
    print(f'Searching: "{QUERY}" — last {args.days} days\n')

    all_items: list[dict] = []

    if _is_set(NEWS_API_KEY):
        try:
            items = fetch_newsapi(QUERY, NEWS_API_KEY, days_back=args.days)
            print(f"  NewsAPI            {len(items):>3} results")
            all_items.extend(items)
        except Exception as e:
            print(f"  NewsAPI            ERROR: {e}")
    else:
        print("  NewsAPI            skipped (add NEWS_API_KEY to .env)")

    try:
        items = fetch_google_news_rss(QUERY, days_back=args.days)
        print(f"  Google News RSS    {len(items):>3} results")
        all_items.extend(items)
    except Exception as e:
        print(f"  Google News RSS    ERROR: {e}")

    if _is_set(YOUTUBE_API_KEY):
        try:
            yt_days = max(args.days, 60)
            items = fetch_youtube(QUERY, YOUTUBE_API_KEY, days_back=yt_days)
            print(f"  YouTube            {len(items):>3} results")
            all_items.extend(items)
        except Exception as e:
            print(f"  YouTube            ERROR: {e}")
    else:
        print("  YouTube            skipped (add YOUTUBE_API_KEY to .env)")

    if _is_set(GUARDIAN_API_KEY):
        try:
            items = fetch_guardian_api(QUERY, GUARDIAN_API_KEY, days_back=args.days)
            print(f"  Guardian API       {len(items):>3} results")
            all_items.extend(items)
        except Exception as e:
            print(f"  Guardian API       ERROR: {e}")
    else:
        print("  Guardian API       skipped (add GUARDIAN_API_KEY to .env)")

    try:
        items = fetch_print_rss(QUERY, days_back=args.days)
        print(f"  Print/Magazine RSS {len(items):>3} results")
        all_items.extend(items)
    except Exception as e:
        print(f"  Print/Magazine RSS ERROR: {e}")

    if _is_set(BLUESKY_IDENTIFIER) and _is_set(BLUESKY_PASSWORD):
        try:
            items = fetch_bluesky(QUERY, days_back=args.days,
                                  identifier=BLUESKY_IDENTIFIER, password=BLUESKY_PASSWORD)
            print(f"  Bluesky            {len(items):>3} results")
            all_items.extend(items)
        except Exception as e:
            print(f"  Bluesky            ERROR: {e}")
    else:
        print("  Bluesky            skipped (add BLUESKY_IDENTIFIER + BLUESKY_PASSWORD to .env)")

    try:
        items = fetch_reddit(QUERY, days_back=args.days)
        print(f"  Reddit             {len(items):>3} results")
        all_items.extend(items)
    except Exception as e:
        print(f"  Reddit             ERROR: {e}")

    # X.com — runs via python3.12 subprocess (twscrape requires 3.10+)
    if _is_set(X_EMAIL) and _is_set(X_PASSWORD):
        try:
            import json
            import subprocess
            env = os.environ.copy()
            env["X_EMAIL"] = X_EMAIL
            env["X_USERNAME"] = X_USERNAME
            env["X_PASSWORD"] = X_PASSWORD
            result = subprocess.run(
                ["python3.12", str(Path(__file__).parent / "x_monitor.py"),
                 QUERY, "--days", str(args.days)],
                capture_output=True, text=True, timeout=120, env=env,
                cwd=str(Path(__file__).parent),
            )
            x_items = json.loads(result.stdout or "[]")
            print(f"  X.com              {len(x_items):>3} results")
            all_items.extend(x_items)
        except Exception as e:
            print(f"  X.com              ERROR: {e}")
    else:
        print("  X.com              skipped (add X_EMAIL + X_PASSWORD to .env)")

    # TikTok
    try:
        from tiktok_monitor import fetch_tiktok
        items = fetch_tiktok(days_back=max(args.days, 30))
        print(f"  TikTok             {len(items):>3} results")
        all_items.extend(items)
    except Exception as e:
        print(f"  TikTok             ERROR: {e}")

    # Facebook public pages
    try:
        items = fetch_facebook_pages(QUERY, days_back=args.days, fb_access_token=FB_ACCESS_TOKEN)
        print(f"  Facebook           {len(items):>3} results")
        all_items.extend(items)
    except Exception as e:
        print(f"  Facebook           ERROR: {e}")

    # Deduplicate across sources then persist
    new_count = 0
    seen_ids: set[str] = set()
    for item in all_items:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        if upsert_item(conn, item):
            new_count += 1

    total = len(seen_ids)
    print(f"\n  {total} unique items fetched — {new_count} new\n")

    # Enrich new items with full article text
    unpushed = get_unpushed(conn)
    if unpushed:
        print(f"  Enriching {len(unpushed)} items with full text...")
        enriched = 0
        for item in unpushed:
            if item["platform"] == "YouTube":
                continue
            full_text, quotes = extract_full_text(item["url"])
            if full_text:
                item["full_text"] = full_text
                item["key_quotes"] = quotes
                upsert_item(conn, item)
                enriched += 1
        print(f"  Full text extracted for {enriched} articles")

    # Push to Notion
    use_notion = (
        not args.no_notion
        and _is_set(NOTION_TOKEN)
        and _is_set(NOTION_DATABASE_ID)
    )
    if use_notion:
        unpushed = get_unpushed(conn)  # re-fetch after enrichment
        print(f"\n  Pushing {len(unpushed)} items to Notion...")
        pushed = errors = 0
        for item in unpushed:
            try:
                notion_id = push_page(NOTION_TOKEN, NOTION_DATABASE_ID, item)
                set_notion_id(conn, item["id"], notion_id)
                pushed += 1
            except Exception as e:
                title_short = (item.get("title") or "")[:50]
                print(f"    ! '{title_short}': {e}")
                errors += 1
        print(f"  Notion: {pushed} pushed, {errors} errors")
    elif not args.no_notion:
        print("\n  Notion: skipped — set NOTION_TOKEN and NOTION_DATABASE_ID in .env")

    # Instagram
    print(f"\n  Fetching Instagram @{INSTAGRAM_USERNAME} (last {max(args.days, 14)} days)...")
    try:
        ig_posts = fetch_instagram_posts(INSTAGRAM_USERNAME, days_back=max(args.days, 14))
        ig_new = sum(1 for p in ig_posts if upsert_ig_post(conn, p))
        print(f"  Instagram          {len(ig_posts):>3} posts, {ig_new} new")
        if use_notion and ig_new:
            push_ig_posts_to_notion(conn, NOTION_TOKEN, NOTION_DATABASE_ID)
    except Exception as e:
        print(f"  Instagram          ERROR: {e}")

    if args.csv:
        csv_path = str(Path(__file__).parent / "press_narges.csv")
        export_csv(conn, csv_path)
        print(f"\n  CSV exported → {csv_path}")

    # Always export Parquet snapshot for cloud dashboard
    from store import export_parquet
    export_parquet(conn)
    print("  Parquet exported → data/")

    print("\nDone.")


if __name__ == "__main__":
    main()
