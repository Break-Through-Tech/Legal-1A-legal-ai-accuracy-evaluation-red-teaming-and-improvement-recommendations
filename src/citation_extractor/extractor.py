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

# Alaska statute number: AS <title>.<chapter>.<section> with optional
# pinpoints. Requires the "AS" or "Alaska Statute" marker so a bare section
# number like "25.24.160" is not treated as a citation by itself.
STATUTE_RE = re.compile(
    r"\b(?:(?:Alaska\s+Statute\s+)?AS\s+|Alaska\s+Statute\s+)"
    r"(?P<section>\d{2}\.\d{2}\.\d{3})"
    r"(?:\([0-9A-Za-z]+\))*",
    re.IGNORECASE,
)

# Civil rule: "Civil Rule 90.3(a)(3)" / "Alaska Civil Rule 90.3" / "Rule 90.3"
CIVIL_RULE_RE = re.compile(
    r"\b(?:Alaska\s+)?(?:Civil\s+)?Rule\s+"
    r"(?P<number>\d+(?:\.\d+)?)"
    r"(?:\([0-9A-Za-z]+\))*",
    re.IGNORECASE,
)

# Evidence rule: "Alaska R. Evid. 104(a)" (also bare "Alaska R. Evid. 104")
EVID_RULE_RE = re.compile(
    r"\bAlaska\s+R\.?\s*Evid\.?\s+"
    r"(?P<number>\d+)"
    r"(?:\([0-9A-Za-z]+\))?",
    re.IGNORECASE,
)

# Civil procedure full form (rare in docs, robust anyway):
# "Alaska R. Civ. P. 90.3"
CIVP_RULE_RE = re.compile(
    r"\bAlaska\s+R\.?\s*Civ\.?\s*P\.?\s+"
    r"(?P<number>\d+(?:\.\d+)?)"
    r"(?:\([0-9A-Za-z]+\))*",
    re.IGNORECASE,
)


@dataclass
class Citation:
    text: str
    normalized: str
    type: str
    paragraph_index: int | None = None
    doc_id: str | None = None


def _normalize_statute(match: re.Match) -> str:
    return f"AS {match.group('section')}"


def _normalize_rule(match: re.Match) -> str:
    return f"Alaska R. Civ. P. {match.group('number')}"


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
    for rx, norm in (
        (EVID_RULE_RE, _normalize_evid),
        (CIVP_RULE_RE, _normalize_civp),
        (CIVIL_RULE_RE, _normalize_rule),
        (STATUTE_RE, _normalize_statute),
    ):
        m = rx.search(cite)
        if m:
            return norm(m)
    return cite.strip()


def extract_citations_from_text(
    text: str, paragraph_index: int | None = None, doc_id: str | None = None
) -> list[Citation]:
    """Extract statute and rule citations from a block of text.

    Each citation is reported as it appears, plus its canonical normalized
    form, type, and position. Duplicate normalized citations within the same
    paragraph are merged.
    """
    text = _clean_text(text)
    found: dict[tuple[str, str], str] = {}

    def _record(match: re.Match, ctype: str, normalized: str) -> None:
        raw = re.sub(r"\s+", " ", match.group(0)).strip()
        found[(ctype, normalized)] = raw

    for m in STATUTE_RE.finditer(text):
        _record(m, "statute", _normalize_statute(m))

    for m in EVID_RULE_RE.finditer(text):
        _record(m, "rule", _normalize_evid(m))

    for m in CIVP_RULE_RE.finditer(text):
        _record(m, "rule", _normalize_civp(m))

    for m in CIVIL_RULE_RE.finditer(text):
        _record(m, "rule", _normalize_rule(m))

    results = [
        Citation(
            text=raw,
            normalized=norm,
            type=ctype,
            paragraph_index=paragraph_index,
            doc_id=doc_id,
        )
        for (ctype, norm), raw in sorted(found.items(), key=lambda kv: (kv[1][1], kv[1][0]))
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