"""End-to-end document detection: citations, quotes, and a document risk flag.

This is the single entry point the rest of the project (and ProSeAI) should use.
It combines the three stages:

    document
      -> statute/rule/case citations + existence verdict
      -> quoted/unquoted passages + fidelity verdict
      -> document risk summary

The corpus is the only source of truth for verdicts. The answer key is never
read here; it is used by ``scripts/evaluate_pipeline.py`` for scoring.

Example
-------
    from citation_extractor.pipeline import analyze_document

    report = analyze_document("data/benchmark/documents/doc-0001.docx")
    report["risk"]["flagged"]        # True on a citation error or quoted alteration
    report["citations"][0]           # verdict for one citation
    report["quotes"][0]              # fidelity for one quoted passage
"""

from __future__ import annotations

import re
from pathlib import Path

from .case_parser import extract_document as extract_case_document
from .case_parser import normalize_case_key
from .existence import (
    check_case_existence,
    load_corpus_name_index,
    load_corpus_reporter_index,
)
from .extractor import extract_citations
from .labels import FABRICATED, OUT_OF_SCOPE, REAL, WRONG_REPORTER
from .quote_fidelity import check_quote
from .source_lookup import DEFAULT_CORPUS_DIR, get_source_text, load_corpus
from .statute_rule_existence import (
    check_rule_existence,
    check_statute_existence,
    load_civil_rule_index,
    load_evidence_rule_index,
    load_statute_index,
)
from .unquoted_passages import extract_passages

CASE_CITE_RE = re.compile(
    r"(?P<reporter>\d+\s+P\.(?:2d|3d)\s+\d+)"
    r"\s*\(\s*Alaska\s+\d{4}\s*\)",
    re.IGNORECASE,
)
_CASE_LEAD_IN_RE = re.compile(
    r"^(?:see also|see,?\s+e\.g\.,?|see|cf\.|in)\s+",
    re.IGNORECASE,
)


def load_indexes(corpus_dir: str | Path = DEFAULT_CORPUS_DIR) -> dict:
    """Load every corpus index once so it can be reused across documents."""
    corpus_dir = Path(corpus_dir)
    return {
        "statutes": load_statute_index(corpus_dir / "statutes.jsonl"),
        "civil_rules": load_civil_rule_index(corpus_dir / "rules.jsonl"),
        "evidence_rules": load_evidence_rule_index(corpus_dir / "rules-evidence.jsonl"),
        "case_names": load_corpus_name_index(corpus_dir / "cases.jsonl"),
        "case_reporters": load_corpus_reporter_index(corpus_dir / "cases.jsonl"),
        "sources": load_corpus(corpus_dir),
    }


def parse_case_citation(citation: str) -> dict | None:
    """Split ``Name v. Name, 123 P.3d 456 (Alaska 2011)`` into name + reporter."""
    match = CASE_CITE_RE.search(citation or "")
    if not match:
        return None
    name = re.sub(r",\s*$", "", citation[: match.start()].strip())
    name = _CASE_LEAD_IN_RE.sub("", name).strip()
    return {"case_name": name, "reporter": match.group("reporter").strip()}


def check_citation(cite: str, ctype: str, indexes: dict) -> str | None:
    """Return the existence verdict for one citation string.

    ``None`` means the citation could not be parsed (only possible for cases).
    """
    if ctype == "statute":
        return check_statute_existence(cite, indexes["statutes"])
    if ctype == "rule":
        return check_rule_existence(cite, indexes["civil_rules"], indexes["evidence_rules"])
    if ctype == "case":
        parsed = parse_case_citation(cite)
        if parsed is None:
            return None
        return check_case_existence(
            parsed["case_name"],
            parsed["reporter"],
            indexes["case_reporters"],
            indexes["case_names"],
        )
    raise ValueError(f"unknown citation type: {ctype}")


def _explanation(verdict: str, malformed: bool = False) -> str:
    if malformed:
        return "malformed statute number"
    if verdict == REAL:
        return "present in corpus"
    if verdict == WRONG_REPORTER:
        return "case name present, reporter not in corpus"
    if verdict == FABRICATED:
        return "not present in corpus"
    if verdict == OUT_OF_SCOPE:
        return "outside the corpus's curated scope"
    return verdict


