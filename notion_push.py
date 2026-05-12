"""Push press items to a Notion database via the Notion API."""
import json

import requests

_API = "https://api.notion.com/v1"
_VERSION = "2022-06-28"


def _h(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": _VERSION,
    }


def create_database(token: str, parent_page_id: str) -> str:
    """Create the press tracking database under a Notion page. Returns the new database ID."""
    body = {
        "parent": {"page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "📰"},
        "title": [{"type": "text", "text": {"content": "Narges Rashidi — Press"}}],
        "properties": {
            "Title": {"title": {}},
            "Source": {"rich_text": {}},
            "Date": {"date": {}},
            "Type": {
                "select": {
                    "options": [
                        {"name": "Interview", "color": "blue"},
                        {"name": "Review", "color": "green"},
                        {"name": "Profile", "color": "purple"},
                        {"name": "Award", "color": "yellow"},
                        {"name": "Mention", "color": "default"},
                    ]
                }
            },
            "Tier": {
                "select": {
                    "options": [
                        {"name": "Tier 1", "color": "red"},
                        {"name": "Tier 2", "color": "orange"},
                        {"name": "Tier 3", "color": "gray"},
                    ]
                }
            },
            "Platform": {
                "select": {
                    "options": [
                        {"name": "Online", "color": "blue"},
                        {"name": "YouTube", "color": "red"},
                        {"name": "Print", "color": "gray"},
                    ]
                }
            },
            "URL": {"url": {}},
            "Views": {"number": {"format": "number_with_commas"}},
            "Likes": {"number": {"format": "number_with_commas"}},
            "Full Text": {"checkbox": {}},
            "Key Quotes": {"rich_text": {}},
            "Snippet": {"rich_text": {}},
            "Notes": {"rich_text": {}},
        },
    }
    resp = requests.post(f"{_API}/databases", headers=_h(token), json=body, timeout=15)
    resp.raise_for_status()
    return resp.json()["id"]


def push_page(token: str, database_id: str, item: dict) -> str:
    """Push one press item as a Notion page. Returns the new page ID."""
    key_quotes = item.get("key_quotes") or []
    if isinstance(key_quotes, str):
        try:
            key_quotes = json.loads(key_quotes)
        except Exception:
            key_quotes = []

    props: dict = {
        "Title": {"title": [{"text": {"content": (item.get("title") or "")[:2000]}}]},
        "Source": {"rich_text": [{"text": {"content": (item.get("source") or "")[:2000]}}]},
        "Type": {"select": {"name": item.get("type") or "Mention"}},
        "Tier": {"select": {"name": item.get("tier") or "Tier 3"}},
        "Platform": {"select": {"name": item.get("platform") or "Online"}},
        "URL": {"url": item.get("url") or "https://example.com"},
        "Full Text": {"checkbox": bool(item.get("full_text"))},
        "Snippet": {"rich_text": [{"text": {"content": (item.get("snippet") or "")[:2000]}}]},
        "Key Quotes": {
            "rich_text": [{"text": {"content": (" | ".join(key_quotes))[:2000]}}]
        },
    }
    if item.get("date"):
        props["Date"] = {"date": {"start": item["date"]}}
    if item.get("views") is not None:
        props["Views"] = {"number": item["views"]}
    if item.get("likes") is not None:
        props["Likes"] = {"number": item["likes"]}

    body: dict = {"parent": {"database_id": database_id}, "properties": props}

    # Store full article text as page body content (first 2000 chars)
    if item.get("full_text"):
        body["children"] = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": item["full_text"][:2000]}}]
                },
            }
        ]

    resp = requests.post(f"{_API}/pages", headers=_h(token), json=body, timeout=15)
    resp.raise_for_status()
    return resp.json()["id"]
