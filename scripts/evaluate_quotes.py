"""Evaluate quote fidelity against answer-key.json.

Extracts quotes from each document, checks each against its source text,
and scores the FAITHFUL/ALTERED predictions against the answer key's quotes.
The answer key is used only to pair extracted quotes with key entries and to
score; predictions use only the document text and the corpus.

Writes every scored quote to data/quote-fidelity-results.json for the
threshold analysis.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from citation_extractor.extractor import normalize_citation
from citation_extractor.quote_extractor import extract_quotes
from citation_extractor.quote_fidelity import check_quote
from citation_extractor.source_lookup import clean_whitespace, get_source_text, load_corpus

ANSWER_KEY_PATH = ROOT / "data" / "benchmark" / "answer-key.json"
DOCUMENTS_DIR = ROOT / "data" / "benchmark" / "documents"
RESULTS_PATH = ROOT / "data" / "quote-fidelity-results.json"


def safe_divide(a, b):
    return a / b if b else 0.0


def same_cite(a, b):
    return bool(a and b) and normalize_citation(a) == normalize_citation(b)


def find_altered(key_quote, extracted, used_indexes):
    """Pair an altered key quote with the extracted quote containing its altered text."""
    altered = clean_whitespace(key_quote["altered_text"])
    # Prefer a quote containing all of the altered text; only then accept a
    # quote that is part of it, so a short phrase elsewhere does not steal the match.
    for contains in (lambda text: altered in text, lambda text: text in altered):
        for i, item in enumerate(extracted):
            if i not in used_indexes and contains(clean_whitespace(item["text"])):
                return i, item
    return None


def find_faithful(key_quote, extracted, used_indexes):
    """Pair a faithful key quote with the first unused extracted quote citing the same source."""
    for i, item in enumerate(extracted):
        if i not in used_indexes and same_cite(item["citation"], key_quote["source_cite"]):
            return i, item
    return None


def predict(item, corpus):
    source = get_source_text(item["citation"], corpus) if item["citation"] else None
    return check_quote(item["text"], source)


def report(title, rows):
    """Print metrics with ALTERED as the positive class."""
    tp = sum(r["true"] == 1 and r["pred"] == 1 for r in rows)
    fp = sum(r["true"] == 0 and r["pred"] == 1 for r in rows)
    fn = sum(r["true"] == 1 and r["pred"] == 0 for r in rows)
    tn = sum(r["true"] == 0 and r["pred"] == 0 for r in rows)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(2 * precision * recall, precision + recall)

    print(f"\n{title}")
    print("=" * 45)
    print(f"Quotes evaluated:      {len(rows)}")
    print(f"Accuracy:              {safe_divide(tp + tn, len(rows)):.2%}")
    print(f"Altered precision:     {precision:.2%}")
    print(f"Altered recall:        {recall:.2%}")
    print(f"Altered F1:            {f1:.2%}")
    print(f"TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")


def main():
    with ANSWER_KEY_PATH.open("r", encoding="utf-8") as f:
        answer_key = json.load(f)
    corpus = load_corpus()

    rows = []       # one per answer-key quote
    extras = []     # extracted quotes that match no answer-key quote

    for document in answer_key:
        doc_id = document["doc_id"]
        key_quotes = document.get("quotes", [])
        extracted = extract_quotes(str(DOCUMENTS_DIR / f"{doc_id}.docx"), doc_id)
        used_indexes = set()

        # Altered first: they can be paired by text, which is unambiguous.
        # Faithful quotes are then paired by citation from what is left.
        ordered = sorted(key_quotes, key=lambda q: q["quote_status"] != "altered")
        for key_quote in ordered:
            is_altered = key_quote["quote_status"] == "altered"
            match = (find_altered if is_altered else find_faithful)(key_quote, extracted, used_indexes)

            row = {
                "doc_id": doc_id,
                "source_cite": key_quote["source_cite"],
                "true": int(is_altered),
                "extracted": match is not None,
            }
            if match is None:
                row.update(text=None, citation=None, tier="not_extracted", score=None, pred=0)
            else:
                index, item = match
                used_indexes.add(index)
                result = predict(item, corpus)
                row.update(
                    text=item["text"],
                    citation=item["citation"],
                    tier=result["tier"],
                    score=result["score"],
                    # Not flagged unless the checker says altered.
                    pred=int(result["faithful"] is False),
                )
            rows.append(row)

        for i, item in enumerate(extracted):
            if i in used_indexes:
                continue
            result = predict(item, corpus)
            extras.append({
                "doc_id": doc_id,
                "text": item["text"],
                "citation": item["citation"],
                "tier": result["tier"],
                "score": result["score"],
                "flagged": result["faithful"] is False,
            })

    found = [r for r in rows if r["extracted"]]
    missing = [r for r in rows if not r["extracted"]]

    print("\nQUOTE EXTRACTION")
    print("=" * 45)
    for label, value in ((1, "altered"), (0, "faithful")):
        subset = [r for r in rows if r["true"] == label]
        n_found = sum(r["extracted"] for r in subset)
        print(f"{value:<9} found {n_found}/{len(subset)} ({safe_divide(n_found, len(subset)):.0%})")

    report("FIDELITY CHECKER (extracted quotes only)", found)
    report("END TO END (missed quotes count as not flagged)", rows)

    print("\nBY MATCH TIER (extracted quotes)")
    print("=" * 45)
    for tier in ("exact", "normalized", "fuzzy", "no_source"):
        subset = [r for r in found if r["tier"] == tier]
        n_altered = sum(r["true"] for r in subset)
        print(f"{tier:<11} n={len(subset):<4} altered: {n_altered:<3} faithful: {len(subset) - n_altered}")

    flagged_extras = [e for e in extras if e["flagged"]]
    print(f"\nExtracted quotes not in answer key: {len(extras)}  (flagged altered: {len(flagged_extras)})")
    for e in flagged_extras[:10]:
        print(f"- {e['doc_id']} [{e['citation']}] score={e['score']:.1f}: {e['text'][:70]}")

    if missing:
        print("\nMissed answer-key quotes (first 20):")
        for r in missing[:20]:
            status = "altered" if r["true"] else "faithful"
            print(f"- {r['doc_id']}: {r['source_cite']} ({status})")

    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump({"quotes": rows, "extras": extras}, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {RESULTS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
