"""Evaluate statute and court-rule existence checking against the answer key.

Stage-2 existence only (DATA_DICTIONARY §9): for every statute and rule
citation in the benchmark, predict present/absent from the corpus alone and
compare against the answer key's ``exists`` field. Cases are out of scope here
(they are scored by ``scripts/evaluate.py``).

Scoring follows §9: recall on fabricated citations is the priority. The single
citation ``AS 11.56.807`` (doc-0136) is excluded entirely, as §9 requires,
because it is confirmed real law that sits outside the corpus's curated scope.

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

# DATA_DICTIONARY §9: exclude this single citation from Stage-2 scoring.
EXCLUDED = {("doc-0136", "AS 11.56.807")}


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
    excluded = out_of_scope = 0
    false_positives = []
    false_negatives = []

    for doc in answer_key:
        for entry in doc["citations"]:
            if entry["type"] == "case":
                continue
            if (doc["doc_id"], entry["cite"]) in EXCLUDED:
                excluded += 1
                continue

            result = predict(entry["cite"], entry["type"], statutes, civil, evidence)
            if result == OUT_OF_SCOPE:
                out_of_scope += 1
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
        f"Excluded per §9: {excluded} (`AS 11.56.807`, doc-0136). "
        f"Out-of-scope (non civil/evidence rules): {out_of_scope}.",
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
    print(f"excluded={excluded} out_of_scope={out_of_scope}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
