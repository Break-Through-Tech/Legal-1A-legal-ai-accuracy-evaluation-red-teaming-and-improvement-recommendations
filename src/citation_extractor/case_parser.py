"""Case-citation extraction utilities for Alaska P.2d/P.3d citations"""

import re
from pathlib import Path
from docx import Document

# CHANGED(2026-10-06) overall notes for this module (numbers measured on the 200 benchmark documents against the answer key):
#   * The case name is still taken FROM cases.jsonl whenever the reporter is known (corpus_case_name): 1,603 of 1,666 extractions use that
#     path, so a "100% recall" with the corpus lookup mostly reflects a corpus lookup. The real text-parsing path (reporter_index=None) was
#     the weak spot: only 52 extractions used it and 26 of those over-captured prose. After the fixes marked CHANGED below it matches
#     the key's cleaned case name for 1,154 of 1,172 key cases (was 761), and all 7 `raw_extracted` examples (DATA_DICTIONARY 4.2) are
#     exact. The accuracy report should still say which path produced each result.
#   * Remaining: 18 extracted names still carry extra words. Some are the document's own wording ("State, Child Support Enforcement
#     Division v. Bromley"; the key's cleaned cite omits "State,"); the rest are lead-ins such as "The Court should further ensure,
#     consistent with ...", which cannot be removed without a real grammar.
#   * Still open (team decision, see the __init__.py note): this module is not exported and uses dicts, not extractor.Citation.


def normalize(text):
    if not text:
        return ""
    text = text.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()

# CHANGED(2026-10-06): this function was called normalize_citation which is the same with extractor.normalize_citation but different behaviour
# Fixed to normalize_case_key
def normalize_case_key(text):
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
    r"(?:\s*,\s*(?P<pinpoint>\d+(?:\s*[-–]\s*\d+)?))?"
    r"\s*\(\s*(?P<court>Alaska(?:\s+Ct\.\s+App\.)?)\s+(?P<year>\d{4})\s*\)",
    re.IGNORECASE,
)

V_PATTERN = re.compile(r"\s+v\.\s+", re.IGNORECASE)

LEADING_BOUNDARY_PATTERN = re.compile(
    r"(?:\bsee also\s+|\bsee\s+|\bcf\.\s+|\bobserved\s+|"
    r"\brecognized\s+|\bheld\s+|\bnoted\s+|\bexplained\s+|"
    r"\bdiscussed\s+|\baddressed\s+|\bconcluded\s+|\bfound\s+|\bin\s+|"
    r"\bsuch as\s+|\bconsistent with\s+)",  # CHANGED(2026-10-06): "cases such as X v. Y", "consistent with X v. Y" left the lead-in in the name
    re.IGNORECASE,
)


def read_docx_paragraphs(path):
    """Return non-empty DOCX paragraphs, preserving original paragraph indexes"""
    document = Document(path)
    return [
        {"paragraph_index": i, "text": p.text}
        for i, p in enumerate(document.paragraphs)
        if p.text.strip()
    ]


# CHANGED(2026-10-06) -- helpers for the caption fix in extract_case_name_from_context (see note there)
#   Abbreviations that end in "." but do not end a sentence, initials are also handled separately ("A.", "D.D.")
#   Sentence-opening words that sometimes are in front of a party name
_ABBREVIATIONS = {
    "dep't", "dept.", "soc.", "servs.", "svcs.", "serv.", "div.", "inc.", "co.", "corp.", "ltd.", "rel.", "no.", "jr.", "sr.", "st.",
    "assoc.", "natl.", "ctr.", "bd.", "univ.", "mr.", "mrs.", "ms.", "dr.", "u.s.", "hosp.", "dist.", "admin.", "fed.", "off.",
    "bur.", "ins.", "auth.", "dev.", "env.", "educ.", "cir.", "ak.",
}
_LEADING_ADVERBS = {
    "additionally", "moreover", "furthermore", "however", "similarly", "likewise", "also", "thus", "therefore", "accordingly",
}
_IN_RE_PATTERN = re.compile(r"\b(?:In\s+re|In\s+the\s+Matter\s+of|Matter\s+of|Ex\s+parte)\s+", re.IGNORECASE)


def _is_sentence_end(token):
    """True if ends of a sentence; False for initials ("A.", "D.D.") and common abbreviations ("Soc.", "Servs.")."""
    if not token.endswith("."):
        return False
    if re.fullmatch(r"(?:[A-Za-z]\.)+", token):
        return False
    return token.casefold() not in _ABBREVIATIONS


def _cut_after_last_sentence_end(text):
    """Keep only the text after the last sentence"""
    cut = 0
    for m in re.finditer(r"(\S+)\s+", text):
        if _is_sentence_end(m.group(1)):
            cut = m.end()
    return text[cut:]


def _in_re_name(context):
    """Caption without " v. " ("In re Marriage of Smith")"""
    last = None
    for m in _IN_RE_PATTERN.finditer(context):
        last = m
    if last is None:
        return None
    name = context[last.start():].strip().rstrip(",").strip()
    for m in re.finditer(r"(\S+)\s+", name):
        if m.start() >= last.end() - last.start() and _is_sentence_end(m.group(1)):
            name = name[:m.end()].strip()
            break
    return name or None


