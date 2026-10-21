"""Evaluate the per-document hallucination-risk score against the answer key.

For each of the 200 benchmark documents: extract citations from the .docx,
run the existence checkers, combine the results with document_risk, and
compare the flag against the answer key's `condition` ("corrupt" = positive).
The answer key is used only for scoring.

Quote-fidelity findings are not included yet (the quote checker is in PR #16),
so corrupt documents whose only planted errors are altered quotes are expected
to be missed; the report breaks recall down by error type to show this.
TODO(after PR #16): update this paragraph and the report intro in main() once
quote findings are added.

Threshold check: the threshold is tuned on even-numbered documents and scored
on odd-numbered ones, so the held-out numbers are not the ones it was tuned on.

    python scripts/evaluate_document_risk.py

Writes reports/document-risk-report.md and prints a summary.
"""

import json
import sys
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from citation_extractor.case_parser import extract_document
from citation_extractor.document_risk import RISK_THRESHOLD, assess_document, existence_findings
from citation_extractor.existence import load_corpus_name_index, load_corpus_reporter_index
from citation_extractor.extractor import extract_citations
from citation_extractor.statute_rule_existence import (
    load_civil_rule_index,
    load_evidence_rule_index,
    load_statute_index,
)

ANSWER_KEY_PATH = ROOT / "data" / "benchmark" / "answer-key.json"
DOCUMENTS_DIR = ROOT / "data" / "benchmark" / "documents"
CORPUS = ROOT / "data" / "corpus"
REPORT_PATH = ROOT / "reports" / "document-risk-report.md"


def planted_errors(document):
    """Describe what the answer key says was planted in a document.

    Returns "none" for clean documents, "citation" if any planted error is an
    injected citation, else "quote_only" (only altered quotes were planted).
    """
    if document["condition"] == "clean":
        return "none"
    if any(c.get("injected") for c in document["citations"]):
        return "citation"
    return "quote_only"


