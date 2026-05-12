"""
Weekly press digest — runs after run.py to generate insights.

Usage:
    python digest.py            # last 7 days
    python digest.py --days 30  # custom window
    python digest.py --no-notion  # print only, don't push to Notion

Produces:
  - Console summary
  - Notion page: "Weekly Digest — YYYY-MM-DD" under the Press database parent
  - press_digest_YYYY-MM-DD.md in the Press folder
"""
import argparse
import os
import re
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NARGES_PAGE_ID = "20fe07a1-14a7-8040-bd50-f0950a4569e7"

DB_PATH = Path(__file__).parent / "press_narges.db"

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "will", "would", "could", "should", "may", "might",
    "it", "its", "she", "her", "he", "his", "they", "their", "we", "our",
    "that", "this", "as", "up", "out", "about", "after", "before", "who",
    "which", "when", "how", "what", "all", "more", "also", "new", "one",
    "two", "not", "no", "so", "if", "than", "then", "into", "over",
    "narges", "rashidi",  # always present — not signal
}


def _fetch_items(conn: sqlite3.Connection, days: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    cur = conn.execute(
        "SELECT * FROM press WHERE date >= ? ORDER BY date DESC", (cutoff,)
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _keyword_frequency(items: list[dict]) -> list[tuple[str, int]]:
    text = " ".join(
        (i.get("title") or "") + " " + (i.get("snippet") or "") for i in items
    )
    words = re.findall(r"\b[a-z]{4,}\b", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS]
    return Counter(filtered).most_common(20)


def _angle_clusters(items: list[dict]) -> dict[str, list[str]]:
    """Group titles by detected angle/narrative."""
    angles: dict[str, list[str]] = {
        "BAFTA / Awards": [],
        "Nazanin / Prisoner 951": [],
        "Iranian identity / diaspora": [],
        "Acting craft / performance": [],
        "Career & upcoming projects": [],
        "Red carpet / fashion": [],
        "Other": [],
    }
    for item in items:
        t = (item.get("title") or "").lower()
        if any(w in t for w in ["bafta", "award", "win", "winner", "nominated"]):
            angles["BAFTA / Awards"].append(item["title"])
        elif any(w in t for w in ["nazanin", "prisoner", "zaghari", "iran", "jailed", "briton"]):
            angles["Nazanin / Prisoner 951"].append(item["title"])
        elif any(w in t for w in ["iranian", "persian", "diaspora", "identity", "heritage"]):
            angles["Iranian identity / diaspora"].append(item["title"])
        elif any(w in t for w in ["acting", "performance", "role", "character", "craft", "actress"]):
            angles["Acting craft / performance"].append(item["title"])
        elif any(w in t for w in ["next", "upcoming", "project", "film", "series", "cast"]):
            angles["Career & upcoming projects"].append(item["title"])
        elif any(w in t for w in ["dress", "fashion", "look", "style", "red carpet", "outfit"]):
            angles["Red carpet / fashion"].append(item["title"])
        else:
            angles["Other"].append(item["title"])
    return {k: v for k, v in angles.items() if v}


def _ai_analysis(items: list[dict], days: int) -> str:
    """Use Claude API for richer messaging pattern analysis if key available."""
    try:
        import anthropic
    except ImportError:
        return ""
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("your_"):
        return ""

    titles_and_snippets = "\n".join(
        f"- [{i.get('source','')} | {i.get('date','')}] {i.get('title','')}. {(i.get('snippet') or '')[:200]}"
        for i in items[:50]  # cap at 50 to keep tokens manageable
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""You are a PR analyst for actor Narges Rashidi.
Analyse the press coverage below from the last {days} days and write a short briefing (200-300 words) covering:
1. The 2-3 dominant narratives/angles being used
2. Which messaging is resonating (quote specific phrases from headlines if possible)
3. Any angles being MISSED that would be worth pitching
4. One tactical recommendation for the next week

Coverage:
{titles_and_snippets}

Be direct and actionable. Write for a PR professional, not a journalist."""
        }],
    )
    return msg.content[0].text


def _build_report(items: list[dict], days: int) -> str:
    today = datetime.now().strftime("%d %B %Y")
    total = len(items)
    tier_counts = Counter(i.get("tier") for i in items)
    type_counts = Counter(i.get("type") for i in items)
    platform_counts = Counter(i.get("platform") for i in items)
    top_sources = Counter(i.get("source") for i in items).most_common(8)
    keywords = _keyword_frequency(items)
    angles = _angle_clusters(items)
    ai = _ai_analysis(items, days)

    lines = [
        f"# Narges Rashidi — Press Digest",
        f"**Period:** Last {days} days to {today}",
        f"**Total items:** {total}",
        "",
        "---",
        "",
        "## Coverage breakdown",
        "",
        "**By tier**",
    ]
    for tier in ["Tier 1", "Tier 2", "Tier 3"]:
        n = tier_counts.get(tier, 0)
        if n:
            lines.append(f"- {tier}: {n} items")

    lines += ["", "**By type**"]
    for t, n in type_counts.most_common():
        lines.append(f"- {t}: {n}")

    lines += ["", "**By platform**"]
    for p, n in platform_counts.most_common():
        lines.append(f"- {p}: {n}")

    lines += ["", "---", "", "## Top outlets"]
    for source, n in top_sources:
        lines.append(f"- {source}: {n} items")

    lines += ["", "---", "", "## Angles in coverage"]
    for angle, titles in angles.items():
        lines.append(f"\n### {angle} ({len(titles)} items)")
        for t in titles[:5]:
            lines.append(f"- {t}")
        if len(titles) > 5:
            lines.append(f"  *(+{len(titles)-5} more)*")

    lines += ["", "---", "", "## Messaging patterns — top keywords"]
    lines.append("")
    lines.append(" | ".join(f"**{w}** ({n})" for w, n in keywords[:10]))

    if ai:
        lines += ["", "---", "", "## AI analysis", "", ai]

    lines += ["", "---", "", "## Notable Tier 1 coverage"]
    tier1 = [i for i in items if i.get("tier") == "Tier 1"][:10]
    for i in tier1:
        lines.append(f"- [{i['title']}]({i['url']}) — {i['source']} ({i['date']})")

    return "\n".join(lines)


def _push_to_notion(report_md: str, days: int) -> None:
    import requests
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = f"Press Digest — {date_str}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    # Create under the Narges parent page
    body = {
        "parent": {"page_id": NARGES_PAGE_ID},
        "icon": {"type": "emoji", "emoji": "📊"},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]}
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": report_md[:2000]}}]
                },
            }
        ],
    }
    resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    page_id = resp.json()["id"]
    print(f"  Notion digest page created: https://notion.so/{page_id.replace('-','')}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--no-notion", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    items = _fetch_items(conn, args.days)

    if not items:
        print(f"No items in the last {args.days} days. Run run.py first.")
        return

    print(f"Analysing {len(items)} items from the last {args.days} days...\n")
    report = _build_report(items, args.days)

    # Save markdown
    date_str = datetime.now().strftime("%Y-%m-%d")
    md_path = Path(__file__).parent / f"press_digest_{date_str}.md"
    md_path.write_text(report)
    print(f"  Digest saved → {md_path.name}")

    # Print summary to console
    print("\n" + "="*60)
    total = len(items)
    tier1 = sum(1 for i in items if i.get("tier") == "Tier 1")
    awards = sum(1 for i in items if i.get("type") == "Award")
    interviews = sum(1 for i in items if i.get("type") == "Interview")
    print(f"  {total} items | {tier1} Tier 1 | {awards} Award pieces | {interviews} Interviews")
    print("="*60)

    # Push to Notion
    _is_set = lambda v: bool(v) and not v.startswith("your_") and not v.startswith("secret_your_")
    if not args.no_notion and _is_set(NOTION_TOKEN):
        try:
            _push_to_notion(report, args.days)
        except Exception as e:
            print(f"  Notion push failed: {e}")
    else:
        print("  Notion: skipped")

    print("\nDone. Open the markdown file for the full digest.")


if __name__ == "__main__":
    main()