def extract_case_name_from_context(context):
    """Extract the likely party names before a reporter citation"""
    context = context.strip()
    if not context:
        return None
    previous = list(FULL_REPORTER_PATTERN.finditer(context))
    if previous:
        context = context[previous[-1].end():].strip()
        context = re.sub(r"^[,;:.]\s*", "", context)

    context = re.sub(r",\s*$", "", context)
    v_matches = list(V_PATTERN.finditer(context))
    if not v_matches:
        return _in_re_name(context)  # CHANGED(2026-10-06): captions without " . " used to return None

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

    left_side = _cut_after_last_sentence_end(left_side).strip()
    first, _, rest = left_side.partition(" ")
    if rest and first.endswith(",") and first[:-1].casefold() in _LEADING_ADVERBS:
        left_side = rest.strip()

    # CHANGED(2026-10-06): drop leading "and"/"but"/"The" only at the start of the name because some party names also contain it ("Smith and Jones v. X")
    left_side = re.sub(
        r"^(?:as|in|see|see also|cf\.|and|but|the)\s+", "", left_side, flags=re.IGNORECASE
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
        # CHANGED(2026-10-06): keep the court and pinpoint (see FULL_REPORTER_PATTERN)
        court = re.sub(r"\s+", " ", match.group("court"))
        pinpoint = match.group("pinpoint")
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
            citation_text = f"{case_name}, {reporter} ({court} {year})"  # CHANGED(2026-10-06): fixed hard-coded "Alaska"
        else:
            citation_text = paragraph_text[match.start():match.end()].strip()

        citations.append({
            "document_id": document_id,
            "paragraph_index": paragraph_index,
            "position_start": citation_start,
            "position_end": match.end(),
            "citation_text": citation_text,
            "normalized_citation": normalize_case_key(citation_text),
            "case_name": case_name,
            "reporter_cite": reporter,
            "year": year,
            "court": court,        # CHANGED(2026-10-06): new field
            "pinpoint": pinpoint,  # CHANGED(2026-10-06): new field (None when the citation has no pinpoint page)
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
            "normalized_citation": normalize_case_key(reporter),
            "case_name": None,
            "reporter_cite": reporter,
            "year": None,
            "citation_type": "reporter_only",
            "extraction_method": "reporter_pattern",
        })
    return results


# CHANGED(2026-10-06):
#   1. The old pattern ended at the first "." or ";", which is the "." INSIDE "P.3d": "..., aff'd, 140 P.3d 100 (Alaska 2006)."
#      fixed: history ends where the cited citation ends; when there is no citation, at the next ";" or at a sentence end (". " + capital letter)
#   2. The cited history ("140 P.3d 100") was also extracted as its own full_case_citation
_HISTORY_SIGNAL = r"(?:aff['’]d|rev['’]d|cert\.\s+denied|reh['’]g\s+denied)"


def detect_subsequent_history(paragraph_text, citation):
    head = citation["position_end"]
    tail = paragraph_text[head:head + 180]
    m = re.match(rf"\s*,?\s*(?P<signal>{_HISTORY_SIGNAL})\s*,?\s*", tail, re.IGNORECASE)
    if not m:
        return None

    rep = FULL_REPORTER_PATTERN.match(tail, m.end())  # history is a citation: end after its "(Alaska yyyy)"
    if rep:
        end = rep.end()
        citation["subsequent_history_span"] = {
            "position_start": head + rep.start(),
            "position_end": head + rep.end(),
            "role": "subsequent_history",
        }
    else:
        stop = re.search(r";|\.\s+(?=[A-Z])|$", tail[m.end():])
        end = m.end() + stop.start()
    return tail[m.start("signal"):end].strip()


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
                "normalized_citation": normalize_case_key(text),
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

    # CHANGED(2026-10-06): a citation that is only the subsequent history of another one, compared by end position
    history_ends = {
        c["subsequent_history_span"]["position_end"] for c in full if c.get("subsequent_history_span")
    }
    full = [c for c in full if c["position_end"] not in history_ends]

    short = extract_reporter_only_citations(
        paragraph_text, document_id, paragraph_index, full
    )
    parsed = full + short
    unparsed = find_unparsed_candidates(
        paragraph_text, document_id, paragraph_index, parsed
    )
    return parsed, unparsed


def extract_document(document_path, reporter_index=None):
    """Extract citations from a DOCX while preserving paragraph and position metadata"""
    path = Path(document_path)
    document_id = path.stem
    citations, unparsed = [], []
    last_full = {}  # CHANGED(2026-10-06): normalized reporter -> recent full citation seen so far in this document

    for paragraph in read_docx_paragraphs(path):
        parsed, failed = extract_paragraph(
            paragraph["text"],
            document_id,
            paragraph["paragraph_index"],
            reporter_index or {},
        )
        # CHANGED(2026-10-06): link each reporter-only to the nearest peceding full citation with the same reporter,
        #   in this paragraph (earlier in the text) or in an earlier paragraph.
        for c in parsed:
            if c["citation_type"] != "reporter_only":
                continue
            key = normalize(c["reporter_cite"])
            earlier = [
                f for f in parsed
                if f["citation_type"] == "full_case_citation"
                and normalize(f["reporter_cite"]) == key
                and f["position_end"] <= c["position_start"]
            ]
            target = earlier[-1] if earlier else last_full.get(key)
            if target:
                c["role"] = "short_form"
                c["resolves_to"] = {
                    "paragraph_index": target["paragraph_index"],
                    "position_start": target["position_start"],
                }
        for c in parsed:
            if c["citation_type"] == "full_case_citation":
                last_full[normalize(c["reporter_cite"])] = c
        citations.extend(parsed)
        unparsed.extend(failed)

    return {
        "document_id": document_id,
        "citations": citations,
        "unparsed_candidates": unparsed,
    }
