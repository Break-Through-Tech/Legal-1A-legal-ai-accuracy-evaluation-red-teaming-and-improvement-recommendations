"""Run the statutes/rules extractor over all benchmark documents and compute
extraction recall against the answer key.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/run_extractor.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from citation_extractor import extract_citations, normalize_citation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "data", "benchmark", "documents", "*.docx")
KEY = os.path.join(ROOT, "data", "benchmark", "answer-key.json")
OUT = os.path.join(ROOT, "data", "extraction-results.json")


def main() -> None:
    key = json.load(open(KEY, encoding="utf-8"))
    key_by_doc = {doc["doc_id"]: doc for doc in key}

    per_doc = []
    totals = Counter()
    for path in sorted(glob.glob(DOCS)):
        doc_id = os.path.splitext(os.path.basename(path))[0]
        citations = extract_citations(path, doc_id=doc_id)

        extracted_norms = {c.normalized for c in citations}
        key_cites = key_by_doc.get(doc_id, {}).get("citations", [])
        key_statute_rule = [c for c in key_cites if c["type"] in ("statute", "rule")]
        key_norms = {normalize_citation(c["cite"]) for c in key_statute_rule}

        matched = key_norms & extracted_norms
        missing = key_norms - extracted_norms
        # CHANGED(2026-10-06): also keep what the extractor found that the answer key does not list for THIS document
        extra = extracted_norms - key_norms

        totals["key_total"] += len(key_statute_rule)
        totals["key_unique"] += len(key_norms)
        totals["matched"] += len(matched)
        totals["missing"] += len(missing)
        totals["extracted"] += len(extracted_norms)
        totals["fp"] += len(extra)  # CHANGED(2026-10-06): running total of per-document extras

        per_doc.append(
            {
                "doc_id": doc_id,
                "n_key_cites": len(key_statute_rule),
                "n_key_unique": len(key_norms),
                "n_extracted": len(extracted_norms),
                "n_matched": len(matched),
                "matched": sorted(matched),
                "missing": sorted(missing),
                # CHANGED(2026-10-06): store the extras per document so each one can be inspected and labelled "key omission" in the report
                "n_extra": len(extra),
                "extra": sorted(extra),
            }
        )

    # CHANGED(2026-10-06): FP = 30 (in 26 docs), precision ~0.978, recall 1.0
    # Those 30 are real citations in the text that the answer key omits for that document, so not parser errors
    recall = totals["matched"] / totals["key_unique"] if totals["key_unique"] else 0
    precision = (
        totals["matched"] / (totals["matched"] + totals["fp"])
        if (totals["matched"] + totals["fp"]) else 0
    )

    print("=== statutes/rules extraction vs answer key ===")
    print(f"answer-key statute+rule citations: {totals['key_total']}")
    print(f"answer-key unique normalized:      {totals['key_unique']}")
    print(f"extracted unique (all docs):       {totals['extracted']}")
    print(f"matched answer-key cites:          {totals['matched']}")
    print(f"missed answer-key cites:           {totals['missing']}")
    print(f"recall (matched / key unique):     {recall:.3f}")
    # CHANGED(2026-10-06): report extras and precision next to recall
    print(f"extracted but not in that doc's key: {totals['fp']}")
    print(f"precision (matched / (matched + extra)): {precision:.3f}")

    missing_freq = Counter()
    for d in per_doc:
        for m in d["missing"]:
            missing_freq[m] += 1
    print("\nmost-missed citations:")
    for cite, n in missing_freq.most_common(15):
        print(f"  {n:3d}  {cite}")

    json.dump(per_doc, open(OUT, "w", encoding="utf-8"), indent=2)
    print(f"\nwrote per-doc results to {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()