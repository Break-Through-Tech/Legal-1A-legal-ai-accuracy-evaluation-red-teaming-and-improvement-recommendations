"""Per-document hallucination-risk score.

Combines the per-citation existence results and the per-passage quote-fidelity
results into one score per document, so a reviewer can tell which filings need
a human check before they reach a litigant.

Each finding has a weight from 0 to 1 by how severe and how certain it is.
The document score is the chance that at least one finding is a real problem:

    score = 1 - (1 - w1) * (1 - w2) * ...

so one fabricated citation is enough for a high score, while several weak
"needs review" flags add up slowly. Findings that are not problems (REAL) or
cannot be judged against this corpus (OUT_OF_SCOPE) weigh 0.

Uses only the corpus and the document, never the answer key, so it runs on
any document. Weights and threshold are starting points; see
scripts/evaluate_document_risk.py for how they are checked against the
benchmark's clean/corrupt labels.
"""

from __future__ import annotations

from typing import Iterable

from .existence import check_case_existence
from .labels import FABRICATED, OUT_OF_SCOPE, REAL, WRONG_REPORTER
from .quote_fidelity import check_quote
from .source_lookup import get_source_text
from .statute_rule_existence import check_rule_existence, check_statute_existence

# Quote-fidelity findings. The quote checker reports faithful/altered;
# an altered passage in quote marks is ALTERED_QUOTE,
# sentence found without quote marks is POSSIBLE_ALTERATION
ALTERED_QUOTE = "altered_quote"
POSSIBLE_ALTERATION = "possible_alteration"

# How much each finding counts toward the score.
FINDING_WEIGHTS = {
    FABRICATED: 1.0,            # cited authority is not in the corpus
    ALTERED_QUOTE: 0.8,         # quoted law does not match the source
    WRONG_REPORTER: 0.5,        # real case, cited with the wrong reporter
    POSSIBLE_ALTERATION: 0.2,   # unquoted copied text with added words
    REAL: 0.0,
    OUT_OF_SCOPE: 0.0,          # real law outside the corpus (e.g. AS 11.56.807)
}
# Documents scoring >= this threshold are flagged for review
# 0.5 flags any single wrong-reporter case or worse
RISK_THRESHOLD = 0.5


def score_document(findings: Iterable[str]) -> float:
    """Combine a document's findings into one risk score from 0 to 1.

    Each finding is a label such as FABRICATED or ALTERED_QUOTE. Unknown labels
    weigh 0, so new finding types never raise the score until given a weight.
    """
    no_problem = 1.0
    for finding in findings:
        no_problem *= 1.0 - FINDING_WEIGHTS.get(finding, 0.0)
    return 1.0 - no_problem


def assess_document(findings: Iterable[str], threshold: float = RISK_THRESHOLD) -> dict:
    """Score a document and decide whether to flag it for review.

    Returns {"score", "flagged", "counts"}, where counts tallies each finding
    with a nonzero weight so a reviewer can see why the document was flagged.
    """
    findings = list(findings)
    score = score_document(findings)
    counts: dict[str, int] = {}
    for finding in findings:
        if FINDING_WEIGHTS.get(finding, 0.0) > 0:
            counts[finding] = counts.get(finding, 0) + 1
    return {"score": score, "flagged": score >= threshold, "counts": counts}


def existence_findings(
    statute_rule_citations: Iterable,
    case_citations: Iterable[dict],
    statute_index: set[str],
    civil_index: set[str],
    evidence_index: set[str],
    reporter_index: dict,
    name_index: dict,
) -> list[str]:
    """Run the existence checkers on one document's extracted citations.

    statute_rule_citations are Citation objects from extractor.extract_citations
    (type "statute" or "rule"); case_citations are dicts from
    case_parser.extract_document (with "case_name" and "reporter_cite").
    Returns one label per distinct citation: REAL, FABRICATED, WRONG_REPORTER or
    OUT_OF_SCOPE. A citation repeated in the document counts once, so citing one
    fabricated case five times is one problem, not five.
    """
    checked = {}  # citation key -> label
    for citation in statute_rule_citations:
        key = (citation.type, citation.normalized)
        if key in checked:
            continue
        if citation.type == "statute":
            checked[key] = check_statute_existence(citation.normalized, statute_index)
        else:
            checked[key] = check_rule_existence(citation.normalized, civil_index, evidence_index)
    for case in case_citations:
        key = ("case", case.get("case_name"), case.get("reporter_cite"))
        if key in checked:
            continue
        checked[key] = check_case_existence(
            case.get("case_name"), case.get("reporter_cite"), reporter_index, name_index
        )
    return list(checked.values())


def quote_findings(passages: Iterable[dict], source_corpus: dict[str, str]) -> list[str]:
    """Run the quote-fidelity checker on one document's passages.

    passages are dicts from unquoted_passages.extract_passages (with "text",
    "citation" and "quoted"); source_corpus is source_lookup.load_corpus().
    Returns one label per judged passage: REAL if faithful, ALTERED_QUOTE if an
    altered passage is in quote marks, POSSIBLE_ALTERATION if it is not.
    Passages with no source or unrelated to their citation are not judged and
    add no finding (a fabricated citation is already counted by existence_findings).
    """
    findings = []
    for passage in passages:
        source = get_source_text(passage["citation"], source_corpus) if passage["citation"] else None
        faithful = check_quote(passage["text"], source)["faithful"]
        if faithful is None:
            continue
        if faithful:
            findings.append(REAL)
        elif passage["quoted"]:
            findings.append(ALTERED_QUOTE)
        else:
            findings.append(POSSIBLE_ALTERATION)
    return findings
