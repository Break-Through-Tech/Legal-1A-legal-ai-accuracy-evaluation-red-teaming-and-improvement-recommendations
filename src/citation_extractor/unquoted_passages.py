"""Find verbatim passages of law that are NOT in quote marks.

Drafts often copy statute text straight into a sentence:

    Under AS 25.24.200, a petition ... may be filed when incompatibility of
    temperament has caused the irremediable breakdown of the marriage.

The quote extractor only sees text between quote marks, so this module finds
these passages by aligning each paragraph's words against the text of every
authority cited near it. The citation may come before or after the passage.

Unquoted text is usually paraphrase: a drafter copies a run of statute words,
then carries on in their own words. That is not a misquote. So a passage is
a run of at least MIN_RUN words copied verbatim, extended only when the run
reaches the end of a source clause and the draft adds 1-MAX_TAIL words before
its own punctuation ("... of the marriage under all circumstances."). The
fidelity checker then decides; a plain verbatim run is an exact match.

Swapped or dropped words between two verbatim runs are NOT checked here.
On the benchmark that rule caught no altered quotes and raised ~600 false
alarms: in unquoted text a changed word is ordinary paraphrase. Quoted
passages, which promise to be verbatim, still get the full check.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .quote_extractor import CITATION_PATTERNS, extract_quotes
from .quote_fidelity import LIST_MARKER_RE, _PUNCT_MAP
from .source_lookup import get_source_text

# Shortest run of matching words that counts as copied text.
MIN_RUN = 8

# Most words added after the end of a source clause.
MAX_TAIL = 4

WORD_RE = re.compile(r"[^\W_]+")
# A period ends a clause only before a space or the end: "AS 25.24.150" does not.
CLAUSE_END_RE = re.compile(r"[;:,!?\"“”()]|\.(?=\s|$)")
NEXT_CHAR_RE = re.compile(r"\s*(\S|$)")


def _words(text: str) -> list[re.Match]:
    """Word tokens with character offsets, normalized like normalize_text."""
    # Both steps replace characters one-for-one, so offsets stay valid.
    text = LIST_MARKER_RE.sub(lambda m: " " * len(m.group()), text.translate(_PUNCT_MAP))
    return list(WORD_RE.finditer(text))


def _cites_in(text: str) -> list[str]:
    found = []
    for pattern in CITATION_PATTERNS:
        found.extend(m.group(0) for m in pattern.finditer(text))
    return found


def _ends_clause(text: str, pos: int) -> bool:
    """True if the next non-space character after `pos` ends a clause (or the text)."""
    nxt = NEXT_CHAR_RE.match(text, pos).group(1)
    return nxt == "" or bool(CLAUSE_END_RE.match(nxt))


def _appended_end(paragraph: str, end: int) -> int | None:
    """End of 1-MAX_TAIL words added after `end`, up to the draft's punctuation; else None."""
    stop = CLAUSE_END_RE.search(paragraph, end)
    stop = stop.start() if stop else len(paragraph)
    tail = paragraph[end:stop]
    # A trailing citation ("under AS 25.24.150") is attribution, not an alteration.
    if any(p.search(tail) for p in CITATION_PATTERNS):
        return None
    return stop if 1 <= len(WORD_RE.findall(tail)) <= MAX_TAIL else None


def _runs(para_tokens: list[str], source_tokens: list[str]):
    """Runs of at least MIN_RUN words that appear verbatim, in order, in the source."""
    matcher = SequenceMatcher(None, para_tokens, source_tokens, autojunk=False)
    return [b for b in matcher.get_matching_blocks() if b.size >= MIN_RUN]


def find_unquoted_passages(paragraph: str, sources: dict[str, str]) -> list[dict]:
    """Find passages of `paragraph` copied from any of `sources` ({citation: text}).

    Each result is {"text", "start", "end", "citation"}, like a quote from
    the quote extractor. Overlapping passages from different sources keep
    only the longest.
    """
    para_words = _words(paragraph)
    para_tokens = [m.group().lower() for m in para_words]
    found = []

    for cite, source in sources.items():
        source_words = _words(source)
        source_tokens = [m.group().lower() for m in source_words]
        for run in _runs(para_tokens, source_tokens):
            start = para_words[run.a].start()
            end = para_words[run.a + run.size - 1].end()
            if _ends_clause(source, source_words[run.b + run.size - 1].end()):
                end = _appended_end(paragraph, end) or end
            found.append({"text": paragraph[start:end], "start": start, "end": end, "citation": cite})

    # Keep the longest of any overlapping passages.
    found.sort(key=lambda p: p["end"] - p["start"], reverse=True)
    kept = []
    for p in found:
        if all(p["end"] <= k["start"] or p["start"] >= k["end"] for k in kept):
            kept.append(p)
    return sorted(kept, key=lambda p: p["start"])


def extract_passages(docx_path: str, corpus: dict[str, str], doc_id: str | None = None) -> list[dict]:
    """Every passage to fidelity-check in a .docx: quoted ones, then unquoted ones.

    Quoted passages come from extract_quotes. Unquoted passages are searched
    for against the authorities cited in the same paragraph and the one
    before it, skipping anything that overlaps a quote. Each result has the
    extract_quotes fields plus "quoted": True/False.
    """
    from docx import Document

    quotes = extract_quotes(docx_path, doc_id)
    results = [dict(q, quoted=True) for q in quotes]

    paragraphs = [p.text for p in Document(docx_path).paragraphs]
    for idx, text in enumerate(paragraphs):
        nearby = _cites_in(text) + (_cites_in(paragraphs[idx - 1]) if idx else [])
        sources = {}
        for cite in nearby:
            source = get_source_text(cite, corpus)
            # One entry per distinct source, keeping the first spelling seen.
            if source and source not in sources.values():
                sources[cite] = source

        quoted_spans = [(q["start"], q["end"]) for q in quotes if q["paragraph_index"] == idx]
        for p in find_unquoted_passages(text, sources):
            if any(p["start"] < e and p["end"] > s for s, e in quoted_spans):
                continue
            results.append(dict(p, doc_id=doc_id, paragraph_index=idx, quoted=False))
    return results
