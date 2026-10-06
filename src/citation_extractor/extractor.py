"""Statutes and rules citation extraction for Alaska legal documents.

The benchmark is the ProseAI frozen Alaska family-law corpus. Citation
formats that appear in the 200 benchmark documents (see data-audit-summary):

Statutes:
  - "AS 25.24.310(a)"                    (canonical)
  - "Alaska Statute AS 25.20.060"        (prose prefix)
  - "Alaska Statute 25.24.160(a)(4)"     (prose prefix, no AS)
  - pinpoints: (a), (a)(3), (d)(2)

Civil rules (docs use the short form; corpus stores "Alaska R. Civ. P. X"):
  - "Civil Rule 90.3(a)(3)"
  - "Alaska Civil Rule 90.3"
  - "Rule 90.3"                         (bare form = civil rule in this corpus)

Evidence rules (already "Alaska R. Evid." in both docs and corpus):
  - "Alaska R. Evid. 104(a)"
"""

from __future__ import annotations

import re
import html
from dataclasses import dataclass

STATUTE_RE = re.compile(
    r"\b(?:Alaska\s+Stat(?:utes?)?\.?\s+(?:AS\s+)?|AS\s+)(?:§+\s*)?"
    r"(?P<title>\d{1,2})\.(?P<chapter>\d{2})\.(?P<section>\d{3})(?!\d)"
    r"(?:\([0-9A-Za-z]+\))*",
    re.IGNORECASE,
)

# CHANGED(2026-10-06): a statute number with 4+ digits are reported with status="MALFORMED" instead of being dropped / matched as a shorter section
MALFORMED_STATUTE_RE = re.compile(
    r"\b(?:Alaska\s+Stat(?:utes?)?\.?\s+(?:AS\s+)?|AS\s+)(?:§+\s*)?"
    r"(?P<title>\d{1,2})\.(?P<chapter>\d{2})\.(?P<section>\d{4,})",
    re.IGNORECASE,
)

_STATUTE_TAIL_RE = re.compile(
    r"\s*(?:-|–|to|and|,)\s*(?:and\s+)?\.(?P<section>\d{3})(?!\d)(?:\([0-9A-Za-z]+\))*",
    re.IGNORECASE,
)

_NUM = r"\d+(?:\.\d+)?(?:\([0-9A-Za-z]+\))*"
RULE_RE = re.compile(
    r"\b(?:Alaska\s+)?"
    r"(?:(?P<family>(?i:Evidence|Appellate|Criminal|Probate|Administrative|Civil))\s+)?"
    r"(?:(?:Rule|RULE)\s+(?P<one>" + _NUM + r")"
    r"|(?:Rules|RULES)\s+(?P<many>" + _NUM + r"(?:\s*(?:,\s*and|,|and)\s*" + _NUM + r")*))"
)

EVID_RULE_RE = re.compile(
    r"\b(?:Alaska\s+R\.?\s*Evid\.?|Alaska\s+Rules?\s+of\s+Evidence)\s+"
    r"(?P<number>\d+)"
    r"(?:\([0-9A-Za-z]+\))?",
    re.IGNORECASE,
)

CIVP_RULE_RE = re.compile(
    r"\bAlaska\s+R\.?\s*Civ\.?\s*P\.?\s+"
    r"(?P<number>\d+(?:\.\d+)?)"
    r"(?:\([0-9A-Za-z]+\))*",
    re.IGNORECASE,
)


# CHANGED(2026-10-06): added start/end and status because case_parser already has positions, so statutes, rules and cases can share a schema
#   status==None for a normal citation, status=="MALFORMED" for a statute number with 4+ digits, and status=="OUT_OF_SCOPE" for rule family
@dataclass
class Citation:
    text: str
    normalized: str
    type: str
    paragraph_index: int | None = None
    doc_id: str | None = None
    start: int | None = None
    end: int | None = None
    status: str | None = None


def _normalize_statute(match: re.Match) -> str:
    return f"AS {match.group('title')}.{match.group('chapter')}.{match.group('section')}"


def _rule_numbers(match: re.Match) -> list[str]:
    """Rule numbers in a RULE_RE match; pinpoints are dropped first so "90.3(a)(2)" is not read as rules 90.3 and 2."""
    block = match.group("one") or match.group("many")
    return re.findall(r"\d+(?:\.\d+)?", re.sub(r"\([0-9A-Za-z]+\)", "", block))


def _rule_kind(match: re.Match) -> str:
    family = (match.group("family") or "").casefold()
    if family in ("", "civil"):
        return "civil"
    if family == "evidence":
        return "evidence"
    return "other"


