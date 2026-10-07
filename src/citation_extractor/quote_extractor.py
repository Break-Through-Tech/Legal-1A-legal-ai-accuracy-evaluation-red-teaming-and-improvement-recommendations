"""Quoted-passage extraction for Alaska legal documents.

Finds verbatim quotations in a document and attaches each one to the
statute or rule citation it is quoting, e.g.

    ...Civil Rule 90.3(a), which provides that "a child support award ..."
                ^^^^^^^^^^^^^^^^^^                  ^^^^^^^^^^^^^^^^^^^^^^
                attached citation                   the quote

Quote text is returned exactly as it appears between the quote marks.
Normalization (case, punctuation, whitespace) is the fidelity checker's job,
not this module's.
"""

from __future__ import annotations

import re

from .extractor import CIVIL_RULE_RE, CIVP_RULE_RE, EVID_RULE_RE, STATUTE_RE

# Quotes shorter than this many words are usually defined-term labels
# ("Petitioner") rather than quotations of law.
MIN_QUOTE_WORDS = 3

# Group 1 is the text between the marks. [^"]* stops at the next mark, so
# straight quotes pair up in order: 1st with 2nd, 3rd with 4th, ...
QUOTE_PATTERNS = [
    re.compile(r'"([^"]*)"'),   # straight quotes
    re.compile(r'“([^”]*)”'),   # curly quotes
]

# A defined-term label: (hereinafter "Petitioner")
LABEL_RE = re.compile(r"hereinafter\W*$", re.IGNORECASE)

CITATION_PATTERNS = [STATUTE_RE, CIVIL_RULE_RE, CIVP_RULE_RE, EVID_RULE_RE]


def find_quotes(paragraph_text: str) -> list[dict]:
    """Return every quoted span in a paragraph.

    Each result is {"text": ..., "start": ..., "end": ...} where start/end are
    the character positions of the quote text itself (not the quote marks).
    Handles both curly quotes (“ ... ”) and straight quotes (" ... ").
    """
    quotes = []
    for pattern in QUOTE_PATTERNS:
        for m in pattern.finditer(paragraph_text):
            quotes.append({"text": m.group(1), "start": m.start(1), "end": m.end(1)})
    quotes.sort(key=lambda q: q["start"])
    return quotes


def is_legal_quote(quote: dict, paragraph_text: str) -> bool:
    """Decide whether a quoted span is a quotation of law worth checking.

    Rejects:
      - short labels like (hereinafter "Petitioner")
      - anything under MIN_QUOTE_WORDS words
    """
    if len(quote["text"].split()) < MIN_QUOTE_WORDS:
        return False
    # -1 skips the opening quote mark itself.
    before = paragraph_text[max(0, quote["start"] - 20):quote["start"] - 1]
    return not LABEL_RE.search(before)


def attach_citation(paragraph_text: str, quote_start: int) -> str | None:
    """Return the statute/rule citation the quote belongs to, or None.

    Rule of thumb: the closest citation that appears BEFORE the quote in the
    same paragraph. Return the citation exactly as written in the text
    (e.g. "AS 25.24.160(a)(4)(F)"), not normalized.
    """
    best = None
    for pattern in CITATION_PATTERNS:
        for m in pattern.finditer(paragraph_text):
            if m.end() <= quote_start and (best is None or m.end() > best.end()):
                best = m
    return best.group(0) if best else None


def extract_quotes(docx_path: str, doc_id: str | None = None) -> list[dict]:
    """Extract every legal quote from a .docx, in document order.

    Each result:
        {
            "doc_id": ...,
            "paragraph_index": ...,
            "text": ...,           # quote text as written
            "start": ..., "end": ...,
            "citation": ...,       # from attach_citation (may be None)
        }
    """
    from docx import Document

    results = []
    for idx, paragraph in enumerate(Document(docx_path).paragraphs):
        text = paragraph.text
        for quote in find_quotes(text):
            if not is_legal_quote(quote, text):
                continue
            results.append({
                "doc_id": doc_id,
                "paragraph_index": idx,
                "text": quote["text"],
                "start": quote["start"],
                "end": quote["end"],
                "citation": attach_citation(text, quote["start"]),
            })
    return results
