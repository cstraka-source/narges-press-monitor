"""Extract full article text and pull key quotes for open (non-paywalled) URLs."""
import re

import trafilatura

# Curly and straight quotes, min 30 chars, max 350 chars
_QUOTE_RE = re.compile(r'[“”"]([^“”"]{30,350})[“”"]')

# Known paywalled domains — skip fetch, don't waste time
_PAYWALLED = {
    "variety.com", "deadline.com", "hollywoodreporter.com",
    "thetimes.co.uk", "thetimes.com", "telegraph.co.uk",
    "nytimes.com", "wsj.com", "ft.com", "theathletic.com",
}


def _is_paywalled(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in _PAYWALLED)


def extract_full_text(url: str) -> tuple[str, list[str]]:
    """Return (full_text, key_quotes). Returns ("", []) for paywalled or failed URLs."""
    if _is_paywalled(url):
        return "", []
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return "", []
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if not text:
            return "", []
        quotes = _QUOTE_RE.findall(text)[:6]
        return text, quotes
    except Exception:
        return "", []
