"""Legal 1A citation extractor.

Statutes and court-rule citation extraction for the ProseAI benchmark.
"""

from .extractor import extract_citations, extract_citations_from_text, normalize_citation

__all__ = ["extract_citations", "extract_citations_from_text", "normalize_citation"]