"""Case existence checking against the case corpus (cases.jsonl).

Decides whether an extracted case citation is real, a real case cited with the
wrong reporter, or fabricated. Uses only the corpus, never the answer key, so it
works on any document.
"""

import json
from .case_parser import normalize as _normalize_whitespace

REAL = "real"
WRONG_REPORTER = "wrong_reporter"
FABRICATED = "fabricated"


def normalize_key(text):
    """Casefold, collapse whitespace and trim edge punctuation for lookups."""
    return _normalize_whitespace(text).strip(" ,.;:")


def load_corpus_name_index(path):
    """Build normalized case-name -> known corpus records."""
    index = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            name = normalize_key(case.get("case_name"))
            if name:
                index.setdefault(name, []).append(case)
    return index


def load_corpus_reporter_index(path):
    """Build normalized reporter cite -> known corpus records."""
    index = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            reporter = normalize_key(case.get("reporter_cite"))
            if reporter:
                index.setdefault(reporter, []).append(case)
    return index


def names_compatible(a, b):
    """True when one normalized case name is a suffix of the other.

    Tolerates short captions ("rosario v. clare" vs "del rosario v. clare").
    """
    return bool(a and b) and (a == b or a.endswith(b) or b.endswith(a))


def check_case_existence(case_name, reporter, reporter_index, name_index):
    """Return REAL, WRONG_REPORTER or FABRICATED for one case citation.

    Looks up by reporter first (reporter cites are exact, names are not), then
    falls back to the case name to tell a swapped reporter from an invented case.
    """
    name = normalize_key(case_name)

    for case in reporter_index.get(normalize_key(reporter), []):
        if names_compatible(name, normalize_key(case.get("case_name"))):
            return REAL

    if name in name_index or any(names_compatible(name, known) for known in name_index):
        return WRONG_REPORTER  # real case, cited with a reporter that isn't its own

    return FABRICATED
