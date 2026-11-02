"""Legal 1A citation and quote hallucination detector.

Public API:
    analyze_document(path)  full document report (citations, quotes, risk)
    load_indexes()          load the frozen corpus once and reuse it
    extract_citations(path) statute/rule extraction only
    check_citation(cite, type, indexes)  existence verdict for one citation
"""

from .existence import (
    check_case_existence,
    load_corpus_name_index,
    load_corpus_reporter_index,
)
from .extractor import extract_citations, extract_citations_from_text, normalize_citation
from .pipeline import analyze_document, check_citation, load_indexes, parse_case_citation

__all__ = [
    "analyze_document",
    "check_citation",
    "load_indexes",
    "parse_case_citation",
    "extract_citations",
    "extract_citations_from_text",
    "normalize_citation",
    "check_case_existence",
    "load_corpus_name_index",
    "load_corpus_reporter_index",
]
