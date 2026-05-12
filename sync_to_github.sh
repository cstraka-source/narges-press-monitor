#!/bin/bash
# Commits and pushes the latest data snapshot to GitHub so Streamlit Cloud updates.
# Called automatically by the weekly cron job after run.py.
set -e
cd "$(dirname "$0")"
git add data/press.parquet data/instagram.parquet 2>/dev/null || true
git diff --cached --quiet && echo "No data changes to push" && exit 0
git commit -m "data: weekly press snapshot $(date '+%Y-%m-%d')"
git push origin main
echo "Data pushed to GitHub — dashboard will update in ~30 seconds"
