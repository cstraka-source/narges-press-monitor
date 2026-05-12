# Narges Rashidi Press Monitor — Claude Context

This directory is a Brand24 replacement for client Narges Rashidi (Iranian actress, BAFTA 2026 Leading Actress winner for *Prisoner 951*). Built for Christian Straka at If I Only Knew PR.

## What this does
Automatically monitors press, social media, and YouTube for mentions of Narges Rashidi. Stores everything in SQLite, pushes to a Notion database, and generates an interactive Streamlit dashboard + weekly HTML report.

## Run it
```bash
cd '/Users/christianstraka/Library/CloudStorage/Dropbox/06_COMPANIES/If_I_Only_Knew/Press'
python3 run.py              # fetch last 7 days, push to Notion
python3 run.py --days 30   # wider lookback
python3 run.py --no-notion # SQLite only (no Notion push)
python3 report.py --open   # generate HTML report and open in browser
python3 digest.py          # generate weekly text digest → Notion page
streamlit run dashboard.py # open interactive dashboard in browser
```

## Cron (every Monday 8am)
```
0 8 * * 1 cd '...Press' && python3 run.py >> press_cron.log 2>&1 && python3 digest.py >> press_cron.log 2>&1 && python3 report.py >> press_cron.log 2>&1
```

## Files
| File | Purpose |
|------|---------|
| `run.py` | Main orchestrator — calls all sources, deduplicates, enriches, pushes Notion |
| `sources.py` | All fetch functions: NewsAPI, Google News RSS, YouTube, Guardian API, print RSS, Bluesky, Reddit |
| `tiktok_monitor.py` | TikTok hashtag monitoring via TikTokApi + Playwright webkit |
| `facebook_monitor.py` | Facebook via Google News RSS (site:facebook.com) — no auth needed |
| `instagram.py` | Instagram via web profile API (mobile UA) — no login needed |
| `x_monitor.py` | X.com via twscrape — run as python3.12 subprocess (often blocked by Cloudflare) |
| `store.py` | SQLite operations: init_db, upsert_item, get_unpushed, export_csv |
| `enrich.py` | trafilatura full-text extraction (skips known paywalled domains) |
| `notion_push.py` | Pushes items to Notion database via API |
| `report.py` | Generates Brand24-style self-contained HTML report with Chart.js |
| `digest.py` | Generates weekly text digest with angle analysis, pushes to Notion |
| `dashboard.py` | Interactive Streamlit dashboard — reads from SQLite, auto-updates |
| `press_narges.db` | SQLite database (source of truth) |
| `.env` | All API keys and credentials |

## API Keys & Credentials (.env)
```
NEWS_API_KEY=***REMOVED***
YOUTUBE_API_KEY=***REMOVED***
GUARDIAN_API_KEY=***REMOVED***
NOTION_TOKEN=***REMOVED***
NOTION_DATABASE_ID=520eec68cfea46e5a2c375cb24be05bd
SEARCH_QUERY=Narges Rashidi
BLUESKY_IDENTIFIER=pressmonitoriiok.bsky.social
BLUESKY_PASSWORD=***REMOVED***
INSTAGRAM_USERNAME=nargesrashidi
INSTAGRAM_LOGIN_USER=mindsizesports
INSTAGRAM_LOGIN_PASS=***REMOVED***
X_EMAIL=c.straka@icloud.com
X_USERNAME=strakala
X_PASSWORD=***REMOVED***
# FB_ACCESS_TOKEN=  (optional — Facebook Graph API user token for richer FB data)
```

## Notion Setup
- Integration token: `***REMOVED***`
- Database ID: `520eec68cfea46e5a2c375cb24be05bd`
- Parent page: Narges (ID `20fe07a1-14a7-8040-bd50-f0950a4569e7`)
- The integration must be connected to the Narges page in Notion settings

## Data Sources — Status
| Source | Method | Status |
|--------|--------|--------|
| NewsAPI | REST API | ✅ ~43 results/week |
| Google News RSS | feedparser | ✅ ~13 results |
| YouTube | YouTube Data API v3 | ✅ ~13 results |
| Guardian | Guardian Content API | ✅ full text |
| Print/Magazine RSS | feedparser (Heat, Empire, etc.) | ✅ when articles exist |
| Bluesky | AT Protocol authenticated search | ✅ ~12 results |
| Reddit | Public JSON search | ✅ ~5 results |
| TikTok | TikTokApi v7.3.3 + Playwright webkit | ✅ ~22 results |
| Facebook | Google News RSS site:facebook.com | ✅ ~19 results |
| Instagram | Instagram web profile API (mobile UA) | ✅ 12 most recent posts |
| X.com | twscrape (python3.12 subprocess) | ❌ Cloudflare blocks |

## Database Schema (press_narges.db)
```sql
press table:
  id, title, url, source, date, snippet, platform, type, tier,
  views, likes, full_text, key_quotes, sentiment,
  notion_id, created_at

instagram_posts table:
  id, url, date, caption, likes, comments, media_type, video_views,
  notion_id, created_at
```

## Tier Classification
- **Tier 1**: Guardian, BBC, ITV, Sky News, Channel 4, Variety, Deadline, THR, NYT, Independent, Telegraph, Screen Daily, Sight & Sound, Evening Standard
- **Tier 2**: IndieWire, Empire, Timeout, Vogue, Elle, Grazia, Heat, Radio Times, Metro, Mirror
- **Tier 3**: everything else

## Python Environment
- System Python: 3.9.6 (used for most scripts)
- Python 3.12 (Homebrew): used only for x_monitor.py via subprocess (twscrape requires 3.10+)
- Key packages: requests, feedparser, trafilatura, lxml_html_clean, python-dotenv, vaderSentiment, TikTokApi, playwright, streamlit, plotly, pandas

## Known Issues
- X.com blocked by Cloudflare — needs paid Twitter API ($100/mo) to fix properly
- NewsAPI free tier limits historical lookback to 7 days (426 error on longer periods)
- TikTok hashtags #nargesrashidi951 and #narges_rashidi don't exist (10205 error) — only #nargesrashidi and #prisoner951 work
- Instagram returns 12 most recent posts only (no pagination without official API)

## Client Context
- Narges Rashidi won BAFTA Leading Actress 2026 for *Prisoner 951* (Nazanin Zaghari-Ratcliffe story)
- Her Instagram: @nargesrashidi (50K followers)
- Key hashtags: #nargesrashidi, #prisoner951, #NazaninZaghariRatcliffe, #Prisoner951
- Christian's Bluesky monitor account: pressmonitoriiok.bsky.social
