"""Evaluate extracted case citations against answer-key.json.

Reports extraction coverage and REAL/FABRICATED verification metrics.
The answer key is used only for scoring; predictions are produced from cases.jsonl.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_PATH = ROOT / "data" / "extracted-citations.json"
ANSWER_KEY_PATH = ROOT / "data" / "benchmark" / "answer-key.json"
CORPUS_PATH = ROOT / "data" / "corpus" / "cases.jsonl"


def normalize(text):
    if not text:
        return ""
    text = text.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip(" ,.;:")


def parse_answer_case(citation):
    """Split an answer-key case citation into case name and reporter."""
    match = re.search(
        r"(?P<reporter>\d+\s+P\.(?:2d|3d)\s+\d+)"
        r"\s*\(\s*Alaska\s+\d{4}\s*\)",
        citation or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    case_name = re.sub(r",\s*$", "", citation[:match.start()].strip())
    case_name = re.sub(
        r"^(?:see also|see,?\s+e\.g\.,?|see|cf\.|in)\s+",
        "",
        case_name,
        flags=re.IGNORECASE,
    ).strip()

    return {
        "case_name": case_name,
        "reporter": match.group("reporter").strip(),
    }


def load_corpus_name_index(path):
    """Build normalized case-name -> known corpus records."""
    index = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            name = normalize(case.get("case_name"))
            if name:
                index.setdefault(name, []).append(case)
    return index

# ADDED(2026-10-06): index the corpus by reporter cite
#   since reporter cites are exact same and case names are not'\
def load_corpus_reporter_index(path):
    """Build normalized reporter cite -> known corpus records."""
    index = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            reporter = normalize(case.get("reporter_cite"))
            if reporter:
                index.setdefault(reporter, []).append(case)
    return index


def names_compatible(a, b):
    """True when one normalized case name is a suffix of the other."""
    # ADDED(2026-10-06): tolerate short captions ("rosario v. clare" vs "del rosario v. clare")
    return bool(a and b) and (a == b or a.endswith(b) or b.endswith(a))

# CHANGED(2026-10-06): look up by reporter first and return a reason
def corpus_prediction(case_name, reporter, reporter_index, name_index):
    """Predict "real", "wrong_reporter" or "fabricated" using only cases.jsonl."""
    name = normalize(case_name)
    for case in reporter_index.get(normalize(reporter), []):
        if names_compatible(name, normalize(case.get("case_name"))):
            return "real"
    if name in name_index or any(names_compatible(name, known) for known in name_index):
        return "wrong_reporter" 

    return "fabricated"

def find_exact(answer_case, extracted_cases, used_indexes):
    """Find an unused extraction with an exact cleaned case-name and reporter match."""
    answer_name = normalize(answer_case["case_name"])
    answer_reporter = normalize(answer_case["reporter"])
    
    for i, item in enumerate(extracted_cases):
        if i in used_indexes:
            continue
        if item.get("citation_type") != "full_case_citation":
            continue

        if (
            normalize(item.get("case_name")) == answer_name
            and normalize(item.get("reporter_cite")) == answer_reporter
        ):
            return i, item

    return None


def find_substring_fallback(answer_case, extracted_cases, used_indexes):
    """Find an unused extraction using the legacy case-name substring tolerance.

    The reporter must still match exactly. This fallback accepts the match,
    but callers should count how often it is required.
    """
    answer_name = normalize(answer_case["case_name"])
    answer_reporter = normalize(answer_case["reporter"])

    for i, item in enumerate(extracted_cases):
        if i in used_indexes:
            continue
        if item.get("citation_type") != "full_case_citation":
            continue

        extracted_name = normalize(item.get("case_name"))

        if (
            normalize(item.get("reporter_cite")) == answer_reporter
            and answer_name
            and answer_name in extracted_name
        ):
            return i, item

    return None
    


def safe_divide(a, b):
    return a / b if b else 0.0


def confusion(rows):
    """TP/FP/FN/TN for scored rows, with fabricated = 1."""
    return {
        "TP": sum(r["true"] == 1 and r["pred"] == 1 for r in rows),
        "FP": sum(r["true"] == 0 and r["pred"] == 1 for r in rows),
        "FN": sum(r["true"] == 1 and r["pred"] == 0 for r in rows),
        "TN": sum(r["true"] == 0 and r["pred"] == 0 for r in rows),
    }


def main():
    for path in (EXTRACTED_PATH, ANSWER_KEY_PATH, CORPUS_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Missing required file: {path}")

    with EXTRACTED_PATH.open("r", encoding="utf-8") as f:
        extracted_documents = json.load(f)

    with ANSWER_KEY_PATH.open("r", encoding="utf-8") as f:
        answer_key = json.load(f)

    extracted_by_doc = {
        document["document_id"]: document.get("citations", [])
        for document in extracted_documents
    }
    name_index = load_corpus_name_index(CORPUS_PATH)
    reporter_index = load_corpus_reporter_index(CORPUS_PATH)

    expected = 0
    found = 0
    fallback_hits = 0  # CHANGED(2026-10-06): key cases that only matched the fallback
    missing = []
    y_true = []
    y_pred = []
    unverified = []    # ADDED(2026-10-06): collect unverified cites and per-citation rows
    rows = []

    for document in answer_key:
        doc_id = document["doc_id"]
        extracted_cases = extracted_by_doc.get(doc_id, [])
        used_indexes = set()

        for citation in document.get("citations", []):
            if citation.get("type") != "case":
                continue

            # ADDED(2026-10-06): exists:false + not injected = unverified/out of scope so skip
            if not citation["exists"] and not citation["injected"]:
                unverified.append((doc_id, citation["cite"]))
                continue

            # CHANGED(2026-10-06): now match on cleaned `cite`
            parsed = parse_answer_case(citation.get("cite", ""))
            if parsed is None:
                continue

            expected += 1
            # CHANGED(2026-10-06): try the exact name+reporter match first, then the fallback
            #   count and printed how often the fallback was needed
            result = find_exact(parsed, extracted_cases, used_indexes)
            used_fallback = False
            if result is None:
                result = find_substring_fallback(parsed, extracted_cases, used_indexes)
                if result is not None:
                    fallback_hits += 1
                    used_fallback = True

            if result is None:
                missing.append((doc_id, citation.get("cite", "")))
                continue

            match_index, match = result
            used_indexes.add(match_index)
            found += 1

            # Ground truth comes from answer-key.json.
            actual_exists = bool(citation.get("exists"))

            # Prediction comes from the extracted values + cases.jsonl only.
            prediction = corpus_prediction(
                match.get("case_name"),
                match.get("reporter_cite"),
                reporter_index,
                name_index,
            )
            predicted_exists = prediction == "real"

            # FABRICATED is the positive class: 1 = fabricated, 0 = real.
            y_true.append(0 if actual_exists else 1)
            y_pred.append(0 if predicted_exists else 1)

            rows.append({
                "injected": citation["injected"],  # False / "fabricated_case" / "wrong_reporter"
                "condition": document["condition"],  # "clean" / "corrupt"
                "fallback": used_fallback,
                "true": y_true[-1],
                "pred": y_pred[-1],
                "reason": prediction,
            })

    tp = sum(t == 1 and p == 1 for t, p in zip(y_true, y_pred))
    fp = sum(t == 0 and p == 1 for t, p in zip(y_true, y_pred))
    fn = sum(t == 1 and p == 0 for t, p in zip(y_true, y_pred))
    tn = sum(t == 0 and p == 0 for t, p in zip(y_true, y_pred))

    accuracy = safe_divide(tp + tn, len(y_true))
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    extraction_recall = safe_divide(found, expected)

    print("\nRESULTS AGAINST ANSWER KEY")
    print("=" * 45)
    print(f"Documents:             {len(extracted_documents)}")
    print(f"Expected case cites:   {expected}")
    print(f"Found case cites:      {found}")
    print(f"Missing case cites:    {len(missing)}")
    print(f"Needed substring fallback: {fallback_hits} of {expected}")  # CHANGED(2026-10-06): report how often exact matching was not enough
    print(f"Extraction recall:     {extraction_recall:.2%}")
    print()
    print(f"Cases evaluated:       {len(y_true)}")
    print(f"Accuracy:              {accuracy:.2%}")
    print(f"Fabrication precision: {precision:.2%}")
    print(f"Fabrication recall:    {recall:.2%}")
    print(f"Fabrication F1:        {f1:.2%}")
    print(f"TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")

    # ADDED (2026-10-06): break down the score
    #   Note: `exists` means "in corpus" and the predictor checks the corpus too, so expect 100% on non-injected cases
    print("\nBY INJECTED ERROR TYPE")
    print("=" * 45)
    for kind, reason in (("fabricated_case", "fabricated"), ("wrong_reporter", "wrong_reporter")):
        subset = [r for r in rows if r["injected"] == kind]
        caught = sum(r["pred"] for r in subset)
        right_reason = sum(r["reason"] == reason for r in subset)
        print(
            f"{kind:<16} n={len(subset):<3} caught: {caught}/{len(subset)}"
            f" | right reason: {right_reason}/{len(subset)}"
        )

    print("\nBY DOCUMENT CONDITION")
    print("=" * 45)
    for condition in ("clean", "corrupt"):
        subset = [r for r in rows if r["condition"] == condition]
        print(f"{condition:<8} n={len(subset):<5} {confusion(subset)}")

    print(f"\nUnverified (excluded): {len(unverified)}")

    if missing:
        print("\nMissing answer-key citations (first 20):")
        for doc_id, cite in missing[:20]:
            print(f"- {doc_id}: {cite}")



if __name__ == "__main__":
    main()
