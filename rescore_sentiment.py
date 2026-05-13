"""
Re-score sentiment for all existing press items using the new subject-aware scorer.

Usage:
  python3 rescore_sentiment.py            # re-score all items
  python3 rescore_sentiment.py --dry      # show what would change, don't write
"""
import argparse
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# override=True so .env beats any empty-string env vars set by the parent shell
load_dotenv(override=True)

DB_PATH = Path(__file__).parent / "press_narges.db"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry", action="store_true", help="Don't write changes")
    args = p.parse_args()

    from sentiment import score_sentiment_batch

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT id, title, snippet, full_text, sentiment FROM press ORDER BY date DESC")
    rows = cur.fetchall()
    print(f"Loaded {len(rows)} items")

    texts = []
    for _id, title, snippet, full_text, _old in rows:
        # Use full_text if substantial, otherwise title + snippet
        if full_text and len(full_text) > 200:
            t = (title or "") + ". " + (full_text or "")[:2000]
        else:
            t = (title or "") + ". " + (snippet or "")
        texts.append(t)

    print("Scoring...")
    new_scores = score_sentiment_batch(texts)
    print(f"Got {len(new_scores)} scores")

    changes = []
    for (id_, title, _, _, old), new in zip(rows, new_scores):
        if (old or "neutral") != new:
            changes.append((id_, title, old, new))

    print(f"\n{len(changes)} sentiments changing:\n")
    for id_, title, old, new in changes[:20]:
        flag = "✓" if (new == "neutral" and old == "negative") else "→"
        print(f"  {flag} [{old:>8} → {new:>8}] {(title or '')[:80]}")
    if len(changes) > 20:
        print(f"  ... and {len(changes)-20} more")

    if args.dry:
        print("\nDry run — no changes written.")
        return

    print(f"\nWriting {len(new_scores)} scores...")
    for (id_, *_), new in zip(rows, new_scores):
        conn.execute("UPDATE press SET sentiment = ? WHERE id = ?", (new, id_))
    conn.commit()

    # Export new parquet so the dashboard sees the changes
    from store import export_parquet
    export_parquet(conn)
    print("Parquet exported → data/")
    print("\nDone.")


if __name__ == "__main__":
    main()
