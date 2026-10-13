"""Legal 1A citation extractor.

Statutes and court-rule citation extraction for the ProseAI benchmark.
"""

from .extractor import extract_citations, extract_citations_from_text, normalize_citation
# ADDED(2026-10-06): expose the case existence checker as part of the library API.
from .existence import check_case_existence, load_corpus_name_index, load_corpus_reporter_index

__all__ = [
    "extract_citations",
    "extract_citations_from_text",
    "normalize_citation",
    "check_case_existence",
    "load_corpus_name_index",
    "load_corpus_reporter_index",
]