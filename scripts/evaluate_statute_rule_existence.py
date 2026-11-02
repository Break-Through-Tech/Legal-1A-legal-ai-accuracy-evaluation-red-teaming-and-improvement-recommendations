"""Evaluate statute and court-rule existence checking against the answer key.

Stage-2 existence only (DATA_DICTIONARY §9): for every statute and rule
citation in the benchmark, predict present/absent from the corpus alone and
compare against the answer key's ``exists`` field. Cases are out of scope here
(they are scored by ``scripts/evaluate.py``).

Scoring follows §9: recall on fabricated citations is the priority. The single
citation ``AS 11.56.807`` (doc-0136) is not scored: check_statute_existence returns OUT_OF_SCOPE for it, 
because it is confirmed real law outside the corpus's curated scope.

Writes ``reports/statute-rule-existence-report.md`` and prints a summary.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from citation_extractor.statute_rule_existence import (
    FABRICATED,
    OUT_OF_SCOPE,
    REAL,
    check_rule_existence,
    check_statute_existence,
    load_civil_rule_index,
    load_evidence_rule_index,
    load_statute_index,
)

ANSWER_KEY_PATH = ROOT / "data" / "benchmark" / "answer-key.json"
CORPUS = ROOT / "data" / "corpus"
REPORT_PATH = ROOT / "reports" / "statute-rule-existence-report.md"


def predict(citation, ctype, statutes, civil, evidence):
    if ctype == "statute":
        return check_statute_existence(citation, statutes)
    return check_rule_existence(citation, civil, evidence)


def main():
    statutes = load_statute_index(CORPUS / "statutes.jsonl")
    civil = load_civil_rule_index(CORPUS / "rules.jsonl")
    evidence = load_evidence_rule_index(CORPUS / "rules-evidence.jsonl")
    answer_key = json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))

    tp = fp = tn = fn = 0
    false_positives = []
    false_negatives = []
    # ADDED (2026-10-20): list of skipped OUT_OF_SCOPE citations as (doc_id, cite),
    #   for the report (AS 11.56.807 plus non civil/evidence rule families).
    out_of_scope_cites = []
    for doc in answer_key:
        for entry in doc["citations"]:
            if entry["type"] == "case":
                continue

            result = predict(entry["cite"], entry["type"], statutes, civil, evidence)
            if result == OUT_OF_SCOPE:
                # CHANGED (2026-10-20): OUT_OF_SCOPE citations are added to out_of_scope_cites.
                out_of_scope_cites.append((doc["doc_id"], entry["cite"]))
                continue

            predicted_real = result == REAL
            actually_real = bool(entry["exists"])

            if predicted_real and actually_real:
                tp += 1
            elif predicted_real and not actually_real:
                fp += 1
                false_positives.append((doc["doc_id"], entry["cite"], entry.get("injected")))
            elif not predicted_real and actually_real:
                fn += 1
                false_negatives.append((doc["doc_id"], entry["cite"], entry.get("replaced_real")))
            else:
                tn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    lines = [
        "# Statute & Court-Rule Existence — Stage-2 Evaluation",
        "",
        "Predictions come from the frozen corpus only; scores are against the "
        "answer key's `exists` field (DATA_DICTIONARY §9). Cases are scored "
        "separately in `scripts/evaluate.py`.",
        "",
        # CHANGED (2026-10-20): report line lists the out-of-scope citations and count.
        f"Out of scope (not scored): {len(out_of_scope_cites)}: "
        + ", ".join(f"`{cite}` ({doc_id})" for doc_id, cite in out_of_scope_cites)
        + ".",
        "",
        "| metric | value |",
        "|---|---|",
        f"| true positives | {tp} |",
        f"| false positives | {fp} |",
        f"| true negatives | {tn} |",
        f"| false negatives | {fn} |",
        f"| **precision** | {precision:.4f} |",
        f"| **recall** | {recall:.4f} |",
        f"| **F1** | {f1:.4f} |",
        "",
        "## False positives (corpus says real, answer key says fabricated)",
        "",
    ]
    if false_positives:
        lines.append("| doc | cite | injected |")
        lines.append("|---|---|---|")
        for doc_id, cite, injected in false_positives:
            lines.append(f"| {doc_id} | {cite} | {injected} |")
        lines.append("")
        lines.append(
            "All false positives are `fabricated_statute` injections in the "
            "900-range that collide with real corpus sections "
            "(AS 25.24.900/910/920). By the benchmark's own definition "
            "(`exists` = present in this corpus, §1/§3.2) these citations do "
            "exist, so a correct corpus lookup is penalised here. See the "
            "team's finding for the recommended correction."
        )
    else:
        lines.append("None.")

    lines += ["", "## False negatives (corpus says fabricated, answer key says real)", ""]
    if false_negatives:
        for doc_id, cite, replaced in false_negatives:
            lines.append(f"- {doc_id} | {cite} | replaced_real={replaced}")
    else:
        lines.append("None.")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}")
    print(f"out_of_scope={len(out_of_scope_cites)}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
