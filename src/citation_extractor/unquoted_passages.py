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

CHANGED (2026-11-17): short runs are chained across a small edit, so a one-word natural
misquote is found. The checker still makes the faithful/altered call.

Swapped or dropped words between two verbatim runs are NOT flagged here.
On the benchmark that rule caught no altered quotes and raised ~600 false
alarms: in unquoted text a changed word is ordinary paraphrase. Quoted
passages, which promise to be verbatim, still get the full check.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .quote_extractor import CITATION_PATTERNS, extract_quotes
# CHANGED (2026-11-17): also imports check_quote and locate_sources.
from .quote_fidelity import LIST_MARKER_RE, _PUNCT_MAP, check_quote
from .source_lookup import get_source_text, locate_sources

# Shortest run of matching words that counts as copied text.
MIN_RUN = 8

# ADDED (2026-11-17): chain settings; short runs join across small edits (was one 8-word run).
SEED_RUN = 4          # shortest run that can start or extend a chain
MIN_CHAIN_WORDS = 10  # copied words a chain needs in total
MAX_PARA_GAP = 1      # draft words added between runs
MAX_SOURCE_GAP = 8    # source words dropped between runs

# ADDED (2026-11-17): chained edit is altered only if all edited words are here
# (modals, quantifiers, determiners, negation); content-word edits are usually paraphrase.
FUNCTION_WORDS = frozenset("""
a an the all any each every both either neither other another such same one
shall may must will can should would could might
not no nor only also even just
is are be been being was were
and or but if when where whether unless until than as
who whom which that whose
of to for in on by at with from under over
""".split())

# ADDED (2026-11-17): also flags a pure omission of one of these (+4 natural, +28 noise).
RISK_WORDS = frozenset("""
all any each every both only not no nor unless except
shall must may will can should
""".split())

# ADDED (2026-11-17): on/off switch for RISK_WORDS, tuned by evaluate_holdout.py. Keep True.
RISK_OMISSIONS = True

# NOTE (2026-11-17): tried and dropped: flagging every pure omission (+2 natural, +265 noise), and "edge edits".

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


# ADDED (2026-11-17): "(a)(2)" no longer ends the clause early, so the appended tail is seen (doc-0170).
MARKERS_RE = re.compile(r"(?:\s*\((?:\d+|[a-z]|[ivx]+)\))+", re.IGNORECASE)


def _skip_markers(text: str, pos: int) -> int:
    """Position after any list markers directly following `pos`."""
    m = MARKERS_RE.match(text, pos)
    return m.end() if m else pos


def _ends_clause(text: str, pos: int) -> bool:
    """True if the next non-space character after `pos` ends a clause (or the text)."""
    # CHANGED (2026-11-17): skips list markers first.
    nxt = NEXT_CHAR_RE.match(text, _skip_markers(text, pos)).group(1)
    return nxt == "" or bool(CLAUSE_END_RE.match(nxt))


def _appended_end(paragraph: str, end: int) -> int | None:
    """End of 1-MAX_TAIL words added after `end`, up to the draft's punctuation; else None."""
    # ADDED (2026-11-17): step over list markers so the appended tail is seen.
    end = _skip_markers(paragraph, end)
    stop = CLAUSE_END_RE.search(paragraph, end)
    stop = stop.start() if stop else len(paragraph)
    tail = paragraph[end:stop]
    # A trailing citation ("under AS 25.24.150") is attribution, not an alteration.
    if any(p.search(tail) for p in CITATION_PATTERNS):
        return None
    return stop if 1 <= len(WORD_RE.findall(tail)) <= MAX_TAIL else None


