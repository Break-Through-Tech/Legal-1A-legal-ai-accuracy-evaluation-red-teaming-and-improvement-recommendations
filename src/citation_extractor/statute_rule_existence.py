"""Statute and court-rule existence checking against the frozen corpus.

Answers the Stage-2 existence question (DATA_DICTIONARY §3, §9) for the two
non-case authority types: is a citation the document uses actually present in
the ProSeAI frozen Alaska corpus? Uses only the corpus, never the answer key,
so it runs on any document.

Two rules of the benchmark matter here and are easy to get wrong:

* Statutes match the corpus ``citation`` string directly (§3.1).
* Court rules must be matched on the normalized rule NUMBER, never the
  citation string, because documents write "Civil Rule 90.3(a)" while the
  corpus stores "Alaska R. Civ. P. 90.3". Civil and evidence rules also share
  rule numbers, so they are kept in separate namespaces: "Civil Rule 90.3" and
  "Alaska R. Evid. 90.3" are different authorities (§3.1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .extractor import normalize_citation
from .labels import FABRICATED, OUT_OF_SCOPE, REAL

_STATUTE_NUM_RE = re.compile(r"AS\s+(\d+\.\d+\.\d+)", re.IGNORECASE)
_RULE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*$")

# ADDED (2026-10-20): corpus scope (DATA_DICTIONARY §3.2): all of Title 25 plus
#   Title 18 ch. 65-66. Covers the whole title, so a missing section in any Title 25
#   chapter is FABRICATED, not OUT_OF_SCOPE.
IN_SCOPE_TITLES = {"25"}               # all of Title 25
IN_SCOPE_CHAPTERS = {"18.65", "18.66"} # Title 18, DV/protective orders only

# ADDED (2026-10-20): checks whether a section number falls within the corpus scope, by its title or chapter
def _in_scope(section: str) -> bool:
    title, chapter, _ = section.split(".")
    return title in IN_SCOPE_TITLES or f"{title}.{chapter}" in IN_SCOPE_CHAPTERS


def _rule_number(citation: str) -> str | None:
    """Last number in a normalized rule citation, ignoring any subrule suffix.

    ``normalize_citation`` already collapses both the "Civil Rule" and
    "Alaska R. Civ. P." forms and strips pinpoints, so the number that remains
    is the rule number the corpus indexes on.
    """
    match = _RULE_NUM_RE.search(normalize_citation(citation).strip())
    return match.group(1) if match else None


def _iter_records(path: str | Path) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_statute_index(path: str | Path) -> set[str]:
    """Normalized ``"as 25.24.150"`` keys present in the statute corpus."""
    index: set[str] = set()
    for record in _iter_records(path):
        cite = (record.get("citation") or "").strip().casefold()
        if cite:
            index.add(cite)
    return index


def load_civil_rule_index(path: str | Path) -> set[str]:
    """Civil rule numbers present in the civil-rule corpus (``rules.jsonl``)."""
    index: set[str] = set()
    for record in _iter_records(path):
        number = _rule_number(record.get("citation") or "")
        if number:
            index.add(number)
    return index


def load_evidence_rule_index(path: str | Path) -> set[str]:
    """Evidence rule numbers from ``ruleNumber`` (``rules-evidence.jsonl``, §3.1).

    This file has no ``citation`` field, so the number is read from
    ``ruleNumber`` directly.
    """
    index: set[str] = set()
    for record in _iter_records(path):
        number = str(record.get("ruleNumber") or "").strip()
        if number:
            index.add(number)
    return index


def check_statute_existence(citation: str, statute_index: set[str]) -> str:
    """Return REAL, FABRICATED, or OUT_OF_SCOPE for one statute citation."""
    # CHANGED (2026-10-20): a statute missing from the corpus is OUT_OF_SCOPE when its
    #   title/chapter is outside the corpus (e.g. AS 11.56.807), else FABRICATED.
    match = _STATUTE_NUM_RE.search(normalize_citation(citation))
    key = f"as {match.group(1)}" if match else normalize_citation(citation).strip().casefold()
    if key in statute_index:
        return REAL
    elif match and not _in_scope(match.group(1)):
        return OUT_OF_SCOPE
    else:
        return FABRICATED


def check_rule_existence(
    citation: str, civil_index: set[str], evidence_index: set[str]
) -> str:
    """Return REAL, FABRICATED, or OUT_OF_SCOPE for one court-rule citation.

    Only civil and evidence rules are in scope (the corpus covers those two
    families). Any other rule family is OUT_OF_SCOPE rather than fabricated.
    """
    normalized = normalize_citation(citation)
    number = _rule_number(citation)
    if not number:
        return FABRICATED

    lowered = normalized.casefold()
    if "evid" in lowered:
        return REAL if number in evidence_index else FABRICATED
    if "civ" in lowered or lowered.startswith("rule "):
        return REAL if number in civil_index else FABRICATED
    return OUT_OF_SCOPE
