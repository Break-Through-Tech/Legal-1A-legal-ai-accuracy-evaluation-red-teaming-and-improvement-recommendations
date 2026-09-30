"""Case-citation extraction utilities for Alaska P.2d/P.3d citations."""

import re
from pathlib import Path
from docx import Document


def normalize(text):
    if not text:
        return ""
    text = text.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def normalize_citation(text):
    text = normalize(text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*\(\s*", " (", text)
    text = re.sub(r"\s*\)\s*", ")", text)
    return text.strip()


REPORTER_PATTERN = re.compile(
    r"\b(?P<reporter>\d+\s+P\.(?:2d|3d)\s+\d+)\b", re.IGNORECASE
)

FULL_REPORTER_PATTERN = re.compile(
    r"\b(?P<reporter>\d+\s+P\.(?:2d|3d)\s+\d+)"
    r"\s*\(\s*Alaska\s+(?P<year>\d{4})\s*\)",
    re.IGNORECASE,
)

V_PATTERN = re.compile(r"\s+v\.\s+", re.IGNORECASE)

LEADING_BOUNDARY_PATTERN = re.compile(
    r"(?:\bsee also\s+|\bsee\s+|\bcf\.\s+|\bobserved\s+|"
    r"\brecognized\s+|\bheld\s+|\bnoted\s+|\bexplained\s+|"
    r"\bdiscussed\s+|\baddressed\s+|\bconcluded\s+|\bfound\s+|\bin\s+)",
    re.IGNORECASE,
)


def read_docx_paragraphs(path):
    """Return non-empty DOCX paragraphs while preserving original paragraph indexes."""
    document = Document(path)
    return [
        {"paragraph_index": i, "text": p.text}
        for i, p in enumerate(document.paragraphs)
        if p.text.strip()
    ]


def extract_case_name_from_context(context):
    """Extract the likely party names immediately before a reporter citation."""
    context = context.strip()
    if not context:
        return None

    previous_pattern = re.compile(
        r"\d+\s+P\.(?:2d|3d)\s+\d+\s*\(\s*Alaska\s+\d{4}\s*\)",
        re.IGNORECASE,
    )
    previous = list(previous_pattern.finditer(context))
    if previous:
        context = context[previous[-1].end():].strip()
        context = re.sub(r"^[,;:.]\s*", "", context)

    context = re.sub(r",\s*$", "", context)
    v_matches = list(V_PATTERN.finditer(context))
    if not v_matches:
        return None

    v_match = v_matches[-1]
    left_context = context[:v_match.start()].strip()
    right_side = context[v_match.end():].strip()
    if not left_context or not right_side:
        return None

    boundaries = list(LEADING_BOUNDARY_PATTERN.finditer(left_context))
    if boundaries:
        left_side = left_context[boundaries[-1].end():].strip()
    else:
        punctuation = [
            (left_context.rfind(". "), 2),
            (left_context.rfind("\n"), 1),
            (left_context.rfind(";"), 1),
            (left_context.rfind(":"), 1),
        ]
        punctuation = [x for x in punctuation if x[0] >= 0]
        if punctuation:
            position, length = max(punctuation, key=lambda x: x[0])
            left_side = left_context[position + length:].strip()
        else:
            left_side = left_context.strip()

    left_side = re.sub(
        r"^(?:as|in|see|see also|cf\.)\s+", "", left_side, flags=re.IGNORECASE
    ).strip()
    if not left_side:
        return None
    return f"{left_side} v. {right_side}".strip()


def corpus_case_name(context, reporter, reporter_index):
    candidates = reporter_index.get(normalize(reporter), [])
    normalized_context = normalize(context)
    matches = [
        c.get("case_name")
        for c in candidates
        if c.get("case_name") and normalize(c["case_name"]) in normalized_context
    ]
    return max(matches, key=len) if matches else None


def extract_full_citations(paragraph_text, document_id, paragraph_index, reporter_index=None):
    """Extract full Alaska case citations from one paragraph."""
    reporter_index = reporter_index or {}
    citations = []

    for match in FULL_REPORTER_PATTERN.finditer(paragraph_text):
        reporter = match.group("reporter")
        year = int(match.group("year"))
        context_start = max(0, match.start() - 350)
        context = paragraph_text[context_start:match.start()]

        case_name = corpus_case_name(context, reporter, reporter_index)
        method = "reporter_corpus_match" if case_name else "fallback_text_parse"
        if not case_name:
            case_name = extract_case_name_from_context(context)

        citation_start = match.start()
        if case_name:
            name_matches = list(re.finditer(re.escape(case_name), context, re.IGNORECASE))
            if name_matches:
                citation_start = context_start + name_matches[-1].start()
            citation_text = f"{case_name}, {reporter} (Alaska {year})"
        else:
            citation_text = paragraph_text[match.start():match.end()].strip()

        citations.append({
            "document_id": document_id,
            "paragraph_index": paragraph_index,
            "position_start": citation_start,
            "position_end": match.end(),
            "citation_text": citation_text,
            "normalized_citation": normalize_citation(citation_text),
            "case_name": case_name,
            "reporter_cite": reporter,
            "year": year,
            "citation_type": "full_case_citation",
            "extraction_method": method,
        })
    return citations


def extract_reporter_only_citations(paragraph_text, document_id, paragraph_index, full_citations):
    """Extract reporter-only citations not already contained in a full citation."""
    results = []
    # Use reporter span, not full case-name span, so preceding prose does not hide reporters.
    full_reporter_spans = [m.span() for m in FULL_REPORTER_PATTERN.finditer(paragraph_text)]

    for match in REPORTER_PATTERN.finditer(paragraph_text):
        start, end = match.span()
        if any(a <= start < b for a, b in full_reporter_spans):
            continue
        reporter = match.group("reporter")
        results.append({
            "document_id": document_id,
            "paragraph_index": paragraph_index,
            "position_start": start,
            "position_end": end,
            "citation_text": reporter,
            "normalized_citation": normalize_citation(reporter),
            "case_name": None,
            "reporter_cite": reporter,
            "year": None,
            "citation_type": "reporter_only",
            "extraction_method": "reporter_pattern",
        })
    return results


def detect_subsequent_history(paragraph_text, citation):
    tail = paragraph_text[citation["position_end"]:citation["position_end"] + 180]
    pattern = re.compile(
        r"^\s*,?\s*(?P<history>(?:aff['’]d|rev['’]d|cert\.\s+denied|"
        r"reh['’]g\s+denied).{0,120}?)(?=(?:[.;]|$))",
        re.IGNORECASE,
    )
    match = pattern.search(tail)
    return match.group("history").strip() if match else None


def find_unparsed_candidates(paragraph_text, document_id, paragraph_index, parsed_citations):
    """Log citation-like text that was not captured by a recognized pattern."""
    results, seen = [], set()
    covered = [(c["position_start"], c["position_end"]) for c in parsed_citations]
    patterns = [
        re.compile(
            r"\b[A-Z][^.;\n]{1,180}?\s+v\.\s+[^.;\n]{1,120}?\d{1,4}[^.;\n]{0,100}",
            re.IGNORECASE,
        ),
        re.compile(r"\b\d+\s+P\.[A-Za-z0-9.]*\s+\d+\b", re.IGNORECASE),
    ]

    for pattern in patterns:
        for match in pattern.finditer(paragraph_text):
            start, end = match.span()
            if any(start < b and end > a for a, b in covered):
                continue
            text = match.group(0).strip()
            key = (start, end, text)
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "document_id": document_id,
                "paragraph_index": paragraph_index,
                "position_start": start,
                "position_end": end,
                "citation_text": text,
                "normalized_citation": normalize_citation(text),
                "citation_type": "unparsed_candidate",
                "status": "UNPARSED",
            })
    return results


def extract_paragraph(paragraph_text, document_id, paragraph_index, reporter_index=None):
    """Extract recognized and unparsed citation candidates from one paragraph."""
    full = extract_full_citations(
        paragraph_text, document_id, paragraph_index, reporter_index or {}
    )
    for citation in full:
        citation["subsequent_history"] = detect_subsequent_history(paragraph_text, citation)

    short = extract_reporter_only_citations(
        paragraph_text, document_id, paragraph_index, full
    )
    parsed = full + short
    unparsed = find_unparsed_candidates(
        paragraph_text, document_id, paragraph_index, parsed
    )
    return parsed, unparsed


def extract_document(document_path, reporter_index=None):
    """Extract citations from a DOCX while preserving paragraph and position metadata."""
    path = Path(document_path)
    document_id = path.stem
    citations, unparsed = [], []

    for paragraph in read_docx_paragraphs(path):
        parsed, failed = extract_paragraph(
            paragraph["text"],
            document_id,
            paragraph["paragraph_index"],
            reporter_index or {},
        )
        citations.extend(parsed)
        unparsed.extend(failed)

    return {
        "document_id": document_id,
        "citations": citations,
        "unparsed_candidates": unparsed,
    }