def _runs(para_tokens: list[str], source_tokens: list[str]):
    # CHANGED (2026-11-17): was single runs only; now chains runs and returns the gap words.
    """Copied passages as (para_start, para_end, source_end, added, dropped, chained) word indexes, end exclusive.

    `added` / `dropped` are the words the draft added, or left out of the
    source, between the chained runs; `chained` is True if there were any runs
    to join (empty lists for a single verbatim run).

    A passage is one verbatim run of at least MIN_RUN words, or a chain of runs
    (each at least SEED_RUN words) separated by small edits, copying at least
    MIN_CHAIN_WORDS words in total.
    """
    matcher = SequenceMatcher(None, para_tokens, source_tokens, autojunk=False)
    seeds = [b for b in matcher.get_matching_blocks() if b.size >= SEED_RUN]
    chains, chain = [], []
    for block in seeds:
        if chain:
            last = chain[-1]
            if (block.a - (last.a + last.size) <= MAX_PARA_GAP
                    and block.b - (last.b + last.size) <= MAX_SOURCE_GAP):
                chain.append(block)
                continue
            chains.append(chain)
        chain = [block]
    if chain:
        chains.append(chain)

    runs = []
    for chain in chains:
        copied = sum(b.size for b in chain)
        if copied >= MIN_RUN if len(chain) == 1 else copied >= MIN_CHAIN_WORDS:
            last = chain[-1]
            added, dropped = [], []
            for prev, block in zip(chain, chain[1:]):
                added += para_tokens[prev.a + prev.size:block.a]
                dropped += source_tokens[prev.b + prev.size:block.b]
            runs.append((chain[0].a, last.a + last.size, last.b + last.size, added, dropped, len(chain) > 1))
    return runs


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
        # CHANGED (2026-11-17): also records chained / appended / edited words.
        for a_start, a_end, b_end, added, dropped, chained in _runs(para_tokens, source_tokens):
            start = para_words[a_start].start()
            end = para_words[a_end - 1].end()
            appended = False
            if _ends_clause(source, source_words[b_end - 1].end()):
                tail_end = _appended_end(paragraph, end)
                appended = tail_end is not None
                end = tail_end or end
            found.append({"text": paragraph[start:end], "start": start, "end": end, "citation": cite,
                          "chained": chained, "appended": appended,
                          "added_words": added, "dropped_words": dropped})

    # Keep the longest of any overlapping passages.
    found.sort(key=lambda p: p["end"] - p["start"], reverse=True)
    kept = []
    for p in found:
        if all(p["end"] <= k["start"] or p["start"] >= k["end"] for k in kept):
            kept.append(p)
    return sorted(kept, key=lambda p: p["start"])


# ADDED (2026-11-17): verdict for a passage; downgrades chained edits to "paraphrase".
def judge_passage(passage: dict, source: str | None) -> dict:
    """check_quote for an extracted passage, with chained passages judged conservatively.

    A chained passage (a copied run broken by a small edit) is only called
    altered when every edited word is a FUNCTION_WORDS word. Otherwise the
    edit looks like paraphrase: tier "paraphrase", not judged faithful or altered.
    """
    result = check_quote(passage["text"], source)
    if passage.get("chained") and not passage.get("appended") and result["faithful"] is False:
        added, dropped = passage.get("added_words", []), passage.get("dropped_words", [])
        function_only = all(w in FUNCTION_WORDS for w in added + dropped)
        risky_omission = RISK_OMISSIONS and not added and any(w in RISK_WORDS for w in dropped)
        if not (function_only or risky_omission):
            return dict(result, tier="paraphrase", faithful=None)
    return result


def extract_passages(docx_path: str, corpus: dict[str, str], doc_id: str | None = None) -> list[dict]:
    """Every passage to fidelity-check in a .docx: quoted then unquoted passages.

    Quoted passages come from extract_quotes. Unquoted passages are searched
    for against the authorities cited in the same paragraph and the nearest
    earlier non-blank paragraph, skipping anything that overlaps a quote.
    Each result has the extract_quotes fields plus "quoted": True/False.

    A citation that does not resolve to a corpus section (a fabricated or
    mistyped one) would leave its passage with nothing to be checked against.
    For those, the section the text was actually copied from is located by
    content (source_lookup.locate_sources): "citation" becomes that section. The
    unresolved citation itself is the existence checker's finding, not this module's.
    """
    from docx import Document

    quotes = extract_quotes(docx_path, doc_id)
    # CHANGED (2026-11-17): an unresolved cite now gets its source by content (was "no_source").
    results = []
    for q in quotes:
        item = dict(q, quoted=True)
        if not (item["citation"] and get_source_text(item["citation"], corpus)):
            located = locate_sources(item["text"], corpus)
            if located:
                item["citation"] = located[0]
        results.append(item)

    paragraphs = [p.text for p in Document(docx_path).paragraphs]
    for idx, text in enumerate(paragraphs):
        # CHANGED (2026-11-17): skip blank paragraphs when looking back (doc-0061).
        previous = next((paragraphs[j] for j in range(idx - 1, -1, -1) if paragraphs[j].strip()), "")
        nearby = _cites_in(text) + _cites_in(previous)
        sources = {}
        # ADDED (2026-11-17): set when a nearby citation has no corpus text.
        unresolved = False
        for cite in nearby:
            source = get_source_text(cite, corpus)
            if not source:
                unresolved = True
            # One entry per distinct source, keeping the first spelling seen.
            elif source not in sources.values():
                sources[cite] = source
        # ADDED (2026-11-17): add sections the paragraph shares text with as sources.
        if unresolved:
            for cite in locate_sources(text, corpus):
                source = corpus[cite]
                if source not in sources.values():
                    sources[cite] = source

        quoted_spans = [(q["start"], q["end"]) for q in quotes if q["paragraph_index"] == idx]
        for p in find_unquoted_passages(text, sources):
            if any(p["start"] < e and p["end"] > s for s, e in quoted_spans):
                continue
            results.append(dict(p, doc_id=doc_id, paragraph_index=idx, quoted=False))
    return results