def _normalize_evid(match: re.Match) -> str:
    return f"Alaska R. Evid. {match.group('number')}"


def _normalize_civp(match: re.Match) -> str:
    return f"Alaska R. Civ. P. {match.group('number')}"


def _clean_text(paragraph: str) -> str:
    return html.unescape(paragraph)

def normalize_citation(cite: str) -> str:
    """Normalize a citation string to its canonical base form.

    Strips pinpoints and prose prefixes so extracted and corpus/answer-key
    strings can be compared exactly.
    """
    cite = _clean_text(cite)
    m = EVID_RULE_RE.search(cite)
    if m:
        return _normalize_evid(m)
    m = CIVP_RULE_RE.search(cite)
    if m:
        return _normalize_civp(m)
    m = RULE_RE.search(cite)
    if m:
        number = _rule_numbers(m)[0]
        kind = _rule_kind(m)
        if kind == "civil":
            return f"Alaska R. Civ. P. {number}"
        if kind == "evidence":
            return f"Alaska R. Evid. {number}"
        return cite.strip()
    m = STATUTE_RE.search(cite)
    if m:
        return _normalize_statute(m)
    return cite.strip()


def extract_citations_from_text(
    text: str, paragraph_index: int | None = None, doc_id: str | None = None
) -> list[Citation]:
    """Extract statute and rule citations from a block of text.

    Each citation is reported as it appears, plus its canonical normalized
    form, type, and position. Duplicate normalized citations within the same
    paragraph are merged (the first occurrence's text and position are kept).
    """
    text = _clean_text(text)
    # CHANGED(2026-10-06): the dict now keeps the FIRST occurrence's (start, end, raw, status) so result has a position
    found: dict[tuple[str, str], tuple[int, int, str, str | None]] = {}

    def _record(start: int, end: int, ctype: str, normalized: str, status: str | None = None) -> None:
        raw = re.sub(r"\s+", " ", text[start:end]).strip()
        found.setdefault((ctype, normalized), (start, end, raw, status))

    for m in STATUTE_RE.finditer(text):
        _record(m.start(), m.end(), "statute", _normalize_statute(m))
        pos = m.end()
        while True:
            tail = _STATUTE_TAIL_RE.match(text, pos)
            if not tail:
                break
            norm = f"AS {m.group('title')}.{m.group('chapter')}.{tail.group('section')}"
            _record(m.start(), tail.end(), "statute", norm)
            pos = tail.end()

    for m in MALFORMED_STATUTE_RE.finditer(text):
        norm = f"AS {m.group('title')}.{m.group('chapter')}.{m.group('section')}"
        _record(m.start(), m.end(), "statute", norm, status="MALFORMED")

    for m in EVID_RULE_RE.finditer(text):
        _record(m.start(), m.end(), "rule", _normalize_evid(m))

    for m in CIVP_RULE_RE.finditer(text):
        _record(m.start(), m.end(), "rule", _normalize_civp(m))

    for m in RULE_RE.finditer(text):
        kind = _rule_kind(m)
        for number in _rule_numbers(m):
            if kind == "civil":
                _record(m.start(), m.end(), "rule", f"Alaska R. Civ. P. {number}")
            elif kind == "evidence":
                _record(m.start(), m.end(), "rule", f"Alaska R. Evid. {number}")
            else:
                _record(m.start(), m.end(), "rule", f"{m.group('family').title()} Rule {number}", status="OUT_OF_SCOPE")

    # CHANGED(2026-10-06): sorted by position
    results = [
        Citation(
            text=raw,
            normalized=norm,
            type=ctype,
            paragraph_index=paragraph_index,
            doc_id=doc_id,
            start=start,
            end=end,
            status=status,
        )
        for (ctype, norm), (start, end, raw, status) in sorted(
            found.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[0][1])
        )
    ]
    return results


def extract_citations(docx_path: str, doc_id: str | None = None) -> list[Citation]:
    """Extract statute and rule citations from a .docx file.

    Preserves paragraph structure (citations are attributed to the paragraph
    they appear in). Footnotes are not handled yet; the benchmark uses inline
    parenthetical citations.
    """
    from docx import Document

    document = Document(docx_path)
    results: list[Citation] = []
    for idx, paragraph in enumerate(document.paragraphs):
        text = paragraph.text
        if not text.strip():
            continue
        results.extend(
            extract_citations_from_text(text, paragraph_index=idx, doc_id=doc_id)
        )
    return results