def _statute_rule_citations(path: str, doc_id: str, indexes: dict) -> list[dict]:
    results = []
    for citation in extract_citations(path, doc_id=doc_id):
        malformed = citation.status == "MALFORMED"
        if citation.status == "OUT_OF_SCOPE":
            verdict = OUT_OF_SCOPE
        elif malformed:
            verdict = FABRICATED
        else:
            verdict = check_citation(citation.normalized, citation.type, indexes)

        results.append(
            {
                "type": citation.type,
                "cite": citation.normalized,
                "raw": citation.text,
                "normalized": citation.normalized,
                "verdict": verdict,
                "explanation": _explanation(verdict, malformed),
                "malformed": malformed,
                "case_name": None,
                "reporter_cite": None,
                "paragraph_index": citation.paragraph_index,
                "start": citation.start,
                "end": citation.end,
            }
        )
    return results


def _case_citations(path: str, indexes: dict) -> list[dict]:
    document = extract_case_document(path, indexes["case_reporters"])
    results = []
    for citation in document["citations"]:
        if citation["citation_type"] != "full_case_citation":
            continue
        verdict = check_case_existence(
            citation.get("case_name"),
            citation.get("reporter_cite"),
            indexes["case_reporters"],
            indexes["case_names"],
        )
        results.append(
            {
                "type": "case",
                "cite": citation["citation_text"],
                "raw": citation["citation_text"],
                "normalized": normalize_case_key(citation["citation_text"]),
                "verdict": verdict,
                "explanation": _explanation(verdict),
                "malformed": False,
                "case_name": citation.get("case_name"),
                "reporter_cite": citation.get("reporter_cite"),
                "year": citation.get("year"),
                "court": citation.get("court"),
                "pinpoint": citation.get("pinpoint"),
                "paragraph_index": citation["paragraph_index"],
                "start": citation["position_start"],
                "end": citation["position_end"],
            }
        )
    return results


def _quote_results(path: str, doc_id: str, indexes: dict) -> list[dict]:
    results = []
    for passage in extract_passages(path, indexes["sources"], doc_id):
        source = (
            get_source_text(passage["citation"], indexes["sources"])
            if passage.get("citation")
            else None
        )
        checked = check_quote(passage["text"], source)
        faithful = checked["faithful"]
        if faithful is True:
            status = "faithful"
        elif faithful is False:
            status = "altered"
        else:
            status = "unverified"
        results.append(
            {
                "text": passage["text"],
                "citation": passage.get("citation"),
                "quoted": passage.get("quoted", False),
                "status": status,
                "flagged": status == "altered",
                "tier": checked["tier"],
                "score": checked["score"],
                "paragraph_index": passage.get("paragraph_index"),
                "start": passage.get("start"),
                "end": passage.get("end"),
            }
        )
    return results


def _unique_authorities(citations: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for citation in citations:
        key = (citation["type"], citation["normalized"].casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique


def analyze_document(
    docx_path: str | Path,
    doc_id: str | None = None,
    indexes: dict | None = None,
) -> dict:
    """Run the full detector on one ``.docx`` and return a JSON-ready report."""
    path = str(docx_path)
    doc_id = doc_id or Path(path).stem
    indexes = indexes or load_indexes()

    citations = _statute_rule_citations(path, doc_id, indexes)
    citations.extend(_case_citations(path, indexes))
    quotes = _quote_results(path, doc_id, indexes)

    unique = _unique_authorities(citations)
    fabricated = [
        c for c in unique if c["verdict"] in (FABRICATED, WRONG_REPORTER)
    ]
    out_of_scope = [c for c in unique if c["verdict"] == OUT_OF_SCOPE]
    altered = [q for q in quotes if q["status"] == "altered"]
    quoted_altered = [q for q in altered if q["quoted"]]
    unquoted_altered = [q for q in altered if not q["quoted"]]
    unverified = [q for q in quotes if q["status"] == "unverified"]

    return {
        "doc_id": doc_id,
        "citations": citations,
        "quotes": quotes,
        "risk": {
            # Strict flag: a citation error or a misquoted passage in quote marks.
            "flagged": bool(fabricated or quoted_altered),
            # Broader flag for human review: unquoted copied text that no longer
            # matches its source, and passages whose source could not be found.
            "review_required": bool(fabricated or altered or unverified),
            "fabricated_citations": len(fabricated),
            "wrong_reporter_citations": sum(
                1 for c in fabricated if c["verdict"] == WRONG_REPORTER
            ),
            "altered_quotes": len(altered),
            "quoted_altered_quotes": len(quoted_altered),
            "possible_unquoted_alterations": len(unquoted_altered),
            "out_of_scope_citations": len(out_of_scope),
            "unverified_quotes": len(unverified),
            "unique_authorities": len(unique),
        },
    }
