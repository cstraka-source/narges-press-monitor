"""
Subject-aware sentiment scoring for press monitoring.

Hierarchy of strategies:
  1. Claude API (best) — asks "is this positive/neutral/negative ABOUT {subject}?"
  2. Improved VADER fallback — strips known false-positive triggers (show titles
     like 'Prisoner 951'), then only scores the window of text near the subject.

Both return one of: "positive" | "neutral" | "negative".
"""
import json
import os
import re
import time
from typing import Iterable

SUBJECT = "Narges Rashidi"

# Show titles / names that contain words VADER misreads as negative.
# We replace them with neutral placeholders before scoring.
_NEUTRAL_REPLACEMENTS = {
    "Prisoner 951":     "the series",
    "prisoner 951":     "the series",
    "Prisoner951":      "the series",
    "PRISONER 951":     "the series",
    "Under the Shadow": "her film",
    "Nazanin Zaghari-Ratcliffe": "the real person",
    "Zaghari-Ratcliffe":         "the real person",
    "Nazanin":          "the real person",
}


def _strip_neutral_terms(text: str) -> str:
    for old, new in _NEUTRAL_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def _subject_window(text: str, subject: str = SUBJECT, window: int = 200) -> str:
    """Return concatenated chunks of text around each mention of the subject."""
    if not text:
        return ""
    text_lc = text.lower()
    # Try full name, last name, first name in order
    parts = subject.split()
    candidates = [subject.lower(), parts[-1].lower()]
    if len(parts) > 1:
        candidates.append(parts[0].lower())

    indices = []
    for s in candidates:
        if not s or len(s) < 3:
            continue
        i = 0
        while True:
            idx = text_lc.find(s, i)
            if idx < 0:
                break
            indices.append(idx)
            i = idx + len(s)
        if indices:
            break  # found with most-specific match; don't dilute

    if not indices:
        return ""  # subject not found in text → can't make subject-aware judgement

    chunks = []
    for idx in indices[:5]:  # cap at 5 mentions
        start = max(0, idx - window)
        end   = min(len(text), idx + window)
        chunks.append(text[start:end])
    return " ".join(chunks)


# ── Strategy 1: LLM-based (best) ──────────────────────────────────────────────
_LLM_CLIENT = None
_LLM_MODEL = "claude-haiku-4-5"


def _get_llm_client():
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            from anthropic import Anthropic
            _LLM_CLIENT = Anthropic(api_key=api_key)
        except Exception:
            return None
    return _LLM_CLIENT


_SYSTEM_PROMPT = """You score the sentiment of press mentions about a specific subject.

The subject is: Narges Rashidi — an Iranian actress who won the 2026 BAFTA TV Award for Leading Actress for her role as Nazanin Zaghari-Ratcliffe in the drama 'Prisoner 951'.

Rules:
1. Score sentiment ABOUT THE SUBJECT, not the overall mood of the text.
2. "Prisoner 951" and "Under the Shadow" are show titles — neutral, not negative.
3. The story 'Prisoner 951' depicts harrowing events but coverage of it is generally neutral or positive about her performance.
4. If the text is about other people (e.g. someone else being snubbed at BAFTA) and only briefly mentions her, score as neutral.
5. If she isn't really mentioned or relevant, score neutral.
6. Awards, praise, recognition, positive reviews → positive.
7. Criticism of her performance/choices, scandal, attack → negative.

Return ONLY a single word: positive, neutral, or negative."""


def _score_with_llm(text: str) -> "str | None":
    client = _get_llm_client()
    if client is None:
        return None
    if not text or not text.strip():
        return "neutral"
    text = text[:2500]  # cap input
    try:
        resp = client.messages.create(
            model=_LLM_MODEL,
            max_tokens=8,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Text: {text}\n\nSentiment:"}],
        )
        out = resp.content[0].text.strip().lower()
        if "pos" in out:    return "positive"
        if "neg" in out:    return "negative"
        return "neutral"
    except Exception as e:
        print(f"  LLM sentiment error: {e}")
        return None


def _score_batch_with_llm(texts: list[str]) -> "list[str] | None":
    """One LLM call for up to ~20 items at once — much cheaper than per-item."""
    client = _get_llm_client()
    if client is None:
        return None
    if not texts:
        return []
    # Cap each text to avoid huge prompts
    items = [(t or "")[:1200] for t in texts]
    numbered = "\n\n".join(f"### {i+1}\n{t}" for i, t in enumerate(items))
    prompt = (
        f"Score sentiment for each numbered item about Narges Rashidi.\n"
        f"Return a JSON array of strings: each one of 'positive', 'neutral', 'negative'.\n"
        f"Only the JSON array, no other text.\n\n{numbered}"
    )
    try:
        resp = client.messages.create(
            model=_LLM_MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        out = resp.content[0].text.strip()
        # Strip markdown code fences if present
        out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out, flags=re.IGNORECASE)
        scores = json.loads(out)
        if isinstance(scores, list) and len(scores) == len(texts):
            return [s.lower() if isinstance(s, str) else "neutral" for s in scores]
        # Length mismatch → fail gracefully
        return None
    except Exception as e:
        print(f"  LLM batch sentiment error: {e}")
        return None


# ── Strategy 2: Improved VADER fallback ───────────────────────────────────────
def _score_with_vader(text: str) -> str:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError:
        return "neutral"
    cleaned = _strip_neutral_terms(text)
    windowed = _subject_window(cleaned)

    # If the subject isn't mentioned in the visible text at all, we can't
    # reliably judge sentiment ABOUT her — default to neutral.
    if not windowed:
        return "neutral"

    try:
        score = SentimentIntensityAnalyzer().polarity_scores(windowed)["compound"]
        if score >= 0.20:   # stricter than VADER default of 0.05
            return "positive"
        if score <= -0.20:
            return "negative"
        return "neutral"
    except Exception:
        return "neutral"


# ── Public API ────────────────────────────────────────────────────────────────
def score_sentiment(text: str) -> str:
    """Score a single text — uses LLM if available, else improved VADER."""
    if not text or not text.strip():
        return "neutral"
    llm_score = _score_with_llm(text)
    if llm_score is not None:
        return llm_score
    return _score_with_vader(text)


def score_sentiment_batch(texts: Iterable[str]) -> list[str]:
    """Score many texts efficiently. Uses LLM batch if available."""
    texts = list(texts)
    if not texts:
        return []
    # Try LLM batch in chunks of 15
    client = _get_llm_client()
    if client is not None:
        all_scores: list[str] = []
        for i in range(0, len(texts), 15):
            chunk = texts[i:i+15]
            scores = _score_batch_with_llm(chunk)
            if scores is None:
                # Fall back to per-item VADER for this chunk
                scores = [_score_with_vader(t) for t in chunk]
            all_scores.extend(scores)
            time.sleep(0.3)  # mild rate-limit politeness
        return all_scores
    # No LLM — VADER only
    return [_score_with_vader(t) for t in texts]
