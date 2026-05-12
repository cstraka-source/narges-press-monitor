"""
One-time setup: creates the Notion database and writes its ID to your .env.

Run once before using run.py:
    python setup_notion.py
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

token = os.getenv("NOTION_TOKEN", "")
if not token or token.startswith("secret_your_"):
    print("Error: set NOTION_TOKEN in your .env file first, then re-run this script.")
    sys.exit(1)

print(
    "\nYou need a Notion page ID to put the database in.\n"
    "Open any Notion page in your browser. The URL looks like:\n"
    "  https://www.notion.so/My-Page-1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c\n"
    "Copy the 32-character hex string at the end (with or without dashes).\n"
)
raw = input("Paste the parent page ID: ").strip()
parent_id = raw.replace("-", "").replace(" ", "")
if len(parent_id) != 32:
    print(f"That doesn't look right — got {len(parent_id)} chars after stripping dashes, expected 32.")
    sys.exit(1)

from notion_push import create_database

print("\nCreating database…")
try:
    db_id = create_database(token, parent_id)
except Exception as e:
    print(f"Failed: {e}")
    print(
        "\nCommon cause: the integration doesn't have access to that page.\n"
        "In Notion, open the parent page → ⋯ menu → Connections → add your integration."
    )
    sys.exit(1)

print(f"Created!  Database ID: {db_id}")

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    content = env_path.read_text()
    if "NOTION_DATABASE_ID=" in content:
        content = re.sub(r"NOTION_DATABASE_ID=.*", f"NOTION_DATABASE_ID={db_id}", content)
    else:
        content = content.rstrip("\n") + f"\nNOTION_DATABASE_ID={db_id}\n"
    env_path.write_text(content)
    print(f"Updated .env with NOTION_DATABASE_ID={db_id}")
else:
    print(f"\nAdd this line to your .env:\n  NOTION_DATABASE_ID={db_id}")

print("\nAll done — you can now run:  python run.py")