def metrics(rows, threshold):
    """Precision, recall, F1 and confusion counts for flagging at `threshold`.

    "corrupt" is the positive class: a true positive is a corrupt document
    whose score is at or above the threshold.
    """
    y_true = [r["condition"] == "corrupt" for r in rows]
    y_pred = [r["score"] >= threshold for r in rows]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()
    return {"precision": precision, "recall": recall, "f1": f1,
            "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}


def tune_threshold(rows):
    """Pick the threshold with the best F1 on `rows`.

    Candidates are the distinct nonzero scores seen. Ties go to the lower
    threshold, which favors recall (a missed fabrication is the worst error).
    """
    candidates = sorted({r["score"] for r in rows if r["score"] > 0})
    best = None
    for threshold in candidates:
        f1 = metrics(rows, threshold)["f1"]
        if best is None or f1 > best[1]:
            best = (threshold, f1)
    return best[0] if best else RISK_THRESHOLD


def score_all_documents(answer_key):
    """Extract, check and score every document; one result row per document."""
    statutes = load_statute_index(CORPUS / "statutes.jsonl")
    civil = load_civil_rule_index(CORPUS / "rules.jsonl")
    evidence = load_evidence_rule_index(CORPUS / "rules-evidence.jsonl")
    reporter_index = load_corpus_reporter_index(CORPUS / "cases.jsonl")
    name_index = load_corpus_name_index(CORPUS / "cases.jsonl")

    rows = []
    for document in answer_key:
        doc_id = document["doc_id"]
        path = DOCUMENTS_DIR / f"{doc_id}.docx"
        statute_rule_citations = extract_citations(str(path), doc_id)
        case_citations = extract_document(path, reporter_index)["citations"]

        findings = existence_findings(
            statute_rule_citations, case_citations,
            statutes, civil, evidence, reporter_index, name_index,
        )
        # TODO(after PR #16): add quote-fidelity findings here:
        #   1. load the source text once, before the loop:
        #        source_corpus = source_lookup.load_corpus()
        #   2. per document:
        #        passages = extract_passages(str(path), source_corpus, doc_id)
        #        findings += quote_findings(passages, source_corpus)
        #   3. rerun and compare with the existence-only report: expect more
        #      POSSIBLE_ALTERATION counts on clean documents (PR #16 found 65 false
        #      alarms from unquoted passages); check they stay below the threshold.
        result = assess_document(findings)
        rows.append({
            "doc_id": doc_id,
            "condition": document["condition"],
            "planted": planted_errors(document),
            "score": result["score"],
            "counts": result["counts"],
        })
    return rows


def recall_by_planted(rows, threshold):
    """Recall on corrupt documents, split by what kind of error was planted."""
    out = {}
    for kind in ("citation", "quote_only"):
        subset = [r for r in rows if r["planted"] == kind]
        caught = sum(r["score"] >= threshold for r in subset)
        out[kind] = (caught, len(subset))
    return out


def format_metrics(m):
    """One markdown table row of metrics."""
    return (f"| {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} "
            f"| {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |")


def main():
    answer_key = json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))
    rows = score_all_documents(answer_key)

    overall = metrics(rows, RISK_THRESHOLD)
    tune_rows = [r for r in rows if int(r["doc_id"].split("-")[1]) % 2 == 0]
    test_rows = [r for r in rows if int(r["doc_id"].split("-")[1]) % 2 == 1]
    tuned = tune_threshold(tune_rows)
    held_out = metrics(test_rows, tuned)
    by_planted = recall_by_planted(rows, RISK_THRESHOLD)
    false_alarms = [r for r in rows if r["condition"] == "clean" and r["score"] >= RISK_THRESHOLD]
    missed = [r for r in rows if r["condition"] == "corrupt" and r["score"] < RISK_THRESHOLD]

    header = "| precision | recall | F1 | TP | FP | FN | TN |\n|---|---|---|---|---|---|---|"
    lines = [
        "# Per-Document Hallucination-Risk Score — Evaluation",
        "",
        "Flags a document when its risk score (`document_risk.py`) is at or above the "
        "threshold, and scores the flag against the answer key's `condition` "
        "(`corrupt` = positive). Existence findings only: quote-fidelity findings "
        "are added once PR #16 merges.",
        "",
        f"## All 200 documents (threshold {RISK_THRESHOLD})",
        "",
        header,
        format_metrics(overall),
        "",
        "## Held-out check",
        "",
        f"Threshold tuned on even-numbered documents: **{tuned:.3f}**. "
        "Scored on odd-numbered documents:",
        "",
        header,
        format_metrics(held_out),
        "",
        "## Recall by planted error type",
        "",
        "| planted errors | caught | of |",
        "|---|---|---|",
    ]
    for kind, (caught, total) in by_planted.items():
        lines.append(f"| {kind} | {caught} | {total} |")
    if by_planted["quote_only"][1]:
        lines += ["", "`quote_only` documents are expected to be missed until quote findings are added.", ""]
    else:
        lines += ["", "Every corrupt document in this benchmark has at least one planted citation "
                  "error, so existence findings alone can reach every corrupt document. Quote "
                  "findings will still matter for documents with altered quotes on real citations.", ""]

    lines += ["## False alarms (clean documents flagged)", ""]
    lines += ([f"- {r['doc_id']}: score {r['score']:.2f}, {r['counts']}" for r in false_alarms]
              or ["None."])
    lines += ["", "## Missed corrupt documents", ""]
    lines += ([f"- {r['doc_id']} ({r['planted']}): score {r['score']:.2f}, {r['counts']}" for r in missed]
              or ["None."])

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"threshold={RISK_THRESHOLD} " + " ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                                                  for k, v in overall.items()))
    print(f"held-out: tuned threshold={tuned:.3f} " + " ".join(
        f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in held_out.items()))
    for kind, (caught, total) in by_planted.items():
        print(f"recall on {kind} documents: {caught}/{total}")
    print(f"false alarms on clean documents: {len(false_alarms)}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
