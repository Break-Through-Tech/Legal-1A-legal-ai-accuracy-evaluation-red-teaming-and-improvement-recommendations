"""Quote fidelity: is a quoted passage faithful to its source text?

Each quote is compared to its source in tiers, cheapest first, stopping at
the first tier that settles it:

    1. exact       the quote appears verbatim in the source
    2. normalized  it appears once case, punctuation, quote marks, list
                   markers and whitespace are ignored (ellipses and
                   [brackets] split it into pieces that must appear in order)
    3. fuzzy       otherwise, find the closest stretch of the source and
                   score how similar it is (rapidfuzz, 0-100):
                     UNRELATED_BELOW <= score < FUZZY_THRESHOLD  -> altered
                     score < UNRELATED_BELOW  -> "unrelated": the quote is
                     not from this source at all (testimony, wrong citation),
                     so it is not judged faithful or altered

Planted alterations are small ("shall" -> "may", or "under all circumstances"
tacked onto the end), so an altered quote is the real text with a few words
changed and still scores 79-99. See scripts/sweep_threshold.py.
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from .source_lookup import clean_whitespace

# Every faithful benchmark quote matches at the exact or normalized tier, so
# any fuzzy-tier quote is treated as altered: 100 = "no clean match".
FUZZY_THRESHOLD = 100.0

# Altered benchmark quotes score >= 79; quotes attached to the wrong source
# score <= 67. Chosen from a small sample (21 altered); re-check on new data.
UNRELATED_BELOW = 70.0

# Gaps inside a quote: "...", "…" and ". . ." mark omitted text, and
# brackets mark an editor's change ("allocate[s]"). The pieces either side
# must still appear in the source, in order.
GAP_RE = re.compile(r"\.\s*\.\s*\.|…|\[[^\]]*\]")

# List markers like (1), (e), (iv). Quotes often drop them mid-sentence.
LIST_MARKER_RE = re.compile(r"\((?:\d+|[a-z]|[ivx]+)\)", re.IGNORECASE)

_PUNCT_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalize_text(text: str) -> str:
    """Lowercase, drop list markers and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_PUNCT_MAP)
    text = LIST_MARKER_RE.sub(" ", text).lower()
    return clean_whitespace(re.sub(r"[^\w\s]", " ", text))


def _segments(quote: str) -> list[str]:
    """Normalized pieces of a quote, split at ellipses and brackets."""
    return [s for s in (normalize_text(p) for p in GAP_RE.split(quote)) if s]


def _segments_in_order(segments: list[str], source: str) -> bool:
    pos = 0
    for seg in segments:
        # Pad with spaces so "custody" does not match inside "custodyship".
        i = f" {source} ".find(f" {seg} ", pos)
        if i < 0:
            return False
        pos = i + len(seg)
    return True


def check_quote(
    quote: str,
    source: str | None,
    threshold: float = FUZZY_THRESHOLD,
    unrelated_below: float = UNRELATED_BELOW,
) -> dict:
    """Compare one quote to its source text.

    Returns
        {
            "tier":     "exact" | "normalized" | "fuzzy" | "unrelated" | "no_source",
            "score":    0-100 similarity (100 for exact/normalized; None if no source),
            "faithful": True / False (None if unrelated or no source),
            "closest":  for fuzzy/unrelated, the stretch of source the quote was compared to,
        }
    """
    if not source:
        return {"tier": "no_source", "score": None, "faithful": None, "closest": None}

    if clean_whitespace(quote) in source:
        return {"tier": "exact", "score": 100.0, "faithful": True, "closest": None}

    norm_source = normalize_text(source)
    segments = _segments(quote)
    if segments and _segments_in_order(segments, norm_source):
        return {"tier": "normalized", "score": 100.0, "faithful": True, "closest": None}

    # Find the best-matching stretch of source, then score the whole quote
    # against it, so extra or swapped words count against the quote.
    # Don't use align.score directly: when the quote is longer than the source,
    # partial_ratio finds the source inside the quote and scores 100 even if
    # the quote adds words.
    norm_quote = " ".join(segments)
    align = fuzz.partial_ratio_alignment(norm_quote, norm_source)
    closest = norm_source[align.dest_start:align.dest_end]
    score = fuzz.ratio(norm_quote, closest)
    if score < unrelated_below:
        return {"tier": "unrelated", "score": score, "faithful": None, "closest": closest}
    return {"tier": "fuzzy", "score": score, "faithful": score >= threshold, "closest": closest}
