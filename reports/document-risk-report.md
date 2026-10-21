# Per-Document Hallucination-Risk Score — Evaluation

Flags a document when its risk score (`document_risk.py`) is at or above the threshold, and scores the flag against the answer key's `condition` (`corrupt` = positive). Existence findings only: quote-fidelity findings are added once PR #16 merges.

## All 200 documents (threshold 0.5)

| precision | recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| 0.990 | 1.000 | 0.995 | 103 | 1 | 0 | 96 |

## Held-out check

Threshold tuned on even-numbered documents: **1.000**. Scored on odd-numbered documents:

| precision | recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| 1.000 | 1.000 | 1.000 | 48 | 0 | 0 | 52 |

## Recall by planted error type

| planted errors | caught | of |
|---|---|---|
| citation | 103 | 103 |
| quote_only | 0 | 0 |

Every corrupt document in this benchmark has at least one planted citation error, so existence findings alone can reach every corrupt document. Quote findings will still matter for documents with altered quotes on real citations.

## False alarms (clean documents flagged)

- doc-0136: score 1.00, {'fabricated': 1}

## Missed corrupt documents

None.
