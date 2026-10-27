"""Legal 1A citation extractor and hallucination detector.

Citation extraction, existence checking, quote-fidelity checking and a
per-document hallucination-risk score for the ProseAI benchmark.
"""

from .extractor import extract_citations, extract_citations_from_text, normalize_citation
# ADDED(2026-10-06): expose the case existence checker as part of the library API.
from .existence import check_case_existence, load_corpus_name_index, load_corpus_reporter_index
# ADDED(2026-10-27): expose the Checkpoint 2 modules (statute/rule existence, quote
#   fidelity, document risk). Was: only the Milestone 1 entry points were exported.
from .case_parser import extract_document
from .document_risk import RISK_THRESHOLD, assess_document, existence_findings, quote_findings
from .labels import FABRICATED, OUT_OF_SCOPE, REAL, WRONG_REPORTER
from .quote_fidelity import check_quote
from .source_lookup import get_source_text, load_corpus
from .statute_rule_existence import (
    check_rule_existence,
    check_statute_existence,
    load_civil_rule_index,
    load_evidence_rule_index,
    load_statute_index,
)
from .unquoted_passages import extract_passages

__all__ = [
    # extraction
    "extract_citations",
    "extract_citations_from_text",
    "normalize_citation",
    "extract_document",
    "extract_passages",
    # existence
    "check_case_existence",
    "load_corpus_name_index",
    "load_corpus_reporter_index",
    "check_statute_existence",
    "check_rule_existence",
    "load_statute_index",
    "load_civil_rule_index",
    "load_evidence_rule_index",
    # quote fidelity
    "check_quote",
    "get_source_text",
    "load_corpus",
    # document risk
    "RISK_THRESHOLD",
    "assess_document",
    "existence_findings",
    "quote_findings",
    # labels
    "REAL",
    "FABRICATED",
    "WRONG_REPORTER",
    "OUT_OF_SCOPE",
]
