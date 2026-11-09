# Per-Document Hallucination-Risk Score — Evaluation

Flags a document when its risk score (`document_risk.py`) is at or above the threshold, and scores the flag against the answer key's `condition` (`corrupt` = positive). Findings come from the existence checkers and the quote-fidelity checker.

## All 200 documents (threshold 0.5)

| findings used | precision | recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| existence only | 1.000 | 1.000 | 1.000 | 103 | 0 | 0 | 97 |
| quotes only | 0.955 | 0.204 | 0.336 | 21 | 1 | 82 | 96 |
| combined | 0.990 | 1.000 | 0.995 | 103 | 1 | 0 | 96 |

Of the 40 documents with a planted altered quote, quote findings alone flag 21.

## Held-out check

Threshold tuned on even-numbered documents: **1.000**. Scored on odd-numbered documents:

| precision | recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| 1.000 | 1.000 | 1.000 | 48 | 0 | 0 | 52 |

Same odd-numbered documents at the fixed threshold 0.5:

| precision | recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| 1.000 | 1.000 | 1.000 | 48 | 0 | 0 | 52 |

### Threshold choice

The tuner prefers a high threshold because it avoids the few quote false alarms, and on this benchmark it costs nothing: 0 of 103 corrupt documents have no fabricated citation, so a threshold of 1.0 ("flag only fabrications") still catches all of them. On real filings it would never flag a document whose only problem is a wrong reporter (weight 0.5) or an altered quote (0.8). `RISK_THRESHOLD` stays at 0.5, so any single wrong reporter or stronger finding flags the document (recall first, DATA_DICTIONARY §8.5).

## Recall by planted error type

| planted errors | caught | of |
|---|---|---|
| citation | 103 | 103 |
| quote_only | 0 | 0 |

Every corrupt document in this benchmark has at least one planted citation error, so existence findings alone can reach every corrupt document. Quote findings will still matter for documents with altered quotes on real citations.

## False alarms (clean documents flagged)

- doc-0012: score 0.84, {'altered_quote': 1, 'possible_alteration': 1}

## Missed corrupt documents

None.
